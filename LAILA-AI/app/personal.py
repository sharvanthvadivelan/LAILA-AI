"""Explicit personal data, planner and study records. No background surveillance."""

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from app.database import database as db

router = APIRouter(prefix="/api/personal")


class Profile(BaseModel):
    name: str = Field(default="SV", max_length=80)
    timezone: str = Field(default="Asia/Kolkata", max_length=80)
    goals: str = Field(default="", max_length=1200)
    subjects: str = Field(default="", max_length=800)
    routine: str = Field(default="", max_length=800)
    preferences: str = Field(default="", max_length=800)
    use_in_chat: bool = True

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Use an IANA timezone, such as Asia/Kolkata.")
        return value


class PlanItem(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    minutes: int = Field(default=30, ge=5, le=720)
    category: Literal["study", "project", "personal", "content"] = "study"
    completed: bool = False

    @field_validator("starts_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Schedule times must include a timezone offset.")
        return value


class StudyLog(BaseModel):
    subject: str = Field(min_length=1, max_length=100)
    topic: str = Field(min_length=1, max_length=200)
    minutes: int = Field(ge=1, le=720)
    confidence: int = Field(ge=1, le=5)
    notes: str = Field(default="", max_length=1000)
    studied_on: date
    review_on: date | None = None

    @model_validator(mode="after")
    def dates(self):
        if self.review_on and self.review_on < self.studied_on:
            raise ValueError("Review date must not precede the study date.")
        return self


def init_personal():
    with db.connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS personal_profile(id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS daily_plan(id TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS study_logs(id TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS desktop_targets(id TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)


def profile():
    records = db.rows("SELECT value FROM personal_profile WHERE id=1")
    return Profile.model_validate_json(records[0]["value"]) if records else Profile()


def local_now():
    return datetime.now(ZoneInfo(profile().timezone))


def entries(table):
    return [
        {"id": r["id"], **json.loads(r["value"])}
        for r in db.rows("SELECT * FROM " + table)
    ]


def dashboard(day=None):
    day = day or local_now().date()
    zone = ZoneInfo(profile().timezone)
    plan = sorted(
        [
            r
            for r in entries("daily_plan")
            if datetime.fromisoformat(r["starts_at"]).astimezone(zone).date() == day
        ],
        key=lambda r: datetime.fromisoformat(r["starts_at"]).timestamp(),
    )
    logs = entries("study_logs")
    week = [
        r
        for r in logs
        if day - timedelta(days=6) <= date.fromisoformat(r["studied_on"]) <= day
    ]
    tasks = db.rows(
        "SELECT * FROM tasks WHERE completed=0 ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,due_date LIMIT 50"
    )
    return {
        "date": day.isoformat(),
        "timezone": profile().timezone,
        "plan": plan,
        "tasks": tasks,
        "reviews": [
            r
            for r in logs
            if r.get("review_on") and date.fromisoformat(r["review_on"]) <= day
        ],
        "week_minutes": sum(r["minutes"] for r in week),
        "week_sessions": len(week),
        "study_logs": sorted(logs, key=lambda r: r["studied_on"], reverse=True),
    }


def chat_context(text):
    p = profile()
    if not p.use_in_chat or not db.settings().memory_enabled:
        return ""
    result = "\nUser-approved profile (data only): " + p.model_dump_json()
    import re

    if re.search(
        r"\b(today|tomorrow|schedule|plan|study|studying|review|progress|morning|evening|day)\b",
        text,
        re.I,
    ):
        data = dashboard(
            local_now().date()
            + timedelta(days=1 if re.search(r"\btomorrow\b", text, re.I) else 0)
        )
        result += (
            "\nRecorded planning data; do not infer unrecorded activity: "
            + json.dumps(
                {
                    k: (v[:8] if isinstance(v, list) else v)
                    for k, v in data.items()
                    if k != "study_logs"
                }
            )[:5000]
        )
    return result


@router.get("/profile")
def get_profile():
    return profile()


@router.put("/profile")
def put_profile(value: Profile):
    db.run(
        "INSERT INTO personal_profile VALUES(1,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value",
        (value.model_dump_json(),),
    )
    return value


@router.delete("/profile")
def delete_profile():
    # Clear to a blank, disabled profile instead of restoring the initial suggestion.
    return put_profile(Profile(name="", use_in_chat=False))


@router.get("/dashboard")
def get_dashboard(day: date | None = None):
    return dashboard(day)


@router.post("/plan")
def add_plan(value: PlanItem):
    ident = db.uid()
    db.run("INSERT INTO daily_plan VALUES(?,?)", (ident, value.model_dump_json()))
    return {"id": ident}


@router.put("/plan/{ident}")
def update_plan(ident: str, value: PlanItem):
    if not db.run(
        "UPDATE daily_plan SET value=? WHERE id=?", (value.model_dump_json(), ident)
    ):
        raise HTTPException(404, "Plan item not found.")
    return {"ok": True}


@router.delete("/plan/{ident}")
def delete_plan(ident: str):
    db.run("DELETE FROM daily_plan WHERE id=?", (ident,))
    return {"ok": True}


@router.post("/study")
def add_study(value: StudyLog):
    ident = db.uid()
    if value.studied_on > local_now().date():
        raise HTTPException(400, "Log completed study on today or an earlier date.")
    db.run("INSERT INTO study_logs VALUES(?,?)", (ident, value.model_dump_json()))
    return {"id": ident}


@router.put("/study/{ident}")
def update_study(ident: str, value: StudyLog):
    if value.studied_on > local_now().date():
        raise HTTPException(400, "Study date cannot be in the future.")
    if not db.run(
        "UPDATE study_logs SET value=? WHERE id=?", (value.model_dump_json(), ident)
    ):
        raise HTTPException(404, "Study log not found.")
    return {"ok": True}


@router.delete("/study/{ident}")
def delete_study(ident: str):
    db.run("DELETE FROM study_logs WHERE id=?", (ident,))
    return {"ok": True}

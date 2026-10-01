"""Launch only explicit user-configured local targets, with per-action approval."""

import json
import os
import subprocess
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from app.database import database as db

router = APIRouter(prefix="/api/desktop")


class Target(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["app", "folder"]
    path: str = Field(min_length=1, max_length=1000)


class Launch(BaseModel):
    target_id: str = Field(min_length=1, max_length=80)
    expected_path: str = Field(min_length=1, max_length=1000)


class Proposal(BaseModel):
    conversation_id: str
    target_id: str


def targets():
    return [
        {"id": r["id"], **json.loads(r["value"])}
        for r in db.rows("SELECT * FROM desktop_targets")
    ]


def validate_target(target):
    if os.name != "nt":
        raise ValueError("Desktop launching is available on Windows only.")
    path = Path(target.path).expanduser()
    if not path.is_absolute() or target.path.startswith(("\\\\", "//")):
        raise ValueError(
            "Choose an absolute local Windows path; network paths are not allowed."
        )
    path = path.resolve(strict=True)
    if str(path).startswith(("\\\\", "//")):
        raise ValueError("Network targets are not allowed.")
    if target.kind == "folder":
        if not path.is_dir():
            raise ValueError("Folder not found.")
    elif not path.is_file() or path.suffix.lower() != ".exe":
        raise ValueError(
            "Choose an installed .exe file. Scripts and shortcuts are not supported."
        )
    return str(path)


def launch(a, settings):
    found = next((t for t in targets() if t["id"] == a.target_id), None)
    if not found:
        raise ValueError("This desktop target was removed.")
    path = validate_target(Target(**found))
    if path != a.expected_path:
        raise ValueError(
            "Target changed since approval was requested. Request it again."
        )
    if found["kind"] == "folder":
        os.startfile(path)
    else:
        subprocess.Popen([path], shell=False, cwd=str(Path(path).parent))
    return {
        "launch_requested": True,
        "name": found["name"],
        "path": path,
        "detail": "Windows accepted the launch request; window readiness has not been verified.",
    }


@router.get("/targets")
def get_targets():
    return {"supported": os.name == "nt", "targets": targets()}


@router.post("/targets")
def add_target(value: Target):
    value.path = validate_target(value)
    ident = db.uid()
    db.run("INSERT INTO desktop_targets VALUES(?,?)", (ident, value.model_dump_json()))
    return {"id": ident}


@router.delete("/targets/{ident}")
def remove_target(ident: str):
    db.run("DELETE FROM desktop_targets WHERE id=?", (ident,))
    return {"ok": True}


@router.post("/propose")
async def propose(value: Proposal, request: Request):
    if not db.settings().tools_enabled:
        raise HTTPException(400, "Enable safe agent tools in Settings first.")
    if not db.rows("SELECT id FROM conversations WHERE id=?", (value.conversation_id,)):
        raise HTTPException(404, "Conversation not found.")
    found = next((t for t in targets() if t["id"] == value.target_id), None)
    if not found:
        raise HTTPException(404, "Target not found.")
    result = await request.app.state.registry.execute(
        "desktop_open",
        {"target_id": found["id"], "expected_path": found["path"]},
        value.conversation_id,
    )

    db.message(
        value.conversation_id,
        "assistant",
        "Approval requested to open " + found["name"] + ". The action has not run.",
        {"status": "complete"},
    )
    return result

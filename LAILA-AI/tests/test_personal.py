import asyncio
import json
from datetime import timedelta
import pytest
from app.database import database as db
from app.personal import local_now, chat_context, init_personal
from app.agent.router import tool_names
from app.main import app
from app.tools.calculator import calculate
from app.tools import desktop
from test_laila import FakeOllama, install, chat


def test_profile_privacy_and_export(client):
    data = {"name": "SV", "goals": "Build useful AI", "routine": "Study after class"}
    assert client.put("/api/personal/profile", json=data).status_code == 200
    assert "Build useful AI" in chat_context("Hello")
    assert (
        client.put(
            "/api/personal/profile", json={**data, "use_in_chat": False}
        ).status_code
        == 200
    )
    assert chat_context("Plan today") == ""
    assert (
        client.put("/api/personal/profile", json={"timezone": "Not/AZone"}).status_code
        == 422
    )
    assert "personal_profile" in client.get("/api/export").json()
    assert client.delete("/api/personal/profile").status_code == 200
    assert client.get("/api/personal/profile").json()["goals"] == ""
    init_personal()  # Repeated startup preserves records and existing tables.
    assert client.get("/api/personal/profile").json()["use_in_chat"] is False


def test_schedule_timezone_and_log(client):
    client.put("/api/personal/profile", json={"timezone": "Asia/Kolkata"})
    # 20:00 UTC is the following day in India.
    plan = {
        "title": "Study Python",
        "starts_at": "2026-09-29T20:00:00+00:00",
        "minutes": 30,
    }
    r = client.post("/api/personal/plan", json=plan)
    assert r.status_code == 200
    ident = r.json()["id"]
    assert not client.get("/api/personal/dashboard?day=2026-09-29").json()["plan"]
    result = client.get("/api/personal/dashboard?day=2026-09-30").json()
    assert result["plan"][0]["title"] == "Study Python"
    assert (
        client.post(
            "/api/personal/plan", json={**plan, "starts_at": "2026-09-29T20:00"}
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/api/personal/plan/" + ident, json={**plan, "completed": True}
        ).status_code
        == 200
    )
    today = local_now().date().isoformat()
    log = {
        "subject": "Python",
        "topic": "Loops",
        "minutes": 25,
        "confidence": 2,
        "studied_on": today,
        "review_on": today,
    }
    ident = client.post("/api/personal/study", json=log).json()["id"]
    result = client.get("/api/personal/dashboard").json()
    assert result["week_minutes"] == 25 and result["week_sessions"] == 1
    assert len(result["reviews"]) == 1
    assert (
        client.put(
            "/api/personal/study/" + ident, json={**log, "review_on": None}
        ).status_code
        == 200
    )
    assert not client.get("/api/personal/dashboard").json()["reviews"]
    future = (local_now().date() + timedelta(days=1)).isoformat()
    assert (
        client.post(
            "/api/personal/study", json={**log, "studied_on": future, "review_on": None}
        ).status_code
        == 400
    )
    client.delete("/api/personal/study/" + ident)
    assert client.get("/api/personal/dashboard").json()["week_minutes"] == 0


def test_routing_and_recoverable_calculator(client):
    assert not tool_names("What does the addition operator do?", "chat", [])
    assert not tool_names("Write Python code to add two numbers", "coding", [])
    assert tool_names("What is seven times nine?", "chat", []) == {"calculator"}
    with pytest.raises(ValueError, match="numeric expression"):
        calculate("def add(a, b):")

    class Direct(FakeOllama):
        async def stream(self, model, messages, options, tools=None):
            assert not tools
            assert not any("Previously completed" in m["content"] for m in messages)
            yield {"message": {"content": "The + operator adds values."}, "done": True}

    install(Direct(True))
    cid = chat(client)
    asyncio.run(app.state.registry.execute("calculator", {"expression": "2+2"}, cid))
    response = client.post(
        f"/api/conversations/{cid}/chat",
        json={"text": "What does the addition operator do?"},
    )
    assert "adds values" in response.text


def test_launch_approval_and_revocation(client, monkeypatch):
    cid = chat(client)
    db.run(
        "INSERT INTO desktop_targets VALUES(?,?)",
        (
            "target",
            json.dumps({"name": "Example", "kind": "app", "path": "C:/Example.exe"}),
        ),
    )
    calls = []
    # Fixture replaces OS launching; no real desktop action is performed in tests.
    monkeypatch.setattr(desktop, "validate_target", lambda t: t.path)
    monkeypatch.setattr(
        desktop.subprocess, "Popen", lambda *a, **k: calls.append((a, k))
    )
    pending = client.post(
        "/api/desktop/propose", json={"conversation_id": cid, "target_id": "target"}
    ).json()
    assert not calls and pending["executed"] is False
    assert (
        client.post(
            "/api/approvals/" + pending["pending_approval"], json={"approve": True}
        ).status_code
        == 200
    )
    assert len(calls) == 1 and calls[0][1]["shell"] is False
    assert (
        client.post(
            "/api/approvals/" + pending["pending_approval"], json={"approve": True}
        ).status_code
        == 409
    )
    pending = client.post(
        "/api/desktop/propose", json={"conversation_id": cid, "target_id": "target"}
    ).json()
    client.delete("/api/desktop/targets/target")
    assert (
        client.post(
            "/api/approvals/" + pending["pending_approval"], json={"approve": True}
        ).status_code
        == 400
    )
    assert len(calls) == 1


def test_plan_tool_waits_for_approval(client):
    cid = chat(client)
    pending = asyncio.run(
        app.state.registry.execute(
            "plan_create",
            {"title": "Read", "starts_at": local_now().isoformat(), "minutes": 20},
            cid,
        )
    )
    assert not db.rows("SELECT * FROM daily_plan")
    assert (
        client.post(
            "/api/approvals/" + pending["pending_approval"], json={"approve": True}
        ).status_code
        == 200
    )
    assert len(db.rows("SELECT * FROM daily_plan")) == 1


def test_exact_launch_without_model(client):
    cid = chat(client)
    db.run(
        "INSERT INTO desktop_targets VALUES(?,?)",
        (
            "target",
            json.dumps({"name": "VS Code", "kind": "app", "path": "C:/Code.exe"}),
        ),
    )
    response = client.post(
        f"/api/conversations/{cid}/chat", json={"text": "Open VS Code."}
    )
    assert (
        "Approval requested" in response.text and "not been launched" in response.text
    )
    assert len(db.rows("SELECT * FROM tool_logs WHERE status='pending'")) == 1
    assert (
        client.post(
            "/api/approvals/" + db.rows("SELECT id FROM tool_logs")[0]["id"],
            json={"approve": False},
        ).status_code
        == 200
    )

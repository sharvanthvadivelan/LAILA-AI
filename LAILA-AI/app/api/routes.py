import asyncio, base64, json, secrets, tempfile
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from app.database import database as db
from app.core.config import DATA, Settings, VERSION
from app.llm.model_manager import status
from app.rag.loader import SUPPORTED
from app.rag.retriever import index_document, search
from app.tools.data_analysis import AnalysisRequest, analyze
from app.tools.system_info import system_info
from app.tools.registry import NoteArgs, TaskArgs
from app.vision.vision import validate_image

router = APIRouter(prefix="/api")


def require_chat(cid):
    found = db.rows("SELECT * FROM conversations WHERE id=?", (cid,))
    if not found:
        raise HTTPException(404, "Conversation not found.")
    return found[0]


def idle(request, cid):
    require_chat(cid)
    if cid in request.app.state.active:
        raise HTTPException(409, "Stop generation before changing this conversation.")


def messages(cid):
    result = db.rows(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY rowid", (cid,)
    )
    for row in result:
        row["meta"] = json.loads(row["meta"])
    return result


class ChatPatch(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    pinned: bool = False


class Send(BaseModel):
    text: str = Field(default="", max_length=24000)
    mode: Literal["chat", "study", "coding", "data"] = "chat"
    document_ids: list[str] = Field(default_factory=list, max_length=10)
    images: list[str] = Field(default_factory=list, max_length=1)
    action: Literal["send", "regenerate", "continue"] = "send"


class Edit(BaseModel):
    content: str = Field(min_length=1, max_length=24000)


class Memory(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class Note(NoteArgs):
    pass


class Task(TaskArgs):
    completed: bool = False


class Decision(BaseModel):
    approve: bool


class Render(BaseModel):
    text: str = Field(max_length=100000)


class Speech(BaseModel):
    text: str = Field(min_length=1, max_length=6000)


class Search(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


@router.get("/session")
async def session(request: Request):
    return {"token": request.app.state.token, "version": VERSION}


@router.get("/settings")
async def get_settings():
    return db.settings()


@router.put("/settings")
async def set_settings(value: Settings, request: Request):
    if request.app.state.active or request.app.state.indexing:
        raise HTTPException(
            409,
            "Wait for generation and document indexing to finish before changing settings.",
        )
    from app.core.security import validate_root

    value.approved_directories = [
        str(validate_root(x)) for x in value.approved_directories
    ]
    db.save_settings(value)
    return value


@router.get("/models")
async def models(request: Request):
    return await status(request.app.state.provider, db.settings().model)


@router.get("/system")
async def system(request: Request):
    return {
        "system": await asyncio.to_thread(system_info),
        "ollama": await status(request.app.state.provider, db.settings().model),
    }


@router.get("/conversations")
async def chats(q: str = ""):
    return db.rows(
        "SELECT DISTINCT c.* FROM conversations c LEFT JOIN messages m ON c.id=m.conversation_id WHERE c.title LIKE ? OR m.content LIKE ? ORDER BY c.pinned DESC,c.updated_at DESC LIMIT 200",
        ("%" + q[:200] + "%", "%" + q[:200] + "%"),
    )


@router.post("/conversations")
async def new_chat():
    ident = db.uid()
    db.run(
        "INSERT INTO conversations VALUES(?,?,?,?,?)",
        (ident, "New conversation", 0, db.now(), db.now()),
    )
    return {"id": ident}


@router.get("/conversations/{cid}")
async def chat(cid: str):
    return {"conversation": require_chat(cid), "messages": messages(cid)}


@router.patch("/conversations/{cid}")
async def patch_chat(cid: str, value: ChatPatch, request: Request):
    idle(request, cid)
    db.run(
        "UPDATE conversations SET title=?,pinned=? WHERE id=?",
        (value.title, int(value.pinned), cid),
    )
    return {"ok": True}


@router.delete("/conversations/{cid}")
async def delete_chat(cid: str, request: Request):
    idle(request, cid)
    db.run("DELETE FROM conversations WHERE id=?", (cid,))
    return {"ok": True}


@router.delete("/conversations/{cid}/messages")
async def clear_chat(cid: str, request: Request):
    idle(request, cid)
    with db.connect() as con:
        con.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
        con.execute("DELETE FROM tool_logs WHERE conversation_id=?", (cid,))
    return {"ok": True}


@router.patch("/conversations/{cid}/messages/{mid}")
async def edit_message(cid: str, mid: str, value: Edit, request: Request):
    idle(request, cid)
    with db.connect() as con:
        target = con.execute(
            "SELECT rowid FROM messages WHERE id=? AND conversation_id=? AND role='user'",
            (mid, cid),
        ).fetchone()
        if not target:
            raise HTTPException(404, "User message not found.")
        con.execute(
            "DELETE FROM messages WHERE conversation_id=? AND rowid>?",
            (cid, target["rowid"]),
        )
        con.execute("UPDATE messages SET content=? WHERE id=?", (value.content, mid))
        con.execute(
            "UPDATE tool_logs SET status='rejected' WHERE conversation_id=? AND status='pending'",
            (cid,),
        )
    return {"ok": True}


@router.post("/conversations/{cid}/stop")
async def stop(cid: str, request: Request):
    entry = request.app.state.active.get(cid)
    if entry:
        entry["cancel"].set()
        if entry.get("task"):
            entry["task"].cancel()
    return {"stopped": bool(entry)}


@router.post("/conversations/{cid}/chat")
async def send(cid: str, value: Send, request: Request):
    idle(request, cid)
    for encoded in value.images:
        try:
            validate_image(encoded)
        except Exception as e:
            raise HTTPException(400, str(e))
    text = value.text.strip()
    history = messages(cid)
    if value.action == "regenerate":
        if not history:
            raise HTTPException(400, "No response to regenerate.")
        previous = (
            history[-2]
            if history[-1]["role"] == "assistant" and len(history) > 1
            else history[-1]
        )
        if previous["role"] != "user":
            raise HTTPException(400, "No user message to regenerate.")
        if previous["meta"].get("has_image") and not value.images:
            raise HTTPException(
                400, "Reattach the image to regenerate; image bytes are not stored."
            )
        if history[-1]["role"] == "assistant":
            db.run("DELETE FROM messages WHERE id=?", (history[-1]["id"],))
            history.pop()
        text = previous["content"]
        meta = previous["meta"]
        value.document_ids = meta.get("document_ids", [])
        db.run(
            "UPDATE tool_logs SET status='rejected' WHERE conversation_id=? AND status='pending'",
            (cid,),
        )
    else:
        if value.action == "continue":
            text = "Continue your previous response from where it stopped, without repeating it."
        if not text:
            raise HTTPException(400, "Enter a message.")
        if not history:
            db.run("UPDATE conversations SET title=? WHERE id=?", (text[:70], cid))
        db.message(
            cid,
            "user",
            text,
            {
                "document_ids": value.document_ids,
                "has_image": bool(value.images),
                "mode": value.mode,
            },
        )
    cancel = asyncio.Event()
    entry = {"cancel": cancel, "task": None}
    request.app.state.active[cid] = entry

    async def stream():
        entry["task"] = asyncio.current_task()
        try:
            async for event in request.app.state.agent.run(
                cid, text, value.mode, value.document_ids, value.images, cancel
            ):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        finally:
            request.app.state.active.pop(cid, None)

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/memories")
async def memories():
    return db.rows("SELECT * FROM memories ORDER BY created_at DESC")


@router.post("/memories")
async def add_memory(value: Memory):
    ident = db.uid()
    db.run("INSERT INTO memories VALUES(?,?,?)", (ident, value.content, db.now()))
    return {"id": ident}


@router.put("/memories/{ident}")
async def edit_memory(ident: str, value: Memory):
    if not db.run("UPDATE memories SET content=? WHERE id=?", (value.content, ident)):
        raise HTTPException(404, "Memory not found.")
    return {"ok": True}


@router.delete("/memories")
async def clear_memory():
    db.run("DELETE FROM memories")
    return {"ok": True}


@router.delete("/memories/{ident}")
async def delete_memory(ident: str):
    db.run("DELETE FROM memories WHERE id=?", (ident,))
    return {"ok": True}


@router.get("/notes")
async def notes(q: str = ""):
    return db.rows(
        "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? ORDER BY updated_at DESC",
        ("%" + q[:200] + "%", "%" + q[:200] + "%"),
    )


@router.post("/notes")
async def add_note(value: Note):
    ident = db.uid()
    db.run(
        "INSERT INTO notes VALUES(?,?,?,?)",
        (ident, value.title, value.content, db.now()),
    )
    return {"id": ident}


@router.put("/notes/{ident}")
async def edit_note(ident: str, value: Note):
    if not db.run(
        "UPDATE notes SET title=?,content=?,updated_at=? WHERE id=?",
        (value.title, value.content, db.now(), ident),
    ):
        raise HTTPException(404, "Note not found.")
    return {"ok": True}


@router.delete("/notes/{ident}")
async def delete_note(ident: str):
    db.run("DELETE FROM notes WHERE id=?", (ident,))
    return {"ok": True}


@router.get("/tasks")
async def tasks():
    return db.rows("SELECT * FROM tasks ORDER BY completed,due_date,updated_at DESC")


def task_date(value):
    if value.due_date:
        from datetime import datetime

        try:
            datetime.fromisoformat(value.due_date)
        except ValueError:
            raise HTTPException(400, "Use an ISO date.")


@router.post("/tasks")
async def add_task(value: Task):
    task_date(value)
    ident = db.uid()
    db.run(
        "INSERT INTO tasks VALUES(?,?,?,?,?,?)",
        (
            ident,
            value.title,
            value.due_date,
            value.priority,
            int(value.completed),
            db.now(),
        ),
    )
    return {"id": ident}


@router.put("/tasks/{ident}")
async def edit_task(ident: str, value: Task):
    task_date(value)
    if not db.run(
        "UPDATE tasks SET title=?,due_date=?,priority=?,completed=?,updated_at=? WHERE id=?",
        (
            value.title,
            value.due_date,
            value.priority,
            int(value.completed),
            db.now(),
            ident,
        ),
    ):
        raise HTTPException(404, "Task not found.")
    return {"ok": True}


@router.delete("/tasks/{ident}")
async def delete_task(ident: str):
    db.run("DELETE FROM tasks WHERE id=?", (ident,))
    return {"ok": True}


@router.get("/tools")
async def tools(request: Request):
    return [
        {
            "name": t.name,
            "description": t.description,
            "permission": t.permission,
            "input_schema": t.arguments.model_json_schema(),
            "output_schema": t.output_schema,
        }
        for t in request.app.state.registry.tools.values()
    ]


@router.get("/approvals")
async def approvals(cid: str):
    result = db.rows(
        "SELECT * FROM tool_logs WHERE conversation_id=? AND status='pending'", (cid,)
    )
    for row in result:
        row["arguments"] = json.loads(row["arguments"])
    return result


@router.post("/approvals/{ident}")
async def approve(ident: str, value: Decision, request: Request):
    records = db.rows("SELECT * FROM tool_logs WHERE id=?", (ident,))
    if not records:
        raise HTTPException(404, "Approval not found.")
    row = records[0]
    idle(request, row["conversation_id"])
    # Atomic claim prevents replay/double-click from executing twice.
    claimed = db.run(
        "UPDATE tool_logs SET status=? WHERE id=? AND status='pending'",
        ("running" if value.approve else "rejected", ident),
    )
    if not claimed:
        raise HTTPException(409, "This approval was already handled.")
    if not value.approve:
        return {"rejected": True}
    result = await request.app.state.registry.execute(
        row["name"],
        json.loads(row["arguments"]),
        row["conversation_id"],
        approved=True,
        log_id=ident,
    )
    db.message(
        row["conversation_id"],
        "assistant",
        "Approved tool completed: "
        + row["name"]
        + "\n\n"
        + json.dumps(result, ensure_ascii=False),
        {"status": "complete", "tool_result": True},
    )
    return result


async def save_upload(upload, folder, limit):
    folder.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "").suffix.lower()
    path = folder / (db.uid() + suffix)
    try:
        size = 0
        with path.open("wb") as f:
            while block := await upload.read(65536):
                size += len(block)
                if size > limit:
                    raise HTTPException(413, f"Upload limit is {limit//1_000_000} MB.")
                f.write(block)
        if size == 0:
            raise HTTPException(400, "The file is empty.")
        return path
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


@router.get("/documents")
async def documents():
    return db.rows(
        "SELECT id,filename,status,error,embedding_model,created_at FROM documents ORDER BY created_at DESC"
    )


@router.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    filename = Path((file.filename or "document").replace("\\", "/")).name[:200]
    if Path(filename).suffix.lower() not in SUPPORTED:
        raise HTTPException(400, "Use PDF, DOCX, TXT, MD, CSV, JSON or XLSX.")
    path = await save_upload(file, DATA / "documents", 10_000_000)
    ident = db.uid()
    db.run(
        "INSERT INTO documents VALUES(?,?,?,?,?,?,?)",
        (ident, filename, str(path), "uploaded", None, None, db.now()),
    )
    return {"id": ident, "filename": filename, "status": "uploaded"}


@router.post("/documents/{ident}/index")
async def index(ident: str, request: Request):
    if ident in request.app.state.indexing:
        raise HTTPException(409, "Already indexing.")
    request.app.state.indexing.add(ident)
    try:
        return {
            "chunks": await index_document(
                ident, request.app.state.provider, db.settings().embedding_model
            )
        }
    finally:
        request.app.state.indexing.discard(ident)


@router.delete("/documents/{ident}")
async def delete_document(ident: str, request: Request):
    if ident in request.app.state.indexing or request.app.state.active:
        raise HTTPException(409, "Wait for indexing or chat generation to finish.")
    records = db.rows("SELECT path FROM documents WHERE id=?", (ident,))
    if records:
        Path(records[0]["path"]).unlink(missing_ok=True)
    db.run("DELETE FROM documents WHERE id=?", (ident,))
    return {"ok": True}


@router.post("/documents/search")
async def document_search(value: Search, request: Request):
    return await search(
        value.query, request.app.state.provider, db.settings().embedding_model
    )


@router.post("/analysis")
async def analysis(value: AnalysisRequest):
    records = db.rows("SELECT path FROM documents WHERE id=?", (value.document_id,))
    if not records:
        raise HTTPException(404, "Document not found.")
    return await asyncio.to_thread(analyze, records[0]["path"], value)


@router.get("/voice/status")
async def voice_status(request: Request):
    import importlib.util, os

    s = db.settings()
    result = {
        "stt_installed": bool(importlib.util.find_spec("faster_whisper")),
        "stt_model_present": bool(s.stt_model_path and Path(s.stt_model_path).is_dir()),
        "tts_platform_supported": os.name == "nt",
        "voices": [],
    }
    try:
        result["voices"] = await request.app.state.tts.voices()
    except Exception as e:
        result["tts_error"] = str(e)[:300]
    return result


@router.post("/voice/transcribe")
async def transcribe(request: Request, file: UploadFile = File(...)):
    if Path(file.filename or "").suffix.lower() not in {
        ".webm",
        ".wav",
        ".ogg",
        ".mp4",
        ".m4a",
    }:
        raise HTTPException(400, "Unsupported audio type.")
    path = await save_upload(file, DATA / "audio", 15_000_000)
    try:
        return await request.app.state.stt.transcribe(
            path, db.settings().stt_model_path
        )
    finally:
        path.unlink(missing_ok=True)


@router.post("/voice/speak")
async def speak(value: Speech, request: Request):
    async with request.app.state.tts_lock:
        data = await request.app.state.tts.synthesize(value.text, db.settings())
    return Response(data, media_type="audio/wav")


@router.post("/render")
async def render(value: Render):
    from app.core.markdown import render_markdown

    return {"html": render_markdown(value.text)}


@router.get("/export")
async def export():
    # Excludes uploaded files and vectors. Contains private text, so served without caching.
    return {
        name: db.rows("SELECT * FROM " + name)
        for name in (
            "conversations",
            "messages",
            "notes",
            "tasks",
            "memories",
            "personal_profile",
            "daily_plan",
            "study_logs",
            "desktop_targets",
        )
    }

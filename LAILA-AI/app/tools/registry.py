import asyncio, json
from datetime import datetime
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
from app.core.permissions import Permission
from app.database import database as db
from app.tools.calculator import calculate
from app.tools.filesystem import files, read_file, list_directory
from app.tools.system_info import system_info
from app.tools.data_analysis import analyze, AnalysisRequest
from app.rag.retriever import search
from app.tools.desktop import Launch, launch
from app.personal import PlanItem, add_plan


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Empty(Args):
    pass


class Expression(Args):
    expression: str = Field(max_length=200)


class Query(Args):
    query: str = Field(default="", max_length=500)


class FileQuery(Query):
    content: bool = False


class PathArgs(Args):
    path: str = Field(max_length=1000)


class NoteArgs(Args):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20000)


class TaskArgs(Args):
    title: str = Field(min_length=1, max_length=200)
    due_date: str | None = Field(default=None, max_length=40)
    priority: Literal["low", "normal", "high"] = "normal"


@dataclass
class Tool:
    name: str
    description: str
    arguments: type[BaseModel]
    permission: Permission
    handler: object
    output_schema: dict

    def schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.arguments.model_json_schema(),
            },
        }


class ToolRegistry:
    def __init__(self, provider):
        self.provider = provider
        self.tools = {}

        def register(name, description, args, permission, handler):
            self.tools[name] = Tool(
                name, description, args, permission, handler, {"type": "object"}
            )

        register(
            "calculator",
            "Evaluate arithmetic. Convert percentages to division by 100.",
            Expression,
            Permission.SAFE,
            lambda a, s: calculate(a.expression),
        )
        register(
            "date_time",
            "Read the laptop local date and time.",
            Empty,
            Permission.SAFE,
            lambda a, s: {"datetime": datetime.now().astimezone().isoformat()},
        )
        register(
            "system_info",
            "Read OS, CPU, RAM and Python information.",
            Empty,
            Permission.SAFE,
            lambda a, s: system_info(),
        )
        register(
            "file_search",
            "Search filenames or UTF-8 text within approved directories.",
            FileQuery,
            Permission.SAFE,
            lambda a, s: files(a.query, s.approved_directories, a.content),
        )
        register(
            "file_read",
            "Read a supported document inside an approved directory.",
            PathArgs,
            Permission.SAFE,
            lambda a, s: read_file(a.path, s.approved_directories),
        )
        register(
            "directory_list",
            "List an approved directory.",
            PathArgs,
            Permission.SAFE,
            lambda a, s: {"entries": list_directory(a.path, s.approved_directories)},
        )
        register(
            "document_search",
            "Search indexed local knowledge documents.",
            Query,
            Permission.SAFE,
            None,
        )
        register(
            "notes_search",
            "Search local personal notes.",
            Query,
            Permission.SAFE,
            lambda a, s: {
                "notes": db.rows(
                    "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? LIMIT 30",
                    ("%" + a.query + "%", "%" + a.query + "%"),
                )
            },
        )
        register(
            "notes_create",
            "Propose creating a note. Requires a user approval before writing.",
            NoteArgs,
            Permission.CONFIRM,
            self.create_note,
        )
        register(
            "tasks_list",
            "List local tasks.",
            Empty,
            Permission.SAFE,
            lambda a, s: {
                "tasks": db.rows(
                    "SELECT * FROM tasks ORDER BY completed,updated_at DESC LIMIT 50"
                )
            },
        )
        register(
            "tasks_create",
            "Propose creating a task. Requires user approval.",
            TaskArgs,
            Permission.CONFIRM,
            self.create_task,
        )
        register(
            "data_analysis",
            "Analyze an uploaded CSV, JSON or XLSX without executing generated code.",
            AnalysisRequest,
            Permission.SAFE,
            self.analyze,
        )

        register(
            "desktop_open",
            "Propose opening a configured desktop target. Requires user approval. Use exact ID and expected_path from configured targets.",
            Launch,
            Permission.CONFIRM,
            launch,
        )
        register(
            "plan_create",
            "Propose a dated schedule block. Use an ISO timestamp with timezone offset. Requires approval.",
            PlanItem,
            Permission.CONFIRM,
            lambda a, s: add_plan(a),
        )

    def schemas(self, names=None):
        return [
            t.schema() for t in self.tools.values() if names is None or t.name in names
        ]

    def create_note(self, a, s):
        ident = db.uid()
        db.run(
            "INSERT INTO notes VALUES(?,?,?,?)", (ident, a.title, a.content, db.now())
        )
        return {"created": True, "id": ident, "title": a.title}

    def create_task(self, a, s):
        if a.due_date:
            try:
                datetime.fromisoformat(a.due_date)
            except ValueError:
                raise ValueError("Use an ISO date, for example 2026-10-01.")
        ident = db.uid()
        db.run(
            "INSERT INTO tasks VALUES(?,?,?,?,?,?)",
            (ident, a.title, a.due_date, a.priority, 0, db.now()),
        )
        return {"created": True, "id": ident, "title": a.title}

    def analyze(self, a, s):
        docs = db.rows("SELECT path FROM documents WHERE id=?", (a.document_id,))
        if not docs:
            raise ValueError("Document not found.")
        return analyze(docs[0]["path"], a)

    async def execute(self, name, arguments, cid, approved=False, log_id=None):
        if name not in self.tools:
            raise ValueError("Unknown tool.")
        tool = self.tools[name]
        args = tool.arguments.model_validate(arguments)
        if tool.permission == Permission.DANGEROUS:
            raise PermissionError("Dangerous tools are disabled.")
        ident = log_id or db.uid()
        if not log_id:
            db.run(
                "INSERT INTO tool_logs VALUES(?,?,?,?,?,?,?)",
                (
                    ident,
                    cid,
                    name,
                    json.dumps(arguments),
                    "pending" if tool.permission == Permission.CONFIRM else "running",
                    "{}",
                    db.now(),
                ),
            )
        if tool.permission == Permission.CONFIRM and not approved:
            return {
                "pending_approval": ident,
                "tool": name,
                "arguments": arguments,
                "executed": False,
            }
        try:
            settings = db.settings()
            if name == "document_search":
                result = {
                    "sources": await search(
                        args.query, self.provider, settings.embedding_model
                    )
                }
            else:
                result = await asyncio.to_thread(tool.handler, args, settings)
            db.run(
                "UPDATE tool_logs SET status='completed',result=? WHERE id=?",
                (json.dumps(result, ensure_ascii=False), ident),
            )
            return result
        except Exception as e:
            db.run(
                "UPDATE tool_logs SET status='error',result=? WHERE id=?",
                (json.dumps({"error": str(e)[:300]}), ident),
            )
            raise

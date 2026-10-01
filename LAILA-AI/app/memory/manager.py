from app.database import database as db


def context(settings):
    if not settings.memory_enabled:
        return ""
    memories = db.rows("SELECT content FROM memories ORDER BY created_at DESC LIMIT 30")
    return "\n".join(m["content"] for m in memories)[:6000]


def recent_messages(cid, char_budget):
    history = db.rows(
        "SELECT role,content FROM messages WHERE conversation_id=? ORDER BY rowid DESC LIMIT 100",
        (cid,),
    )
    selected = []
    total = 0
    for msg in history:
        if total + len(msg["content"]) > char_budget:
            break
        selected.append(msg)
        total += len(msg["content"])
    return list(reversed(selected))

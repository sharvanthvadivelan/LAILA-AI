import os
from app.core.security import safe_path, forbidden
from app.rag.loader import extract, SUPPORTED


def files(query, roots, content=False):
    results = []
    inspected = 0
    for root in roots:
        safe_path(root, roots)
        for base, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = [
                d
                for d in dirs
                if not forbidden(__import__("pathlib").Path(base) / d)
                and not (__import__("pathlib").Path(base) / d).is_symlink()
            ]
            for name in names:
                inspected += 1
                if inspected > 5000:
                    return {"files": results, "truncated": True}
                try:
                    p = safe_path(str(__import__("pathlib").Path(base) / name), roots)
                except (ValueError, OSError):
                    continue
                match = query.casefold() in name.casefold()
                snippet = None
                if (
                    content
                    and p.suffix.lower() in {".txt", ".md", ".csv", ".json"}
                    and p.stat().st_size < 1_000_000
                ):
                    try:
                        text = p.read_text(encoding="utf-8")
                        at = text.casefold().find(query.casefold())
                        if at >= 0:
                            match = True
                            snippet = text[max(0, at - 80) : at + 200]
                    except (UnicodeError, OSError):
                        pass
                if match:
                    results.append(
                        {"path": str(p), "bytes": p.stat().st_size, "snippet": snippet}
                    )
                if len(results) >= 50:
                    return {"files": results, "truncated": True}
    return {"files": results, "truncated": False}


def read_file(path, roots):
    p = safe_path(path, roots)
    if not p.is_file() or p.suffix.lower() not in SUPPORTED:
        raise ValueError("Choose a supported document file.")
    if p.stat().st_size > 10_000_000:
        raise ValueError("File exceeds 10 MB.")
    text = "\n".join(f"{location}:\n{text}" for _, location, text in extract(p))
    return {"path": str(p), "content": text[:18000], "truncated": len(text) > 18000}


def list_directory(path, roots):
    p = safe_path(path, roots)
    if not p.is_dir():
        raise ValueError("Not a directory.")
    entries = []
    for child in p.iterdir():
        try:
            resolved = safe_path(str(child), roots)
        except (OSError, ValueError):
            continue
        entries.append(
            {"name": child.name, "path": str(resolved), "directory": resolved.is_dir()}
        )
        if len(entries) >= 200:
            break
    return entries

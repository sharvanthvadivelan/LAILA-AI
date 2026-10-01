from pathlib import Path
import os

FORBIDDEN_PARTS = {
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "appdata",
    ".ssh",
    ".aws",
    ".azure",
    ".config",
    ".gnupg",
    "credentials",
    "keychains",
    ".git",
}
SECRET_NAMES = {
    ".env",
    "login data",
    "cookies",
    "local state",
    "key4.db",
    "logins.json",
    "credentials.json",
}


def forbidden(path: Path):
    return (
        any(p.lower() in FORBIDDEN_PARTS for p in path.parts)
        or path.name.lower() in SECRET_NAMES
        or path.suffix.lower() in {".pem", ".key", ".kdbx"}
    )


def validate_root(value: str) -> Path:
    path = Path(value).expanduser().resolve(strict=True)
    if (
        not path.is_dir()
        or path == Path(path.anchor)
        or path == Path.home().resolve()
        or forbidden(path)
    ):
        raise ValueError(
            "Choose a dedicated documents/workspace folder, not a drive, home or system directory."
        )
    if os.name != "nt" and (
        str(path) in {"/etc", "/usr", "/proc", "/sys", "/dev", "/root", "/var"}
    ):
        raise ValueError("System directories cannot be approved.")
    return path


def safe_path(value: str, roots: list[str]) -> Path:
    if not roots:
        raise ValueError("No approved directory. Add a dedicated folder in Settings.")
    path = Path(value).expanduser().resolve(strict=True)
    allowed = [validate_root(root) for root in roots]
    if forbidden(path) or not any(path == r or path.is_relative_to(r) for r in allowed):
        raise ValueError("Path is outside approved directories or is a protected file.")
    return path

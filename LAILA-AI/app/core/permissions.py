from enum import Enum


class Permission(str, Enum):
    SAFE = "SAFE"
    CONFIRM = "CONFIRM"
    DANGEROUS = "DANGEROUS"


class CodeExecutor:
    """Extension point. No host code execution is enabled in this release."""

    def execute(self, code, language):
        raise PermissionError(
            "Code execution is disabled until an isolated sandbox is configured and approved."
        )

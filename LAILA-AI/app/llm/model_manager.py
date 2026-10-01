import shutil
from app.llm.base import LLMError


async def status(provider, selected):
    result = {
        "installed_on_path": bool(shutil.which("ollama")),
        "running": False,
        "models": [],
        "selected": selected,
        "available": False,
    }
    try:
        result["models"] = await provider.models()
        result["running"] = True
        result["available"] = any(
            x["name"] in {selected, selected + ":latest"} for x in result["models"]
        )
    except LLMError as e:
        result["error"] = str(e)
    return result

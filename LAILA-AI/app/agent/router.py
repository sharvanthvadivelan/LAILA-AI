import re

MODES = {
    "chat": "Answer the user directly or use available tools when needed.",
    "study": "Act as a patient tutor. Use definitions, a worked example, exam keywords and appropriate complexity. Follow the requested answer length. For quizzes, wait for the learner to answer before revealing answers.",
    "coding": "Help write, review and debug code. State assumptions, explain complexity and provide edge cases. Do not claim code was executed or tests passed unless a tool actually ran them. Code execution is unavailable.",
    "data": "Use data_analysis on uploaded dataset IDs to ground statistics in actual data. Never invent measurements.",
}


def route(text, mode, docs, images):
    if images:
        return "VISION"
    if docs:
        return "RAG"
    if mode == "study":
        return "STUDY"
    if mode == "coding":
        return "CODE"
    if mode == "data":
        return "DATA_ANALYSIS"
    if re.search(r"\b(calculate|find|search|note|task|file|time|date)\b", text, re.I):
        return "TOOL"
    return "DIRECT_LLM"


def arithmetic(text):
    match = re.fullmatch(r"\s*calculate\s+([\d\s.+*/()%×÷^−-]+)\s*[?]?\s*", text, re.I)
    pct = re.fullmatch(
        r"\s*calculate\s+([\d.]+)%\s+of\s+([\d.]+)\s*[?]?\s*", text, re.I
    )
    if pct:
        return f"({pct[1]}/100)*{pct[2]}"
    return match[1].replace("−", "-") if match else None


def tool_names(text, mode, docs):
    """Offer a small set of relevant tools; ordinary explanations need no tools."""
    t = text.lower()
    names = set()
    if mode == "data":
        names.add("data_analysis")
    explanation = bool(
        re.search(r"\b(explain|operator|code|function|program|syntax|meaning)\b", t)
    )
    if not explanation and re.search(
        r"\b(calculate|compute|plus|minus|times|divided|percent)\b|\d\s*[+*/%-]\s*\d", t
    ):
        names.add("calculator")
    if re.search(r"\b(current time|what time|today.s date|current date)\b", t):
        names.add("date_time")
    if re.search(r"\b(my|this|laptop|computer)\b", t) and re.search(
        r"\b(ram|cpu|system|hardware)\b", t
    ):
        names.add("system_info")
    if re.search(r"\b(find|search|read|list)\b", t):
        if re.search(r"\b(files?|folders?|directory|directories)\b", t):
            names.update(["file_search", "file_read", "directory_list"])
        if re.search(r"\b(documents?|knowledge)\b", t):
            names.add("document_search")
        if re.search(r"\b(notes?)\b", t):
            names.add("notes_search")
    if re.search(r"\b(tasks?|to.do)\b", t):
        names.add("tasks_list")
    if re.search(r"\b(create|add|save|make|remember)\b", t):
        if re.search(r"\b(notes?)\b", t):
            names.add("notes_create")
        if re.search(r"\b(tasks?|to.do)\b", t):
            names.add("tasks_create")
    if re.search(r"\b(schedule|book|add)\b", t) and re.search(
        r"\b(session|block|schedule|study|meeting)\b", t
    ):
        names.add("plan_create")
    if re.search(r"^\s*(please\s+)?(open|launch|start)\b", t):
        names.add("desktop_open")
    return names

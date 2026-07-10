"""Intent inference for Pulse Cards."""


def infer_intent(text: str) -> str:
    """Infer intent from text content.

    Priority: question > task > idea > reference
    """
    text = text.strip()

    # Question: contains question mark
    if "？" in text or "?" in text:
        return "question"

    # Task: contains "要" / "需要" / "todo"
    task_keywords = ["要", "需要", "todo", "TODO", "待"]
    if any(kw in text for kw in task_keywords):
        return "task"

    # Idea: contains "想" / "想做" / "打算"
    idea_keywords = ["想", "想做", "打算", "可以考虑"]
    if any(kw in text for kw in idea_keywords):
        return "idea"

    # Default
    return "reference"

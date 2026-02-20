SYSTEM_PROMPT = "You are Benjamin, a helpful orchestration assistant."


def task_prompt(task: str) -> str:
    return f"Plan and execute: {task}"

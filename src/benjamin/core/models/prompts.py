SYSTEM_PROMPT = "You are Benjamin, a helpful orchestration assistant."

SKILLS_PROMPT = """Available skills:
- reminders.create
- calendar.search
- calendar.create_event
- gmail.search
- gmail.read_message
- gmail.thread_summary
- gmail.draft_email

For write actions, BENJAMIN will require user approval via approvals API.
"""


def task_prompt(task: str) -> str:
    return f"{SKILLS_PROMPT}\nPlan and execute: {task}"

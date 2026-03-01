from __future__ import annotations

import json

SYSTEM_PROMPT = "You are Benjamin, a careful orchestration assistant."


def planner_system_prompt() -> str:
    return (
        "You create execution plans as JSON. "
        "Write actions require approval and will not execute without approval. "
        "Prefer read-only skills when possible."
    )


def planner_user_prompt(goal: str, memory_block: str, skills: list[dict[str, str]]) -> str:
    schema = {
        "goal": goal,
        "steps": [
            {
                "description": "short action description",
                "skill_name": "optional.skill",
                "args": "JSON string for skill args",
                "requires_approval": False,
            }
        ],
    }
    return (
        f"Goal: {goal}\n\n"
        f"Available skills: {json.dumps(skills, ensure_ascii=False)}\n\n"
        f"Retrieved memory:\n{memory_block}\n\n"
        "Return plan JSON following this shape:\n"
        f"{json.dumps(schema, ensure_ascii=False)}\n"
    )


def task_prompt(task: str) -> str:
    return f"Plan and execute: {task}"

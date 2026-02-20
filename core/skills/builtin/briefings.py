from __future__ import annotations

import json

from core.scheduler.jobs import run_daily_briefing
from core.skills.base import SkillResult


class BriefingsDailySkill:
    name = "briefings.daily"
    side_effect = "read"

    def __init__(self, state_dir: str) -> None:
        self.state_dir = state_dir

    def run(self, query: str) -> SkillResult:
        _ = query
        run_daily_briefing(state_dir=self.state_dir)
        return SkillResult(content=json.dumps({"ok": True}))

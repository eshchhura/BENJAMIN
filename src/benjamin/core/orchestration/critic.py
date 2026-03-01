from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from benjamin.core.orchestration.planner import Plan
from benjamin.core.orchestration.schemas import CriticNormalization, CriticResult


class PlanCritic:
    def __init__(self, default_timezone: str | None = None) -> None:
        self.default_timezone = default_timezone or os.getenv("BENJAMIN_TIMEZONE", "America/New_York")

    def review(self, plan: Plan) -> CriticResult:
        warnings: list[str] = []
        normalizations: list[CriticNormalization] = []
        now = datetime.now(tz=timezone.utc)

        for step in plan.steps:
            if step.skill_name == "calendar.create_event":
                result = self._review_calendar(step, warnings)
                if result.ok is False:
                    return result
                normalizations.extend(result.normalizations)
            elif step.skill_name == "gmail.draft_email":
                result = self._review_gmail(step, warnings)
                if result.ok is False:
                    return result
                normalizations.extend(result.normalizations)
            elif step.skill_name == "reminders.create":
                result = self._review_reminder(step, warnings, now)
                if result.ok is False:
                    return result
                normalizations.extend(result.normalizations)

        return CriticResult(ok=True, plan=plan, warnings=warnings, normalizations=normalizations)

    def _review_calendar(self, step, warnings: list[str]) -> CriticResult:
        try:
            payload = json.loads(step.args)
        except json.JSONDecodeError:
            return CriticResult(
                ok=False,
                errors=["Invalid calendar.create_event payload JSON."],
                user_question="I couldn't parse the event details. Could you resend them in JSON format?",
            )

        normal_changes: dict[str, dict[str, object]] = {}

        start = self._parse_iso(payload.get("start_iso"), payload.get("timezone"))
        end = self._parse_iso(payload.get("end_iso"), payload.get("timezone"))
        if start is None or end is None:
            return CriticResult(
                ok=False,
                errors=["calendar.create_event requires valid start_iso and end_iso."],
                user_question="I couldn't understand the event times. Can you provide valid start and end times?",
            )

        timezone_name = payload.get("timezone")
        if timezone_name is None or str(timezone_name).strip() == "":
            payload["timezone"] = self.default_timezone
            normal_changes["timezone"] = {"from": timezone_name, "to": self.default_timezone}
        elif not self._valid_timezone(str(timezone_name)):
            return CriticResult(
                ok=False,
                errors=[f"Invalid timezone: {timezone_name}"],
                user_question="The timezone looks invalid. What timezone should I use (for example, America/New_York)?",
            )

        if end <= start:
            return CriticResult(
                ok=False,
                errors=["Event end time must be after start time."],
                user_question="Your event end time is before the start time. What should the correct end time be?",
            )

        if start > datetime.now(tz=timezone.utc) + timedelta(days=365 * 2):
            warnings.append("calendar.create_event start time is more than 2 years in the future.")

        if (end - start) > timedelta(hours=8):
            warnings.append("calendar.create_event duration exceeds 8 hours.")

        if normal_changes:
            step.args = json.dumps(payload)
            return CriticResult(
                ok=True,
                normalizations=[CriticNormalization(step_id=step.id, changes=normal_changes)],
            )
        return CriticResult(ok=True)

    def _review_gmail(self, step, warnings: list[str]) -> CriticResult:
        try:
            payload = json.loads(step.args)
        except json.JSONDecodeError:
            return CriticResult(
                ok=False,
                errors=["Invalid gmail.draft_email payload JSON."],
                user_question="I couldn't parse the email draft details. Could you resend them in JSON format?",
            )

        normal_changes: dict[str, dict[str, object]] = {}
        to_list = payload.get("to") or []
        if not isinstance(to_list, list):
            to_list = []
        normalized = []
        for address in to_list:
            candidate = str(address).strip()
            if candidate:
                normalized.append(candidate)
        deduped = list(dict.fromkeys(normalized))
        if deduped != to_list:
            payload["to"] = deduped
            normal_changes["to"] = {"from": to_list, "to": deduped}

        if not deduped:
            return CriticResult(
                ok=False,
                errors=["gmail.draft_email requires at least one recipient."],
                user_question="Who should I email? Provide at least one recipient.",
            )

        subject = str(payload.get("subject") or "").strip()
        if subject == "":
            warnings.append("gmail.draft_email subject is empty.")

        if normal_changes:
            step.args = json.dumps(payload)
            return CriticResult(
                ok=True,
                normalizations=[CriticNormalization(step_id=step.id, changes=normal_changes)],
            )
        return CriticResult(ok=True)

    def _review_reminder(self, step, warnings: list[str], now: datetime) -> CriticResult:
        try:
            payload = json.loads(step.args)
        except json.JSONDecodeError:
            return CriticResult(
                ok=False,
                errors=["Invalid reminders.create payload JSON."],
                user_question="I couldn't parse the reminder details. Could you resend them in JSON format?",
            )

        normal_changes: dict[str, dict[str, object]] = {}
        message = str(payload.get("message") or "").strip()
        if message == "":
            return CriticResult(
                ok=False,
                errors=["reminders.create requires a non-empty message."],
                user_question="What reminder message should I save?",
            )

        run_at = self._parse_iso(payload.get("run_at_iso"), payload.get("timezone"))
        if run_at is None:
            return CriticResult(
                ok=False,
                errors=["reminders.create requires valid run_at_iso."],
                user_question="When should I schedule this reminder? Please provide a valid date/time.",
            )

        if run_at <= now:
            original_run_at = payload.get("run_at_iso")
            adjusted = now + timedelta(minutes=5)
            adjusted_iso = adjusted.isoformat()
            payload["run_at_iso"] = adjusted_iso
            normal_changes["run_at_iso"] = {"from": original_run_at, "to": adjusted_iso}

        if normal_changes:
            step.args = json.dumps(payload)
            return CriticResult(
                ok=True,
                normalizations=[CriticNormalization(step_id=step.id, changes=normal_changes)],
            )
        return CriticResult(ok=True)

    def _parse_iso(self, value: object, timezone_value: object) -> datetime | None:
        if not isinstance(value, str) or value.strip() == "":
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            tz_name = str(timezone_value).strip() if timezone_value is not None else self.default_timezone
            if not self._valid_timezone(tz_name):
                return None
            parsed = parsed.replace(tzinfo=ZoneInfo(tz_name))
        return parsed.astimezone(timezone.utc)

    def _valid_timezone(self, timezone_name: str) -> bool:
        try:
            ZoneInfo(timezone_name)
            return True
        except ZoneInfoNotFoundError:
            return False

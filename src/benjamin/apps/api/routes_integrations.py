from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends

from .deps import get_breaker_manager, get_calendar_connector, get_email_connector, get_memory_manager

router = APIRouter()


@router.get("/status")
def integrations_status(
    memory_manager=Depends(get_memory_manager),
    calendar_connector=Depends(get_calendar_connector),
    email_connector=Depends(get_email_connector),
    breaker_manager=Depends(get_breaker_manager),
) -> dict[str, object]:
    google_enabled = os.getenv("BENJAMIN_GOOGLE_ENABLED", "off").casefold() == "on"
    token_path = Path(os.getenv("BENJAMIN_GOOGLE_TOKEN_PATH", str(memory_manager.state_dir / "google_token.json"))).expanduser()
    return {
        "google_enabled": google_enabled,
        "google_token_present": token_path.exists(),
        "calendar_ready": calendar_connector is not None,
        "gmail_ready": email_connector is not None,
        "timezone": os.getenv("BENJAMIN_TIMEZONE", "America/New_York"),
        "breakers": breaker_manager.snapshot(),
    }

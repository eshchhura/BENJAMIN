# jarvis/skills/scheduler.py
# -----------------------------------
# Handles scheduling intents: e.g., “remind me to call Alice tomorrow at 3 PM”,
# “list my tomorrow’s events”, “delete reminder X”.
# Uses APScheduler for in-program reminders or integrates with Google Calendar API.
# -----------------------------------

import logging
import sqlite3
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from jarvis.config import Config

logger = logging.getLogger(__name__)

# Initialize a global scheduler (runs in background thread)
scheduler = BackgroundScheduler()
scheduler.start()

def can_handle(intent: str) -> bool:
    return intent in {"create_reminder", "list_reminders", "delete_reminder"}

def handle(intent: str, params: dict, context: dict) -> str:
    """
    For simplicity, reminders are stored in a local SQLite DB (memory_db.py).
    APScheduler jobs fire at the specified datetime to send notifications.
    """
    cfg = Config()
    db_path = cfg.get("memory", "long_term_db_path")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY, message TEXT, run_at TEXT)"
    )
    conn.commit()

    try:
        if intent == "create_reminder":
            msg = params.get("message")
            run_at_str = params.get("datetime")  # e.g., "2025-06-10 15:00"
            if not msg or not run_at_str:
                return "I need both a reminder message and a date/time."
            run_at = datetime.fromisoformat(run_at_str)
            c.execute("INSERT INTO reminders (message, run_at) VALUES (?, ?)", (msg, run_at_str))
            reminder_id = c.lastrowid
            conn.commit()
            # Schedule APScheduler job
            scheduler.add_job(
                func=_trigger_reminder,
                trigger="date",
                run_date=run_at,
                args=[reminder_id, msg],
                id=f"reminder_{reminder_id}"
            )
            return f"Reminder #{reminder_id} set for {run_at.strftime('%Y-%m-%d %H:%M')}."
        
        elif intent == "list_reminders":
            c.execute("SELECT id, message, run_at FROM reminders ORDER BY run_at")
            rows = c.fetchall()
            if not rows:
                return "You have no upcoming reminders."
            lines = [f"#{r[0]}: '{r[1]}' at {r[2]}" for r in rows]
            return "Your reminders:\n" + "\n".join(lines)

        elif intent == "delete_reminder":
            rem_id = params.get("id")
            if not rem_id:
                return "I need the reminder ID you want to delete."
            c.execute("DELETE FROM reminders WHERE id = ?", (rem_id,))
            conn.commit()
            # Also remove from scheduler if exists
            job_id = f"reminder_{rem_id}"
            try:
                scheduler.remove_job(job_id)
            except Exception:
                pass
            return f"Deleted reminder #{rem_id}."
        
        else:
            return "Scheduler received an unknown intent."
    except Exception as e:
        logger.exception("Error in scheduler.handle: %s", e)
        return "An error occurred while handling scheduling."
    finally:
        conn.close()

def _trigger_reminder(reminder_id: int, message: str):
    """
    APScheduler callback when a reminder time arrives.
    For now, just prints to console or could integrate with TTS.
    """
    logger.info("Reminder #%d: %s", reminder_id, message)
    # You might call back into the main assistant to speak this out loud.


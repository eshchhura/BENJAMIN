# jarvis/memory/long_term.py
# -----------------------------------
# Persistent storage of user facts, preferences, and conversation summaries.
# Uses SQLite via SQLAlchemy or raw sqlite3 for simplicity.
# -----------------------------------

import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class LongTermMemory:
    """
    Manages a SQLite database of:
    - user_facts (key-value pairs)
    - interaction_log (timestamp, input, intent, response)
    - reminders (migrated from scheduler if desired)
    """

    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._initialize_tables()

    def _initialize_tables(self):
        c = self.conn.cursor()
        # Table: user_facts (e.g., {'key': 'allergic_to', 'value': 'peanuts'})
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_facts (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # Table: interaction_log (timestamp TEXT, input TEXT, intent TEXT, response TEXT)
        c.execute("""
            CREATE TABLE IF NOT EXISTS interaction_log (
                timestamp TEXT,
                user_input TEXT,
                intent TEXT,
                response TEXT
            )
        """)
        self.conn.commit()

    def store_fact(self, key: str, value: str):
        """
        Insert or update a user fact.
        """
        c = self.conn.cursor()
        c.execute("INSERT OR REPLACE INTO user_facts (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    def retrieve_fact(self, key: str) -> str:
        c = self.conn.cursor()
        c.execute("SELECT value FROM user_facts WHERE key = ?", (key,))
        row = c.fetchone()
        return row[0] if row else None

    def log_interaction(self, user_input: str, intent: str, response: str):
        """
        Append a new row to interaction_log with current timestamp.
        """
        ts = datetime.now().isoformat()
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO interaction_log (timestamp, user_input, intent, response) VALUES (?, ?, ?, ?)",
            (ts, user_input, intent, response)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()

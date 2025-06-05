# jarvis/utils/helpers.py
# -----------------------------------
# Miscellaneous helper functions used across modules, e.g., date parsing, file path normalization.
# -----------------------------------

from datetime import datetime

def parse_datetime(text: str):
    """
    Attempt to parse ambiguous datetime strings (e.g., "tomorrow at 3pm") into ISO format.
    Placeholder: in production, integrate Duckling or dateparser.
    """
    try:
        dt = datetime.fromisoformat(text)
        return dt
    except ValueError:
        # Fallback: use dateparser library if installed
        import dateparser
        dt = dateparser.parse(text)
        return dt

def normalize_entity_values(entities: dict):
    """
    Standardize entity keys/values (e.g., lowercase keys, strip whitespace).
    """
    return {k.lower().strip(): v.strip() if isinstance(v, str) else v for k, v in entities.items()}

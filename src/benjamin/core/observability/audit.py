from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuditRecord:
    timestamp: datetime
    action: str

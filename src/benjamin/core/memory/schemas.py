from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SemanticFact(BaseModel):
    id: str
    key: str
    value: str
    scope: str = "global"
    tags: list[str] = Field(default_factory=list)
    created_at_iso: str
    updated_at_iso: str


class Episode(BaseModel):
    id: str
    kind: str
    summary: str
    ts_iso: str
    meta: dict[str, Any] = Field(default_factory=dict)


class MemoryQuery(BaseModel):
    text: str
    limit: int = 10

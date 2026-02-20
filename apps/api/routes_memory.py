from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from core.memory.manager import MemoryManager

from .deps import get_memory_manager

router = APIRouter()


class SemanticUpsertRequest(BaseModel):
    key: str
    value: str
    scope: str = "global"
    tags: list[str] = Field(default_factory=list)


@router.get("/semantic")
def list_semantic(
    scope: str | None = Query(default=None),
    memory_manager: MemoryManager = Depends(get_memory_manager),
) -> dict[str, list[dict]]:
    items = [fact.model_dump() for fact in memory_manager.semantic.list_all(scope=scope)]
    return {"items": items}


@router.post("/semantic")
def upsert_semantic(
    request: SemanticUpsertRequest,
    memory_manager: MemoryManager = Depends(get_memory_manager),
) -> dict[str, dict]:
    fact = memory_manager.semantic.upsert(
        key=request.key,
        value=request.value,
        scope=request.scope,
        tags=request.tags,
    )
    return {"item": fact.model_dump()}


@router.get("/episodic")
def list_episodic(
    limit: int = Query(default=50, ge=1, le=200),
    memory_manager: MemoryManager = Depends(get_memory_manager),
) -> dict[str, list[dict]]:
    items = [episode.model_dump() for episode in memory_manager.episodic.list_recent(limit=limit)]
    return {"items": items}

"""Built-in web search stub skill."""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.orchestration.schemas import ContextPack
from core.skills.base import Skill


class WebSearchInput(BaseModel):
    query: str


class WebSearchResult(BaseModel):
    title: str
    snippet: str
    url: str


class WebSearchOutput(BaseModel):
    results: list[WebSearchResult] = Field(default_factory=list)
    reason: str = "web.search is not implemented yet"


class WebSearchSkill(Skill):
    """Read-only placeholder web search skill for planner tool selection."""

    name = "web.search"
    description = "Search the web for public information (stub)"
    side_effect = "read"
    input_model = WebSearchInput
    output_model = WebSearchOutput

    def run(self, input_data: WebSearchInput, ctx: ContextPack) -> WebSearchOutput:
        _ = (input_data, ctx)
        return WebSearchOutput()

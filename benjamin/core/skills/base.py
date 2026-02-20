"""Skill abstraction with runtime input/output validation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel

from core.orchestration.schemas import ContextPack


class Skill(ABC):
    """Base class for all skills with strict schema contracts."""

    name: str
    description: str
    side_effect: Literal["read", "write"] = "read"
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    @abstractmethod
    def run(self, input_data: BaseModel, ctx: ContextPack) -> BaseModel:
        """Implement skill logic. Receives validated input model."""

    def execute(self, args: dict, ctx: ContextPack) -> BaseModel:
        """Validate input args, run, then validate output model."""

        validated_input = self.input_model.model_validate(args)
        raw_output = self.run(validated_input, ctx)
        if isinstance(raw_output, self.output_model):
            return raw_output
        return self.output_model.model_validate(raw_output)

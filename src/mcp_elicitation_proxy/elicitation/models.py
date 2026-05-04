from __future__ import annotations

from pydantic import BaseModel, Field


class ElicitationField(BaseModel):
    name: str
    type: str = "string"
    description: str | None = None
    required: bool = True


class ElicitationRequest(BaseModel):
    message: str
    fields: list[ElicitationField] = Field(default_factory=list)

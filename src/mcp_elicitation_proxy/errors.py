from __future__ import annotations

import json

from pydantic import BaseModel, Field


class StructuredToolErrorPayload(BaseModel):
    error: str
    tool: str
    reason: str
    missing_or_ambiguous: list[str] = Field(default_factory=list)
    message: str


def to_json_message(payload: StructuredToolErrorPayload) -> str:
    return json.dumps(payload.model_dump())

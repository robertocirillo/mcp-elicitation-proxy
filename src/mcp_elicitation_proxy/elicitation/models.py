from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ElicitationField(BaseModel):
    name: str
    type: str = "string"
    description: str | None = None
    required: bool = True


class ElicitationRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    message: str
    fields: list[ElicitationField] = Field(default_factory=list)
    response_model: type[BaseModel] | None = Field(default=None, exclude=True)

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def combined_required_fields(
    tool_name: str,
    tool_schema: dict[str, Any] | None,
    tool_required_fields: Mapping[str, Sequence[str]],
) -> list[str]:
    required_fields: list[str] = []

    if tool_schema is not None:
        schema_required_fields = tool_schema.get("required")
        if isinstance(schema_required_fields, list):
            required_fields.extend(
                field for field in schema_required_fields if isinstance(field, str)
            )

    for field in tool_required_fields.get(tool_name, []):
        if isinstance(field, str) and field not in required_fields:
            required_fields.append(field)

    return required_fields

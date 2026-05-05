from __future__ import annotations

from typing import Any


def merge_elicited_values(
    arguments: dict[str, Any],
    values: dict[str, Any],
    fields: list[str],
) -> dict[str, Any]:
    updated_arguments = dict(arguments)
    for field in fields:
        if field in values:
            updated_arguments[field] = values[field]
    return updated_arguments

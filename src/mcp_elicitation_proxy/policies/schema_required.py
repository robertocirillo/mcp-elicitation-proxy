from __future__ import annotations

from typing import Any

from .base import InspectionResult


class SchemaRequiredPolicy:
    async def inspect(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_schema: dict[str, Any] | None,
        context: Any,
    ) -> InspectionResult:
        return InspectionResult.ok()

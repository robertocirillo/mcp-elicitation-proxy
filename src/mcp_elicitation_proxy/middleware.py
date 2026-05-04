from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .pipeline import ElicitationPipeline
from .policies.base import InspectionResult


@dataclass(slots=True)
class ElicitationMiddleware:
    pipeline: ElicitationPipeline | None = None

    async def inspect_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_schema: dict[str, Any] | None,
        context: Any = None,
    ) -> InspectionResult:
        if self.pipeline is None:
            return InspectionResult.ok()
        return await self.pipeline.inspect(tool_name, arguments, tool_schema, context)

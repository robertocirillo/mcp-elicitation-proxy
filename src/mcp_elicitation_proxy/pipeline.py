from __future__ import annotations

from typing import Any, Sequence

from .policies.base import InspectionResult, InspectionStatus, ToolElicitationPolicy


class ElicitationPipeline:
    def __init__(self, policies: Sequence[ToolElicitationPolicy] | None = None) -> None:
        self._policies = list(policies or [])

    async def inspect(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_schema: dict[str, Any] | None,
        context: Any = None,
    ) -> InspectionResult:
        current_arguments = dict(arguments)
        changed = False

        for policy in self._policies:
            result = await policy.inspect(tool_name, current_arguments, tool_schema, context)
            if result.updated_arguments is not None:
                current_arguments = dict(result.updated_arguments)
                changed = True
            if result.status != InspectionStatus.OK:
                return result

        if changed:
            return InspectionResult.ok(updated_arguments=current_arguments)
        return InspectionResult.ok()

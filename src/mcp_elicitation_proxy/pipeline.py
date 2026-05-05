from __future__ import annotations

from typing import Any, Sequence

from .config import AppConfig
from .policies.base import InspectionResult, InspectionStatus, ToolElicitationPolicy
from .policies.schema_required import SchemaRequiredPolicy
from .policies.sensitive_required import SensitiveRequiredFieldPolicy


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


def build_pipeline(config: AppConfig) -> ElicitationPipeline:
    policies: list[ToolElicitationPolicy] = []
    tool_required_fields = {
        tool_name: tool_config.required
        for tool_name, tool_config in config.tools.items()
        if tool_config.required
    }

    if config.policies.sensitive_required.enabled:
        policies.append(
            SensitiveRequiredFieldPolicy(
                tool_required_fields=tool_required_fields,
                sensitive_name_markers=(
                    config.policies.sensitive_required.sensitive_name_markers
                ),
                sensitive_schema_markers=(
                    config.policies.sensitive_required.sensitive_schema_markers
                ),
            )
        )

    if config.policies.schema_required.enabled:
        policies.append(
            SchemaRequiredPolicy(tool_required_fields=tool_required_fields)
        )

    return ElicitationPipeline(policies)

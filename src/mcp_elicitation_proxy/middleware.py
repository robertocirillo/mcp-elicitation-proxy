from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import mcp.types as mt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult

from .errors import StructuredToolErrorPayload, to_json_message
from .pipeline import ElicitationPipeline
from .policies.base import InspectionIssue, InspectionResult, InspectionStatus


@dataclass(slots=True)
class ElicitationMiddleware(Middleware):
    pipeline: ElicitationPipeline | None = None

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        tool_name = context.message.name
        arguments = dict(context.message.arguments or {})
        tool_schema = await self._resolve_tool_schema(context, tool_name)

        result = await self.inspect_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            tool_schema=tool_schema,
            context=context.fastmcp_context,
        )

        if result.status == InspectionStatus.OK:
            if result.updated_arguments is None:
                return await call_next(context)

            message = context.message.model_copy(
                update={"arguments": dict(result.updated_arguments)}
            )
            return await call_next(context.copy(message=message))

        return self._fallback_result(tool_name, result)

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

    async def _resolve_tool_schema(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        tool_name: str,
    ) -> dict[str, Any] | None:
        fastmcp_context = context.fastmcp_context
        if fastmcp_context is None:
            return None

        try:
            tool = await fastmcp_context.fastmcp.get_tool(tool_name)
        except Exception:
            return None

        if tool is None:
            return None

        parameters = getattr(tool, "parameters", None)
        if isinstance(parameters, dict):
            return parameters
        return None

    def _fallback_result(
        self,
        tool_name: str,
        result: InspectionResult,
    ) -> ToolResult:
        payload = StructuredToolErrorPayload(
            error="tool_call_blocked",
            tool=tool_name,
            status=result.status.value,
            reason=self._reason_for(result),
            missing_or_ambiguous=self._fields_for(result.issues),
            message=self._message_for(result),
        )
        return ToolResult(
            content=to_json_message(payload),
            structured_content=payload.model_dump(),
        )

    def _reason_for(self, result: InspectionResult) -> str:
        if result.status == InspectionStatus.NEEDS_ELICITATION:
            return "required_fields_missing_or_empty"
        return result.status.value

    def _fields_for(self, issues: list[InspectionIssue]) -> list[str]:
        return [issue.field for issue in issues if issue.field is not None]

    def _message_for(self, result: InspectionResult) -> str:
        if result.status == InspectionStatus.NEEDS_ELICITATION:
            fields = self._fields_for(result.issues)
            if fields:
                return (
                    "Tool call requires additional input for: "
                    + ", ".join(fields)
                    + "."
                )
            return "Tool call requires additional input."

        messages = [issue.message for issue in result.issues]
        return " ".join(messages) if messages else "Tool call was blocked."

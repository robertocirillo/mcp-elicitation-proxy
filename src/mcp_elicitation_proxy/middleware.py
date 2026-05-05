from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import mcp.types as mt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult

from .elicitation.client import (
    ElicitationOutcomeStatus,
    merge_elicited_values,
    request_missing_values,
)
from .errors import (
    StructuredToolErrorPayload,
    build_elicitation_blocked_payload,
    build_tool_call_blocked_payload,
    to_json_message,
)
from .pipeline import ElicitationPipeline
from .policies.base import InspectionResult, InspectionStatus


logger = logging.getLogger(__name__)


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
            return await self._forward_tool_call(context, call_next, result)

        if result.status != InspectionStatus.NEEDS_ELICITATION:
            return self._fallback_result(tool_name, result)

        elicitation = await request_missing_values(
            context.fastmcp_context,
            tool_name,
            result.issues,
            tool_schema,
        )
        if elicitation.status == ElicitationOutcomeStatus.UNAVAILABLE:
            return self._fallback_result(tool_name, result)

        if elicitation.status != ElicitationOutcomeStatus.ACCEPTED:
            return self._fallback_payload_result(
                build_elicitation_blocked_payload(
                    tool_name,
                    status=elicitation.status.value,
                    fields=elicitation.fields,
                    message=elicitation.message
                    or "Elicitation did not provide required values.",
                )
            )

        updated_arguments = merge_elicited_values(
            arguments,
            elicitation.values or {},
            elicitation.fields,
        )
        updated_result = await self.inspect_tool_call(
            tool_name=tool_name,
            arguments=updated_arguments,
            tool_schema=tool_schema,
            context=context.fastmcp_context,
        )
        if updated_result.status == InspectionStatus.OK:
            if updated_result.updated_arguments is not None:
                updated_arguments = dict(updated_result.updated_arguments)
            return await self._forward_tool_call(
                context,
                call_next,
                InspectionResult.ok(updated_arguments=updated_arguments),
            )

        return self._fallback_result(tool_name, updated_result)

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
            logger.warning(
                "Failed to resolve tool schema for tool %r; continuing without schema.",
                tool_name,
                exc_info=True,
            )
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
        payload = build_tool_call_blocked_payload(tool_name, result)
        return self._fallback_payload_result(payload)

    def _fallback_payload_result(
        self,
        payload: StructuredToolErrorPayload,
    ) -> ToolResult:
        return ToolResult(
            content=to_json_message(payload),
            structured_content=payload.model_dump(),
        )

    async def _forward_tool_call(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
        result: InspectionResult,
    ) -> ToolResult:
        if result.updated_arguments is None:
            return await call_next(context)

        message = context.message.model_copy(
            update={"arguments": dict(result.updated_arguments)}
        )
        return await call_next(context.copy(message=message))

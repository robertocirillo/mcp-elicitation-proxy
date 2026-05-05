from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import mcp.types as mt
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult

from .config import ElicitationConfig, ToolPolicyConfig
from .elicitation.builder import build_elicitation_request
from .elicitation.client import merge_elicited_values
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
    elicitation: ElicitationConfig = field(default_factory=ElicitationConfig)
    tool_configs: dict[str, ToolPolicyConfig] = field(default_factory=dict)

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

        if not self.elicitation.enabled:
            return self._elicitation_blocked_result(
                tool_name,
                result,
                reason="elicitation_disabled",
            )

        request = build_elicitation_request(
            tool_name,
            result.issues,
            tool_schema,
            self.tool_configs.get(tool_name),
        )
        fields = [request_field.name for request_field in request.fields]
        if not fields or request.response_model is None:
            return self._unsupported_elicitation_result(tool_name, result, fields)

        elicit = getattr(context.fastmcp_context, "elicit", None)
        if not callable(elicit) or not _client_supports_elicitation(
            context.fastmcp_context
        ):
            return self._unsupported_elicitation_result(tool_name, result, fields)

        try:
            response = await elicit(request.message, request.response_model)
        except Exception:
            logger.warning(
                "Elicitation failed for tool %r; returning structured fallback.",
                tool_name,
                exc_info=True,
            )
            return self._elicitation_blocked_result(
                tool_name,
                result,
                reason="elicitation_failed",
                fields=fields,
            )

        action = getattr(response, "action", None)
        if action != "accept":
            return self._elicitation_blocked_result(
                tool_name,
                result,
                reason=_reason_for_elicitation_action(action),
                fields=fields,
            )

        values = _accepted_values(response)
        if values is None:
            return self._elicitation_blocked_result(
                tool_name,
                result,
                reason="elicitation_failed",
                fields=fields,
            )

        updated_arguments = merge_elicited_values(
            arguments,
            values,
            fields,
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

    def _elicitation_blocked_result(
        self,
        tool_name: str,
        result: InspectionResult,
        *,
        reason: str,
        fields: list[str] | None = None,
    ) -> ToolResult:
        return self._fallback_payload_result(
            build_elicitation_blocked_payload(
                tool_name,
                reason=reason,
                fields=fields if fields is not None else _fields_for(result),
            )
        )

    def _unsupported_elicitation_result(
        self,
        tool_name: str,
        result: InspectionResult,
        fields: list[str],
    ) -> ToolResult:
        if self.elicitation.fallback_on_unsupported == "structured_error":
            return self._elicitation_blocked_result(
                tool_name,
                result,
                reason="elicitation_unsupported",
                fields=fields,
            )

        return self._elicitation_blocked_result(
            tool_name,
            result,
            reason="elicitation_failed",
            fields=fields,
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


def _fields_for(result: InspectionResult) -> list[str]:
    return [issue.field for issue in result.issues if issue.field is not None]


def _reason_for_elicitation_action(action: object) -> str:
    if action == "decline":
        return "elicitation_declined"
    if action == "cancel":
        return "elicitation_cancelled"
    return "elicitation_failed"


def _accepted_values(response: Any) -> dict[str, Any] | None:
    data = getattr(response, "data", None)
    if data is None:
        data = getattr(response, "content", None)

    model_dump = getattr(data, "model_dump", None)
    if callable(model_dump):
        return model_dump(by_alias=True)

    if isinstance(data, dict):
        return dict(data)

    return None


def _client_supports_elicitation(context: Any) -> bool:
    session = getattr(context, "session", None)
    check_client_capability = getattr(session, "check_client_capability", None)
    if not callable(check_client_capability):
        return True

    return bool(
        check_client_capability(
            mt.ClientCapabilities(elicitation=mt.ElicitationCapability())
        )
    )

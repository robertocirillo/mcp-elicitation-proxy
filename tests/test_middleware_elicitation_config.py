from __future__ import annotations

from typing import Any

import mcp.types as mt
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.tools.base import ToolResult

from mcp_elicitation_proxy.config import ElicitationConfig, ToolPolicyConfig
from mcp_elicitation_proxy.middleware import ElicitationMiddleware
from mcp_elicitation_proxy.pipeline import ElicitationPipeline
from mcp_elicitation_proxy.policies.schema_required import SchemaRequiredPolicy
from tests.conftest import _call_result_data
from tests.test_elicitation_middleware import (
    _ElicitResponse,
    _FastMCPContext,
    _schema,
)


def _middleware(
    *,
    elicitation: ElicitationConfig | None = None,
    tool_configs: dict[str, ToolPolicyConfig] | None = None,
) -> ElicitationMiddleware:
    return ElicitationMiddleware(
        ElicitationPipeline([SchemaRequiredPolicy()]),
        elicitation=elicitation or ElicitationConfig(),
        tool_configs=tool_configs or {},
    )


def _context(
    arguments: dict[str, Any],
    fastmcp_context: Any,
) -> MiddlewareContext[mt.CallToolRequestParams]:
    return MiddlewareContext(
        message=mt.CallToolRequestParams(name="search_docs", arguments=arguments),
        source="client",
        type="request",
        method="tools/call",
        fastmcp_context=fastmcp_context,
    )


async def test_elicitation_disabled_returns_structured_error_without_calling_ctx_elicit() -> None:
    middleware = _middleware(elicitation=ElicitationConfig(enabled=False))
    fastmcp_context = _FastMCPContext(_schema(required=["ticket_id", "project"]))
    call_next_calls = 0

    async def call_next(
        context: MiddlewareContext[mt.CallToolRequestParams],
    ) -> ToolResult:
        nonlocal call_next_calls
        call_next_calls += 1
        return ToolResult(structured_content={"forwarded": context.message.name})

    result = await middleware.on_call_tool(
        _context({"ticket_id": "OPS-123"}, fastmcp_context),
        call_next,
    )

    payload = _call_result_data(result)
    assert fastmcp_context.elicit_calls == 0
    assert call_next_calls == 0
    assert payload == {
        "error": "elicitation_required",
        "tool": "search_docs",
        "status": "needs_elicitation",
        "reason": "elicitation_disabled",
        "missing_or_ambiguous": ["project"],
        "message": "Input incompleto. Richiama il tool specificando i campi mancanti.",
    }


async def test_elicitation_enabled_uses_tool_specific_message() -> None:
    middleware = _middleware(
        tool_configs={
            "search_docs": ToolPolicyConfig(
                elicit={"message": "In quale progetto devo cercare?"}
            )
        }
    )
    fastmcp_context = _FastMCPContext(
        _schema(required=["ticket_id", "project"]),
        elicit_response=_ElicitResponse(data={"project": "ops"}),
    )

    async def call_next(
        context: MiddlewareContext[mt.CallToolRequestParams],
    ) -> ToolResult:
        return ToolResult(structured_content={"arguments": context.message.arguments})

    await middleware.on_call_tool(
        _context({"ticket_id": "OPS-123"}, fastmcp_context),
        call_next,
    )

    assert fastmcp_context.elicit_messages == ["In quale progetto devo cercare?"]


async def test_elicitation_enabled_uses_tool_specific_fields() -> None:
    middleware = _middleware(
        tool_configs={
            "search_docs": ToolPolicyConfig(
                elicit={
                    "fields": {
                        "project": {
                            "type": "string",
                            "description": "Progetto o scope in cui cercare",
                        }
                    }
                }
            )
        }
    )
    fastmcp_context = _FastMCPContext(
        _schema(required=["ticket_id", "project"]),
        elicit_response=_ElicitResponse(data={"project": "ops"}),
    )

    async def call_next(
        context: MiddlewareContext[mt.CallToolRequestParams],
    ) -> ToolResult:
        return ToolResult(structured_content={"arguments": context.message.arguments})

    await middleware.on_call_tool(
        _context({"ticket_id": "OPS-123"}, fastmcp_context),
        call_next,
    )

    requested_schema = fastmcp_context.elicit_response_types[0].model_json_schema()
    assert requested_schema["properties"]["project"]["type"] == "string"
    assert (
        requested_schema["properties"]["project"]["description"]
        == "Progetto o scope in cui cercare"
    )


async def test_elicitation_declined_returns_structured_error_without_call_next() -> None:
    payload, call_next_calls = await _blocked_elicitation_payload(
        _ElicitResponse(action="decline")
    )

    assert call_next_calls == 0
    assert payload["reason"] == "elicitation_declined"


async def test_elicitation_cancelled_returns_structured_error_without_call_next() -> None:
    payload, call_next_calls = await _blocked_elicitation_payload(
        _ElicitResponse(action="cancel")
    )

    assert call_next_calls == 0
    assert payload["reason"] == "elicitation_cancelled"


async def test_elicitation_exception_returns_structured_error_without_call_next() -> None:
    middleware = _middleware()
    fastmcp_context = _FastMCPContext(
        _schema(required=["ticket_id", "project"]),
        elicit_error=RuntimeError("client failed elicitation"),
    )
    call_next_calls = 0

    async def call_next(
        context: MiddlewareContext[mt.CallToolRequestParams],
    ) -> ToolResult:
        nonlocal call_next_calls
        call_next_calls += 1
        return ToolResult(structured_content={"forwarded": context.message.name})

    result = await middleware.on_call_tool(
        _context({"ticket_id": "OPS-123"}, fastmcp_context),
        call_next,
    )

    payload = _call_result_data(result)
    assert call_next_calls == 0
    assert payload["error"] == "elicitation_required"
    assert payload["status"] == "needs_elicitation"
    assert payload["reason"] == "elicitation_failed"


async def test_elicitation_accept_merges_only_requested_fields_and_calls_next_once() -> None:
    middleware = _middleware()
    original_arguments = {"ticket_id": "OPS-123", "query": "keep me"}
    fastmcp_context = _FastMCPContext(
        _schema(required=["ticket_id", "project"]),
        elicit_response=_ElicitResponse(
            data={"project": "ops", "query": "do not merge"}
        ),
    )
    call_next_calls = 0
    forwarded_arguments: dict[str, Any] | None = None

    async def call_next(
        context: MiddlewareContext[mt.CallToolRequestParams],
    ) -> ToolResult:
        nonlocal call_next_calls, forwarded_arguments
        call_next_calls += 1
        forwarded_arguments = context.message.arguments
        return ToolResult(structured_content={"arguments": context.message.arguments})

    result = await middleware.on_call_tool(
        _context(original_arguments, fastmcp_context),
        call_next,
    )

    payload = _call_result_data(result)
    assert call_next_calls == 1
    assert payload["arguments"] == {
        "ticket_id": "OPS-123",
        "query": "keep me",
        "project": "ops",
    }
    assert forwarded_arguments == payload["arguments"]
    assert original_arguments == {"ticket_id": "OPS-123", "query": "keep me"}


async def _blocked_elicitation_payload(response: object) -> tuple[dict[str, Any], int]:
    middleware = _middleware()
    fastmcp_context = _FastMCPContext(
        _schema(required=["ticket_id", "project"]),
        elicit_response=response,
    )
    call_next_calls = 0

    async def call_next(
        context: MiddlewareContext[mt.CallToolRequestParams],
    ) -> ToolResult:
        nonlocal call_next_calls
        call_next_calls += 1
        return ToolResult(structured_content={"forwarded": context.message.name})

    result = await middleware.on_call_tool(
        _context({"ticket_id": "OPS-123"}, fastmcp_context),
        call_next,
    )

    return _call_result_data(result), call_next_calls

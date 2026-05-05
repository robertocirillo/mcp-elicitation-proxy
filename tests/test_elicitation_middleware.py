from __future__ import annotations

import logging
from typing import Any

import mcp.types as mt
import pytest
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.tools.base import ToolResult

from mcp_elicitation_proxy.middleware import ElicitationMiddleware
from mcp_elicitation_proxy.pipeline import ElicitationPipeline
from mcp_elicitation_proxy.policies.schema_required import SchemaRequiredPolicy
from tests.conftest import _call_result_data


class _Tool:
    def __init__(self, parameters: dict[str, Any]) -> None:
        self.parameters = parameters


class _FastMCP:
    def __init__(
        self,
        schema: dict[str, Any] | None,
        *,
        fail_schema_lookup: bool = False,
    ) -> None:
        self._schema = schema
        self._fail_schema_lookup = fail_schema_lookup

    async def get_tool(self, name: str) -> _Tool | None:
        if self._fail_schema_lookup:
            raise RuntimeError("schema lookup failed")
        if self._schema is None:
            return None
        return _Tool(self._schema)


class _FastMCPContext:
    def __init__(
        self,
        schema: dict[str, Any] | None,
        *,
        fail_schema_lookup: bool = False,
    ) -> None:
        self.fastmcp = _FastMCP(schema, fail_schema_lookup=fail_schema_lookup)
        self.elicit_calls = 0

    async def elicit(self, *args: Any, **kwargs: Any) -> None:
        self.elicit_calls += 1


def _schema(required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string"},
            "project": {"type": "string"},
        },
        "required": required,
    }


def _middleware() -> ElicitationMiddleware:
    return ElicitationMiddleware(ElicitationPipeline([SchemaRequiredPolicy()]))


def _context(
    tool_name: str,
    arguments: dict[str, Any],
    fastmcp_context: _FastMCPContext | None,
) -> MiddlewareContext[mt.CallToolRequestParams]:
    return MiddlewareContext(
        message=mt.CallToolRequestParams(name=tool_name, arguments=arguments),
        source="client",
        type="request",
        method="tools/call",
        fastmcp_context=fastmcp_context,
    )


async def test_middleware_blocks_incomplete_generic_tool_call_without_call_next() -> None:
    middleware = _middleware()
    fastmcp_context = _FastMCPContext(_schema(required=["ticket_id", "project"]))
    call_next_calls = 0

    async def call_next(
        context: MiddlewareContext[mt.CallToolRequestParams],
    ) -> ToolResult:
        nonlocal call_next_calls
        call_next_calls += 1
        return ToolResult(structured_content={"forwarded": context.message.name})

    result = await middleware.on_call_tool(
        _context(
            "lookup_ticket",
            {"ticket_id": "OPS-123"},
            fastmcp_context,
        ),
        call_next,
    )

    assert isinstance(result, ToolResult)
    payload = _call_result_data(result)
    assert call_next_calls == 0
    assert fastmcp_context.elicit_calls == 0
    assert payload["error"] == "tool_call_blocked"
    assert payload["tool"] == "lookup_ticket"
    assert payload["status"] == "needs_elicitation"
    assert payload["reason"] == "required_fields_missing_or_empty"
    assert payload["missing_or_ambiguous"] == ["project"]
    assert "project" in payload["message"]


async def test_middleware_forwards_complete_generic_tool_call() -> None:
    middleware = _middleware()
    fastmcp_context = _FastMCPContext(_schema(required=["ticket_id", "project"]))
    call_next_calls = 0

    async def call_next(
        context: MiddlewareContext[mt.CallToolRequestParams],
    ) -> ToolResult:
        nonlocal call_next_calls
        call_next_calls += 1
        return ToolResult(
            structured_content={
                "tool": context.message.name,
                "arguments": context.message.arguments,
            }
        )

    result = await middleware.on_call_tool(
        _context(
            "lookup_ticket",
            {"ticket_id": "OPS-123", "project": "ops"},
            fastmcp_context,
        ),
        call_next,
    )

    payload = _call_result_data(result)
    assert call_next_calls == 1
    assert fastmcp_context.elicit_calls == 0
    assert payload == {
        "tool": "lookup_ticket",
        "arguments": {"ticket_id": "OPS-123", "project": "ops"},
    }


async def test_middleware_does_not_block_when_schema_is_unavailable() -> None:
    middleware = _middleware()
    fastmcp_context = _FastMCPContext(None)

    async def call_next(
        context: MiddlewareContext[mt.CallToolRequestParams],
    ) -> ToolResult:
        return ToolResult(structured_content={"forwarded": context.message.name})

    result = await middleware.on_call_tool(
        _context("lookup_ticket", {"ticket_id": "OPS-123"}, fastmcp_context),
        call_next,
    )

    assert _call_result_data(result) == {"forwarded": "lookup_ticket"}


async def test_middleware_logs_schema_lookup_failure_and_forwards(
    caplog: pytest.LogCaptureFixture,
) -> None:
    middleware = _middleware()
    fastmcp_context = _FastMCPContext(None, fail_schema_lookup=True)
    call_next_calls = 0

    async def call_next(
        context: MiddlewareContext[mt.CallToolRequestParams],
    ) -> ToolResult:
        nonlocal call_next_calls
        call_next_calls += 1
        return ToolResult(structured_content={"forwarded": context.message.name})

    with caplog.at_level(logging.WARNING, logger="mcp_elicitation_proxy.middleware"):
        result = await middleware.on_call_tool(
            _context(
                "lookup_ticket",
                {"ticket_id": "OPS-123", "token": "secret-token"},
                fastmcp_context,
            ),
            call_next,
        )

    assert call_next_calls == 1
    assert _call_result_data(result) == {"forwarded": "lookup_ticket"}
    assert "Failed to resolve tool schema for tool 'lookup_ticket'" in caplog.text
    assert "secret-token" not in caplog.text


@pytest.mark.parametrize("wrapper_name", ["call_upstream_tool", "call_tool", "proxy_call"])
async def test_middleware_tests_do_not_register_generic_wrapper_tools(
    proxy_client,
    wrapper_name: str,
) -> None:
    tools = await proxy_client.list_tools()

    assert wrapper_name not in {tool.name for tool in tools}

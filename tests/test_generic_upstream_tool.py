from __future__ import annotations

from tests.conftest import (
    UPSTREAM_TICKET_TOOL_DESCRIPTION,
    _call_result_data,
    _tool_schema,
)


async def test_lookup_ticket_discovery_exposes_only_upstream_tool(
    ticket_proxy_client,
) -> None:
    tools = await ticket_proxy_client.list_tools()
    tool_names = {tool.name for tool in tools}

    assert tool_names == {"lookup_ticket"}
    assert "call_upstream_tool" not in tool_names
    assert "call_tool" not in tool_names
    assert "proxy_call" not in tool_names

    lookup_ticket_tool = next(tool for tool in tools if tool.name == "lookup_ticket")
    assert lookup_ticket_tool.description == UPSTREAM_TICKET_TOOL_DESCRIPTION

    schema = _tool_schema(lookup_ticket_tool)
    assert set(schema["properties"]) >= {"ticket_id", "project"}
    assert set(schema.get("required", [])) >= {"ticket_id", "project"}


async def test_lookup_ticket_complete_input_reaches_upstream(ticket_proxy_client) -> None:
    result = await ticket_proxy_client.call_tool(
        "lookup_ticket",
        {"ticket_id": "SUP-123", "project": "support"},
    )

    payload = _call_result_data(result)
    assert payload == {
        "ticket_id": "SUP-123",
        "project": "support",
        "status": "open",
        "summary": "support: SUP-123",
    }


async def test_lookup_ticket_incomplete_input_returns_structured_fallback(
    ticket_proxy_client,
) -> None:
    result = await ticket_proxy_client.call_tool(
        "lookup_ticket",
        {"ticket_id": "SUP-123"},
    )

    payload = _call_result_data(result)
    assert payload["error"] == "tool_call_blocked"
    assert payload["tool"] == "lookup_ticket"
    assert payload["status"] == "needs_elicitation"
    assert payload["reason"] == "required_fields_missing_or_empty"
    assert payload["missing_or_ambiguous"] == ["project"]
    assert "project" in payload["message"]

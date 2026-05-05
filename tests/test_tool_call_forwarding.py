from __future__ import annotations

from tests.conftest import _call_result_data


async def test_tool_call_is_forwarded_to_upstream(proxy_client) -> None:
    arguments = {
        "query": "release notes mcp-bridge 0.2.0",
        "project": "mcp-bridge",
    }

    result = await proxy_client.call_tool("search_docs", arguments)
    payload = _call_result_data(result)

    assert payload["query"] == arguments["query"]
    assert payload["project"] == arguments["project"]
    assert payload["results"]
    assert payload["results"][0] == "mcp-bridge: release notes mcp-bridge 0.2.0"


async def test_incomplete_tool_call_returns_structured_fallback(proxy_client) -> None:
    result = await proxy_client.call_tool(
        "search_docs",
        {"query": "release notes mcp-bridge 0.2.0"},
    )

    payload = _call_result_data(result)
    assert payload["error"] == "elicitation_required"
    assert payload["tool"] == "search_docs"
    assert payload["status"] == "needs_elicitation"
    assert payload["reason"] == "elicitation_unsupported"
    assert payload["missing_or_ambiguous"] == ["project"]
    assert payload["message"]

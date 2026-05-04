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

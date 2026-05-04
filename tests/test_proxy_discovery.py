from __future__ import annotations

from tests.conftest import UPSTREAM_TOOL_DESCRIPTION, _tool_schema


async def test_proxy_exposes_upstream_tool_without_generic_wrappers(proxy_client) -> None:
    tools = await proxy_client.list_tools()
    tool_names = {tool.name for tool in tools}

    assert "search_docs" in tool_names
    assert "call_upstream_tool" not in tool_names
    assert "call_tool" not in tool_names
    assert "proxy_call" not in tool_names
    assert tool_names == {"search_docs"}

    search_docs_tool = next(tool for tool in tools if tool.name == "search_docs")
    assert search_docs_tool.description == UPSTREAM_TOOL_DESCRIPTION

    schema = _tool_schema(search_docs_tool)
    assert schema
    assert set(schema["properties"]) >= {"query", "project"}
    assert set(schema.get("required", [])) >= {"query", "project"}

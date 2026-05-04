from __future__ import annotations

from mcp_elicitation_proxy.pipeline import ElicitationPipeline
from mcp_elicitation_proxy.policies.base import InspectionStatus
from tests.conftest import _call_result_data


async def test_empty_pipeline_returns_ok() -> None:
    pipeline = ElicitationPipeline([])

    result = await pipeline.inspect(
        tool_name="search_docs",
        arguments={"query": "x", "project": "y"},
        tool_schema={"type": "object"},
        context=None,
    )

    assert result.status == InspectionStatus.OK
    assert result.issues == []
    assert result.updated_arguments is None


async def test_complete_arguments_reach_upstream_without_elicitation(proxy_client) -> None:
    result = await proxy_client.call_tool(
        "search_docs",
        {"query": "api auth flow", "project": "mcp-bridge"},
    )

    payload = _call_result_data(result)
    assert payload["query"] == "api auth flow"
    assert payload["project"] == "mcp-bridge"

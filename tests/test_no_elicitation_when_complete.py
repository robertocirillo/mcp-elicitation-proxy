from __future__ import annotations

from typing import Any

from mcp_elicitation_proxy.pipeline import ElicitationPipeline
from mcp_elicitation_proxy.policies.base import (
    InspectionIssue,
    InspectionResult,
    InspectionStatus,
)
from mcp_elicitation_proxy.policies.schema_required import SchemaRequiredPolicy
from tests.conftest import _call_result_data


class _StaticPolicy:
    def __init__(self, result: InspectionResult) -> None:
        self._result = result

    async def inspect(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_schema: dict[str, Any] | None,
        context: Any,
    ) -> InspectionResult:
        return self._result


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


async def test_pipeline_returns_schema_required_policy_result() -> None:
    pipeline = ElicitationPipeline([SchemaRequiredPolicy()])
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "project": {"type": "string"},
        },
        "required": ["query", "project"],
    }

    result = await pipeline.inspect(
        tool_name="search_docs",
        arguments={"query": "api auth flow"},
        tool_schema=schema,
        context=None,
    )

    assert result.status == InspectionStatus.NEEDS_ELICITATION
    assert [(issue.field, issue.reason) for issue in result.issues] == [
        ("project", "missing_required_field")
    ]

    complete_result = await pipeline.inspect(
        tool_name="search_docs",
        arguments={"query": "api auth flow", "project": "mcp-bridge"},
        tool_schema=schema,
        context=None,
    )

    assert complete_result.status == InspectionStatus.OK
    assert complete_result.issues == []


async def test_pipeline_returns_first_non_ok_policy_result() -> None:
    first_issue = InspectionIssue(
        field="query",
        reason="missing_required_field",
        message="Required field 'query' is missing.",
    )
    second_issue = InspectionIssue(
        field="scope",
        reason="ambiguous_scope",
        message="Scope is ambiguous.",
    )
    pipeline = ElicitationPipeline(
        [
            _StaticPolicy(InspectionResult.ok()),
            _StaticPolicy(InspectionResult.needs_elicitation([first_issue])),
            _StaticPolicy(InspectionResult.confirm([second_issue])),
        ]
    )

    result = await pipeline.inspect(
        tool_name="search_docs",
        arguments={},
        tool_schema={"type": "object"},
        context=None,
    )

    assert result.status == InspectionStatus.NEEDS_ELICITATION
    assert result.issues == [first_issue]


async def test_complete_arguments_reach_upstream_without_elicitation(proxy_client) -> None:
    result = await proxy_client.call_tool(
        "search_docs",
        {"query": "api auth flow", "project": "mcp-bridge"},
    )

    payload = _call_result_data(result)
    assert payload["query"] == "api auth flow"
    assert payload["project"] == "mcp-bridge"

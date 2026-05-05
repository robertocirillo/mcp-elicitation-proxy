from __future__ import annotations

from typing import Any

from mcp_elicitation_proxy.config import AppConfig
from mcp_elicitation_proxy.pipeline import build_pipeline
from mcp_elicitation_proxy.policies.base import InspectionStatus


def _config(raw: dict[str, Any] | None = None) -> AppConfig:
    return AppConfig.model_validate(
        {
            "upstream": {"url": "http://localhost:8001/mcp"},
            **(raw or {}),
        }
    )


async def test_configured_required_fields_trigger_elicitation() -> None:
    pipeline = build_pipeline(
        _config({"tools": {"search_docs": {"required": ["project"]}}})
    )

    result = await pipeline.inspect(
        "search_docs",
        arguments={"query": "docs"},
        tool_schema=None,
    )

    assert result.status == InspectionStatus.NEEDS_ELICITATION
    assert [(issue.field, issue.reason) for issue in result.issues] == [
        ("project", "missing_required_field")
    ]


async def test_schema_and_config_required_fields_are_combined_in_order() -> None:
    pipeline = build_pipeline(
        _config(
            {
                "tools": {
                    "search_docs": {"required": ["project", "query", "scope"]}
                }
            }
        )
    )

    result = await pipeline.inspect(
        "search_docs",
        arguments={},
        tool_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "project": {"type": "string"},
                "scope": {"type": "string"},
            },
            "required": ["query"],
        },
    )

    assert result.status == InspectionStatus.NEEDS_ELICITATION
    assert [issue.field for issue in result.issues] == ["query", "project", "scope"]


async def test_schema_required_policy_can_be_disabled() -> None:
    pipeline = build_pipeline(
        _config(
            {
                "policies": {"schema_required": {"enabled": False}},
                "tools": {"search_docs": {"required": ["project"]}},
            }
        )
    )

    result = await pipeline.inspect(
        "search_docs",
        arguments={"query": "docs"},
        tool_schema={"type": "object", "required": ["query", "project"]},
    )

    assert result.status == InspectionStatus.OK
    assert result.issues == []


async def test_sensitive_policy_runs_before_schema_required() -> None:
    pipeline = build_pipeline(
        _config({"tools": {"sync_repository": {"required": ["api_key"]}}})
    )

    result = await pipeline.inspect(
        "sync_repository",
        arguments={"query": "release notes"},
        tool_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "api_key": {"type": "string"},
            },
        },
    )

    assert result.status == InspectionStatus.REJECT
    assert [(issue.field, issue.reason) for issue in result.issues] == [
        ("api_key", "sensitive_required_field")
    ]


async def test_sensitive_policy_can_be_disabled() -> None:
    pipeline = build_pipeline(
        _config(
            {
                "policies": {"sensitive_required": {"enabled": False}},
                "tools": {"sync_repository": {"required": ["api_key"]}},
            }
        )
    )

    result = await pipeline.inspect(
        "sync_repository",
        arguments={"query": "release notes"},
        tool_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "api_key": {"type": "string"},
            },
        },
    )

    assert result.status == InspectionStatus.NEEDS_ELICITATION
    assert [(issue.field, issue.reason) for issue in result.issues] == [
        ("api_key", "missing_required_field")
    ]

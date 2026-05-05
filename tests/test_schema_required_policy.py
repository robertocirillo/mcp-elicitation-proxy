from __future__ import annotations

from typing import Any

from mcp_elicitation_proxy.policies.base import InspectionStatus
from mcp_elicitation_proxy.policies.schema_required import SchemaRequiredPolicy


def _schema(required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "project": {"type": "string"},
            "scope": {"type": "string"},
            "tags": {"type": "array"},
            "metadata": {"type": "object"},
            "include_archived": {"type": "boolean"},
            "limit": {"type": "integer"},
        },
    }
    if required is not None:
        schema["required"] = required
    return schema


async def _inspect(
    arguments: dict[str, Any],
    tool_schema: dict[str, Any] | None,
) -> Any:
    return await SchemaRequiredPolicy().inspect(
        tool_name="any_tool",
        arguments=arguments,
        tool_schema=tool_schema,
        context=None,
    )


async def test_returns_ok_without_schema() -> None:
    result = await _inspect({"query": "x"}, None)

    assert result.status == InspectionStatus.OK
    assert result.issues == []


async def test_returns_ok_without_required_fields() -> None:
    result = await _inspect({}, _schema())

    assert result.status == InspectionStatus.OK
    assert result.issues == []


async def test_returns_ok_when_required_fields_are_present() -> None:
    result = await _inspect(
        {"query": "api auth flow", "project": "mcp-bridge"},
        _schema(required=["query", "project"]),
    )

    assert result.status == InspectionStatus.OK
    assert result.issues == []


async def test_detects_missing_required_field() -> None:
    result = await _inspect(
        {"query": "api auth flow"},
        _schema(required=["query", "project"]),
    )

    assert result.status == InspectionStatus.NEEDS_ELICITATION
    assert len(result.issues) == 1
    assert result.issues[0].field == "project"
    assert result.issues[0].reason == "missing_required_field"
    assert result.issues[0].message == "Required field 'project' is missing."


async def test_detects_empty_string_required_field() -> None:
    result = await _inspect(
        {"query": "", "project": "mcp-bridge"},
        _schema(required=["query", "project"]),
    )

    assert result.status == InspectionStatus.NEEDS_ELICITATION
    assert len(result.issues) == 1
    assert result.issues[0].field == "query"
    assert result.issues[0].reason == "empty_required_field"


async def test_detects_whitespace_required_field() -> None:
    result = await _inspect(
        {"query": "   ", "project": "mcp-bridge"},
        _schema(required=["query", "project"]),
    )

    assert result.status == InspectionStatus.NEEDS_ELICITATION
    assert len(result.issues) == 1
    assert result.issues[0].field == "query"
    assert result.issues[0].reason == "empty_required_field"


async def test_detects_none_required_field() -> None:
    result = await _inspect(
        {"query": "api auth flow", "project": None},
        _schema(required=["query", "project"]),
    )

    assert result.status == InspectionStatus.NEEDS_ELICITATION
    assert len(result.issues) == 1
    assert result.issues[0].field == "project"
    assert result.issues[0].reason == "empty_required_field"


async def test_detects_empty_list_and_empty_dict() -> None:
    result = await _inspect(
        {"tags": [], "metadata": {}},
        _schema(required=["tags", "metadata"]),
    )

    assert result.status == InspectionStatus.NEEDS_ELICITATION
    assert [(issue.field, issue.reason) for issue in result.issues] == [
        ("tags", "empty_required_field"),
        ("metadata", "empty_required_field"),
    ]


async def test_does_not_treat_non_empty_list_or_dict_as_empty() -> None:
    result = await _inspect(
        {"tags": ["release"], "metadata": {"owner": "docs"}},
        _schema(required=["tags", "metadata"]),
    )

    assert result.status == InspectionStatus.OK
    assert result.issues == []


async def test_does_not_treat_false_or_zero_as_empty() -> None:
    result = await _inspect(
        {"include_archived": False, "limit": 0},
        _schema(required=["include_archived", "limit"]),
    )

    assert result.status == InspectionStatus.OK
    assert result.issues == []


async def test_reports_multiple_issues_in_required_order() -> None:
    result = await _inspect({}, _schema(required=["query", "project", "scope"]))

    assert result.status == InspectionStatus.NEEDS_ELICITATION
    assert [(issue.field, issue.reason) for issue in result.issues] == [
        ("query", "missing_required_field"),
        ("project", "missing_required_field"),
        ("scope", "missing_required_field"),
    ]


async def test_returns_ok_when_required_is_not_a_list() -> None:
    result = await _inspect({}, {"type": "object", "required": "query"})

    assert result.status == InspectionStatus.OK
    assert result.issues == []


async def test_does_not_mutate_arguments() -> None:
    arguments = {"query": "api auth flow"}

    await _inspect(arguments, _schema(required=["query", "project"]))

    assert arguments == {"query": "api auth flow"}

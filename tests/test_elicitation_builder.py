from __future__ import annotations

from mcp_elicitation_proxy.config import ToolPolicyConfig
from mcp_elicitation_proxy.elicitation.builder import build_elicitation_request
from mcp_elicitation_proxy.policies.base import InspectionIssue


def _issue(field: str) -> InspectionIssue:
    return InspectionIssue(
        field=field,
        reason="missing_required_field",
        message=f"Required field '{field}' is missing.",
    )


def test_builder_uses_tool_specific_message() -> None:
    request = build_elicitation_request(
        "search_docs",
        [_issue("project")],
        tool_config=ToolPolicyConfig(
            elicit={"message": "In quale progetto devo cercare?"}
        ),
    )

    assert request.message == "In quale progetto devo cercare?"


def test_builder_uses_default_message_without_config() -> None:
    request = build_elicitation_request("search_docs", [_issue("project")])

    assert "search_docs" in request.message
    assert request.message == (
        "Input for tool 'search_docs' is incomplete. "
        "Please provide the missing fields."
    )


def test_builder_uses_configured_field_description_and_type() -> None:
    request = build_elicitation_request(
        "search_docs",
        [_issue("project")],
        tool_config=ToolPolicyConfig(
            elicit={
                "fields": {
                    "project": {
                        "type": "integer",
                        "description": "Progetto o scope in cui cercare",
                    }
                }
            }
        ),
    )

    assert len(request.fields) == 1
    assert request.fields[0].type == "integer"
    assert request.fields[0].description == "Progetto o scope in cui cercare"


def test_builder_only_includes_issue_fields() -> None:
    request = build_elicitation_request(
        "search_docs",
        [_issue("project")],
        tool_config=ToolPolicyConfig(
            elicit={
                "fields": {
                    "query": {
                        "type": "string",
                        "description": "Query completa",
                    },
                    "project": {
                        "type": "string",
                        "description": "Progetto o scope in cui cercare",
                    },
                }
            }
        ),
    )

    assert [field.name for field in request.fields] == ["project"]


def test_builder_preserves_issue_order() -> None:
    request = build_elicitation_request(
        "search_docs",
        [_issue("project"), _issue("query")],
    )

    assert [field.name for field in request.fields] == ["project", "query"]

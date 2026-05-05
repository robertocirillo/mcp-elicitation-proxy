from __future__ import annotations

import keyword
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, Field, create_model

from .models import ElicitationField, ElicitationRequest
from ..config import ToolElicitFieldConfig, ToolPolicyConfig
from ..policies.base import InspectionIssue


PRIMITIVE_JSON_TYPES = {"string", "integer", "number", "boolean"}


def build_elicitation_request(
    tool_name: str,
    issues: Iterable[InspectionIssue],
    tool_schema: dict[str, Any] | None = None,
    tool_config: ToolPolicyConfig | None = None,
) -> ElicitationRequest:
    issue_list = _issues_with_fields(issues)
    fields = [
        _field_for_issue(issue, tool_schema, _configured_field(issue, tool_config))
        for issue in issue_list
    ]
    return ElicitationRequest(
        message=_message_for(tool_name, tool_config),
        fields=fields,
        response_model=_response_model_for(tool_name, issue_list, tool_schema, tool_config),
    )


def _issues_with_fields(
    issues: Iterable[InspectionIssue],
) -> list[InspectionIssue]:
    result: list[InspectionIssue] = []
    seen: set[str] = set()
    for issue in issues:
        if issue.field is None or issue.field in seen:
            continue
        result.append(issue)
        seen.add(issue.field)
    return result


def _field_for_issue(
    issue: InspectionIssue,
    tool_schema: dict[str, Any] | None,
    field_config: ToolElicitFieldConfig | None,
) -> ElicitationField:
    field_schema = _field_schema(issue.field, tool_schema)
    field_type = _configured_type(field_config) or _elicitation_json_type(field_schema)
    return ElicitationField(
        name=issue.field or "",
        type=field_type,
        description=_configured_description(issue, field_config),
        required=True,
    )


def _response_model_for(
    tool_name: str,
    issues: list[InspectionIssue],
    tool_schema: dict[str, Any] | None,
    tool_config: ToolPolicyConfig | None,
) -> type[BaseModel] | None:
    if not issues:
        return None

    used_model_fields: set[str] = set()
    model_fields: dict[str, tuple[type[Any], Any]] = {}
    for index, issue in enumerate(issues, start=1):
        if issue.field is None:
            continue
        model_field_name = _model_field_name(issue.field, index, used_model_fields)
        used_model_fields.add(model_field_name)
        field_schema = _field_schema(issue.field, tool_schema)
        field_config = _configured_field(issue, tool_config)
        model_fields[model_field_name] = (
            _configured_python_type(field_config) or _python_type(field_schema),
            Field(
                ...,
                alias=issue.field,
                description=_configured_description(issue, field_config),
            ),
        )

    if not model_fields:
        return None

    model_name = f"{_model_identifier(tool_name)}ElicitationResponse"
    return create_model(model_name, **model_fields)


def _field_schema(
    field_name: str | None,
    tool_schema: dict[str, Any] | None,
) -> dict[str, Any]:
    if field_name is None or tool_schema is None:
        return {}

    properties = tool_schema.get("properties")
    if not isinstance(properties, dict):
        return {}

    field_schema = properties.get(field_name)
    if isinstance(field_schema, dict):
        return field_schema
    return {}


def _elicitation_json_type(field_schema: dict[str, Any]) -> str:
    schema_type = _schema_type(field_schema)
    if schema_type in PRIMITIVE_JSON_TYPES:
        return schema_type
    return "string"


def _python_type(field_schema: dict[str, Any]) -> type[Any]:
    schema_type = _schema_type(field_schema)
    if schema_type == "integer":
        return int
    if schema_type == "number":
        return float
    if schema_type == "boolean":
        return bool
    return str


def _schema_type(field_schema: dict[str, Any]) -> str | None:
    schema_type = field_schema.get("type")
    if isinstance(schema_type, str):
        return schema_type
    if isinstance(schema_type, list):
        non_null_types = [item for item in schema_type if item != "null"]
        if len(non_null_types) == 1 and isinstance(non_null_types[0], str):
            return non_null_types[0]
    return None


def _model_field_name(
    field_name: str,
    index: int,
    used_model_fields: set[str],
) -> str:
    if field_name.isidentifier() and not keyword.iskeyword(field_name):
        candidate = field_name
    else:
        candidate = f"field_{index}"

    while candidate in used_model_fields:
        candidate = f"{candidate}_{index}"
    return candidate


def _model_identifier(tool_name: str) -> str:
    parts = [
        part.capitalize()
        for part in "".join(
            character if character.isalnum() else " " for character in tool_name
        ).split()
    ]
    return "".join(parts) or "Tool"


def _message_for(tool_name: str, tool_config: ToolPolicyConfig | None) -> str:
    if tool_config is not None and tool_config.elicit is not None:
        if tool_config.elicit.message:
            return tool_config.elicit.message
    return (
        f"Input for tool '{tool_name}' is incomplete. "
        "Please provide the missing fields."
    )


def _configured_field(
    issue: InspectionIssue,
    tool_config: ToolPolicyConfig | None,
) -> ToolElicitFieldConfig | None:
    if issue.field is None or tool_config is None or tool_config.elicit is None:
        return None
    return tool_config.elicit.fields.get(issue.field)


def _configured_type(field_config: ToolElicitFieldConfig | None) -> str | None:
    if field_config is None or field_config.type not in PRIMITIVE_JSON_TYPES:
        return None
    return field_config.type


def _configured_python_type(
    field_config: ToolElicitFieldConfig | None,
) -> type[Any] | None:
    field_type = _configured_type(field_config)
    if field_type == "integer":
        return int
    if field_type == "number":
        return float
    if field_type == "boolean":
        return bool
    if field_type == "string":
        return str
    return None


def _configured_description(
    issue: InspectionIssue,
    field_config: ToolElicitFieldConfig | None,
) -> str:
    if field_config is not None and field_config.description:
        return field_config.description
    if issue.field is not None:
        return f"Value for '{issue.field}'."
    return issue.message

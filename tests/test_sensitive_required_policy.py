from __future__ import annotations

from typing import Any

from mcp_elicitation_proxy.policies.base import InspectionStatus
from mcp_elicitation_proxy.policies.sensitive_required import (
    SensitiveRequiredFieldPolicy,
    is_sensitive_field,
)


def _schema(
    *,
    properties: dict[str, dict[str, Any]],
    required: list[str] | None = None,
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required is not None:
        schema["required"] = required
    return schema


async def _inspect(
    arguments: dict[str, Any],
    tool_schema: dict[str, Any] | None,
) -> Any:
    return await SensitiveRequiredFieldPolicy().inspect(
        tool_name="any_tool",
        arguments=arguments,
        tool_schema=tool_schema,
        context=None,
    )


def test_classifies_sensitive_field_names() -> None:
    for field_name in [
        "password",
        "passphrase",
        "client_secret",
        "session_token",
        "access_token",
        "api_key",
        "apikey",
        "credential_id",
        "private_key",
        "payment_method",
        "card_number",
        "cvv",
    ]:
        assert is_sensitive_field(field_name)


def test_classifies_sensitive_schema_format_description_and_title() -> None:
    assert is_sensitive_field("auth", {"format": "password"})
    assert is_sensitive_field("auth", {"description": "OAuth access token to use."})
    assert is_sensitive_field("auth", {"title": "API key"})


def test_does_not_classify_plain_required_fields() -> None:
    assert not is_sensitive_field(
        "project",
        {"title": "Project", "description": "Project identifier."},
    )


async def test_rejects_missing_sensitive_required_field_from_name() -> None:
    result = await _inspect(
        {"query": "docs"},
        _schema(
            properties={
                "query": {"type": "string"},
                "api_key": {"type": "string"},
            },
            required=["query", "api_key"],
        ),
    )

    assert result.status == InspectionStatus.REJECT
    assert [(issue.field, issue.reason) for issue in result.issues] == [
        ("api_key", "sensitive_required_field")
    ]


async def test_rejects_missing_sensitive_required_field_from_description() -> None:
    result = await _inspect(
        {"query": "docs"},
        _schema(
            properties={
                "query": {"type": "string"},
                "auth": {
                    "type": "string",
                    "description": "Bearer token used for the upstream request.",
                },
            },
            required=["query", "auth"],
        ),
    )

    assert result.status == InspectionStatus.REJECT
    assert [(issue.field, issue.reason) for issue in result.issues] == [
        ("auth", "sensitive_required_field")
    ]


async def test_rejects_missing_sensitive_required_field_from_title() -> None:
    result = await _inspect(
        {"query": "docs"},
        _schema(
            properties={
                "query": {"type": "string"},
                "auth": {"type": "string", "title": "Private key"},
            },
            required=["query", "auth"],
        ),
    )

    assert result.status == InspectionStatus.REJECT
    assert [(issue.field, issue.reason) for issue in result.issues] == [
        ("auth", "sensitive_required_field")
    ]


async def test_allows_non_sensitive_missing_required_fields_for_elicitation() -> None:
    result = await _inspect(
        {"query": "docs"},
        _schema(
            properties={
                "query": {"type": "string"},
                "project": {"type": "string"},
            },
            required=["query", "project"],
        ),
    )

    assert result.status == InspectionStatus.OK
    assert result.issues == []


async def test_allows_sensitive_required_field_when_value_is_present() -> None:
    result = await _inspect(
        {"query": "docs", "access_token": "already-provided"},
        _schema(
            properties={
                "query": {"type": "string"},
                "access_token": {"type": "string"},
            },
            required=["query", "access_token"],
        ),
    )

    assert result.status == InspectionStatus.OK
    assert result.issues == []

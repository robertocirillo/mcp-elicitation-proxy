from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class InspectionStatus(StrEnum):
    OK = "ok"
    NEEDS_ELICITATION = "needs_elicitation"
    REJECT = "reject"
    CONFIRM = "confirm"


@dataclass(slots=True)
class InspectionIssue:
    field: str | None
    reason: str
    message: str


@dataclass(slots=True)
class InspectionResult:
    status: InspectionStatus
    issues: list[InspectionIssue] = field(default_factory=list)
    updated_arguments: dict[str, Any] | None = None

    @classmethod
    def ok(cls, updated_arguments: dict[str, Any] | None = None) -> "InspectionResult":
        return cls(status=InspectionStatus.OK, updated_arguments=updated_arguments)

    @classmethod
    def needs_elicitation(
        cls,
        issues: list[InspectionIssue],
        updated_arguments: dict[str, Any] | None = None,
    ) -> "InspectionResult":
        return cls(
            status=InspectionStatus.NEEDS_ELICITATION,
            issues=issues,
            updated_arguments=updated_arguments,
        )

    @classmethod
    def reject(
        cls,
        issues: list[InspectionIssue],
        updated_arguments: dict[str, Any] | None = None,
    ) -> "InspectionResult":
        return cls(
            status=InspectionStatus.REJECT,
            issues=issues,
            updated_arguments=updated_arguments,
        )

    @classmethod
    def confirm(
        cls,
        issues: list[InspectionIssue],
        updated_arguments: dict[str, Any] | None = None,
    ) -> "InspectionResult":
        return cls(
            status=InspectionStatus.CONFIRM,
            issues=issues,
            updated_arguments=updated_arguments,
        )


class ToolElicitationPolicy(Protocol):
    async def inspect(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_schema: dict[str, Any] | None,
        context: Any,
    ) -> InspectionResult:
        ...

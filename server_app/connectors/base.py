from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ConnectorResult:
    status: str
    summary: str
    records: list[dict[str, Any]] = field(default_factory=list)


class ConnectorAdapter(Protocol):
    connector_type: str

    def test_connection(self) -> ConnectorResult: ...

    def discover(self) -> ConnectorResult: ...

    def import_sync(self) -> ConnectorResult: ...

    def provision(self, payload: dict[str, Any]) -> ConnectorResult: ...

    def deprovision(self, payload: dict[str, Any]) -> ConnectorResult: ...

    def group_sync(self) -> ConnectorResult: ...

    def reconcile(self) -> ConnectorResult: ...


class DryRunConnector:
    connector_type = "generic"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def test_connection(self) -> ConnectorResult:
        if self._should_fail("test_connection"):
            return self._failure("test_connection")
        return ConnectorResult("ok", f"{self.connector_type} connector configuration validated.")

    def discover(self) -> ConnectorResult:
        if self._should_fail("discover"):
            return self._failure("discover")
        return ConnectorResult("ok", f"{self.connector_type} discovery completed in dry-run mode.")

    def import_sync(self) -> ConnectorResult:
        if self._should_fail("import"):
            return self._failure("import")
        return ConnectorResult("ok", f"{self.connector_type} import/sync completed in dry-run mode.")

    def provision(self, payload: dict[str, Any]) -> ConnectorResult:
        if self._should_fail("provision"):
            return self._failure("provision")
        return ConnectorResult("ok", f"{self.connector_type} provision dry-run accepted.", [payload])

    def deprovision(self, payload: dict[str, Any]) -> ConnectorResult:
        if self._should_fail("deprovision"):
            return self._failure("deprovision")
        return ConnectorResult("ok", f"{self.connector_type} deprovision dry-run accepted.", [payload])

    def group_sync(self) -> ConnectorResult:
        if self._should_fail("group_sync"):
            return self._failure("group_sync")
        return ConnectorResult("ok", f"{self.connector_type} group sync completed in dry-run mode.")

    def reconcile(self) -> ConnectorResult:
        if self._should_fail("reconcile"):
            return self._failure("reconcile")
        return ConnectorResult("ok", f"{self.connector_type} reconciliation snapshot completed in dry-run mode.")

    def _should_fail(self, operation: str) -> bool:
        return operation in set(self.config.get("fail_operations", []))

    def _failure(self, operation: str) -> ConnectorResult:
        return ConnectorResult("error", f"{self.connector_type} {operation} failed by connector configuration.")

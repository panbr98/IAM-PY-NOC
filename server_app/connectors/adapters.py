from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from server_app.connectors.base import ConnectorResult, DryRunConnector


class CsvConnector(DryRunConnector):
    connector_type = "csv"

    def import_sync(self) -> ConnectorResult:
        if self._should_fail("import"):
            return self._failure("import")
        csv_data = str(self.config.get("csv_data", ""))
        if not csv_data.strip():
            return ConnectorResult("ok", "CSV connector has no inline data; dry-run completed.", [])
        records = list(csv.DictReader(StringIO(csv_data)))
        return ConnectorResult("ok", f"CSV parsed {len(records)} record(s).", records)


class ScimConnector(DryRunConnector):
    connector_type = "scim"


class LdapConnector(DryRunConnector):
    connector_type = "ldap"


class ActiveDirectoryConnector(DryRunConnector):
    connector_type = "ad"


class GoogleWorkspaceConnector(DryRunConnector):
    connector_type = "google_workspace"


class JiraConnector(DryRunConnector):
    connector_type = "jira"


class GitHubConnector(DryRunConnector):
    connector_type = "github"


class RestConnector(DryRunConnector):
    connector_type = "rest"


CONNECTOR_ADAPTERS = {
    "csv": CsvConnector,
    "scim": ScimConnector,
    "ldap": LdapConnector,
    "ad": ActiveDirectoryConnector,
    "google_workspace": GoogleWorkspaceConnector,
    "jira": JiraConnector,
    "github": GitHubConnector,
    "rest": RestConnector,
}


def build_connector(connector_type: str, config: dict[str, Any] | None = None) -> DryRunConnector:
    return CONNECTOR_ADAPTERS.get(connector_type, DryRunConnector)(config)

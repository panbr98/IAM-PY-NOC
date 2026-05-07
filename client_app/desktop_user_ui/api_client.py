from __future__ import annotations

import json
from pathlib import Path
import socket
from typing import Any

import httpx


class ServerProfileStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("client_profiles.json")

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, profiles: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(profiles, indent=2), encoding="utf-8")

    def upsert(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        profiles = self.load()
        replaced = False
        for index, existing in enumerate(profiles):
            if existing.get("name") == profile.get("name"):
                profiles[index] = profile
                replaced = True
                break
        if not replaced:
            profiles.append(profile)
        self.save(profiles)
        return profiles


def normalize_api_base_url(value: str) -> str:
    url = value.strip()
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    if url.endswith("/"):
        url = url[:-1]
    if url.endswith("/api/v1"):
        return url
    if "/api/" in url:
        return url
    return f"{url}/api/v1"


def build_discovery_candidates(existing_profiles: list[dict[str, Any]]) -> list[str]:
    candidates = {
        "http://127.0.0.1:8787/api/v1",
        "http://localhost:8787/api/v1",
    }
    for profile in existing_profiles:
        base_url = profile.get("base_url")
        if isinstance(base_url, str) and base_url.strip():
            candidates.add(normalize_api_base_url(base_url))

    for address in _local_private_addresses():
        octets = address.split(".")
        if len(octets) != 4:
            continue
        prefix = ".".join(octets[:3])
        for suffix in [1, 2, 10, 20, int(octets[3])]:
            candidates.add(f"http://{prefix}.{suffix}:8787/api/v1")

    return sorted(candidates)


def discover_server_profiles(
    candidate_urls: list[str],
    *,
    timeout_seconds: float = 0.35,
) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    for base_url in candidate_urls:
        try:
            response = httpx.get(f"{normalize_api_base_url(base_url)}/server-info", timeout=timeout_seconds)
            response.raise_for_status()
            info = response.json()
        except Exception:
            continue
        discovered.append(
            {
                "name": f"{info['company_name']} [{info['host']}:{info['port']}]",
                "base_url": normalize_api_base_url(base_url),
                "fingerprint": info["fingerprint"],
                "bootstrap_mode": "discovery",
            }
        )
    return discovered


def _local_private_addresses() -> set[str]:
    addresses: set[str] = set()
    try:
        hostname = socket.gethostname()
        for address in socket.gethostbyname_ex(hostname)[2]:
            if _is_private_ipv4(address):
                addresses.add(address)
    except OSError:
        return addresses
    return addresses


def _is_private_ipv4(value: str) -> bool:
    return value.startswith("10.") or value.startswith("192.168.") or value.startswith("172.")


class NoctrixApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = normalize_api_base_url(base_url)
        self.token: str | None = None

    def _headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        response = httpx.get(f"{self.base_url}{path}", headers=self._headers(), params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, *, json_payload: dict[str, Any] | None = None) -> Any:
        response = httpx.post(f"{self.base_url}{path}", headers=self._headers(), json=json_payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def _put(self, path: str, *, json_payload: dict[str, Any]) -> Any:
        response = httpx.put(f"{self.base_url}{path}", headers=self._headers(), json=json_payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def _delete(self, path: str) -> Any:
        response = httpx.delete(f"{self.base_url}{path}", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def get_server_info(self) -> dict[str, Any]:
        return httpx.get(f"{self.base_url}/server-info", timeout=10).json()

    def login(self, username: str, password: str) -> str:
        response = httpx.post(
            f"{self.base_url}/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        response.raise_for_status()
        self.token = response.json()["access_token"]
        return self.token

    def get_me(self) -> dict[str, Any]:
        response = httpx.get(f"{self.base_url}/me", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def get_permissions(self) -> list[str]:
        response = httpx.get(f"{self.base_url}/permissions", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def get_resources(self) -> list[dict[str, Any]]:
        response = httpx.get(f"{self.base_url}/resources", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def get_access_requests(self) -> list[dict[str, Any]]:
        response = httpx.get(f"{self.base_url}/access-requests", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def get_identities(self) -> list[dict[str, Any]]:
        response = httpx.get(f"{self.base_url}/identities", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def create_identity(
        self,
        *,
        username: str,
        full_name: str,
        email: str,
        role: str,
        manager_id: int | None = None,
    ) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/identities",
            headers=self._headers(),
            json={
                "username": username,
                "full_name": full_name,
                "email": email,
                "role": role,
                "manager_id": manager_id,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def update_identity(
        self,
        identity_id: int,
        *,
        full_name: str,
        email: str,
        role: str,
        manager_id: int | None,
        status: str,
    ) -> dict[str, Any]:
        response = httpx.put(
            f"{self.base_url}/identities/{identity_id}",
            headers=self._headers(),
            json={
                "full_name": full_name,
                "email": email,
                "role": role,
                "manager_id": manager_id,
                "status": status,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def delete_identity(self, identity_id: int) -> dict[str, Any]:
        response = httpx.delete(
            f"{self.base_url}/identities/{identity_id}",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def import_identities_csv(self, csv_data: str, default_role: str = "employee") -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/identities/import-csv",
            headers=self._headers(),
            json={"csv_data": csv_data, "default_role": default_role},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_systems(self) -> list[dict[str, Any]]:
        response = httpx.get(f"{self.base_url}/systems", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def create_system(self, *, name: str, description: str = "", owner_identity_id: int | None = None) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/systems",
            headers=self._headers(),
            json={
                "name": name,
                "description": description,
                "owner_identity_id": owner_identity_id,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def update_system(
        self,
        system_id: int,
        *,
        name: str,
        description: str = "",
        owner_identity_id: int | None = None,
    ) -> dict[str, Any]:
        response = httpx.put(
            f"{self.base_url}/systems/{system_id}",
            headers=self._headers(),
            json={
                "name": name,
                "description": description,
                "owner_identity_id": owner_identity_id,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def delete_system(self, system_id: int) -> dict[str, Any]:
        response = httpx.delete(f"{self.base_url}/systems/{system_id}", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def get_assignments(self) -> list[dict[str, Any]]:
        response = httpx.get(f"{self.base_url}/resource-assignments", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def get_approvals(self) -> list[dict[str, Any]]:
        response = httpx.get(f"{self.base_url}/approvals", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def decide_approval(self, request_id: int, decision: str, comment: str = "") -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/access-requests/{request_id}/approve",
            headers=self._headers(),
            json={"decision": decision, "comment": comment},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_delegations(self) -> list[dict[str, Any]]:
        response = httpx.get(f"{self.base_url}/delegations", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def create_delegation(
        self,
        *,
        delegator_identity_id: int,
        delegate_identity_id: int,
        scope: str,
        starts_at: str,
        ends_at: str,
    ) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/delegations",
            headers=self._headers(),
            json={
                "delegator_identity_id": delegator_identity_id,
                "delegate_identity_id": delegate_identity_id,
                "scope": scope,
                "starts_at": starts_at,
                "ends_at": ends_at,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def update_delegation(
        self,
        delegation_id: int,
        *,
        scope: str,
        starts_at: str,
        ends_at: str,
        status: str,
    ) -> dict[str, Any]:
        response = httpx.put(
            f"{self.base_url}/delegations/{delegation_id}",
            headers=self._headers(),
            json={
                "scope": scope,
                "starts_at": starts_at,
                "ends_at": ends_at,
                "status": status,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def delete_delegation(self, delegation_id: int) -> dict[str, Any]:
        response = httpx.delete(f"{self.base_url}/delegations/{delegation_id}", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def get_tasks(self) -> list[dict[str, Any]]:
        response = httpx.get(f"{self.base_url}/provisioning/tasks", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def get_task_mappings(self) -> list[dict[str, Any]]:
        response = httpx.get(f"{self.base_url}/task-mappings", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def update_task_mapping(
        self,
        mapping_id: int,
        *,
        system_id: int,
        resource_id: int,
        action: str = "grant",
        trigger_event: str = "approval_approved",
        task_type: str = "manual_provision",
        default_owner_role: str = "operator",
        sla_hours: int = 24,
        provisioning_mode: str = "manual",
        connector_id: int | None = None,
        connector_operation: str | None = None,
        connector_query_id: int | None = None,
        payload_template: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = httpx.put(
            f"{self.base_url}/task-mappings/{mapping_id}",
            headers=self._headers(),
            json={
                "system_id": system_id,
                "resource_id": resource_id,
                "action": action,
                "trigger_event": trigger_event,
                "task_type": task_type,
                "default_owner_role": default_owner_role,
                "sla_hours": sla_hours,
                "provisioning_mode": provisioning_mode,
                "connector_id": connector_id,
                "connector_operation": connector_operation,
                "connector_query_id": connector_query_id,
                "payload_template": payload_template or {},
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def delete_task_mapping(self, mapping_id: int) -> dict[str, Any]:
        response = httpx.delete(
            f"{self.base_url}/task-mappings/{mapping_id}",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def create_task_mapping(
        self,
        *,
        system_id: int,
        resource_id: int,
        action: str = "grant",
        trigger_event: str = "approval_approved",
        task_type: str = "manual_provision",
        default_owner_role: str = "operator",
        sla_hours: int = 24,
        provisioning_mode: str = "manual",
        connector_id: int | None = None,
        connector_operation: str | None = None,
        connector_query_id: int | None = None,
        payload_template: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/task-mappings",
            headers=self._headers(),
            json={
                "system_id": system_id,
                "resource_id": resource_id,
                "action": action,
                "trigger_event": trigger_event,
                "task_type": task_type,
                "default_owner_role": default_owner_role,
                "sla_hours": sla_hours,
                "provisioning_mode": provisioning_mode,
                "connector_id": connector_id,
                "connector_operation": connector_operation,
                "connector_query_id": connector_query_id,
                "payload_template": payload_template or {},
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def complete_task(self, task_id: int, completion_notes: str = "") -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/provisioning/tasks/{task_id}/complete",
            headers=self._headers(),
            json={"completion_notes": completion_notes},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_audit(
        self,
        *,
        severity: str | None = None,
        entity_type: str | None = None,
        search: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params = {"limit": str(limit)}
        if severity:
            params["severity"] = severity
        if entity_type:
            params["entity_type"] = entity_type
        if search:
            params["search"] = search
        response = httpx.get(f"{self.base_url}/audit", headers=self._headers(), params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_dashboard_summary(self) -> dict[str, Any]:
        response = httpx.get(f"{self.base_url}/dashboard/summary", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def get_settings(self) -> dict[str, Any]:
        response = httpx.get(f"{self.base_url}/settings", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def update_settings(
        self,
        *,
        company_name: str,
        environment: str,
        database_url: str,
        tls_enabled: bool,
    ) -> dict[str, Any]:
        response = httpx.put(
            f"{self.base_url}/settings",
            headers=self._headers(),
            json={
                "company_name": company_name,
                "environment": environment,
                "database_url": database_url,
                "tls_enabled": tls_enabled,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def create_resource(
        self,
        *,
        name: str,
        system_id: int,
        requestable: bool = True,
        description: str = "",
    ) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/resources",
            headers=self._headers(),
            json={
                "name": name,
                "system_id": system_id,
                "requestable": requestable,
                "description": description,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def update_resource(
        self,
        resource_id: int,
        *,
        name: str,
        system_id: int,
        requestable: bool,
        description: str,
    ) -> dict[str, Any]:
        response = httpx.put(
            f"{self.base_url}/resources/{resource_id}",
            headers=self._headers(),
            json={
                "name": name,
                "system_id": system_id,
                "requestable": requestable,
                "description": description,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def delete_resource(self, resource_id: int) -> dict[str, Any]:
        response = httpx.delete(f"{self.base_url}/resources/{resource_id}", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def emergency_terminate(self, identity_id: int) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/identities/{identity_id}/emergency-terminate",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_policy_evaluations(self, access_request_id: int | None = None) -> list[dict[str, Any]]:
        params = {"access_request_id": str(access_request_id)} if access_request_id else None
        response = httpx.get(f"{self.base_url}/policy-evaluations", headers=self._headers(), params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_approval_instances(self, access_request_id: int | None = None) -> list[dict[str, Any]]:
        params = {"access_request_id": str(access_request_id)} if access_request_id else None
        response = httpx.get(f"{self.base_url}/approval-instances", headers=self._headers(), params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_expiring_assignments(self, within_days: int = 30) -> list[dict[str, Any]]:
        response = httpx.get(f"{self.base_url}/assignments/expiring", headers=self._headers(), params={"within_days": within_days}, timeout=10)
        response.raise_for_status()
        return response.json()

    def revoke_assignment(self, assignment_id: int, notes: str = "") -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/assignments/{assignment_id}/revoke",
            headers=self._headers(),
            params={"notes": notes},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def create_reconciliation_run(self, *, name: str, desired_access: list[dict[str, Any]], actual_access: list[dict[str, Any]], system_id: int | None = None) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/reconciliation/runs",
            headers=self._headers(),
            json={"name": name, "system_id": system_id, "desired_access": desired_access, "actual_access": actual_access},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_reconciliation_findings(self, run_id: int | None = None) -> list[dict[str, Any]]:
        params = {"run_id": str(run_id)} if run_id else None
        response = httpx.get(f"{self.base_url}/reconciliation/findings", headers=self._headers(), params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_reconciliation_runs(self) -> list[dict[str, Any]]:
        return self._get("/reconciliation/runs")

    def remediate_reconciliation_finding(self, finding_id: int) -> dict[str, Any]:
        response = httpx.post(f"{self.base_url}/reconciliation/findings/{finding_id}/remediate", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def create_certification_campaign(self, *, name: str, reviewer_identity_id: int | None = None, scope: str = "all_assignments") -> dict[str, Any]:
        response = httpx.post(f"{self.base_url}/certifications/campaigns", headers=self._headers(), json={"name": name, "scope": scope, "reviewer_identity_id": reviewer_identity_id}, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_certification_campaigns(self) -> list[dict[str, Any]]:
        return self._get("/certifications/campaigns")

    def close_certification_campaign(self, campaign_id: int) -> dict[str, Any]:
        return self._post(f"/certifications/campaigns/{campaign_id}/close")

    def get_certification_items(self, campaign_id: int | None = None) -> list[dict[str, Any]]:
        params = {"campaign_id": str(campaign_id)} if campaign_id else None
        response = httpx.get(f"{self.base_url}/certifications/items", headers=self._headers(), params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def decide_certification_item(self, item_id: int, decision: str, notes: str = "") -> dict[str, Any]:
        response = httpx.post(f"{self.base_url}/certifications/items/{item_id}/decision", headers=self._headers(), json={"decision": decision, "notes": notes}, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_pam_secrets(self) -> list[dict[str, Any]]:
        response = httpx.get(f"{self.base_url}/pam/secrets", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def create_pam_secret(self, *, name: str, secret_value: str, account_username: str = "", system_id: int | None = None, resource_id: int | None = None) -> dict[str, Any]:
        response = httpx.post(f"{self.base_url}/pam/secrets", headers=self._headers(), json={"name": name, "secret_value": secret_value, "account_username": account_username, "system_id": system_id, "resource_id": resource_id}, timeout=10)
        response.raise_for_status()
        return response.json()

    def checkout_pam_secret(self, secret_id: int, reason: str, *, break_glass: bool = False) -> dict[str, Any]:
        suffix = "break-glass" if break_glass else "checkout"
        response = httpx.post(f"{self.base_url}/pam/secrets/{secret_id}/{suffix}", headers=self._headers(), json={"reason": reason, "duration_minutes": 60}, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_pam_checkouts(self) -> list[dict[str, Any]]:
        return self._get("/pam/checkouts")

    def checkin_pam_checkout(self, checkout_id: int) -> dict[str, Any]:
        return self._post(f"/pam/checkouts/{checkout_id}/checkin")

    def create_pam_jit(self, *, resource_id: int | None, reason: str, duration_minutes: int = 60) -> dict[str, Any]:
        return self._post(
            "/pam/jit",
            json_payload={"resource_id": resource_id, "reason": reason, "duration_minutes": duration_minutes},
        )

    def get_connectors(self) -> list[dict[str, Any]]:
        response = httpx.get(f"{self.base_url}/connectors", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def create_connector(self, *, name: str, connector_type: str, dry_run: bool = True, system_id: int | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
        response = httpx.post(f"{self.base_url}/connectors", headers=self._headers(), json={"name": name, "connector_type": connector_type, "dry_run": dry_run, "system_id": system_id, "config": config or {}}, timeout=10)
        response.raise_for_status()
        return response.json()

    def run_connector(self, connector_id: int, operation: str = "sync") -> dict[str, Any]:
        response = httpx.post(f"{self.base_url}/connectors/{connector_id}/run/{operation}", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def test_connector(self, connector_id: int) -> dict[str, Any]:
        return self._post(f"/connectors/{connector_id}/test")

    def get_connector_runs(self) -> list[dict[str, Any]]:
        return self._get("/connector-runs")

    def list_connector_queries(self) -> list[dict[str, Any]]:
        return self._get("/connector-queries")

    def create_connector_query(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post("/connector-queries", json_payload=payload)

    def update_connector_query(self, query_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._put(f"/connector-queries/{query_id}", json_payload=payload)

    def delete_connector_query(self, query_id: int) -> dict[str, Any]:
        return self._delete(f"/connector-queries/{query_id}")

    def run_connector_query(self, query_id: int) -> dict[str, Any]:
        return self._post(f"/connector-queries/{query_id}/run")

    def get_jobs(self) -> list[dict[str, Any]]:
        response = httpx.get(f"{self.base_url}/jobs", headers=self._headers(), timeout=10)
        response.raise_for_status()
        return response.json()

    def create_job(self, *, job_type: str, payload: dict[str, Any] | None = None, run_after: str | None = None) -> dict[str, Any]:
        return self._post(
            "/jobs",
            json_payload={"job_type": job_type, "payload": payload or {}, "run_after": run_after},
        )

    def run_next_job(self) -> dict[str, Any] | None:
        return self._post("/jobs/run-next")

    def list_scim_users(self) -> list[dict[str, Any]]:
        payload = self._get("/scim/v2/Users")
        return payload.get("Resources", [])

    def list_scim_groups(self) -> list[dict[str, Any]]:
        payload = self._get("/scim/v2/Groups")
        return payload.get("Resources", [])

    def create_scim_user(self, *, user_name: str, display_name: str, email: str) -> dict[str, Any]:
        response = httpx.post(f"{self.base_url}/scim/v2/Users", headers=self._headers(), json={"userName": user_name, "displayName": display_name, "active": True, "emails": [{"value": email, "primary": True}]}, timeout=10)
        response.raise_for_status()
        return response.json()

    def create_scim_group(self, *, display_name: str, members: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return self._post(
            "/scim/v2/Groups",
            json_payload={"displayName": display_name, "members": members or []},
        )

    def list_scim_mappings(self) -> list[dict[str, Any]]:
        return self._get("/scim/mappings")

    def create_scim_mapping(
        self,
        *,
        scim_group_id: str,
        resource_id: int,
        direction: str = "inbound",
        active: bool = True,
    ) -> dict[str, Any]:
        return self._post(
            "/scim/mappings",
            json_payload={
                "scim_group_id": scim_group_id,
                "resource_id": resource_id,
                "direction": direction,
                "active": active,
            },
        )

    def update_scim_mapping(
        self,
        mapping_id: int,
        *,
        scim_group_id: str,
        resource_id: int,
        direction: str = "inbound",
        active: bool = True,
    ) -> dict[str, Any]:
        return self._put(
            f"/scim/mappings/{mapping_id}",
            json_payload={
                "scim_group_id": scim_group_id,
                "resource_id": resource_id,
                "direction": direction,
                "active": active,
            },
        )

    def delete_scim_mapping(self, mapping_id: int) -> dict[str, Any]:
        return self._delete(f"/scim/mappings/{mapping_id}")

    def list_governance(self, endpoint: str) -> list[dict[str, Any]]:
        return self._get(f"/{endpoint}")

    def create_governance(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post(f"/{endpoint}", json_payload=payload)

    def update_governance(self, endpoint: str, item_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._put(f"/{endpoint}/{item_id}", json_payload=payload)

    def delete_governance(self, endpoint: str, item_id: int) -> dict[str, Any]:
        return self._delete(f"/{endpoint}/{item_id}")

    def get_path(self, path: str) -> Any:
        return self._get(_normalize_path(path))

    def post_path(self, path: str, payload: dict[str, Any]) -> Any:
        return self._post(_normalize_path(path), json_payload=payload)

    def put_path(self, path: str, payload: dict[str, Any]) -> Any:
        return self._put(_normalize_path(path), json_payload=payload)

    def delete_path(self, path: str) -> Any:
        return self._delete(_normalize_path(path))

    def create_access_request(
        self,
        *,
        beneficiary_identity_id: int,
        resource_id: int,
        reason: str,
        urgency: str = "normal",
        comments: str = "",
    ) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/access-requests",
            headers=self._headers(),
            json={
                "beneficiary_identity_id": beneficiary_identity_id,
                "resource_id": resource_id,
                "reason": reason,
                "urgency": urgency,
                "comments": comments,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()


def _normalize_path(path: str) -> str:
    value = path.strip()
    return value if value.startswith("/") else f"/{value}"

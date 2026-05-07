from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class ServerInfo(BaseModel):
    product_name: str
    environment: str
    company_name: str
    host: str
    port: int
    fingerprint: str
    health: str


class SetupWizardStatus(BaseModel):
    configured: bool
    company_name: str
    environment: str
    super_admin_username: str | None = None
    database_url: str | None = None
    tls_enabled: bool = False
    fingerprint: str | None = None


class SetupWizardBootstrapRequest(BaseModel):
    company_name: str
    environment: Literal["demo", "production"] = "demo"
    super_admin_username: str
    super_admin_full_name: str
    super_admin_email: str
    super_admin_password: str = Field(min_length=8)
    import_sample_data: bool = True


class DashboardSummary(BaseModel):
    identities: int
    systems: int
    resources: int
    open_requests: int
    pending_approvals: int
    pending_tasks: int
    active_assignments: int
    critical_audit_events: int


class SettingsRead(BaseModel):
    company_name: str
    environment: str
    database_url: str
    tls_enabled: bool
    fingerprint: str


class SettingsUpdate(BaseModel):
    company_name: str
    environment: Literal["demo", "production"]
    database_url: str
    tls_enabled: bool = False


class IdentityCreate(BaseModel):
    username: str
    full_name: str
    email: str
    role: Literal["super_admin", "manager", "operator", "employee"] = "employee"
    manager_id: int | None = None


class IdentityUpdate(BaseModel):
    full_name: str
    email: str
    role: Literal["super_admin", "manager", "operator", "employee"]
    manager_id: int | None = None
    status: Literal["active", "disabled", "terminated"] = "active"


class IdentityImportRequest(BaseModel):
    csv_data: str
    default_role: Literal["employee", "operator", "manager"] = "employee"


class IdentityImportResult(BaseModel):
    created_count: int
    skipped_count: int
    usernames: list[str]
    skipped_rows: list[str] = []


class IdentityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    email: str
    role: str
    status: str
    manager_id: int | None


class SystemCreate(BaseModel):
    name: str
    description: str = ""
    owner_identity_id: int | None = None


class SystemUpdate(BaseModel):
    name: str
    description: str = ""
    owner_identity_id: int | None = None


class SystemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    owner_identity_id: int | None


class ResourceCreate(BaseModel):
    name: str
    system_id: int
    requestable: bool = True
    description: str = ""


class ResourceUpdate(BaseModel):
    name: str
    system_id: int
    requestable: bool = True
    description: str = ""


class ResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    system_id: int
    requestable: bool
    description: str


class TaskMappingCreate(BaseModel):
    system_id: int
    resource_id: int
    action: str = "grant"
    trigger_event: str = "approval_approved"
    task_type: str = "manual_provision"
    default_owner_role: str = "operator"
    sla_hours: int = 24
    provisioning_mode: Literal["manual", "automatic"] = "manual"
    connector_id: int | None = None
    connector_operation: str | None = None
    connector_query_id: int | None = None
    payload_template: dict[str, Any] = Field(default_factory=dict)


class TaskMappingUpdate(BaseModel):
    system_id: int
    resource_id: int
    action: str = "grant"
    trigger_event: str = "approval_approved"
    task_type: str = "manual_provision"
    default_owner_role: str = "operator"
    sla_hours: int = 24
    provisioning_mode: Literal["manual", "automatic"] = "manual"
    connector_id: int | None = None
    connector_operation: str | None = None
    connector_query_id: int | None = None
    payload_template: dict[str, Any] = Field(default_factory=dict)


class TaskMappingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    system_id: int
    resource_id: int
    action: str
    trigger_event: str
    task_type: str
    default_owner_role: str
    sla_hours: int
    provisioning_mode: str
    connector_id: int | None
    connector_operation: str | None
    connector_query_id: int | None
    payload_template_json: str


class AccessRequestCreate(BaseModel):
    beneficiary_identity_id: int
    resource_id: int
    reason: str
    start_date: datetime | None = None
    end_date: datetime | None = None
    urgency: str = "normal"
    comments: str = ""


class AccessRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requester_identity_id: int
    beneficiary_identity_id: int
    resource_id: int
    manager_identity_id: int | None
    reason: str
    start_date: datetime | None
    end_date: datetime | None
    urgency: str
    comments: str
    status: str
    risk_score: int
    risk_level: str
    policy_evaluation_summary: str
    approval_policy_id: int | None
    current_stage_order: int | None
    source_type: str


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str = ""


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    access_request_id: int
    approver_identity_id: int
    decision: str
    comment: str
    status: str


class ProvisioningTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    access_request_id: int | None
    identity_id: int
    resource_id: int | None
    task_type: str
    owner_role: str
    status: str
    urgency: str
    details: str


class ProvisioningTaskComplete(BaseModel):
    completion_notes: str = ""


class ResourceAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identity_id: int
    resource_id: int
    status: str
    granted_at: datetime | None
    expires_at: datetime | None
    source_type: str
    source_id: int | None
    risk_score: int
    revoked_at: datetime | None
    governance_state: str


class DelegationCreate(BaseModel):
    delegator_identity_id: int
    delegate_identity_id: int
    scope: str
    starts_at: datetime
    ends_at: datetime


class DelegationUpdate(BaseModel):
    scope: str
    starts_at: datetime
    ends_at: datetime
    status: Literal["draft", "active", "expired", "revoked"]


class DelegationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    delegator_identity_id: int
    delegate_identity_id: int
    scope: str
    starts_at: datetime
    ends_at: datetime
    status: str


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_identity_id: int | None
    event_type: str
    entity_type: str
    entity_id: int | None
    severity: str
    details: str
    created_at: datetime

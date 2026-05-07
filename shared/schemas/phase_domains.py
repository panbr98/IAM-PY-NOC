from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: str
    entity_type: str
    entity_id: int | None
    evidence_type: str
    content: str
    actor_identity_id: int | None
    created_at: datetime


class ReconciliationRunCreate(BaseModel):
    name: str
    system_id: int | None = None
    connector_id: int | None = None
    desired_access: list[dict[str, Any]] = Field(default_factory=list)
    actual_access: list[dict[str, Any]] = Field(default_factory=list)


class ReconciliationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    connector_id: int | None
    system_id: int | None
    status: str
    summary: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class ReconciliationFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    finding_type: str
    identity_id: int | None
    resource_id: int | None
    account_identifier: str
    severity: str
    status: str
    details: str


class RemediationActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    finding_id: int
    action_type: str
    status: str
    provisioning_task_id: int | None
    details: str


class CertificationCampaignCreate(BaseModel):
    name: str
    scope: str = "all_assignments"
    reviewer_identity_id: int | None = None
    due_at: datetime | None = None


class CertificationCampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scope: str
    reviewer_identity_id: int | None
    status: str
    due_at: datetime | None
    created_at: datetime
    closed_at: datetime | None


class CertificationItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    assignment_id: int | None
    identity_id: int
    resource_id: int
    reviewer_identity_id: int | None
    decision: str
    status: str
    decision_notes: str
    decided_at: datetime | None


class CertificationDecision(BaseModel):
    decision: str
    notes: str = ""


class PamSecretCreate(BaseModel):
    name: str
    system_id: int | None = None
    resource_id: int | None = None
    account_username: str = ""
    secret_value: str
    rotation_interval_days: int = 30


class PamSecretRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    system_id: int | None
    resource_id: int | None
    account_username: str
    privileged: bool
    status: str
    rotation_interval_days: int
    current_version_id: int | None
    created_at: datetime


class PamCheckoutCreate(BaseModel):
    reason: str
    duration_minutes: int = 60


class PamCheckoutRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    secret_id: int
    requester_identity_id: int
    status: str
    reason: str
    checked_out_at: datetime
    due_back_at: datetime | None
    checked_in_at: datetime | None
    break_glass: bool
    revealed_secret: str | None = None


class PamJitAccessCreate(BaseModel):
    resource_id: int | None = None
    reason: str
    duration_minutes: int = 60


class PamJitAccessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identity_id: int
    resource_id: int | None
    status: str
    reason: str
    starts_at: datetime | None
    expires_at: datetime | None


class ConnectorCreate(BaseModel):
    name: str
    connector_type: str
    system_id: int | None = None
    dry_run: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    secret: str = ""


class ConnectorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    connector_type: str
    system_id: int | None
    status: str
    dry_run: bool
    config_json: str
    last_test_status: str
    created_at: datetime


class ConnectorRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    connector_id: int
    operation: str
    status: str
    dry_run: bool
    summary: str
    started_at: datetime | None
    completed_at: datetime | None


class ConnectorQueryBase(BaseModel):
    name: str
    system_id: int
    connector_id: int
    operation: str = "discover"
    query: dict[str, Any] = Field(default_factory=dict)
    active: bool = True


class ConnectorQueryCreate(ConnectorQueryBase):
    pass


class ConnectorQueryUpdate(ConnectorQueryBase):
    pass


class ConnectorQueryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    system_id: int
    connector_id: int
    operation: str
    query_json: str
    active: bool
    created_at: datetime


class SchedulerJobCreate(BaseModel):
    job_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    run_after: datetime | None = None


class SchedulerJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: str
    status: str
    payload_json: str
    attempts: int
    max_attempts: int
    last_error: str
    run_after: datetime | None
    created_at: datetime
    updated_at: datetime | None


class ScimUserPayload(BaseModel):
    userName: str
    displayName: str | None = None
    active: bool = True
    emails: list[dict[str, Any]] = Field(default_factory=list)


class ScimGroupPayload(BaseModel):
    displayName: str
    members: list[dict[str, Any]] = Field(default_factory=list)


class ScimMappingCreate(BaseModel):
    scim_group_id: str
    resource_id: int
    direction: str = "inbound"
    active: bool = True


class ScimMappingUpdate(BaseModel):
    scim_group_id: str
    resource_id: int
    direction: str = "inbound"
    active: bool = True


class ScimMappingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    direction: str
    source_path: str
    target_path: str
    active: bool
    scim_group_id: str | None = None
    resource_id: int | None = None


class ScimResourceRead(BaseModel):
    id: str
    userName: str | None = None
    displayName: str | None = None
    active: bool | None = None
    members: list[dict[str, Any]] = Field(default_factory=list)


class ScimListResponse(BaseModel):
    Resources: list[dict[str, Any]]
    totalResults: int
    startIndex: int = 1
    itemsPerPage: int

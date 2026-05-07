from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server_app.core.database import Base


class Identity(Base):
    __tablename__ = "identities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    role: Mapped[str] = mapped_column(String(50), default="employee")
    status: Mapped[str] = mapped_column(String(50), default="active")
    password_hash: Mapped[str] = mapped_column(String(512))
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("identities.id"), nullable=True)


class ConfigEntry(Base):
    __tablename__ = "config_entries"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class System(Base):
    __tablename__ = "systems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_identity_id: Mapped[int | None] = mapped_column(ForeignKey("identities.id"), nullable=True)


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    system_id: Mapped[int] = mapped_column(ForeignKey("systems.id"))
    requestable: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(Text, default="")


class TaskMapping(Base):
    __tablename__ = "task_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("systems.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    action: Mapped[str] = mapped_column(String(50), default="grant")
    trigger_event: Mapped[str] = mapped_column(String(100), default="approval_approved")
    task_type: Mapped[str] = mapped_column(String(100), default="manual_provision")
    default_owner_role: Mapped[str] = mapped_column(String(50), default="operator")
    sla_hours: Mapped[int] = mapped_column(Integer, default=24)
    provisioning_mode: Mapped[str] = mapped_column(String(50), default="manual")
    connector_id: Mapped[int | None] = mapped_column(ForeignKey("connectors.id"), nullable=True)
    connector_operation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    connector_query_id: Mapped[int | None] = mapped_column(ForeignKey("connector_queries.id"), nullable=True)
    payload_template_json: Mapped[str] = mapped_column(Text, default="{}")


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requester_identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    beneficiary_identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    manager_identity_id: Mapped[int | None] = mapped_column(ForeignKey("identities.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    urgency: Mapped[str] = mapped_column(String(50), default="normal")
    comments: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="submitted")
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(50), default="low")
    policy_evaluation_summary: Mapped[str] = mapped_column(Text, default="")
    approval_policy_id: Mapped[int | None] = mapped_column(ForeignKey("approval_policies.id"), nullable=True)
    current_stage_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="direct_request")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_request_id: Mapped[int] = mapped_column(ForeignKey("access_requests.id"))
    approver_identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    decision: Mapped[str] = mapped_column(String(50), default="pending")
    comment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="pending")


class ProvisioningTask(Base):
    __tablename__ = "provisioning_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_request_id: Mapped[int | None] = mapped_column(ForeignKey("access_requests.id"), nullable=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("resources.id"), nullable=True)
    task_type: Mapped[str] = mapped_column(String(100))
    owner_role: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    urgency: Mapped[str] = mapped_column(String(50), default="normal")
    details: Mapped[str] = mapped_column(Text, default="")


class ResourceAssignment(Base):
    __tablename__ = "resource_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    status: Mapped[str] = mapped_column(String(50), default="active")
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="direct_request")
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    governance_state: Mapped[str] = mapped_column(String(50), default="approved")


class Delegation(Base):
    __tablename__ = "delegations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delegator_identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    delegate_identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    scope: Mapped[str] = mapped_column(String(100))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(50), default="draft")
    max_duration_days: Mapped[int] = mapped_column(Integer, default=30)
    no_self_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    no_policy_bypass: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_identity_id: Mapped[int | None] = mapped_column(ForeignKey("identities.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    severity: Mapped[str] = mapped_column(String(50), default="info")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BusinessRole(Base):
    __tablename__ = "business_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    requestable: Mapped[bool] = mapped_column(Boolean, default=True)
    risk_level: Mapped[str] = mapped_column(String(50), default="normal")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class TechnicalRole(Base):
    __tablename__ = "technical_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    requestable: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class BusinessRoleTechnicalRole(Base):
    __tablename__ = "business_role_technical_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_role_id: Mapped[int] = mapped_column(ForeignKey("business_roles.id"))
    technical_role_id: Mapped[int] = mapped_column(ForeignKey("technical_roles.id"))


class BusinessRoleResource(Base):
    __tablename__ = "business_role_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_role_id: Mapped[int] = mapped_column(ForeignKey("business_roles.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))


class TechnicalRoleResource(Base):
    __tablename__ = "technical_role_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    technical_role_id: Mapped[int] = mapped_column(ForeignKey("technical_roles.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))


class BusinessRoleMembership(Base):
    __tablename__ = "business_role_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    business_role_id: Mapped[int] = mapped_column(ForeignKey("business_roles.id"))
    source: Mapped[str] = mapped_column(String(50), default="manual")
    status: Mapped[str] = mapped_column(String(50), default="active")


class TechnicalRoleMembership(Base):
    __tablename__ = "technical_role_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    technical_role_id: Mapped[int] = mapped_column(ForeignKey("technical_roles.id"))
    source: Mapped[str] = mapped_column(String(50), default="manual")
    status: Mapped[str] = mapped_column(String(50), default="active")


class BirthrightRule(Base):
    __tablename__ = "birthright_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    attribute_name: Mapped[str] = mapped_column(String(100))
    operator: Mapped[str] = mapped_column(String(50), default="equals")
    expected_value: Mapped[str] = mapped_column(String(200))
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    grant_basis: Mapped[str] = mapped_column(String(50), default="birthright")


class AttributeAccessRule(Base):
    __tablename__ = "attribute_access_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    attribute_name: Mapped[str] = mapped_column(String(100))
    operator: Mapped[str] = mapped_column(String(50), default="equals")
    expected_value: Mapped[str] = mapped_column(String(200))
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(50), default="assign")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AccessPolicy(Base):
    __tablename__ = "access_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("resources.id"), nullable=True)
    system_id: Mapped[int | None] = mapped_column(ForeignKey("systems.id"), nullable=True)
    business_role_id: Mapped[int | None] = mapped_column(ForeignKey("business_roles.id"), nullable=True)
    technical_role_id: Mapped[int | None] = mapped_column(ForeignKey("technical_roles.id"), nullable=True)
    max_duration_days: Mapped[int] = mapped_column(Integer, default=30)
    privileged: Mapped[bool] = mapped_column(Boolean, default=False)
    base_risk_score: Mapped[int] = mapped_column(Integer, default=0)
    require_justification: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SoDPolicy(Base):
    __tablename__ = "sod_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(50), default="warn")
    severity: Mapped[str] = mapped_column(String(50), default="high")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SoDPolicyPair(Base):
    __tablename__ = "sod_policy_pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sod_policy_id: Mapped[int] = mapped_column(ForeignKey("sod_policies.id"))
    left_resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    right_resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))


class RiskRule(Base):
    __tablename__ = "risk_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    condition_type: Mapped[str] = mapped_column(String(100))
    condition_value: Mapped[str] = mapped_column(String(200))
    score: Mapped[int] = mapped_column(Integer, default=0)
    severity: Mapped[str] = mapped_column(String(50), default="medium")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ApprovalPolicy(Base):
    __tablename__ = "approval_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    scope_type: Mapped[str] = mapped_column(String(50), default="default")
    scope_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_risk_score: Mapped[int] = mapped_column(Integer, default=0)
    sequential: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class ApprovalStage(Base):
    __tablename__ = "approval_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("approval_policies.id"))
    stage_order: Mapped[int] = mapped_column(Integer, default=1)
    mode: Mapped[str] = mapped_column(String(50), default="all")
    approver_type: Mapped[str] = mapped_column(String(50))
    approver_value: Mapped[str] = mapped_column(String(200), default="")
    required_count: Mapped[int] = mapped_column(Integer, default=1)


class ApprovalStageDecision(Base):
    __tablename__ = "approval_stage_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_request_id: Mapped[int] = mapped_column(ForeignKey("access_requests.id"))
    stage_id: Mapped[int] = mapped_column(ForeignKey("approval_stages.id"))
    approver_identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    delegate_identity_id: Mapped[int | None] = mapped_column(ForeignKey("identities.id"), nullable=True)
    decision: Mapped[str] = mapped_column(String(50), default="pending")
    comment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    acted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AccessExpiryPolicy(Base):
    __tablename__ = "access_expiry_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("resources.id"), nullable=True)
    business_role_id: Mapped[int | None] = mapped_column(ForeignKey("business_roles.id"), nullable=True)
    technical_role_id: Mapped[int | None] = mapped_column(ForeignKey("technical_roles.id"), nullable=True)
    default_duration_days: Mapped[int] = mapped_column(Integer, default=30)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PolicyEvaluationResult(Base):
    __tablename__ = "policy_evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    access_request_id: Mapped[int | None] = mapped_column(ForeignKey("access_requests.id"), nullable=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("resources.id"), nullable=True)
    result_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="info")
    score: Mapped[int] = mapped_column(Integer, default=0)
    severity: Mapped[str] = mapped_column(String(50), default="info")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(100), default="note")
    content: Mapped[str] = mapped_column(Text, default="")
    actor_identity_id: Mapped[int | None] = mapped_column(ForeignKey("identities.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    connector_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    system_id: Mapped[int | None] = mapped_column(ForeignKey("systems.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    desired_snapshot: Mapped[str] = mapped_column(Text, default="[]")
    actual_snapshot: Mapped[str] = mapped_column(Text, default="[]")
    summary: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReconciliationFinding(Base):
    __tablename__ = "reconciliation_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("reconciliation_runs.id"))
    finding_type: Mapped[str] = mapped_column(String(100))
    identity_id: Mapped[int | None] = mapped_column(ForeignKey("identities.id"), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("resources.id"), nullable=True)
    account_identifier: Mapped[str] = mapped_column(String(200), default="")
    severity: Mapped[str] = mapped_column(String(50), default="medium")
    status: Mapped[str] = mapped_column(String(50), default="open")
    details: Mapped[str] = mapped_column(Text, default="")


class RemediationAction(Base):
    __tablename__ = "remediation_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("reconciliation_findings.id"))
    action_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    provisioning_task_id: Mapped[int | None] = mapped_column(ForeignKey("provisioning_tasks.id"), nullable=True)
    details: Mapped[str] = mapped_column(Text, default="")


class CertificationCampaign(Base):
    __tablename__ = "certification_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    scope: Mapped[str] = mapped_column(String(100), default="all_assignments")
    reviewer_identity_id: Mapped[int | None] = mapped_column(ForeignKey("identities.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CertificationItem(Base):
    __tablename__ = "certification_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("certification_campaigns.id"))
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("resource_assignments.id"), nullable=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"))
    reviewer_identity_id: Mapped[int | None] = mapped_column(ForeignKey("identities.id"), nullable=True)
    decision: Mapped[str] = mapped_column(String(50), default="pending")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    decision_notes: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PamVaultSecret(Base):
    __tablename__ = "pam_vault_secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    system_id: Mapped[int | None] = mapped_column(ForeignKey("systems.id"), nullable=True)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("resources.id"), nullable=True)
    account_username: Mapped[str] = mapped_column(String(200), default="")
    privileged: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    rotation_interval_days: Mapped[int] = mapped_column(Integer, default=30)
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PamSecretVersion(Base):
    __tablename__ = "pam_secret_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    secret_id: Mapped[int] = mapped_column(ForeignKey("pam_vault_secrets.id"))
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    encrypted_secret: Mapped[str] = mapped_column(Text, default="")
    created_by_identity_id: Mapped[int | None] = mapped_column(ForeignKey("identities.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PamCheckout(Base):
    __tablename__ = "pam_checkouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    secret_id: Mapped[int] = mapped_column(ForeignKey("pam_vault_secrets.id"))
    requester_identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    status: Mapped[str] = mapped_column(String(50), default="checked_out")
    reason: Mapped[str] = mapped_column(Text, default="")
    checked_out_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    due_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    break_glass: Mapped[bool] = mapped_column(Boolean, default=False)


class PamJitAccess(Base):
    __tablename__ = "pam_jit_access"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("identities.id"))
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("resources.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    reason: Mapped[str] = mapped_column(Text, default="")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Connector(Base):
    __tablename__ = "connectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    connector_type: Mapped[str] = mapped_column(String(100))
    system_id: Mapped[int | None] = mapped_column(ForeignKey("systems.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    secret_ref: Mapped[str] = mapped_column(Text, default="")
    last_test_status: Mapped[str] = mapped_column(String(50), default="untested")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConnectorRun(Base):
    __tablename__ = "connector_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id"))
    operation: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConnectorQuery(Base):
    __tablename__ = "connector_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    system_id: Mapped[int] = mapped_column(ForeignKey("systems.id"))
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id"))
    operation: Mapped[str] = mapped_column(String(100))
    query_json: Mapped[str] = mapped_column(Text, default="{}")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SchedulerJob(Base):
    __tablename__ = "scheduler_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="queued")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str] = mapped_column(Text, default="")
    run_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScimUser(Base):
    __tablename__ = "scim_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scim_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    identity_id: Mapped[int | None] = mapped_column(ForeignKey("identities.id"), nullable=True)
    user_name: Mapped[str] = mapped_column(String(200), unique=True)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_json: Mapped[str] = mapped_column(Text, default="{}")


class ScimGroup(Base):
    __tablename__ = "scim_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scim_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), unique=True)
    raw_json: Mapped[str] = mapped_column(Text, default="{}")


class ScimGroupMembership(Base):
    __tablename__ = "scim_group_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("scim_groups.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("scim_users.id"))


class ScimMapping(Base):
    __tablename__ = "scim_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    direction: Mapped[str] = mapped_column(String(50), default="inbound")
    source_path: Mapped[str] = mapped_column(String(200))
    target_path: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

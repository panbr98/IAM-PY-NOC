from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from server_app.core.audit import record_audit
from server_app.core.models import (
    CertificationCampaign,
    CertificationItem,
    Connector,
    ConnectorQuery,
    ConnectorRun,
    EvidenceRecord,
    Identity,
    PamCheckout,
    PamJitAccess,
    PamSecretVersion,
    PamVaultSecret,
    ProvisioningTask,
    ReconciliationFinding,
    ReconciliationRun,
    RemediationAction,
    ResourceAssignment,
    SchedulerJob,
    ScimMapping,
    ScimGroup,
    ScimGroupMembership,
    ScimUser,
    System,
    Resource,
)
from server_app.connectors import build_connector
from shared.crypto.secrets import decode_secret, encode_secret, mask_secret
from shared.schemas.phase_domains import (
    CertificationCampaignCreate,
    CertificationDecision,
    ConnectorCreate,
    ConnectorQueryCreate,
    ConnectorQueryRead,
    ConnectorQueryUpdate,
    PamCheckoutCreate,
    PamJitAccessCreate,
    PamSecretCreate,
    ReconciliationRunCreate,
    SchedulerJobCreate,
    ScimGroupPayload,
    ScimMappingCreate,
    ScimMappingUpdate,
    ScimUserPayload,
)


class ReconciliationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run(self, payload: ReconciliationRunCreate, actor_id: int | None) -> ReconciliationRun:
        run = ReconciliationRun(
            name=payload.name,
            connector_id=payload.connector_id,
            system_id=payload.system_id,
            status="running",
            desired_snapshot=json.dumps(payload.desired_access),
            actual_snapshot=json.dumps(payload.actual_access),
            started_at=datetime.now(UTC),
        )
        self.session.add(run)
        self.session.flush()
        findings = self._diff(payload.desired_access, payload.actual_access)
        for finding in findings:
            self.session.add(ReconciliationFinding(run_id=run.id, **finding))
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        run.summary = f"{len(findings)} findings: " + ", ".join(sorted({item["finding_type"] for item in findings})) if findings else "0 findings."
        self._evidence("reconciliation", "reconciliation_run", run.id, run.summary, actor_id)
        self._audit(actor_id, "reconciliation.completed", "reconciliation_run", run.id, run.summary)
        return run

    def list_runs(self) -> list[ReconciliationRun]:
        return self.session.query(ReconciliationRun).order_by(ReconciliationRun.id).all()

    def list_findings(self, run_id: int | None = None) -> list[ReconciliationFinding]:
        query = self.session.query(ReconciliationFinding).order_by(ReconciliationFinding.id)
        if run_id is not None:
            query = query.filter(ReconciliationFinding.run_id == run_id)
        return query.all()

    def remediate(self, finding_id: int, actor_id: int | None) -> RemediationAction:
        finding = self._require(ReconciliationFinding, finding_id, "Finding not found.")
        task_type = {
            "unauthorized_access": "urgent_deprovision",
            "orphan_account": "orphan_account_review",
            "missing_access": "manual_provision",
            "stale_access": "access_review",
            "privileged_finding": "privileged_access_review",
        }.get(finding.finding_type, "manual_follow_up")
        task_id = None
        if finding.identity_id:
            task = ProvisioningTask(
                access_request_id=None,
                identity_id=finding.identity_id,
                resource_id=finding.resource_id,
                task_type=task_type,
                owner_role="operator",
                status="pending",
                urgency="critical" if finding.severity in {"high", "critical"} else "normal",
                details=f"Remediate reconciliation finding {finding.id}: {finding.details}",
            )
            self.session.add(task)
            self.session.flush()
            task_id = task.id
        action = RemediationAction(
            finding_id=finding.id,
            action_type=task_type,
            status="queued",
            provisioning_task_id=task_id,
            details="Queued remediation task." if task_id else "Queued manual remediation review.",
        )
        finding.status = "remediation_queued"
        self.session.add(action)
        self._audit(actor_id, "reconciliation.remediation_queued", "reconciliation_finding", finding.id, action.details)
        return action

    def _diff(self, desired: list[dict[str, Any]], actual: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def key(item: dict[str, Any]) -> tuple[str, str]:
            return (str(item.get("identity_id") or item.get("account") or ""), str(item.get("resource_id") or item.get("entitlement") or ""))

        desired_by_key = {key(item): item for item in desired}
        actual_by_key = {key(item): item for item in actual}
        findings: list[dict[str, Any]] = []
        for item_key, item in actual_by_key.items():
            if item_key not in desired_by_key:
                finding_type = "orphan_account" if not item.get("identity_id") else "unauthorized_access"
                if item.get("privileged"):
                    finding_type = "privileged_finding"
                findings.append(self._finding(finding_type, item, "Actual access is not present in desired state."))
        for item_key, item in desired_by_key.items():
            if item_key not in actual_by_key:
                findings.append(self._finding("missing_access", item, "Desired access is missing from actual state."))
        for item in actual:
            if item.get("stale"):
                findings.append(self._finding("stale_access", item, "Actual account/access is stale."))
        return findings

    def _finding(self, finding_type: str, item: dict[str, Any], details: str) -> dict[str, Any]:
        return {
            "finding_type": finding_type,
            "identity_id": item.get("identity_id"),
            "resource_id": item.get("resource_id"),
            "account_identifier": str(item.get("account") or item.get("userName") or ""),
            "severity": "high" if finding_type in {"unauthorized_access", "privileged_finding"} else "medium",
            "status": "open",
            "details": details,
        }

    def _evidence(self, domain: str, entity_type: str, entity_id: int, content: str, actor_id: int | None) -> None:
        self.session.add(EvidenceRecord(domain=domain, entity_type=entity_type, entity_id=entity_id, evidence_type="system", content=content, actor_identity_id=actor_id))

    def _audit(self, actor_id: int | None, event_type: str, entity_type: str, entity_id: int | None, details: str) -> None:
        record_audit(self.session, actor_identity_id=actor_id, event_type=event_type, entity_type=entity_type, entity_id=entity_id, details=details)

    def _require(self, model, entity_id: int, message: str):
        item = self.session.get(model, entity_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
        return item


class CertificationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_campaign(self, payload: CertificationCampaignCreate, actor_id: int | None) -> CertificationCampaign:
        campaign = CertificationCampaign(name=payload.name, scope=payload.scope, reviewer_identity_id=payload.reviewer_identity_id, status="active", due_at=payload.due_at)
        self.session.add(campaign)
        self.session.flush()
        assignments = self.session.query(ResourceAssignment).filter(ResourceAssignment.status == "active").all()
        for assignment in assignments:
            reviewer_id = payload.reviewer_identity_id or self._manager_for(assignment.identity_id) or actor_id
            self.session.add(
                CertificationItem(
                    campaign_id=campaign.id,
                    assignment_id=assignment.id,
                    identity_id=assignment.identity_id,
                    resource_id=assignment.resource_id,
                    reviewer_identity_id=reviewer_id,
                )
            )
        self._audit(actor_id, "certification.campaign_created", "certification_campaign", campaign.id, f"Created {len(assignments)} review items.")
        return campaign

    def list_campaigns(self) -> list[CertificationCampaign]:
        return self.session.query(CertificationCampaign).order_by(CertificationCampaign.id).all()

    def list_items(self, campaign_id: int | None = None, reviewer_id: int | None = None) -> list[CertificationItem]:
        query = self.session.query(CertificationItem).order_by(CertificationItem.id)
        if campaign_id is not None:
            query = query.filter(CertificationItem.campaign_id == campaign_id)
        if reviewer_id is not None:
            query = query.filter(CertificationItem.reviewer_identity_id == reviewer_id)
        return query.all()

    def decide(self, item_id: int, payload: CertificationDecision, actor_id: int) -> CertificationItem:
        item = self._require(CertificationItem, item_id, "Certification item not found.")
        if item.reviewer_identity_id not in {None, actor_id}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned reviewer may decide this item.")
        if payload.decision not in {"keep", "revoke"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Decision must be keep or revoke.")
        item.decision = payload.decision
        item.status = "completed"
        item.decision_notes = payload.notes
        item.decided_at = datetime.now(UTC)
        self.session.add(EvidenceRecord(domain="certification", entity_type="certification_item", entity_id=item.id, evidence_type="review_decision", content=f"{payload.decision}: {payload.notes}", actor_identity_id=actor_id))
        if payload.decision == "revoke":
            self.session.add(
                ProvisioningTask(
                    access_request_id=None,
                    identity_id=item.identity_id,
                    resource_id=item.resource_id,
                    task_type="certification_revoke",
                    owner_role="operator",
                    status="pending",
                    urgency="high",
                    details=f"Certification item {item.id} requested revoke.",
                )
            )
        self._audit(actor_id, f"certification.{payload.decision}", "certification_item", item.id, payload.notes or payload.decision)
        return item

    def close_campaign(self, campaign_id: int, actor_id: int | None) -> CertificationCampaign:
        campaign = self._require(CertificationCampaign, campaign_id, "Campaign not found.")
        open_items = self.session.query(CertificationItem).filter(CertificationItem.campaign_id == campaign_id, CertificationItem.status != "completed").count()
        if open_items:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Campaign has open review items.")
        campaign.status = "closed"
        campaign.closed_at = datetime.now(UTC)
        self._audit(actor_id, "certification.campaign_closed", "certification_campaign", campaign.id, "Closed campaign.")
        return campaign

    def _manager_for(self, identity_id: int) -> int | None:
        identity = self.session.get(Identity, identity_id)
        return identity.manager_id if identity else None

    def _audit(self, actor_id: int | None, event_type: str, entity_type: str, entity_id: int | None, details: str) -> None:
        record_audit(self.session, actor_identity_id=actor_id, event_type=event_type, entity_type=entity_type, entity_id=entity_id, details=details)

    def _require(self, model, entity_id: int, message: str):
        item = self.session.get(model, entity_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
        return item


class PamService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_secret(self, payload: PamSecretCreate, actor_id: int) -> PamVaultSecret:
        secret = PamVaultSecret(name=payload.name, system_id=payload.system_id, resource_id=payload.resource_id, account_username=payload.account_username, rotation_interval_days=payload.rotation_interval_days)
        self.session.add(secret)
        self.session.flush()
        version = PamSecretVersion(secret_id=secret.id, version_number=1, encrypted_secret=encode_secret(payload.secret_value), created_by_identity_id=actor_id)
        self.session.add(version)
        self.session.flush()
        secret.current_version_id = version.id
        self._audit(actor_id, "pam.secret_created", "pam_secret", secret.id, f"Created vault secret {secret.name}.")
        return secret

    def list_secrets(self) -> list[PamVaultSecret]:
        return self.session.query(PamVaultSecret).order_by(PamVaultSecret.id).all()

    def checkout(self, secret_id: int, payload: PamCheckoutCreate, actor_id: int, *, break_glass: bool = False) -> tuple[PamCheckout, str]:
        secret = self._require(PamVaultSecret, secret_id, "Secret not found.")
        active = self.session.query(PamCheckout).filter(PamCheckout.secret_id == secret_id, PamCheckout.status == "checked_out").first()
        if active and not break_glass:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Secret is already checked out.")
        checkout = PamCheckout(secret_id=secret_id, requester_identity_id=actor_id, reason=payload.reason, due_back_at=datetime.now(UTC) + timedelta(minutes=payload.duration_minutes), break_glass=break_glass)
        self.session.add(checkout)
        version = self._require(PamSecretVersion, int(secret.current_version_id or 0), "Secret version not found.")
        revealed = decode_secret(version.encrypted_secret)
        event = "pam.break_glass_checkout" if break_glass else "pam.checkout"
        self._audit(actor_id, event, "pam_secret", secret.id, f"{event}: {mask_secret(revealed)}")
        return checkout, revealed

    def checkin(self, checkout_id: int, actor_id: int) -> PamCheckout:
        checkout = self._require(PamCheckout, checkout_id, "Checkout not found.")
        if checkout.requester_identity_id != actor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the requester can check in.")
        checkout.status = "checked_in"
        checkout.checked_in_at = datetime.now(UTC)
        self._audit(actor_id, "pam.checkin", "pam_checkout", checkout.id, "Checked in privileged credential.")
        return checkout

    def create_jit(self, payload: PamJitAccessCreate, actor_id: int) -> PamJitAccess:
        item = PamJitAccess(identity_id=actor_id, resource_id=payload.resource_id, reason=payload.reason, starts_at=datetime.now(UTC), expires_at=datetime.now(UTC) + timedelta(minutes=payload.duration_minutes))
        self.session.add(item)
        self._audit(actor_id, "pam.jit_created", "pam_jit_access", None, payload.reason)
        return item

    def list_checkouts(self) -> list[PamCheckout]:
        return self.session.query(PamCheckout).order_by(PamCheckout.id).all()

    def terminate_identity(self, identity_id: int, actor_id: int | None) -> int:
        count = 0
        for checkout in self.session.query(PamCheckout).filter(PamCheckout.requester_identity_id == identity_id, PamCheckout.status == "checked_out").all():
            checkout.status = "terminated"
            checkout.checked_in_at = datetime.now(UTC)
            count += 1
        for jit in self.session.query(PamJitAccess).filter(PamJitAccess.identity_id == identity_id, PamJitAccess.status == "active").all():
            jit.status = "terminated"
        if count:
            self._audit(actor_id, "pam.emergency_terminated", "identity", identity_id, f"Terminated {count} active privileged checkout(s).")
        return count

    def _audit(self, actor_id: int | None, event_type: str, entity_type: str, entity_id: int | None, details: str) -> None:
        record_audit(self.session, actor_identity_id=actor_id, event_type=event_type, entity_type=entity_type, entity_id=entity_id, details=details)

    def _require(self, model, entity_id: int, message: str):
        item = self.session.get(model, entity_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
        return item


class ConnectorService:
    CONNECTOR_TYPES = {"csv", "scim", "ldap", "ad", "google_workspace", "jira", "github", "rest"}

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, payload: ConnectorCreate, actor_id: int) -> Connector:
        if payload.connector_type not in self.CONNECTOR_TYPES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported connector type.")
        if payload.connector_type == "scim" and payload.system_id is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="SCIM connectors require a system_id.")
        if payload.system_id is not None and not self.session.get(System, payload.system_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found.")
        connector = Connector(name=payload.name, connector_type=payload.connector_type, system_id=payload.system_id, dry_run=payload.dry_run, config_json=json.dumps(payload.config), secret_ref=encode_secret(payload.secret) if payload.secret else "")
        self.session.add(connector)
        self.session.flush()
        self._audit(actor_id, "connector.created", "connector", connector.id, f"Created {connector.connector_type} connector.")
        return connector

    def list(self) -> list[Connector]:
        return self.session.query(Connector).order_by(Connector.id).all()

    def test(self, connector_id: int, actor_id: int) -> ConnectorRun:
        connector = self._require(Connector, connector_id, "Connector not found.")
        connector.last_test_status = "ok"
        adapter = build_connector(connector.connector_type, json.loads(connector.config_json or "{}"))
        result = adapter.test_connection()
        return self._run(connector, "test_connection", actor_id, result.summary)

    def run(self, connector_id: int, operation: str, actor_id: int) -> ConnectorRun:
        connector = self._require(Connector, connector_id, "Connector not found.")
        if operation not in {"discover", "import", "sync", "provision", "deprovision", "group_sync", "reconcile"}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported connector operation.")
        adapter = build_connector(connector.connector_type, json.loads(connector.config_json or "{}"))
        if operation == "discover":
            result = adapter.discover()
        elif operation in {"import", "sync"}:
            result = adapter.import_sync()
        elif operation == "provision":
            result = adapter.provision({})
        elif operation == "deprovision":
            result = adapter.deprovision({})
        elif operation == "group_sync":
            result = adapter.group_sync()
        else:
            result = adapter.reconcile()
        return self._run(connector, operation, actor_id, result.summary)

    def list_runs(self) -> list[ConnectorRun]:
        return self.session.query(ConnectorRun).order_by(ConnectorRun.id).all()

    def _run(self, connector: Connector, operation: str, actor_id: int, summary: str) -> ConnectorRun:
        run = ConnectorRun(connector_id=connector.id, operation=operation, status="completed", dry_run=connector.dry_run, summary=summary, started_at=datetime.now(UTC), completed_at=datetime.now(UTC))
        self.session.add(run)
        self._audit(actor_id, f"connector.{operation}", "connector", connector.id, summary)
        return run

    def _audit(self, actor_id: int | None, event_type: str, entity_type: str, entity_id: int | None, details: str) -> None:
        record_audit(self.session, actor_identity_id=actor_id, event_type=event_type, entity_type=entity_type, entity_id=entity_id, details=details)

    def _require(self, model, entity_id: int, message: str):
        item = self.session.get(model, entity_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
        return item


class JobService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, payload: SchedulerJobCreate, actor_id: int | None) -> SchedulerJob:
        job = SchedulerJob(job_type=payload.job_type, payload_json=json.dumps(payload.payload), run_after=payload.run_after)
        self.session.add(job)
        record_audit(self.session, actor_identity_id=actor_id, event_type="job.created", entity_type="scheduler_job", entity_id=None, details=payload.job_type)
        return job

    def list(self) -> list[SchedulerJob]:
        return self.session.query(SchedulerJob).order_by(SchedulerJob.id).all()

    def run_next(self, actor_id: int | None) -> SchedulerJob | None:
        now = datetime.now(UTC)
        job = self.session.query(SchedulerJob).filter(SchedulerJob.status == "queued", or_(SchedulerJob.run_after.is_(None), SchedulerJob.run_after <= now)).order_by(SchedulerJob.id).first()
        if not job:
            return None
        job.status = "completed"
        job.attempts += 1
        job.updated_at = now
        record_audit(self.session, actor_identity_id=actor_id, event_type="job.completed", entity_type="scheduler_job", entity_id=job.id, details=job.job_type)
        return job


class ConnectorQueryService:
    OPERATIONS = {"discover", "import", "sync", "provision", "deprovision", "group_sync", "reconcile"}

    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[ConnectorQueryRead]:
        return [ConnectorQueryRead.model_validate(item) for item in self.session.query(ConnectorQuery).order_by(ConnectorQuery.id).all()]

    def create(self, payload: ConnectorQueryCreate, actor_id: int) -> ConnectorQueryRead:
        self._validate(payload)
        item = ConnectorQuery(name=payload.name, system_id=payload.system_id, connector_id=payload.connector_id, operation=payload.operation, query_json=json.dumps(payload.query), active=payload.active)
        self.session.add(item)
        self.session.flush()
        record_audit(self.session, actor_identity_id=actor_id, event_type="connector_query.created", entity_type="connector_query", entity_id=item.id, details=item.name)
        return ConnectorQueryRead.model_validate(item)

    def update(self, query_id: int, payload: ConnectorQueryUpdate, actor_id: int) -> ConnectorQueryRead:
        item = self._require(ConnectorQuery, query_id, "Connector query not found.")
        self._validate(payload)
        item.name = payload.name
        item.system_id = payload.system_id
        item.connector_id = payload.connector_id
        item.operation = payload.operation
        item.query_json = json.dumps(payload.query)
        item.active = payload.active
        record_audit(self.session, actor_identity_id=actor_id, event_type="connector_query.updated", entity_type="connector_query", entity_id=item.id, details=item.name)
        return ConnectorQueryRead.model_validate(item)

    def delete(self, query_id: int, actor_id: int) -> None:
        item = self._require(ConnectorQuery, query_id, "Connector query not found.")
        self.session.delete(item)
        record_audit(self.session, actor_identity_id=actor_id, event_type="connector_query.deleted", entity_type="connector_query", entity_id=query_id, details=item.name)

    def run(self, query_id: int, actor_id: int) -> ConnectorRun:
        item = self._require(ConnectorQuery, query_id, "Connector query not found.")
        if not item.active:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Connector query is inactive.")
        return ConnectorService(self.session).run(item.connector_id, item.operation, actor_id)

    def _validate(self, payload: ConnectorQueryCreate | ConnectorQueryUpdate) -> None:
        if payload.operation not in self.OPERATIONS:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported connector operation.")
        if not self.session.get(System, payload.system_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found.")
        connector = self.session.get(Connector, payload.connector_id)
        if not connector:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found.")
        if connector.system_id is not None and connector.system_id != payload.system_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Connector does not belong to system.")

    def _require(self, model, entity_id: int, message: str):
        item = self.session.get(model, entity_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
        return item


class ScimService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_users(self) -> list[dict[str, Any]]:
        return [self._user_resource(item) for item in self.session.query(ScimUser).order_by(ScimUser.id).all()]

    def create_user(self, payload: ScimUserPayload, actor_id: int | None = None) -> dict[str, Any]:
        scim_id = uuid4().hex
        email = payload.emails[0].get("value") if payload.emails else f"{payload.userName}@scim.local"
        identity = self.session.query(Identity).filter(Identity.username == payload.userName).first()
        if not identity:
            from shared.auth.security import hash_password

            identity = Identity(username=payload.userName, full_name=payload.displayName or payload.userName, email=email, role="employee", status="active" if payload.active else "disabled", password_hash=hash_password("ChangeMe123!"))
            self.session.add(identity)
            self.session.flush()
        user = ScimUser(scim_id=scim_id, identity_id=identity.id, user_name=payload.userName, display_name=payload.displayName or identity.full_name, active=payload.active, raw_json=payload.model_dump_json())
        self.session.add(user)
        self.session.flush()
        record_audit(self.session, actor_identity_id=actor_id, event_type="scim.user_created", entity_type="scim_user", entity_id=user.id, details=user.user_name)
        return self._user_resource(user)

    def list_groups(self) -> list[dict[str, Any]]:
        return [self._group_resource(item) for item in self.session.query(ScimGroup).order_by(ScimGroup.id).all()]

    def create_group(self, payload: ScimGroupPayload, actor_id: int | None = None) -> dict[str, Any]:
        group = ScimGroup(scim_id=uuid4().hex, display_name=payload.displayName, raw_json=payload.model_dump_json())
        self.session.add(group)
        self.session.flush()
        for member in payload.members:
            value = str(member.get("value", ""))
            user = self.session.query(ScimUser).filter(ScimUser.scim_id == value).first()
            if user:
                self.session.add(ScimGroupMembership(group_id=group.id, user_id=user.id))
        record_audit(self.session, actor_identity_id=actor_id, event_type="scim.group_created", entity_type="scim_group", entity_id=group.id, details=group.display_name)
        return self._group_resource(group)

    def list_mappings(self) -> list[dict[str, Any]]:
        return [self._mapping_resource(item) for item in self.session.query(ScimMapping).order_by(ScimMapping.id).all()]

    def create_mapping(self, payload: ScimMappingCreate, actor_id: int | None = None) -> dict[str, Any]:
        self._require_group_and_resource(payload.scim_group_id, payload.resource_id)
        mapping = ScimMapping(
            direction=payload.direction,
            source_path=f"Groups:{payload.scim_group_id}",
            target_path=f"resources:{payload.resource_id}",
            active=payload.active,
        )
        self.session.add(mapping)
        self.session.flush()
        record_audit(self.session, actor_identity_id=actor_id, event_type="scim.mapping_created", entity_type="scim_mapping", entity_id=mapping.id, details=mapping.source_path)
        return self._mapping_resource(mapping)

    def update_mapping(self, mapping_id: int, payload: ScimMappingUpdate, actor_id: int | None = None) -> dict[str, Any]:
        mapping = self._require(ScimMapping, mapping_id, "SCIM mapping not found.")
        self._require_group_and_resource(payload.scim_group_id, payload.resource_id)
        mapping.direction = payload.direction
        mapping.source_path = f"Groups:{payload.scim_group_id}"
        mapping.target_path = f"resources:{payload.resource_id}"
        mapping.active = payload.active
        record_audit(self.session, actor_identity_id=actor_id, event_type="scim.mapping_updated", entity_type="scim_mapping", entity_id=mapping.id, details=mapping.source_path)
        return self._mapping_resource(mapping)

    def delete_mapping(self, mapping_id: int, actor_id: int | None = None) -> None:
        mapping = self._require(ScimMapping, mapping_id, "SCIM mapping not found.")
        self.session.delete(mapping)
        record_audit(self.session, actor_identity_id=actor_id, event_type="scim.mapping_deleted", entity_type="scim_mapping", entity_id=mapping_id, details=mapping.source_path)

    def _user_resource(self, user: ScimUser) -> dict[str, Any]:
        return {"id": user.scim_id, "userName": user.user_name, "displayName": user.display_name, "active": user.active}

    def _group_resource(self, group: ScimGroup) -> dict[str, Any]:
        members = [
            {"value": user.scim_id, "display": user.display_name or user.user_name}
            for user in self.session.query(ScimUser).join(ScimGroupMembership, ScimGroupMembership.user_id == ScimUser.id).filter(ScimGroupMembership.group_id == group.id).all()
        ]
        return {"id": group.scim_id, "displayName": group.display_name, "members": members}

    def _mapping_resource(self, mapping: ScimMapping) -> dict[str, Any]:
        return {
            "id": mapping.id,
            "direction": mapping.direction,
            "source_path": mapping.source_path,
            "target_path": mapping.target_path,
            "active": mapping.active,
            "scim_group_id": self._path_value(mapping.source_path, "Groups"),
            "resource_id": self._int_path_value(mapping.target_path, "resources"),
        }

    def _require_group_and_resource(self, scim_group_id: str, resource_id: int) -> None:
        if not self.session.query(ScimGroup).filter(ScimGroup.scim_id == scim_group_id).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SCIM group not found.")
        if not self.session.get(Resource, resource_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found.")

    def _require(self, model, entity_id: int, message: str):
        item = self.session.get(model, entity_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
        return item

    def _path_value(self, path: str, prefix: str) -> str | None:
        marker = f"{prefix}:"
        return path[len(marker) :] if path.startswith(marker) else None

    def _int_path_value(self, path: str, prefix: str) -> int | None:
        value = self._path_value(path, prefix)
        return int(value) if value and value.isdigit() else None

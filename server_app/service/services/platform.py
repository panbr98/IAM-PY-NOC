from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from io import StringIO

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from server_app.core.audit import record_audit
from server_app.core.models import (
    AccessRequest,
    Approval,
    AuditEvent,
    ConfigEntry,
    Delegation,
    Identity,
    ProvisioningTask,
    Resource,
    ResourceAssignment,
    System,
    TaskMapping,
)
from shared.schemas.domain import (
    AccessRequestCreate,
    ApprovalDecisionRequest,
    DashboardSummary,
    DelegationCreate,
    DelegationUpdate,
    IdentityCreate,
    IdentityImportRequest,
    IdentityImportResult,
    IdentityUpdate,
    ProvisioningTaskComplete,
    ResourceCreate,
    ResourceUpdate,
    SettingsRead,
    SettingsUpdate,
    SetupWizardBootstrapRequest,
    SetupWizardStatus,
    SystemCreate,
    SystemUpdate,
    TaskMappingCreate,
    TaskMappingUpdate,
)


class PlatformService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_setup_status(self) -> SetupWizardStatus:
        entries = {item.key: item.value for item in self.session.query(ConfigEntry).all()}
        return SetupWizardStatus(
            configured=entries.get("setup.configured", "false").lower() == "true",
            company_name=entries.get("company.name", "Example Company"),
            environment=entries.get("environment", "demo"),
            super_admin_username=entries.get("super_admin.username"),
            database_url=entries.get("database.url"),
            tls_enabled=entries.get("tls.enabled", "false").lower() == "true",
            fingerprint=entries.get("server.fingerprint"),
        )

    def get_server_info(self, host: str, port: int, product_name: str) -> dict[str, str | int]:
        status_payload = self.get_setup_status()
        return {
            "product_name": product_name,
            "environment": status_payload.environment,
            "company_name": status_payload.company_name,
            "host": host,
            "port": port,
            "fingerprint": status_payload.fingerprint or "UNSET",
            "health": "ok",
        }

    def get_settings(self, default_database_url: str) -> SettingsRead:
        status_payload = self.get_setup_status()
        return SettingsRead(
            company_name=status_payload.company_name,
            environment=status_payload.environment,
            database_url=status_payload.database_url or default_database_url,
            tls_enabled=status_payload.tls_enabled,
            fingerprint=status_payload.fingerprint or "UNSET",
        )

    def update_settings(self, payload: SettingsUpdate, actor_id: int | None) -> SettingsRead:
        self._set_config("company.name", payload.company_name)
        self._set_config("environment", payload.environment)
        self._set_config("database.url", payload.database_url)
        self._set_config("tls.enabled", str(payload.tls_enabled).lower())
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="settings.updated",
            entity_type="platform",
            entity_id=None,
            details=f"Updated company={payload.company_name}, environment={payload.environment}, tls={payload.tls_enabled}.",
        )
        return self.get_settings(payload.database_url)

    def bootstrap_setup(self, payload: SetupWizardBootstrapRequest) -> SetupWizardStatus:
        admin = self.session.query(Identity).filter(Identity.role == "super_admin").first()
        if admin:
            admin.username = payload.super_admin_username
            admin.full_name = payload.super_admin_full_name
            admin.email = payload.super_admin_email
            from shared.auth.security import hash_password

            admin.password_hash = hash_password(payload.super_admin_password)

        self._set_config("setup.configured", "true")
        self._set_config("company.name", payload.company_name)
        self._set_config("environment", payload.environment)
        self._set_config("super_admin.username", payload.super_admin_username)

        if payload.import_sample_data:
            self._ensure_sample_data(admin.id if admin else None)

        record_audit(
            self.session,
            actor_identity_id=admin.id if admin else None,
            event_type="setup.bootstrap_completed",
            entity_type="platform",
            entity_id=None,
            details=f"Configured {payload.company_name} in {payload.environment} mode.",
        )
        return self.get_setup_status()

    def get_dashboard_summary(self) -> DashboardSummary:
        return DashboardSummary(
            identities=self.session.query(func.count(Identity.id)).scalar() or 0,
            systems=self.session.query(func.count(System.id)).scalar() or 0,
            resources=self.session.query(func.count(Resource.id)).scalar() or 0,
            open_requests=self.session.query(func.count(AccessRequest.id)).filter(
                AccessRequest.status.in_(["submitted", "provisioning"])
            ).scalar()
            or 0,
            pending_approvals=self.session.query(func.count(Approval.id)).filter(
                Approval.status == "pending"
            ).scalar()
            or 0,
            pending_tasks=self.session.query(func.count(ProvisioningTask.id)).filter(
                ProvisioningTask.status == "pending"
            ).scalar()
            or 0,
            active_assignments=self.session.query(func.count(ResourceAssignment.id)).filter(
                ResourceAssignment.status == "active"
            ).scalar()
            or 0,
            critical_audit_events=self.session.query(func.count(AuditEvent.id)).filter(
                AuditEvent.severity == "critical"
            ).scalar()
            or 0,
        )

    def create_identity(self, payload: IdentityCreate, actor_id: int) -> Identity:
        from shared.auth.security import hash_password

        self._ensure_unique_identity(username=payload.username, email=payload.email)
        identity = Identity(
            username=payload.username,
            full_name=payload.full_name,
            email=payload.email,
            role=payload.role,
            manager_id=payload.manager_id,
            password_hash=hash_password("ChangeMe123!"),
            status="active",
        )
        self.session.add(identity)
        self.session.flush()
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="identity.created",
            entity_type="identity",
            entity_id=identity.id,
            details=f"Created identity {identity.username}.",
        )
        return identity

    def update_identity(self, identity_id: int, payload: IdentityUpdate, actor_id: int) -> Identity:
        identity = self._require_entity(Identity, identity_id, "Identity not found.")
        existing = self.session.query(Identity).filter(
            Identity.email == payload.email,
            Identity.id != identity_id,
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use.")
        identity.full_name = payload.full_name
        identity.email = payload.email
        identity.role = payload.role
        identity.manager_id = payload.manager_id
        identity.status = payload.status
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="identity.updated",
            entity_type="identity",
            entity_id=identity.id,
            details=f"Updated identity {identity.username}.",
        )
        return identity

    def delete_identity(self, identity_id: int, actor_id: int) -> None:
        identity = self._require_entity(Identity, identity_id, "Identity not found.")
        has_refs = any(
            [
                self.session.query(AccessRequest).filter(
                    (AccessRequest.requester_identity_id == identity_id)
                    | (AccessRequest.beneficiary_identity_id == identity_id)
                    | (AccessRequest.manager_identity_id == identity_id)
                ).first(),
                self.session.query(Approval).filter(Approval.approver_identity_id == identity_id).first(),
                self.session.query(ResourceAssignment).filter(ResourceAssignment.identity_id == identity_id).first(),
                self.session.query(ProvisioningTask).filter(ProvisioningTask.identity_id == identity_id).first(),
                self.session.query(Delegation).filter(
                    (Delegation.delegator_identity_id == identity_id)
                    | (Delegation.delegate_identity_id == identity_id)
                ).first(),
            ]
        )
        if has_refs:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Identity has related workflow records and cannot be deleted.",
            )
        self.session.delete(identity)
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="identity.deleted",
            entity_type="identity",
            entity_id=identity_id,
            details=f"Deleted identity {identity.username}.",
        )

    def import_identities_from_csv(self, payload: IdentityImportRequest, actor_id: int) -> IdentityImportResult:
        reader = csv.DictReader(StringIO(payload.csv_data.strip()))
        created_count = 0
        skipped_count = 0
        usernames: list[str] = []
        skipped_rows: list[str] = []

        for index, row in enumerate(reader, start=2):
            username = (row.get("username") or "").strip()
            email = (row.get("email") or "").strip()
            full_name = (row.get("full_name") or username).strip()
            if not username or not email:
                skipped_count += 1
                skipped_rows.append(f"row {index}: missing username or email")
                continue
            exists = self.session.query(Identity).filter(
                (Identity.username == username) | (Identity.email == email)
            ).first()
            if exists:
                skipped_count += 1
                skipped_rows.append(f"row {index}: duplicate username or email")
                continue

            manager_username = (row.get("manager_username") or "").strip()
            manager = None
            if manager_username:
                manager = self.session.query(Identity).filter(Identity.username == manager_username).first()

            identity = self.create_identity(
                IdentityCreate(
                    username=username,
                    full_name=full_name,
                    email=email,
                    role=(row.get("role") or payload.default_role).strip() or payload.default_role,
                    manager_id=manager.id if manager else None,
                ),
                actor_id,
            )
            created_count += 1
            usernames.append(identity.username)

        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="identity.csv_imported",
            entity_type="identity",
            entity_id=None,
            details=f"Created {created_count} identities and skipped {skipped_count}.",
        )
        return IdentityImportResult(
            created_count=created_count,
            skipped_count=skipped_count,
            usernames=usernames,
            skipped_rows=skipped_rows,
        )

    def create_system(self, payload: SystemCreate, actor_id: int) -> System:
        self._ensure_unique_name(System, payload.name, "System name already exists.")
        system = System(**payload.model_dump())
        self.session.add(system)
        self.session.flush()
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="system.created",
            entity_type="system",
            entity_id=system.id,
            details=f"Created system {system.name}.",
        )
        return system

    def update_system(self, system_id: int, payload: SystemUpdate, actor_id: int) -> System:
        system = self._require_entity(System, system_id, "System not found.")
        self._ensure_unique_name(System, payload.name, "System name already exists.", system_id)
        system.name = payload.name
        system.description = payload.description
        system.owner_identity_id = payload.owner_identity_id
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="system.updated",
            entity_type="system",
            entity_id=system.id,
            details=f"Updated system {system.name}.",
        )
        return system

    def delete_system(self, system_id: int, actor_id: int) -> None:
        system = self._require_entity(System, system_id, "System not found.")
        if self.session.query(Resource).filter(Resource.system_id == system_id).first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="System still has resources.")
        self.session.delete(system)
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="system.deleted",
            entity_type="system",
            entity_id=system_id,
            details=f"Deleted system {system.name}.",
        )

    def create_resource(self, payload: ResourceCreate, actor_id: int) -> Resource:
        self._require_entity(System, payload.system_id, "System not found.")
        resource = Resource(**payload.model_dump())
        self.session.add(resource)
        self.session.flush()
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="resource.created",
            entity_type="resource",
            entity_id=resource.id,
            details=f"Created resource {resource.name}.",
        )
        return resource

    def update_resource(self, resource_id: int, payload: ResourceUpdate, actor_id: int) -> Resource:
        resource = self._require_entity(Resource, resource_id, "Resource not found.")
        self._require_entity(System, payload.system_id, "System not found.")
        resource.name = payload.name
        resource.system_id = payload.system_id
        resource.requestable = payload.requestable
        resource.description = payload.description
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="resource.updated",
            entity_type="resource",
            entity_id=resource.id,
            details=f"Updated resource {resource.name}.",
        )
        return resource

    def delete_resource(self, resource_id: int, actor_id: int) -> None:
        resource = self._require_entity(Resource, resource_id, "Resource not found.")
        has_refs = any(
            [
                self.session.query(AccessRequest).filter(AccessRequest.resource_id == resource_id).first(),
                self.session.query(ResourceAssignment).filter(ResourceAssignment.resource_id == resource_id).first(),
                self.session.query(TaskMapping).filter(TaskMapping.resource_id == resource_id).first(),
                self.session.query(ProvisioningTask).filter(ProvisioningTask.resource_id == resource_id).first(),
            ]
        )
        if has_refs:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resource has related workflow records and cannot be deleted.",
            )
        self.session.delete(resource)
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="resource.deleted",
            entity_type="resource",
            entity_id=resource_id,
            details=f"Deleted resource {resource.name}.",
        )

    def create_task_mapping(self, payload: TaskMappingCreate, actor_id: int) -> TaskMapping:
        values = self._task_mapping_values(payload)
        task_mapping = TaskMapping(**values)
        self.session.add(task_mapping)
        self.session.flush()
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="task_mapping.created",
            entity_type="task_mapping",
            entity_id=task_mapping.id,
            details="Created provisioning task mapping.",
        )
        return task_mapping

    def update_task_mapping(self, mapping_id: int, payload: TaskMappingUpdate, actor_id: int) -> TaskMapping:
        task_mapping = self._require_entity(TaskMapping, mapping_id, "Task mapping not found.")
        self._task_mapping_values(payload)
        task_mapping.system_id = payload.system_id
        task_mapping.resource_id = payload.resource_id
        task_mapping.action = payload.action
        task_mapping.trigger_event = payload.trigger_event
        task_mapping.task_type = payload.task_type
        task_mapping.default_owner_role = payload.default_owner_role
        task_mapping.sla_hours = payload.sla_hours
        task_mapping.provisioning_mode = payload.provisioning_mode
        task_mapping.connector_id = payload.connector_id
        task_mapping.connector_operation = payload.connector_operation
        task_mapping.connector_query_id = payload.connector_query_id
        task_mapping.payload_template_json = json.dumps(payload.payload_template)
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="task_mapping.updated",
            entity_type="task_mapping",
            entity_id=task_mapping.id,
            details="Updated provisioning task mapping.",
        )
        return task_mapping

    def _task_mapping_values(self, payload: TaskMappingCreate | TaskMappingUpdate) -> dict:
        if payload.provisioning_mode == "automatic" and not payload.connector_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Automatic provisioning requires connector_id.")
        if payload.provisioning_mode == "automatic" and not payload.connector_operation:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Automatic provisioning requires connector_operation.")
        self._require_entity(System, payload.system_id, "System not found.")
        resource = self._require_entity(Resource, payload.resource_id, "Resource not found.")
        if resource.system_id != payload.system_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Resource does not belong to system.")
        values = payload.model_dump(exclude={"payload_template"})
        values["payload_template_json"] = json.dumps(payload.payload_template)
        return values

    def delete_task_mapping(self, mapping_id: int, actor_id: int) -> None:
        task_mapping = self._require_entity(TaskMapping, mapping_id, "Task mapping not found.")
        self.session.delete(task_mapping)
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="task_mapping.deleted",
            entity_type="task_mapping",
            entity_id=mapping_id,
            details="Deleted provisioning task mapping.",
        )

    def submit_access_request(self, payload: AccessRequestCreate, actor: Identity) -> AccessRequest:
        beneficiary = self.session.get(Identity, payload.beneficiary_identity_id)
        resource = self.session.get(Resource, payload.resource_id)
        if not beneficiary or not resource:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beneficiary or resource not found.")

        access_request = AccessRequest(
            requester_identity_id=actor.id,
            beneficiary_identity_id=payload.beneficiary_identity_id,
            resource_id=payload.resource_id,
            manager_identity_id=beneficiary.manager_id,
            reason=payload.reason,
            start_date=payload.start_date,
            end_date=payload.end_date,
            urgency=payload.urgency,
            comments=payload.comments,
            status="submitted",
        )
        self.session.add(access_request)
        self.session.flush()

        if beneficiary.manager_id:
            approval = Approval(
                access_request_id=access_request.id,
                approver_identity_id=beneficiary.manager_id,
                decision="pending",
                comment="",
                status="pending",
            )
            self.session.add(approval)

        record_audit(
            self.session,
            actor_identity_id=actor.id,
            event_type="access_request.submitted",
            entity_type="access_request",
            entity_id=access_request.id,
            details=f"Requested resource {resource.name} for {beneficiary.username}.",
        )
        return access_request

    def decide_approval(
        self,
        *,
        request_id: int,
        decision: ApprovalDecisionRequest,
        actor: Identity,
    ) -> Approval:
        approval = (
            self.session.query(Approval)
            .filter(Approval.access_request_id == request_id, Approval.approver_identity_id == actor.id)
            .first()
        )
        if not approval:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found for actor.")
        if approval.status != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval already decided.")

        access_request = self.session.get(AccessRequest, request_id)
        if not access_request:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access request not found.")

        approval.decision = decision.decision
        approval.comment = decision.comment
        approval.status = "completed"

        if decision.decision == "reject":
            access_request.status = "rejected"
            record_audit(
                self.session,
                actor_identity_id=actor.id,
                event_type="approval.rejected",
                entity_type="access_request",
                entity_id=access_request.id,
                details=decision.comment,
            )
            return approval

        access_request.status = "provisioning"
        mapping = (
            self.session.query(TaskMapping)
            .filter(TaskMapping.resource_id == access_request.resource_id, TaskMapping.action == "grant")
            .first()
        )
        if not mapping:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No task mapping defined for the requested resource.",
            )

        task = ProvisioningTask(
            access_request_id=access_request.id,
            identity_id=access_request.beneficiary_identity_id,
            resource_id=access_request.resource_id,
            task_type=mapping.task_type,
            owner_role=mapping.default_owner_role,
            status="pending",
            urgency=access_request.urgency,
            details=f"Manual provisioning for access request {access_request.id}.",
        )
        self.session.add(task)
        self.session.flush()

        record_audit(
            self.session,
            actor_identity_id=actor.id,
            event_type="approval.approved",
            entity_type="access_request",
            entity_id=access_request.id,
            details=f"Created provisioning task {task.id}.",
        )
        return approval

    def complete_task(
        self,
        *,
        task_id: int,
        payload: ProvisioningTaskComplete,
        actor: Identity,
    ) -> ProvisioningTask:
        task = self.session.get(ProvisioningTask, task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        if task.status == "completed":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task already completed.")

        task.status = "completed"
        task.details = f"{task.details}\n{payload.completion_notes}".strip()

        if task.access_request_id and task.resource_id:
            assignment = ResourceAssignment(
                identity_id=task.identity_id,
                resource_id=task.resource_id,
                status="active",
                granted_at=datetime.now(UTC),
            )
            self.session.add(assignment)

            request = self.session.get(AccessRequest, task.access_request_id)
            if request:
                request.status = "completed"

        record_audit(
            self.session,
            actor_identity_id=actor.id,
            event_type="provisioning.completed",
            entity_type="provisioning_task",
            entity_id=task.id,
            details=payload.completion_notes,
        )
        return task

    def create_delegation(self, payload: DelegationCreate, actor_id: int) -> Delegation:
        starts_at = self._ensure_utc(payload.starts_at)
        ends_at = self._ensure_utc(payload.ends_at)
        delegation = Delegation(
            delegator_identity_id=payload.delegator_identity_id,
            delegate_identity_id=payload.delegate_identity_id,
            scope=payload.scope,
            starts_at=starts_at,
            ends_at=ends_at,
            status="active" if starts_at <= datetime.now(UTC) <= ends_at else "draft",
        )
        self.session.add(delegation)
        self.session.flush()
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="delegation.created",
            entity_type="delegation",
            entity_id=delegation.id,
            details=f"Delegated {delegation.scope}.",
        )
        return delegation

    def update_delegation(self, delegation_id: int, payload: DelegationUpdate, actor_id: int) -> Delegation:
        delegation = self._require_entity(Delegation, delegation_id, "Delegation not found.")
        delegation.scope = payload.scope
        delegation.starts_at = self._ensure_utc(payload.starts_at)
        delegation.ends_at = self._ensure_utc(payload.ends_at)
        delegation.status = payload.status
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="delegation.updated",
            entity_type="delegation",
            entity_id=delegation.id,
            details=f"Updated delegation status to {delegation.status}.",
        )
        return delegation

    def delete_delegation(self, delegation_id: int, actor_id: int) -> None:
        delegation = self._require_entity(Delegation, delegation_id, "Delegation not found.")
        self.session.delete(delegation)
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type="delegation.deleted",
            entity_type="delegation",
            entity_id=delegation_id,
            details="Deleted delegation.",
        )

    def emergency_terminate(self, *, identity_id: int, actor: Identity) -> Identity:
        identity = self.session.get(Identity, identity_id)
        if not identity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found.")

        identity.status = "terminated"

        open_requests = (
            self.session.query(AccessRequest)
            .filter(
                AccessRequest.beneficiary_identity_id == identity_id,
                AccessRequest.status.in_(["submitted", "approved", "provisioning"]),
            )
            .all()
        )
        for request in open_requests:
            request.status = "cancelled"

        active_assignments = (
            self.session.query(ResourceAssignment)
            .filter(ResourceAssignment.identity_id == identity_id, ResourceAssignment.status == "active")
            .all()
        )
        for assignment in active_assignments:
            assignment.status = "revocation_pending"
            task = ProvisioningTask(
                access_request_id=None,
                identity_id=identity_id,
                resource_id=assignment.resource_id,
                task_type="urgent_deprovision",
                owner_role="operator",
                status="pending",
                urgency="critical",
                details=f"Emergency termination for assignment {assignment.id}.",
            )
            self.session.add(task)

        from server_app.service.services.phase_domains import PamService

        terminated_checkouts = PamService(self.session).terminate_identity(identity_id, actor.id)

        record_audit(
            self.session,
            actor_identity_id=actor.id,
            event_type="identity.emergency_terminated",
            entity_type="identity",
            entity_id=identity.id,
            severity="critical",
            details=f"Identity disabled, pending work cancelled, urgent deprovision created, PAM checkouts terminated={terminated_checkouts}.",
        )
        return identity

    def get_audit_events(
        self,
        *,
        severity: str | None = None,
        entity_type: str | None = None,
        search: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        query = self.session.query(AuditEvent).order_by(AuditEvent.id.desc())
        if severity:
            query = query.filter(AuditEvent.severity == severity)
        if entity_type:
            query = query.filter(AuditEvent.entity_type == entity_type)
        if search:
            query = query.filter(
                or_(
                    AuditEvent.details.ilike(f"%{search}%"),
                    AuditEvent.event_type.ilike(f"%{search}%"),
                    AuditEvent.entity_type.ilike(f"%{search}%"),
                )
            )
        return list(reversed(query.limit(limit).all()))

    def _set_config(self, key: str, value: str) -> None:
        entry = self.session.get(ConfigEntry, key)
        if entry:
            entry.value = value
        else:
            self.session.add(ConfigEntry(key=key, value=value))

    def _ensure_unique_identity(self, *, username: str, email: str) -> None:
        exists = self.session.query(Identity).filter(
            (Identity.username == username) | (Identity.email == email)
        ).first()
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already exists.")

    def _ensure_unique_name(self, model, name: str, message: str, exclude_id: int | None = None) -> None:
        query = self.session.query(model).filter(model.name == name)
        if exclude_id is not None:
            query = query.filter(model.id != exclude_id)
        if query.first():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)

    def _require_entity(self, model, entity_id: int, not_found: str):
        entity = self.session.get(model, entity_id)
        if not entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found)
        return entity

    def _ensure_sample_data(self, actor_id: int | None) -> None:
        if not self.session.query(System).filter(System.name == "HR SaaS").first():
            system = System(
                name="HR SaaS",
                description="Wizard-added sample system",
                owner_identity_id=actor_id,
            )
            self.session.add(system)
            self.session.flush()

            resource = Resource(
                name="HR Viewer",
                system_id=system.id,
                requestable=True,
                description="Wizard-added requestable role",
            )
            self.session.add(resource)
            self.session.flush()

            self.session.add(
                TaskMapping(
                    system_id=system.id,
                    resource_id=resource.id,
                    action="grant",
                    task_type="manual_provision",
                    default_owner_role="operator",
                    sla_hours=12,
                )
            )

    def _ensure_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

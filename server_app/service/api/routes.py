from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server_app.core.models import (
    AccessRequest,
    Approval,
    AuditEvent,
    Delegation,
    Identity,
    ProvisioningTask,
    Resource,
    ResourceAssignment,
    System,
    TaskMapping,
)
from server_app.core.rbac import permissions_for_role
from server_app.service.api.deps import get_current_identity, get_db, require
from server_app.service.services.governance import GovernanceService
from server_app.service.services.platform import PlatformService
from shared.auth.security import create_access_token, verify_password
from shared.config.settings import get_settings
from shared.schemas.domain import (
    AccessRequestCreate,
    AccessRequestRead,
    ApprovalDecisionRequest,
    ApprovalRead,
    AuditEventRead,
    DashboardSummary,
    DelegationCreate,
    DelegationRead,
    DelegationUpdate,
    IdentityCreate,
    IdentityImportRequest,
    IdentityImportResult,
    IdentityRead,
    IdentityUpdate,
    LoginRequest,
    ProvisioningTaskComplete,
    ProvisioningTaskRead,
    ResourceAssignmentRead,
    ResourceCreate,
    ResourceRead,
    ResourceUpdate,
    ServerInfo,
    SettingsRead,
    SettingsUpdate,
    SetupWizardBootstrapRequest,
    SetupWizardStatus,
    SystemCreate,
    SystemRead,
    SystemUpdate,
    TaskMappingCreate,
    TaskMappingRead,
    TaskMappingUpdate,
    TokenResponse,
)

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    identity = db.query(Identity).filter(Identity.username == payload.username).first()
    if not identity or not verify_password(payload.password, identity.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    settings = get_settings()
    token = create_access_token(str(identity.id), settings, {"role": identity.role})
    return TokenResponse(access_token=token)


@router.get("/server-info", response_model=ServerInfo)
def server_info(db: Session = Depends(get_db)) -> ServerInfo:
    settings = get_settings()
    payload = PlatformService(db).get_server_info(settings.api_host, settings.api_port, settings.product_name)
    return ServerInfo(**payload)


@router.get("/setup-wizard/status", response_model=SetupWizardStatus)
def setup_status(db: Session = Depends(get_db)) -> SetupWizardStatus:
    return PlatformService(db).get_setup_status()


@router.post("/setup-wizard/bootstrap", response_model=SetupWizardStatus)
def setup_bootstrap(payload: SetupWizardBootstrapRequest, db: Session = Depends(get_db)) -> SetupWizardStatus:
    status_payload = PlatformService(db).bootstrap_setup(payload)
    db.commit()
    return status_payload


@router.get("/settings", response_model=SettingsRead)
def get_settings_route(
    db: Session = Depends(get_db),
    _: Identity = Depends(require("admin.dashboard")),
) -> SettingsRead:
    settings = get_settings()
    return PlatformService(db).get_settings(settings.database_url)


@router.put("/settings", response_model=SettingsRead)
def update_settings_route(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("admin.dashboard")),
) -> SettingsRead:
    result = PlatformService(db).update_settings(payload, actor.id)
    db.commit()
    return result


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    db: Session = Depends(get_db),
    _: Identity = Depends(require("admin.dashboard")),
) -> DashboardSummary:
    return PlatformService(db).get_dashboard_summary()


@router.get("/me", response_model=IdentityRead)
def me(identity: Identity = Depends(get_current_identity)) -> IdentityRead:
    return IdentityRead.model_validate(identity)


@router.get("/permissions", response_model=list[str])
def permissions(identity: Identity = Depends(get_current_identity)) -> list[str]:
    return permissions_for_role(identity.role)


@router.get("/identities", response_model=list[IdentityRead])
def list_identities(
    db: Session = Depends(get_db),
    _: Identity = Depends(require("identities.read")),
) -> list[IdentityRead]:
    return [IdentityRead.model_validate(item) for item in db.query(Identity).order_by(Identity.id).all()]


@router.post("/identities", response_model=IdentityRead)
def create_identity(
    payload: IdentityCreate,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("identities.write")),
) -> IdentityRead:
    identity = PlatformService(db).create_identity(payload, actor.id)
    db.commit()
    return IdentityRead.model_validate(identity)


@router.put("/identities/{identity_id}", response_model=IdentityRead)
def update_identity(
    identity_id: int,
    payload: IdentityUpdate,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("identities.write")),
) -> IdentityRead:
    identity = PlatformService(db).update_identity(identity_id, payload, actor.id)
    db.commit()
    return IdentityRead.model_validate(identity)


@router.delete("/identities/{identity_id}")
def delete_identity(
    identity_id: int,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("identities.write")),
) -> dict[str, bool]:
    PlatformService(db).delete_identity(identity_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.post("/identities/import-csv", response_model=IdentityImportResult)
def import_identities(
    payload: IdentityImportRequest,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("identities.write")),
) -> IdentityImportResult:
    result = PlatformService(db).import_identities_from_csv(payload, actor.id)
    db.commit()
    return result


@router.get("/systems", response_model=list[SystemRead])
def list_systems(
    db: Session = Depends(get_db),
    _: Identity = Depends(require("systems.read")),
) -> list[SystemRead]:
    return [SystemRead.model_validate(item) for item in db.query(System).order_by(System.id).all()]


@router.post("/systems", response_model=SystemRead)
def create_system(
    payload: SystemCreate,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("systems.write")),
) -> SystemRead:
    system = PlatformService(db).create_system(payload, actor.id)
    db.commit()
    return SystemRead.model_validate(system)


@router.put("/systems/{system_id}", response_model=SystemRead)
def update_system(
    system_id: int,
    payload: SystemUpdate,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("systems.write")),
) -> SystemRead:
    system = PlatformService(db).update_system(system_id, payload, actor.id)
    db.commit()
    return SystemRead.model_validate(system)


@router.delete("/systems/{system_id}")
def delete_system(
    system_id: int,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("systems.write")),
) -> dict[str, bool]:
    PlatformService(db).delete_system(system_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.get("/resources", response_model=list[ResourceRead])
def list_resources(
    db: Session = Depends(get_db),
    identity: Identity = Depends(get_current_identity),
) -> list[ResourceRead]:
    if not any(perm in permissions_for_role(identity.role) for perm in ["resources.read", "requests.write"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions.")
    return [ResourceRead.model_validate(item) for item in db.query(Resource).order_by(Resource.id).all()]


@router.post("/resources", response_model=ResourceRead)
def create_resource(
    payload: ResourceCreate,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("resources.write")),
) -> ResourceRead:
    resource = PlatformService(db).create_resource(payload, actor.id)
    db.commit()
    return ResourceRead.model_validate(resource)


@router.put("/resources/{resource_id}", response_model=ResourceRead)
def update_resource(
    resource_id: int,
    payload: ResourceUpdate,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("resources.write")),
) -> ResourceRead:
    resource = PlatformService(db).update_resource(resource_id, payload, actor.id)
    db.commit()
    return ResourceRead.model_validate(resource)


@router.delete("/resources/{resource_id}")
def delete_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("resources.write")),
) -> dict[str, bool]:
    PlatformService(db).delete_resource(resource_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.get("/task-mappings", response_model=list[TaskMappingRead])
def list_task_mappings(
    db: Session = Depends(get_db),
    _: Identity = Depends(require("task_mappings.read")),
) -> list[TaskMappingRead]:
    return [TaskMappingRead.model_validate(item) for item in db.query(TaskMapping).order_by(TaskMapping.id).all()]


@router.post("/task-mappings", response_model=TaskMappingRead)
def create_task_mapping(
    payload: TaskMappingCreate,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("task_mappings.write")),
) -> TaskMappingRead:
    task_mapping = PlatformService(db).create_task_mapping(payload, actor.id)
    db.commit()
    return TaskMappingRead.model_validate(task_mapping)


@router.put("/task-mappings/{mapping_id}", response_model=TaskMappingRead)
def update_task_mapping(
    mapping_id: int,
    payload: TaskMappingUpdate,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("task_mappings.write")),
) -> TaskMappingRead:
    task_mapping = PlatformService(db).update_task_mapping(mapping_id, payload, actor.id)
    db.commit()
    return TaskMappingRead.model_validate(task_mapping)


@router.delete("/task-mappings/{mapping_id}")
def delete_task_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("task_mappings.write")),
) -> dict[str, bool]:
    PlatformService(db).delete_task_mapping(mapping_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.get("/access-requests", response_model=list[AccessRequestRead])
def list_access_requests(
    db: Session = Depends(get_db),
    identity: Identity = Depends(require("requests.read")),
) -> list[AccessRequestRead]:
    query = db.query(AccessRequest).order_by(AccessRequest.id)
    if identity.role == "employee":
        query = query.filter(
            (AccessRequest.requester_identity_id == identity.id)
            | (AccessRequest.beneficiary_identity_id == identity.id)
        )
    return [AccessRequestRead.model_validate(item) for item in query.all()]


@router.post("/access-requests", response_model=AccessRequestRead)
def create_access_request(
    payload: AccessRequestCreate,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("requests.write")),
) -> AccessRequestRead:
    access_request = GovernanceService(db).submit_access_request(payload, actor)
    db.commit()
    return AccessRequestRead.model_validate(access_request)


@router.post("/access-requests/{request_id}/approve", response_model=ApprovalRead)
def approve_access_request(
    request_id: int,
    payload: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("approvals.decide")),
) -> ApprovalRead:
    approval = GovernanceService(db).decide_approval(request_id=request_id, decision=payload, actor=actor)
    db.commit()
    return ApprovalRead(
        id=approval.id,
        access_request_id=approval.access_request_id,
        approver_identity_id=approval.approver_identity_id,
        decision=approval.decision,
        comment=approval.comment,
        status=approval.status,
    )


@router.get("/approvals", response_model=list[ApprovalRead])
def list_approvals(
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("approvals.read")),
) -> list[ApprovalRead]:
    items = GovernanceService(db).list_approvals(actor)
    return [
        ApprovalRead(
            id=item.id,
            access_request_id=item.access_request_id,
            approver_identity_id=item.approver_identity_id,
            decision=item.decision,
            comment=item.comment,
            status=item.status,
        )
        for item in items
    ]


@router.get("/provisioning/tasks", response_model=list[ProvisioningTaskRead])
def list_tasks(
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("provisioning.read")),
) -> list[ProvisioningTaskRead]:
    query = db.query(ProvisioningTask).order_by(ProvisioningTask.id)
    if actor.role == "operator":
        query = query.filter(ProvisioningTask.owner_role == actor.role)
    return [ProvisioningTaskRead.model_validate(item) for item in query.all()]


@router.post("/provisioning/tasks/{task_id}/complete", response_model=ProvisioningTaskRead)
def complete_task(
    task_id: int,
    payload: ProvisioningTaskComplete,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("provisioning.complete")),
) -> ProvisioningTaskRead:
    task = GovernanceService(db).complete_task(task_id=task_id, payload=payload, actor=actor)
    db.commit()
    return ProvisioningTaskRead.model_validate(task)


@router.get("/resource-assignments", response_model=list[ResourceAssignmentRead])
def list_assignments(
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("assignments.read")),
) -> list[ResourceAssignmentRead]:
    query = db.query(ResourceAssignment).order_by(ResourceAssignment.id)
    if actor.role == "employee":
        query = query.filter(ResourceAssignment.identity_id == actor.id)
    return [ResourceAssignmentRead.model_validate(item) for item in query.all()]


@router.get("/delegations", response_model=list[DelegationRead])
def list_delegations(
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("delegations.read")),
) -> list[DelegationRead]:
    query = db.query(Delegation).order_by(Delegation.id)
    if actor.role == "employee":
        query = query.filter(
            (Delegation.delegator_identity_id == actor.id) | (Delegation.delegate_identity_id == actor.id)
        )
    return [DelegationRead.model_validate(item) for item in query.all()]


@router.post("/delegations", response_model=DelegationRead)
def create_delegation(
    payload: DelegationCreate,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("delegations.write")),
) -> DelegationRead:
    delegation = PlatformService(db).create_delegation(payload, actor.id)
    db.commit()
    return DelegationRead.model_validate(delegation)


@router.put("/delegations/{delegation_id}", response_model=DelegationRead)
def update_delegation(
    delegation_id: int,
    payload: DelegationUpdate,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("delegations.write")),
) -> DelegationRead:
    delegation = PlatformService(db).update_delegation(delegation_id, payload, actor.id)
    db.commit()
    return DelegationRead.model_validate(delegation)


@router.delete("/delegations/{delegation_id}")
def delete_delegation(
    delegation_id: int,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("delegations.write")),
) -> dict[str, bool]:
    PlatformService(db).delete_delegation(delegation_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.get("/audit", response_model=list[AuditEventRead])
def list_audit(
    db: Session = Depends(get_db),
    severity: str | None = None,
    entity_type: str | None = None,
    search: str | None = None,
    limit: int = 100,
    _: Identity = Depends(require("audit.read")),
) -> list[AuditEventRead]:
    events = PlatformService(db).get_audit_events(
        severity=severity,
        entity_type=entity_type,
        search=search,
        limit=limit,
    )
    return [AuditEventRead.model_validate(item) for item in events]


@router.post("/identities/{identity_id}/emergency-terminate", response_model=IdentityRead)
def emergency_terminate(
    identity_id: int,
    db: Session = Depends(get_db),
    actor: Identity = Depends(require("emergency_termination.execute")),
) -> IdentityRead:
    identity = PlatformService(db).emergency_terminate(identity_id=identity_id, actor=actor)
    db.commit()
    return IdentityRead.model_validate(identity)

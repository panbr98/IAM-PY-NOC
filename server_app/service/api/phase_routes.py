from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from server_app.core.models import Identity
from server_app.service.api.deps import get_current_identity, get_db, require
from server_app.service.services.phase_domains import (
    CertificationService,
    ConnectorQueryService,
    ConnectorService,
    JobService,
    PamService,
    ReconciliationService,
    ScimService,
)
from shared.schemas.phase_domains import (
    CertificationCampaignCreate,
    CertificationCampaignRead,
    CertificationDecision,
    CertificationItemRead,
    ConnectorCreate,
    ConnectorQueryCreate,
    ConnectorQueryRead,
    ConnectorQueryUpdate,
    ConnectorRead,
    ConnectorRunRead,
    PamCheckoutCreate,
    PamCheckoutRead,
    PamJitAccessCreate,
    PamJitAccessRead,
    PamSecretCreate,
    PamSecretRead,
    ReconciliationFindingRead,
    ReconciliationRunCreate,
    ReconciliationRunRead,
    RemediationActionRead,
    SchedulerJobCreate,
    SchedulerJobRead,
    ScimGroupPayload,
    ScimListResponse,
    ScimMappingCreate,
    ScimMappingRead,
    ScimMappingUpdate,
    ScimUserPayload,
)

router = APIRouter()


@router.get("/reconciliation/runs", response_model=list[ReconciliationRunRead])
def list_reconciliation_runs(db: Session = Depends(get_db), _: Identity = Depends(require("reconciliation.read"))):
    return ReconciliationService(db).list_runs()


@router.post("/reconciliation/runs", response_model=ReconciliationRunRead)
def create_reconciliation_run(payload: ReconciliationRunCreate, db: Session = Depends(get_db), actor: Identity = Depends(require("reconciliation.execute"))):
    run = ReconciliationService(db).run(payload, actor.id)
    db.commit()
    return run


@router.get("/reconciliation/findings", response_model=list[ReconciliationFindingRead])
def list_reconciliation_findings(run_id: int | None = None, db: Session = Depends(get_db), _: Identity = Depends(require("reconciliation.read"))):
    return ReconciliationService(db).list_findings(run_id)


@router.post("/reconciliation/findings/{finding_id}/remediate", response_model=RemediationActionRead)
def remediate_reconciliation_finding(finding_id: int, db: Session = Depends(get_db), actor: Identity = Depends(require("reconciliation.execute"))):
    action = ReconciliationService(db).remediate(finding_id, actor.id)
    db.commit()
    return action


@router.get("/certifications/campaigns", response_model=list[CertificationCampaignRead])
def list_certification_campaigns(db: Session = Depends(get_db), _: Identity = Depends(require("certifications.read"))):
    return CertificationService(db).list_campaigns()


@router.post("/certifications/campaigns", response_model=CertificationCampaignRead)
def create_certification_campaign(payload: CertificationCampaignCreate, db: Session = Depends(get_db), actor: Identity = Depends(require("certifications.write"))):
    campaign = CertificationService(db).create_campaign(payload, actor.id)
    db.commit()
    return campaign


@router.post("/certifications/campaigns/{campaign_id}/close", response_model=CertificationCampaignRead)
def close_certification_campaign(campaign_id: int, db: Session = Depends(get_db), actor: Identity = Depends(require("certifications.write"))):
    campaign = CertificationService(db).close_campaign(campaign_id, actor.id)
    db.commit()
    return campaign


@router.get("/certifications/items", response_model=list[CertificationItemRead])
def list_certification_items(campaign_id: int | None = None, db: Session = Depends(get_db), actor: Identity = Depends(require("certifications.read"))):
    reviewer_id = actor.id if actor.role not in {"super_admin", "operator"} else None
    return CertificationService(db).list_items(campaign_id=campaign_id, reviewer_id=reviewer_id)


@router.post("/certifications/items/{item_id}/decision", response_model=CertificationItemRead)
def decide_certification_item(item_id: int, payload: CertificationDecision, db: Session = Depends(get_db), actor: Identity = Depends(require("certifications.decide"))):
    item = CertificationService(db).decide(item_id, payload, actor.id)
    db.commit()
    return item


@router.get("/pam/secrets", response_model=list[PamSecretRead])
def list_pam_secrets(db: Session = Depends(get_db), _: Identity = Depends(require("pam.vault.read"))):
    return PamService(db).list_secrets()


@router.post("/pam/secrets", response_model=PamSecretRead)
def create_pam_secret(payload: PamSecretCreate, db: Session = Depends(get_db), actor: Identity = Depends(require("pam.vault.admin"))):
    secret = PamService(db).create_secret(payload, actor.id)
    db.commit()
    return secret


@router.post("/pam/secrets/{secret_id}/checkout", response_model=PamCheckoutRead)
def checkout_pam_secret(secret_id: int, payload: PamCheckoutCreate, db: Session = Depends(get_db), actor: Identity = Depends(require("pam.checkout"))):
    checkout, revealed = PamService(db).checkout(secret_id, payload, actor.id)
    db.commit()
    data = PamCheckoutRead.model_validate(checkout)
    data.revealed_secret = revealed
    return data


@router.post("/pam/secrets/{secret_id}/break-glass", response_model=PamCheckoutRead)
def break_glass_pam_secret(secret_id: int, payload: PamCheckoutCreate, db: Session = Depends(get_db), actor: Identity = Depends(require("pam.break_glass"))):
    checkout, revealed = PamService(db).checkout(secret_id, payload, actor.id, break_glass=True)
    db.commit()
    data = PamCheckoutRead.model_validate(checkout)
    data.revealed_secret = revealed
    return data


@router.post("/pam/checkouts/{checkout_id}/checkin", response_model=PamCheckoutRead)
def checkin_pam_secret(checkout_id: int, db: Session = Depends(get_db), actor: Identity = Depends(require("pam.checkout"))):
    checkout = PamService(db).checkin(checkout_id, actor.id)
    db.commit()
    return checkout


@router.get("/pam/checkouts", response_model=list[PamCheckoutRead])
def list_pam_checkouts(db: Session = Depends(get_db), _: Identity = Depends(require("pam.vault.read"))):
    return PamService(db).list_checkouts()


@router.post("/pam/jit", response_model=PamJitAccessRead)
def create_pam_jit(payload: PamJitAccessCreate, db: Session = Depends(get_db), actor: Identity = Depends(require("pam.checkout"))):
    item = PamService(db).create_jit(payload, actor.id)
    db.commit()
    return item


@router.get("/connectors", response_model=list[ConnectorRead])
def list_connectors(db: Session = Depends(get_db), _: Identity = Depends(require("connectors.read"))):
    return ConnectorService(db).list()


@router.post("/connectors", response_model=ConnectorRead)
def create_connector(payload: ConnectorCreate, db: Session = Depends(get_db), actor: Identity = Depends(require("connectors.write"))):
    connector = ConnectorService(db).create(payload, actor.id)
    db.commit()
    return connector


@router.post("/connectors/{connector_id}/test", response_model=ConnectorRunRead)
def test_connector(connector_id: int, db: Session = Depends(get_db), actor: Identity = Depends(require("connectors.execute"))):
    run = ConnectorService(db).test(connector_id, actor.id)
    db.commit()
    return run


@router.post("/connectors/{connector_id}/run/{operation}", response_model=ConnectorRunRead)
def run_connector(connector_id: int, operation: str, db: Session = Depends(get_db), actor: Identity = Depends(require("connectors.execute"))):
    run = ConnectorService(db).run(connector_id, operation, actor.id)
    db.commit()
    return run


@router.get("/connector-runs", response_model=list[ConnectorRunRead])
def list_connector_runs(db: Session = Depends(get_db), _: Identity = Depends(require("connectors.read"))):
    return ConnectorService(db).list_runs()


@router.get("/connector-queries", response_model=list[ConnectorQueryRead])
def list_connector_queries(db: Session = Depends(get_db), _: Identity = Depends(require("connectors.read"))):
    return ConnectorQueryService(db).list()


@router.post("/connector-queries", response_model=ConnectorQueryRead)
def create_connector_query(payload: ConnectorQueryCreate, db: Session = Depends(get_db), actor: Identity = Depends(require("connectors.write"))):
    query = ConnectorQueryService(db).create(payload, actor.id)
    db.commit()
    return query


@router.put("/connector-queries/{query_id}", response_model=ConnectorQueryRead)
def update_connector_query(query_id: int, payload: ConnectorQueryUpdate, db: Session = Depends(get_db), actor: Identity = Depends(require("connectors.write"))):
    query = ConnectorQueryService(db).update(query_id, payload, actor.id)
    db.commit()
    return query


@router.delete("/connector-queries/{query_id}")
def delete_connector_query(query_id: int, db: Session = Depends(get_db), actor: Identity = Depends(require("connectors.write"))):
    ConnectorQueryService(db).delete(query_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.post("/connector-queries/{query_id}/run", response_model=ConnectorRunRead)
def run_connector_query(query_id: int, db: Session = Depends(get_db), actor: Identity = Depends(require("connectors.execute"))):
    run = ConnectorQueryService(db).run(query_id, actor.id)
    db.commit()
    return run


@router.get("/jobs", response_model=list[SchedulerJobRead])
def list_jobs(db: Session = Depends(get_db), _: Identity = Depends(require("jobs.read"))):
    return JobService(db).list()


@router.post("/jobs", response_model=SchedulerJobRead)
def create_job(payload: SchedulerJobCreate, db: Session = Depends(get_db), actor: Identity = Depends(require("jobs.write"))):
    job = JobService(db).create(payload, actor.id)
    db.commit()
    return job


@router.post("/jobs/run-next", response_model=SchedulerJobRead | None)
def run_next_job(db: Session = Depends(get_db), actor: Identity = Depends(require("jobs.execute"))):
    job = JobService(db).run_next(actor.id)
    db.commit()
    return job


@router.get("/scim/v2/Users", response_model=ScimListResponse)
def list_scim_users(db: Session = Depends(get_db), _: Identity = Depends(require("scim.read"))):
    users = ScimService(db).list_users()
    return ScimListResponse(Resources=users, totalResults=len(users), itemsPerPage=len(users))


@router.post("/scim/v2/Users")
def create_scim_user(payload: ScimUserPayload, db: Session = Depends(get_db), actor: Identity = Depends(require("scim.write"))):
    user = ScimService(db).create_user(payload, actor.id)
    db.commit()
    return user


@router.get("/scim/v2/Groups", response_model=ScimListResponse)
def list_scim_groups(db: Session = Depends(get_db), _: Identity = Depends(require("scim.read"))):
    groups = ScimService(db).list_groups()
    return ScimListResponse(Resources=groups, totalResults=len(groups), itemsPerPage=len(groups))


@router.post("/scim/v2/Groups")
def create_scim_group(payload: ScimGroupPayload, db: Session = Depends(get_db), actor: Identity = Depends(require("scim.write"))):
    group = ScimService(db).create_group(payload, actor.id)
    db.commit()
    return group


@router.get("/scim/mappings", response_model=list[ScimMappingRead])
def list_scim_mappings(db: Session = Depends(get_db), _: Identity = Depends(require("scim.read"))):
    return ScimService(db).list_mappings()


@router.post("/scim/mappings", response_model=ScimMappingRead)
def create_scim_mapping(payload: ScimMappingCreate, db: Session = Depends(get_db), actor: Identity = Depends(require("scim.write"))):
    mapping = ScimService(db).create_mapping(payload, actor.id)
    db.commit()
    return mapping


@router.put("/scim/mappings/{mapping_id}", response_model=ScimMappingRead)
def update_scim_mapping(mapping_id: int, payload: ScimMappingUpdate, db: Session = Depends(get_db), actor: Identity = Depends(require("scim.write"))):
    mapping = ScimService(db).update_mapping(mapping_id, payload, actor.id)
    db.commit()
    return mapping


@router.delete("/scim/mappings/{mapping_id}")
def delete_scim_mapping(mapping_id: int, db: Session = Depends(get_db), actor: Identity = Depends(require("scim.write"))):
    ScimService(db).delete_mapping(mapping_id, actor.id)
    db.commit()
    return {"deleted": True}

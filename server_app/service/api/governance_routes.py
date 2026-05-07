from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from server_app.core.models import ResourceAssignment
from server_app.service.api.deps import get_current_identity, get_db, require
from server_app.service.services.governance import GovernanceService
from shared.schemas.domain import ResourceAssignmentRead
from shared.schemas.governance import (
    AccessExpiryPolicyCreate,
    AccessExpiryPolicyRead,
    AccessExpiryPolicyUpdate,
    AccessPolicyCreate,
    AccessPolicyRead,
    AccessPolicyUpdate,
    ApprovalPolicyCreate,
    ApprovalPolicyRead,
    ApprovalPolicyUpdate,
    ApprovalStageDecisionRead,
    ApprovalStageRead,
    AttributeAccessRuleCreate,
    AttributeAccessRuleRead,
    AttributeAccessRuleUpdate,
    BirthrightRuleCreate,
    BirthrightRuleRead,
    BirthrightRuleUpdate,
    BusinessRoleCreate,
    BusinessRoleRead,
    BusinessRoleUpdate,
    PolicyEvaluationResultRead,
    RiskRuleCreate,
    RiskRuleRead,
    RiskRuleUpdate,
    RoleRecalculationResponse,
    SoDPolicyCreate,
    SoDPolicyRead,
    SoDPolicyUpdate,
    TechnicalRoleCreate,
    TechnicalRoleRead,
    TechnicalRoleUpdate,
)

router = APIRouter()


@router.get("/business-roles", response_model=list[BusinessRoleRead])
def list_business_roles(db: Session = Depends(get_db), _=Depends(require("systems.read"))):
    return GovernanceService(db).list_business_roles()


@router.post("/business-roles", response_model=BusinessRoleRead)
def create_business_role(payload: BusinessRoleCreate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).create_business_role(payload, actor.id)
    db.commit()
    return result


@router.put("/business-roles/{role_id}", response_model=BusinessRoleRead)
def update_business_role(role_id: int, payload: BusinessRoleUpdate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).update_business_role(role_id, payload, actor.id)
    db.commit()
    return result


@router.delete("/business-roles/{role_id}")
def delete_business_role(role_id: int, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    GovernanceService(db).delete_business_role(role_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.get("/technical-roles", response_model=list[TechnicalRoleRead])
def list_technical_roles(db: Session = Depends(get_db), _=Depends(require("systems.read"))):
    return GovernanceService(db).list_technical_roles()


@router.post("/technical-roles", response_model=TechnicalRoleRead)
def create_technical_role(payload: TechnicalRoleCreate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).create_technical_role(payload, actor.id)
    db.commit()
    return result


@router.put("/technical-roles/{role_id}", response_model=TechnicalRoleRead)
def update_technical_role(role_id: int, payload: TechnicalRoleUpdate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).update_technical_role(role_id, payload, actor.id)
    db.commit()
    return result


@router.delete("/technical-roles/{role_id}")
def delete_technical_role(role_id: int, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    GovernanceService(db).delete_technical_role(role_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.get("/birthright-rules", response_model=list[BirthrightRuleRead])
def list_birthright_rules(db: Session = Depends(get_db), _=Depends(require("systems.read"))):
    return GovernanceService(db).list_birthright_rules()


@router.post("/birthright-rules", response_model=BirthrightRuleRead)
def create_birthright_rule(payload: BirthrightRuleCreate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).create_birthright_rule(payload, actor.id)
    db.commit()
    return result


@router.put("/birthright-rules/{rule_id}", response_model=BirthrightRuleRead)
def update_birthright_rule(rule_id: int, payload: BirthrightRuleUpdate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).update_birthright_rule(rule_id, payload, actor.id)
    db.commit()
    return result


@router.delete("/birthright-rules/{rule_id}")
def delete_birthright_rule(rule_id: int, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    GovernanceService(db).delete_birthright_rule(rule_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.get("/attribute-access-rules", response_model=list[AttributeAccessRuleRead])
def list_attribute_access_rules(db: Session = Depends(get_db), _=Depends(require("systems.read"))):
    return GovernanceService(db).list_attribute_access_rules()


@router.post("/attribute-access-rules", response_model=AttributeAccessRuleRead)
def create_attribute_access_rule(payload: AttributeAccessRuleCreate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).create_attribute_access_rule(payload, actor.id)
    db.commit()
    return result


@router.put("/attribute-access-rules/{rule_id}", response_model=AttributeAccessRuleRead)
def update_attribute_access_rule(rule_id: int, payload: AttributeAccessRuleUpdate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).update_attribute_access_rule(rule_id, payload, actor.id)
    db.commit()
    return result


@router.delete("/attribute-access-rules/{rule_id}")
def delete_attribute_access_rule(rule_id: int, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    GovernanceService(db).delete_attribute_access_rule(rule_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.get("/access-policies", response_model=list[AccessPolicyRead])
def list_access_policies(db: Session = Depends(get_db), _=Depends(require("systems.read"))):
    return GovernanceService(db).list_access_policies()


@router.post("/access-policies", response_model=AccessPolicyRead)
def create_access_policy(payload: AccessPolicyCreate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).create_access_policy(payload, actor.id)
    db.commit()
    return result


@router.put("/access-policies/{policy_id}", response_model=AccessPolicyRead)
def update_access_policy(policy_id: int, payload: AccessPolicyUpdate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).update_access_policy(policy_id, payload, actor.id)
    db.commit()
    return result


@router.delete("/access-policies/{policy_id}")
def delete_access_policy(policy_id: int, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    GovernanceService(db).delete_access_policy(policy_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.get("/sod-policies", response_model=list[SoDPolicyRead])
def list_sod_policies(db: Session = Depends(get_db), _=Depends(require("systems.read"))):
    return GovernanceService(db).list_sod_policies()


@router.post("/sod-policies", response_model=SoDPolicyRead)
def create_sod_policy(payload: SoDPolicyCreate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).create_sod_policy(payload, actor.id)
    db.commit()
    return result


@router.put("/sod-policies/{policy_id}", response_model=SoDPolicyRead)
def update_sod_policy(policy_id: int, payload: SoDPolicyUpdate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).update_sod_policy(policy_id, payload, actor.id)
    db.commit()
    return result


@router.delete("/sod-policies/{policy_id}")
def delete_sod_policy(policy_id: int, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    GovernanceService(db).delete_sod_policy(policy_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.get("/risk-rules", response_model=list[RiskRuleRead])
def list_risk_rules(db: Session = Depends(get_db), _=Depends(require("systems.read"))):
    return GovernanceService(db).list_risk_rules()


@router.post("/risk-rules", response_model=RiskRuleRead)
def create_risk_rule(payload: RiskRuleCreate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).create_risk_rule(payload, actor.id)
    db.commit()
    return result


@router.put("/risk-rules/{rule_id}", response_model=RiskRuleRead)
def update_risk_rule(rule_id: int, payload: RiskRuleUpdate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).update_risk_rule(rule_id, payload, actor.id)
    db.commit()
    return result


@router.delete("/risk-rules/{rule_id}")
def delete_risk_rule(rule_id: int, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    GovernanceService(db).delete_risk_rule(rule_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.get("/approval-policies", response_model=list[ApprovalPolicyRead])
def list_approval_policies(db: Session = Depends(get_db), _=Depends(require("systems.read"))):
    return GovernanceService(db).list_approval_policies()


@router.post("/approval-policies", response_model=ApprovalPolicyRead)
def create_approval_policy(payload: ApprovalPolicyCreate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).create_approval_policy(payload, actor.id)
    db.commit()
    return result


@router.put("/approval-policies/{policy_id}", response_model=ApprovalPolicyRead)
def update_approval_policy(policy_id: int, payload: ApprovalPolicyUpdate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).update_approval_policy(policy_id, payload, actor.id)
    db.commit()
    return result


@router.delete("/approval-policies/{policy_id}")
def delete_approval_policy(policy_id: int, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    GovernanceService(db).delete_approval_policy(policy_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.get("/approval-instances", response_model=list[ApprovalStageDecisionRead])
def list_approval_instances(access_request_id: int | None = None, db: Session = Depends(get_db), actor=Depends(get_current_identity)):
    return GovernanceService(db).list_approval_instances(access_request_id=access_request_id, actor=actor)


@router.get("/approval-stages", response_model=list[ApprovalStageRead])
def list_approval_stages(access_request_id: int | None = None, db: Session = Depends(get_db), actor=Depends(get_current_identity)):
    return GovernanceService(db).list_approval_stages(access_request_id=access_request_id)


@router.get("/access-expiry-policies", response_model=list[AccessExpiryPolicyRead])
def list_access_expiry_policies(db: Session = Depends(get_db), _=Depends(require("systems.read"))):
    return GovernanceService(db).list_access_expiry_policies()


@router.post("/access-expiry-policies", response_model=AccessExpiryPolicyRead)
def create_access_expiry_policy(payload: AccessExpiryPolicyCreate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).create_access_expiry_policy(payload, actor.id)
    db.commit()
    return result


@router.put("/access-expiry-policies/{policy_id}", response_model=AccessExpiryPolicyRead)
def update_access_expiry_policy(policy_id: int, payload: AccessExpiryPolicyUpdate, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    result = GovernanceService(db).update_access_expiry_policy(policy_id, payload, actor.id)
    db.commit()
    return result


@router.delete("/access-expiry-policies/{policy_id}")
def delete_access_expiry_policy(policy_id: int, db: Session = Depends(get_db), actor=Depends(require("systems.write"))):
    GovernanceService(db).delete_access_expiry_policy(policy_id, actor.id)
    db.commit()
    return {"deleted": True}


@router.get("/policy-evaluations", response_model=list[PolicyEvaluationResultRead])
def list_policy_evaluations(access_request_id: int | None = None, identity_id: int | None = None, db: Session = Depends(get_db), actor=Depends(get_current_identity)):
    return GovernanceService(db).list_policy_evaluations(access_request_id=access_request_id, identity_id=identity_id)


@router.post("/identities/{identity_id}/governance/recalculate", response_model=RoleRecalculationResponse)
def recalculate_identity(identity_id: int, db: Session = Depends(get_db), actor=Depends(require("identities.write"))):
    result = GovernanceService(db).recalculate_identity_governance(identity_id, actor.id)
    db.commit()
    return result


@router.get("/assignments/expiring", response_model=list[ResourceAssignmentRead])
def list_expiring_assignments(within_days: int = 30, db: Session = Depends(get_db), actor=Depends(require("assignments.read"))):
    items = GovernanceService(db).list_expiring_assignments(within_days)
    return [ResourceAssignmentRead.model_validate(item) for item in items]


@router.post("/assignments/{assignment_id}/revoke", response_model=ResourceAssignmentRead)
def revoke_assignment(assignment_id: int, notes: str = "", db: Session = Depends(get_db), actor=Depends(require("provisioning.complete"))):
    item = GovernanceService(db).revoke_assignment(assignment_id, actor, notes)
    db.commit()
    return ResourceAssignmentRead.model_validate(item)

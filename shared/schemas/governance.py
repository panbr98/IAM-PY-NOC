from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BusinessRoleBase(BaseModel):
    name: str
    description: str = ""
    requestable: bool = True
    risk_level: str = "normal"
    active: bool = True
    technical_role_ids: list[int] = Field(default_factory=list)
    resource_ids: list[int] = Field(default_factory=list)


class BusinessRoleCreate(BusinessRoleBase):
    pass


class BusinessRoleUpdate(BusinessRoleBase):
    pass


class BusinessRoleRead(BusinessRoleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TechnicalRoleBase(BaseModel):
    name: str
    description: str = ""
    requestable: bool = True
    active: bool = True
    resource_ids: list[int] = Field(default_factory=list)


class TechnicalRoleCreate(TechnicalRoleBase):
    pass


class TechnicalRoleUpdate(TechnicalRoleBase):
    pass


class TechnicalRoleRead(TechnicalRoleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class BusinessRoleMembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identity_id: int
    business_role_id: int
    source: str
    status: str


class TechnicalRoleMembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identity_id: int
    technical_role_id: int
    source: str
    status: str


class BirthrightRuleBase(BaseModel):
    name: str
    attribute_name: str
    operator: str = "equals"
    expected_value: str
    target_type: str
    target_id: int
    active: bool = True
    grant_basis: str = "birthright"


class BirthrightRuleCreate(BirthrightRuleBase):
    pass


class BirthrightRuleUpdate(BirthrightRuleBase):
    pass


class BirthrightRuleRead(BirthrightRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class AttributeAccessRuleBase(BaseModel):
    name: str
    attribute_name: str
    operator: str = "equals"
    expected_value: str
    target_type: str
    target_id: int
    mode: str = "assign"
    active: bool = True


class AttributeAccessRuleCreate(AttributeAccessRuleBase):
    pass


class AttributeAccessRuleUpdate(AttributeAccessRuleBase):
    pass


class AttributeAccessRuleRead(AttributeAccessRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class AccessPolicyBase(BaseModel):
    name: str
    resource_id: int | None = None
    system_id: int | None = None
    business_role_id: int | None = None
    technical_role_id: int | None = None
    max_duration_days: int = 30
    privileged: bool = False
    base_risk_score: int = 0
    require_justification: bool = False
    active: bool = True


class AccessPolicyCreate(AccessPolicyBase):
    pass


class AccessPolicyUpdate(AccessPolicyBase):
    pass


class AccessPolicyRead(AccessPolicyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class SoDPolicyBase(BaseModel):
    name: str
    description: str = ""
    mode: str = "warn"
    severity: str = "high"
    active: bool = True
    resource_pairs: list[list[int]] = Field(default_factory=list)


class SoDPolicyCreate(SoDPolicyBase):
    pass


class SoDPolicyUpdate(SoDPolicyBase):
    pass


class SoDPolicyRead(SoDPolicyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class RiskRuleBase(BaseModel):
    name: str
    condition_type: str
    condition_value: str
    score: int
    severity: str = "medium"
    active: bool = True


class RiskRuleCreate(RiskRuleBase):
    pass


class RiskRuleUpdate(RiskRuleBase):
    pass


class RiskRuleRead(RiskRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ApprovalStageInput(BaseModel):
    stage_order: int = 1
    mode: str = "all"
    approver_type: str
    approver_value: str = ""
    required_count: int = 1


class ApprovalPolicyBase(BaseModel):
    name: str
    scope_type: str = "default"
    scope_id: int | None = None
    min_risk_score: int = 0
    sequential: bool = True
    active: bool = True
    stages: list[ApprovalStageInput] = Field(default_factory=list)


class ApprovalPolicyCreate(ApprovalPolicyBase):
    pass


class ApprovalPolicyUpdate(ApprovalPolicyBase):
    pass


class ApprovalPolicyRead(ApprovalPolicyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class ApprovalStageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    policy_id: int
    stage_order: int
    mode: str
    approver_type: str
    approver_value: str
    required_count: int


class ApprovalStageDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    access_request_id: int
    stage_id: int
    approver_identity_id: int
    delegate_identity_id: int | None
    decision: str
    comment: str
    status: str
    acted_at: datetime | None


class AccessExpiryPolicyBase(BaseModel):
    name: str
    resource_id: int | None = None
    business_role_id: int | None = None
    technical_role_id: int | None = None
    default_duration_days: int = 30
    active: bool = True


class AccessExpiryPolicyCreate(AccessExpiryPolicyBase):
    pass


class AccessExpiryPolicyUpdate(AccessExpiryPolicyBase):
    pass


class AccessExpiryPolicyRead(AccessExpiryPolicyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class PolicyEvaluationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    access_request_id: int | None
    identity_id: int
    resource_id: int | None
    result_type: str
    status: str
    score: int
    severity: str
    details: str
    created_at: datetime


class RoleRecalculationResponse(BaseModel):
    business_role_memberships_created: int
    technical_role_memberships_created: int
    assignments_created: int
    evaluations_created: int

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from server_app.core.audit import record_audit
from server_app.connectors import build_connector
from server_app.core.models import (
    AccessExpiryPolicy,
    AccessPolicy,
    AccessRequest,
    Approval,
    ApprovalPolicy,
    ApprovalStage,
    ApprovalStageDecision,
    AttributeAccessRule,
    BirthrightRule,
    BusinessRole,
    BusinessRoleMembership,
    BusinessRoleResource,
    BusinessRoleTechnicalRole,
    Connector,
    ConnectorRun,
    Delegation,
    Identity,
    PolicyEvaluationResult,
    ProvisioningTask,
    Resource,
    ResourceAssignment,
    RiskRule,
    SoDPolicy,
    SoDPolicyPair,
    System,
    TaskMapping,
    TechnicalRole,
    TechnicalRoleMembership,
    TechnicalRoleResource,
)
from shared.schemas.domain import (
    AccessRequestCreate,
    ApprovalDecisionRequest,
    ProvisioningTaskComplete,
)
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


class GovernanceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # CRUD
    def list_business_roles(self) -> list[BusinessRoleRead]:
        roles = self.session.query(BusinessRole).order_by(BusinessRole.id).all()
        return [self._business_role_read(role) for role in roles]

    def create_business_role(self, payload: BusinessRoleCreate, actor_id: int) -> BusinessRoleRead:
        role = BusinessRole(
            name=payload.name,
            description=payload.description,
            requestable=payload.requestable,
            risk_level=payload.risk_level,
            active=payload.active,
        )
        self.session.add(role)
        self.session.flush()
        self._sync_business_role_links(role.id, payload.technical_role_ids, payload.resource_ids)
        self._audit(actor_id, "business_role.created", "business_role", role.id, f"Created {role.name}.")
        return self._business_role_read(role)

    def update_business_role(self, role_id: int, payload: BusinessRoleUpdate, actor_id: int) -> BusinessRoleRead:
        role = self._require(BusinessRole, role_id, "Business role not found.")
        role.name = payload.name
        role.description = payload.description
        role.requestable = payload.requestable
        role.risk_level = payload.risk_level
        role.active = payload.active
        self._sync_business_role_links(role.id, payload.technical_role_ids, payload.resource_ids)
        self._audit(actor_id, "business_role.updated", "business_role", role.id, f"Updated {role.name}.")
        return self._business_role_read(role)

    def delete_business_role(self, role_id: int, actor_id: int) -> None:
        role = self._require(BusinessRole, role_id, "Business role not found.")
        self.session.query(BusinessRoleTechnicalRole).filter_by(business_role_id=role_id).delete()
        self.session.query(BusinessRoleResource).filter_by(business_role_id=role_id).delete()
        self.session.query(BusinessRoleMembership).filter_by(business_role_id=role_id).delete()
        self.session.delete(role)
        self._audit(actor_id, "business_role.deleted", "business_role", role_id, "Deleted business role.")

    def list_technical_roles(self) -> list[TechnicalRoleRead]:
        roles = self.session.query(TechnicalRole).order_by(TechnicalRole.id).all()
        return [self._technical_role_read(role) for role in roles]

    def create_technical_role(self, payload: TechnicalRoleCreate, actor_id: int) -> TechnicalRoleRead:
        role = TechnicalRole(
            name=payload.name,
            description=payload.description,
            requestable=payload.requestable,
            active=payload.active,
        )
        self.session.add(role)
        self.session.flush()
        self._sync_technical_role_links(role.id, payload.resource_ids)
        self._audit(actor_id, "technical_role.created", "technical_role", role.id, f"Created {role.name}.")
        return self._technical_role_read(role)

    def update_technical_role(self, role_id: int, payload: TechnicalRoleUpdate, actor_id: int) -> TechnicalRoleRead:
        role = self._require(TechnicalRole, role_id, "Technical role not found.")
        role.name = payload.name
        role.description = payload.description
        role.requestable = payload.requestable
        role.active = payload.active
        self._sync_technical_role_links(role.id, payload.resource_ids)
        self._audit(actor_id, "technical_role.updated", "technical_role", role.id, f"Updated {role.name}.")
        return self._technical_role_read(role)

    def delete_technical_role(self, role_id: int, actor_id: int) -> None:
        role = self._require(TechnicalRole, role_id, "Technical role not found.")
        self.session.query(TechnicalRoleResource).filter_by(technical_role_id=role_id).delete()
        self.session.query(BusinessRoleTechnicalRole).filter_by(technical_role_id=role_id).delete()
        self.session.query(TechnicalRoleMembership).filter_by(technical_role_id=role_id).delete()
        self.session.delete(role)
        self._audit(actor_id, "technical_role.deleted", "technical_role", role_id, "Deleted technical role.")

    def list_birthright_rules(self) -> list[BirthrightRuleRead]:
        return [BirthrightRuleRead.model_validate(item) for item in self.session.query(BirthrightRule).order_by(BirthrightRule.id).all()]

    def create_birthright_rule(self, payload: BirthrightRuleCreate, actor_id: int) -> BirthrightRuleRead:
        rule = BirthrightRule(**payload.model_dump())
        self.session.add(rule)
        self.session.flush()
        self._audit(actor_id, "birthright_rule.created", "birthright_rule", rule.id, f"Created {rule.name}.")
        return BirthrightRuleRead.model_validate(rule)

    def update_birthright_rule(self, rule_id: int, payload: BirthrightRuleUpdate, actor_id: int) -> BirthrightRuleRead:
        rule = self._require(BirthrightRule, rule_id, "Birthright rule not found.")
        for key, value in payload.model_dump().items():
            setattr(rule, key, value)
        self._audit(actor_id, "birthright_rule.updated", "birthright_rule", rule.id, f"Updated {rule.name}.")
        return BirthrightRuleRead.model_validate(rule)

    def delete_birthright_rule(self, rule_id: int, actor_id: int) -> None:
        rule = self._require(BirthrightRule, rule_id, "Birthright rule not found.")
        self.session.delete(rule)
        self._audit(actor_id, "birthright_rule.deleted", "birthright_rule", rule_id, "Deleted birthright rule.")

    def list_attribute_access_rules(self) -> list[AttributeAccessRuleRead]:
        return [AttributeAccessRuleRead.model_validate(item) for item in self.session.query(AttributeAccessRule).order_by(AttributeAccessRule.id).all()]

    def create_attribute_access_rule(self, payload: AttributeAccessRuleCreate, actor_id: int) -> AttributeAccessRuleRead:
        rule = AttributeAccessRule(**payload.model_dump())
        self.session.add(rule)
        self.session.flush()
        self._audit(actor_id, "attribute_rule.created", "attribute_access_rule", rule.id, f"Created {rule.name}.")
        return AttributeAccessRuleRead.model_validate(rule)

    def update_attribute_access_rule(self, rule_id: int, payload: AttributeAccessRuleUpdate, actor_id: int) -> AttributeAccessRuleRead:
        rule = self._require(AttributeAccessRule, rule_id, "Attribute access rule not found.")
        for key, value in payload.model_dump().items():
            setattr(rule, key, value)
        self._audit(actor_id, "attribute_rule.updated", "attribute_access_rule", rule.id, f"Updated {rule.name}.")
        return AttributeAccessRuleRead.model_validate(rule)

    def delete_attribute_access_rule(self, rule_id: int, actor_id: int) -> None:
        rule = self._require(AttributeAccessRule, rule_id, "Attribute access rule not found.")
        self.session.delete(rule)
        self._audit(actor_id, "attribute_rule.deleted", "attribute_access_rule", rule_id, "Deleted attribute access rule.")

    def list_access_policies(self) -> list[AccessPolicyRead]:
        return [AccessPolicyRead.model_validate(item) for item in self.session.query(AccessPolicy).order_by(AccessPolicy.id).all()]

    def create_access_policy(self, payload: AccessPolicyCreate, actor_id: int) -> AccessPolicyRead:
        item = AccessPolicy(**payload.model_dump())
        self.session.add(item)
        self.session.flush()
        self._audit(actor_id, "access_policy.created", "access_policy", item.id, f"Created {item.name}.")
        return AccessPolicyRead.model_validate(item)

    def update_access_policy(self, policy_id: int, payload: AccessPolicyUpdate, actor_id: int) -> AccessPolicyRead:
        item = self._require(AccessPolicy, policy_id, "Access policy not found.")
        for key, value in payload.model_dump().items():
            setattr(item, key, value)
        self._audit(actor_id, "access_policy.updated", "access_policy", item.id, f"Updated {item.name}.")
        return AccessPolicyRead.model_validate(item)

    def delete_access_policy(self, policy_id: int, actor_id: int) -> None:
        item = self._require(AccessPolicy, policy_id, "Access policy not found.")
        self.session.delete(item)
        self._audit(actor_id, "access_policy.deleted", "access_policy", policy_id, "Deleted access policy.")

    def list_sod_policies(self) -> list[SoDPolicyRead]:
        policies = self.session.query(SoDPolicy).order_by(SoDPolicy.id).all()
        result = []
        for policy in policies:
            pairs = self.session.query(SoDPolicyPair).filter_by(sod_policy_id=policy.id).all()
            result.append(
                SoDPolicyRead(
                    id=policy.id,
                    name=policy.name,
                    description=policy.description,
                    mode=policy.mode,
                    severity=policy.severity,
                    active=policy.active,
                    resource_pairs=[[pair.left_resource_id, pair.right_resource_id] for pair in pairs],
                )
            )
        return result

    def create_sod_policy(self, payload: SoDPolicyCreate, actor_id: int) -> SoDPolicyRead:
        item = SoDPolicy(
            name=payload.name,
            description=payload.description,
            mode=payload.mode,
            severity=payload.severity,
            active=payload.active,
        )
        self.session.add(item)
        self.session.flush()
        self._sync_sod_pairs(item.id, payload.resource_pairs)
        self._audit(actor_id, "sod_policy.created", "sod_policy", item.id, f"Created {item.name}.")
        return self.list_sod_policies()[-1]

    def update_sod_policy(self, policy_id: int, payload: SoDPolicyUpdate, actor_id: int) -> SoDPolicyRead:
        item = self._require(SoDPolicy, policy_id, "SoD policy not found.")
        item.name = payload.name
        item.description = payload.description
        item.mode = payload.mode
        item.severity = payload.severity
        item.active = payload.active
        self._sync_sod_pairs(policy_id, payload.resource_pairs)
        self._audit(actor_id, "sod_policy.updated", "sod_policy", item.id, f"Updated {item.name}.")
        return [policy for policy in self.list_sod_policies() if policy.id == policy_id][0]

    def delete_sod_policy(self, policy_id: int, actor_id: int) -> None:
        item = self._require(SoDPolicy, policy_id, "SoD policy not found.")
        self.session.query(SoDPolicyPair).filter_by(sod_policy_id=policy_id).delete()
        self.session.delete(item)
        self._audit(actor_id, "sod_policy.deleted", "sod_policy", policy_id, "Deleted SoD policy.")

    def list_risk_rules(self) -> list[RiskRuleRead]:
        return [RiskRuleRead.model_validate(item) for item in self.session.query(RiskRule).order_by(RiskRule.id).all()]

    def create_risk_rule(self, payload: RiskRuleCreate, actor_id: int) -> RiskRuleRead:
        item = RiskRule(**payload.model_dump())
        self.session.add(item)
        self.session.flush()
        self._audit(actor_id, "risk_rule.created", "risk_rule", item.id, f"Created {item.name}.")
        return RiskRuleRead.model_validate(item)

    def update_risk_rule(self, rule_id: int, payload: RiskRuleUpdate, actor_id: int) -> RiskRuleRead:
        item = self._require(RiskRule, rule_id, "Risk rule not found.")
        for key, value in payload.model_dump().items():
            setattr(item, key, value)
        self._audit(actor_id, "risk_rule.updated", "risk_rule", item.id, f"Updated {item.name}.")
        return RiskRuleRead.model_validate(item)

    def delete_risk_rule(self, rule_id: int, actor_id: int) -> None:
        item = self._require(RiskRule, rule_id, "Risk rule not found.")
        self.session.delete(item)
        self._audit(actor_id, "risk_rule.deleted", "risk_rule", rule_id, "Deleted risk rule.")

    def list_approval_policies(self) -> list[ApprovalPolicyRead]:
        policies = self.session.query(ApprovalPolicy).order_by(ApprovalPolicy.id).all()
        return [self._approval_policy_read(item) for item in policies]

    def create_approval_policy(self, payload: ApprovalPolicyCreate, actor_id: int) -> ApprovalPolicyRead:
        item = ApprovalPolicy(
            name=payload.name,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            min_risk_score=payload.min_risk_score,
            sequential=payload.sequential,
            active=payload.active,
        )
        self.session.add(item)
        self.session.flush()
        self._sync_approval_stages(item.id, payload.stages)
        self._audit(actor_id, "approval_policy.created", "approval_policy", item.id, f"Created {item.name}.")
        return self._approval_policy_read(item)

    def update_approval_policy(self, policy_id: int, payload: ApprovalPolicyUpdate, actor_id: int) -> ApprovalPolicyRead:
        item = self._require(ApprovalPolicy, policy_id, "Approval policy not found.")
        item.name = payload.name
        item.scope_type = payload.scope_type
        item.scope_id = payload.scope_id
        item.min_risk_score = payload.min_risk_score
        item.sequential = payload.sequential
        item.active = payload.active
        self._sync_approval_stages(policy_id, payload.stages)
        self._audit(actor_id, "approval_policy.updated", "approval_policy", item.id, f"Updated {item.name}.")
        return self._approval_policy_read(item)

    def delete_approval_policy(self, policy_id: int, actor_id: int) -> None:
        item = self._require(ApprovalPolicy, policy_id, "Approval policy not found.")
        self.session.query(ApprovalStage).filter_by(policy_id=policy_id).delete()
        self.session.delete(item)
        self._audit(actor_id, "approval_policy.deleted", "approval_policy", policy_id, "Deleted approval policy.")

    def list_access_expiry_policies(self) -> list[AccessExpiryPolicyRead]:
        return [AccessExpiryPolicyRead.model_validate(item) for item in self.session.query(AccessExpiryPolicy).order_by(AccessExpiryPolicy.id).all()]

    def create_access_expiry_policy(self, payload: AccessExpiryPolicyCreate, actor_id: int) -> AccessExpiryPolicyRead:
        item = AccessExpiryPolicy(**payload.model_dump())
        self.session.add(item)
        self.session.flush()
        self._audit(actor_id, "expiry_policy.created", "access_expiry_policy", item.id, f"Created {item.name}.")
        return AccessExpiryPolicyRead.model_validate(item)

    def update_access_expiry_policy(self, policy_id: int, payload: AccessExpiryPolicyUpdate, actor_id: int) -> AccessExpiryPolicyRead:
        item = self._require(AccessExpiryPolicy, policy_id, "Access expiry policy not found.")
        for key, value in payload.model_dump().items():
            setattr(item, key, value)
        self._audit(actor_id, "expiry_policy.updated", "access_expiry_policy", item.id, f"Updated {item.name}.")
        return AccessExpiryPolicyRead.model_validate(item)

    def delete_access_expiry_policy(self, policy_id: int, actor_id: int) -> None:
        item = self._require(AccessExpiryPolicy, policy_id, "Access expiry policy not found.")
        self.session.delete(item)
        self._audit(actor_id, "expiry_policy.deleted", "access_expiry_policy", policy_id, "Deleted expiry policy.")

    # Reads
    def list_approval_instances(self, access_request_id: int | None = None, actor: Identity | None = None) -> list[ApprovalStageDecisionRead]:
        query = self.session.query(ApprovalStageDecision).order_by(ApprovalStageDecision.id)
        if access_request_id is not None:
            query = query.filter(ApprovalStageDecision.access_request_id == access_request_id)
        if actor and actor.role not in {"super_admin"}:
            query = query.filter(
                or_(
                    ApprovalStageDecision.approver_identity_id == actor.id,
                    ApprovalStageDecision.delegate_identity_id == actor.id,
                )
            )
        return [ApprovalStageDecisionRead.model_validate(item) for item in query.all()]

    def list_approval_stages(self, access_request_id: int | None = None) -> list[ApprovalStageRead]:
        query = self.session.query(ApprovalStage).order_by(ApprovalStage.policy_id, ApprovalStage.stage_order)
        if access_request_id is not None:
            request = self._require(AccessRequest, access_request_id, "Access request not found.")
            if request.approval_policy_id:
                query = query.filter(ApprovalStage.policy_id == request.approval_policy_id)
        return [ApprovalStageRead.model_validate(item) for item in query.all()]

    def list_policy_evaluations(self, access_request_id: int | None = None, identity_id: int | None = None) -> list[PolicyEvaluationResultRead]:
        query = self.session.query(PolicyEvaluationResult).order_by(PolicyEvaluationResult.id)
        if access_request_id is not None:
            query = query.filter(PolicyEvaluationResult.access_request_id == access_request_id)
        if identity_id is not None:
            query = query.filter(PolicyEvaluationResult.identity_id == identity_id)
        return [PolicyEvaluationResultRead.model_validate(item) for item in query.all()]

    def list_expiring_assignments(self, within_days: int = 30) -> list[ResourceAssignment]:
        limit_date = datetime.now(UTC) + timedelta(days=within_days)
        return (
            self.session.query(ResourceAssignment)
            .filter(
                ResourceAssignment.status == "active",
                ResourceAssignment.expires_at.is_not(None),
                ResourceAssignment.expires_at <= limit_date,
            )
            .order_by(ResourceAssignment.expires_at)
            .all()
        )

    # Identity recalculation
    def recalculate_identity_governance(self, identity_id: int, actor_id: int | None = None) -> RoleRecalculationResponse:
        identity = self._require(Identity, identity_id, "Identity not found.")
        business_created = 0
        technical_created = 0
        assignments_created = 0
        evals_created = 0

        for rule in self.session.query(BirthrightRule).filter(BirthrightRule.active.is_(True)).all():
            if not self._match_identity_rule(identity, rule.attribute_name, rule.operator, rule.expected_value):
                continue
            counts = self._apply_target_to_identity(identity, rule.target_type, rule.target_id, rule.grant_basis)
            business_created += counts["business"]
            technical_created += counts["technical"]
            assignments_created += counts["assignments"]

        for rule in self.session.query(AttributeAccessRule).filter(AttributeAccessRule.active.is_(True)).all():
            if not self._match_identity_rule(identity, rule.attribute_name, rule.operator, rule.expected_value):
                continue
            eval = PolicyEvaluationResult(
                access_request_id=None,
                identity_id=identity.id,
                resource_id=rule.target_id if rule.target_type == "resource" else None,
                result_type="attribute_rule",
                status=rule.mode,
                score=0,
                severity="info",
                details=f"Matched attribute rule {rule.name} for target {rule.target_type}:{rule.target_id}.",
            )
            self.session.add(eval)
            evals_created += 1
            if rule.mode == "assign":
                counts = self._apply_target_to_identity(identity, rule.target_type, rule.target_id, "attribute_rule")
                business_created += counts["business"]
                technical_created += counts["technical"]
                assignments_created += counts["assignments"]

        self._audit(actor_id, "governance.recalculated", "identity", identity.id, "Recalculated birthright and attribute rules.")
        return RoleRecalculationResponse(
            business_role_memberships_created=business_created,
            technical_role_memberships_created=technical_created,
            assignments_created=assignments_created,
            evaluations_created=evals_created,
        )

    # Request flow
    def submit_access_request(self, payload: AccessRequestCreate, actor: Identity) -> AccessRequest:
        beneficiary = self._require(Identity, payload.beneficiary_identity_id, "Beneficiary not found.")
        resource = self._require(Resource, payload.resource_id, "Resource not found.")
        request = AccessRequest(
            requester_identity_id=actor.id,
            beneficiary_identity_id=beneficiary.id,
            resource_id=resource.id,
            manager_identity_id=beneficiary.manager_id,
            reason=payload.reason,
            start_date=payload.start_date,
            end_date=payload.end_date,
            urgency=payload.urgency,
            comments=payload.comments,
            status="submitted",
            source_type="direct_request",
        )
        self.session.add(request)
        self.session.flush()

        eval_results, blocked, risk_score = self._evaluate_request(request, actor)
        request.risk_score = risk_score
        request.risk_level = self._risk_level(risk_score)
        request.policy_evaluation_summary = "; ".join(result.details for result in eval_results)
        if blocked:
            request.status = "rejected"
            self._audit(actor.id, "access_request.blocked", "access_request", request.id, request.policy_evaluation_summary, "critical")
            return request

        policy = self._resolve_approval_policy(resource, request)
        request.approval_policy_id = policy.id if policy else None
        if policy:
            request.current_stage_order = 1
            self._instantiate_stage(request, policy, 1)
            request.status = "submitted"
        else:
            # Fallback manager stage when no configured policy exists.
            self._instantiate_fallback_manager_stage(request, beneficiary)
            request.status = "submitted"

        self._audit(actor.id, "access_request.submitted", "access_request", request.id, request.policy_evaluation_summary or f"Requested {resource.name}.")
        return request

    def list_approvals(self, actor: Identity) -> list[ApprovalStageDecision]:
        query = self.session.query(ApprovalStageDecision).order_by(ApprovalStageDecision.id)
        if actor.role != "super_admin":
            query = query.filter(
                or_(
                    ApprovalStageDecision.approver_identity_id == actor.id,
                    ApprovalStageDecision.delegate_identity_id == actor.id,
                )
            )
        return query.all()

    def decide_approval(self, request_id: int, decision: ApprovalDecisionRequest, actor: Identity) -> ApprovalStageDecision:
        stage_decision = (
            self.session.query(ApprovalStageDecision)
            .filter(
                ApprovalStageDecision.access_request_id == request_id,
                ApprovalStageDecision.status == "pending",
                or_(
                    ApprovalStageDecision.approver_identity_id == actor.id,
                    ApprovalStageDecision.delegate_identity_id == actor.id,
                ),
            )
            .order_by(ApprovalStageDecision.id)
            .first()
        )
        if not stage_decision:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval decision not found for actor.")

        request = self._require(AccessRequest, request_id, "Access request not found.")
        if actor.id in {request.requester_identity_id, request.beneficiary_identity_id}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Self-approval is not allowed.")

        stage_decision.decision = decision.decision
        stage_decision.comment = decision.comment
        stage_decision.status = "completed"
        stage_decision.acted_at = datetime.now(UTC)

        approval_mirror = (
            self.session.query(Approval)
            .filter(
                Approval.access_request_id == request_id,
                Approval.approver_identity_id == stage_decision.approver_identity_id,
                Approval.status == "pending",
            )
            .first()
        )
        if approval_mirror:
            approval_mirror.decision = decision.decision
            approval_mirror.comment = decision.comment
            approval_mirror.status = "completed"

        stage = self._require(ApprovalStage, stage_decision.stage_id, "Approval stage not found.")
        all_stage_decisions = (
            self.session.query(ApprovalStageDecision)
            .filter(
                ApprovalStageDecision.access_request_id == request_id,
                ApprovalStageDecision.stage_id == stage.id,
            )
            .all()
        )

        if decision.decision == "reject":
            request.status = "rejected"
            self._create_follow_up_tasks(request, "approval_rejected")
            self._audit(actor.id, "approval.rejected", "access_request", request.id, decision.comment or "Rejected request.")
            return stage_decision

        stage_complete = self._stage_complete(stage, all_stage_decisions)
        if not stage_complete:
            self._audit(actor.id, "approval.partially_completed", "access_request", request.id, f"Completed stage {stage.stage_order} decision.")
            return stage_decision

        next_stage_order = stage.stage_order + 1
        next_stage = (
            self.session.query(ApprovalStage)
            .filter(ApprovalStage.policy_id == stage.policy_id, ApprovalStage.stage_order == next_stage_order)
            .first()
        )
        if next_stage:
            request.current_stage_order = next_stage_order
            self._instantiate_stage(request, self._require(ApprovalPolicy, stage.policy_id, "Approval policy not found."), next_stage_order)
            request.status = "approval_in_progress"
        else:
            request.status = "provisioning"
            self._create_follow_up_tasks(request, "approval_approved")
        self._audit(actor.id, "approval.approved", "access_request", request.id, decision.comment or "Approved request.")
        return stage_decision

    def complete_task(self, task_id: int, payload: ProvisioningTaskComplete, actor: Identity) -> ProvisioningTask:
        task = self._require(ProvisioningTask, task_id, "Task not found.")
        if task.status == "completed":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task already completed.")
        self._complete_task_and_apply_assignment(task, payload.completion_notes)
        self._audit(actor.id, "provisioning.completed", "provisioning_task", task.id, payload.completion_notes or "Completed provisioning task.")
        return task

    def revoke_assignment(self, assignment_id: int, actor: Identity, notes: str = "") -> ResourceAssignment:
        assignment = self._require(ResourceAssignment, assignment_id, "Assignment not found.")
        assignment.status = "revocation_pending"
        assignment.revoked_at = datetime.now(UTC)
        self._create_assignment_task(assignment, "revoke_requested", notes or f"Revocation requested for assignment {assignment.id}.")
        self._audit(actor.id, "assignment.revocation_requested", "resource_assignment", assignment.id, notes or "Revocation requested.")
        return assignment

    # Helpers
    def _evaluate_request(self, request: AccessRequest, actor: Identity) -> tuple[list[PolicyEvaluationResult], bool, int]:
        results: list[PolicyEvaluationResult] = []
        blocked = False
        risk_score = 0
        resource = self._require(Resource, request.resource_id, "Resource not found.")

        access_policy = self._resolve_access_policy(resource)
        if access_policy:
            if access_policy.privileged:
                risk_score += 30
                results.append(self._evaluation(request, "access_policy", "warn", 30, "high", f"Privileged access policy {access_policy.name} matched."))
            risk_score += access_policy.base_risk_score

        active_resource_ids = {
            item.resource_id
            for item in self.session.query(ResourceAssignment).filter(
                ResourceAssignment.identity_id == request.beneficiary_identity_id,
                ResourceAssignment.status == "active",
            )
        }
        for pair in self.session.query(SoDPolicyPair).all():
            if request.resource_id not in {pair.left_resource_id, pair.right_resource_id}:
                continue
            conflicting = pair.right_resource_id if request.resource_id == pair.left_resource_id else pair.left_resource_id
            if conflicting not in active_resource_ids:
                continue
            policy = self._require(SoDPolicy, pair.sod_policy_id, "SoD policy not found.")
            risk_score += 25
            status_value = "block" if policy.mode == "block" else "warn"
            results.append(
                self._evaluation(
                    request,
                    "sod_policy",
                    status_value,
                    25,
                    policy.severity,
                    f"SoD policy {policy.name} matched against resource pair {pair.left_resource_id}/{pair.right_resource_id}.",
                )
            )
            if policy.mode == "block":
                blocked = True

        for rule in self.session.query(RiskRule).filter(RiskRule.active.is_(True)).all():
            if self._risk_rule_matches(rule, request, actor, resource):
                risk_score += rule.score
                results.append(
                    self._evaluation(
                        request,
                        "risk_rule",
                        "warn",
                        rule.score,
                        rule.severity,
                        f"Risk rule {rule.name} matched.",
                    )
                )

        if request.urgency in {"high", "critical"}:
            urgency_score = 20 if request.urgency == "high" else 35
            risk_score += urgency_score
            results.append(self._evaluation(request, "urgency", "warn", urgency_score, "medium", f"Urgency {request.urgency} increased risk."))

        if actor.id != request.beneficiary_identity_id:
            risk_score += 10
            results.append(self._evaluation(request, "beneficiary_mismatch", "warn", 10, "medium", "Request submitted on behalf of another identity."))

        return results, blocked, risk_score

    def _resolve_access_policy(self, resource: Resource) -> AccessPolicy | None:
        return (
            self.session.query(AccessPolicy)
            .filter(
                AccessPolicy.active.is_(True),
                or_(AccessPolicy.resource_id == resource.id, AccessPolicy.system_id == resource.system_id),
            )
            .order_by(AccessPolicy.resource_id.desc())
            .first()
        )

    def _resolve_approval_policy(self, resource: Resource, request: AccessRequest) -> ApprovalPolicy | None:
        candidates = (
            self.session.query(ApprovalPolicy)
            .filter(ApprovalPolicy.active.is_(True))
            .order_by(ApprovalPolicy.min_risk_score.desc(), ApprovalPolicy.id.asc())
            .all()
        )
        for policy in candidates:
            if request.risk_score < policy.min_risk_score:
                continue
            if policy.scope_type == "resource" and policy.scope_id == resource.id:
                return policy
            if policy.scope_type == "system" and policy.scope_id == resource.system_id:
                return policy
            if policy.scope_type == "risk":
                return policy
            if policy.scope_type == "default":
                return policy
        return None

    def _instantiate_fallback_manager_stage(self, request: AccessRequest, beneficiary: Identity) -> None:
        if not beneficiary.manager_id:
            request.status = "provisioning"
            self._create_follow_up_tasks(request, "approval_approved")
            return
        stage = ApprovalStage(
            policy_id=0,
            stage_order=1,
            mode="all",
            approver_type="manager",
            approver_value="",
            required_count=1,
        )
        self.session.add(stage)
        self.session.flush()
        decision = ApprovalStageDecision(
            access_request_id=request.id,
            stage_id=stage.id,
            approver_identity_id=beneficiary.manager_id,
            delegate_identity_id=self._active_delegate_for(beneficiary.manager_id, "approval"),
            decision="pending",
            comment="",
            status="pending",
        )
        self.session.add(decision)
        self.session.add(
            Approval(
                access_request_id=request.id,
                approver_identity_id=beneficiary.manager_id,
                decision="pending",
                comment="",
                status="pending",
            )
        )

    def _instantiate_stage(self, request: AccessRequest, policy: ApprovalPolicy, stage_order: int) -> None:
        stages = (
            self.session.query(ApprovalStage)
            .filter(ApprovalStage.policy_id == policy.id, ApprovalStage.stage_order == stage_order)
            .all()
        )
        for stage in stages:
            approver_ids = self._resolve_stage_approvers(stage, request)
            if not approver_ids:
                continue
            for approver_id in approver_ids:
                delegate_id = self._active_delegate_for(approver_id, "approval")
                self.session.add(
                    ApprovalStageDecision(
                        access_request_id=request.id,
                        stage_id=stage.id,
                        approver_identity_id=approver_id,
                        delegate_identity_id=delegate_id,
                        decision="pending",
                        comment="",
                        status="pending",
                    )
                )
                self.session.add(
                    Approval(
                        access_request_id=request.id,
                        approver_identity_id=approver_id,
                        decision="pending",
                        comment="",
                        status="pending",
                    )
                )

    def _resolve_stage_approvers(self, stage: ApprovalStage, request: AccessRequest) -> list[int]:
        resource = self._require(Resource, request.resource_id, "Resource not found.")
        system = self._require(System, resource.system_id, "System not found.")
        if stage.approver_type == "manager":
            return [request.manager_identity_id] if request.manager_identity_id else []
        if stage.approver_type in {"resource_owner", "system_owner"}:
            return [system.owner_identity_id] if system.owner_identity_id else []
        if stage.approver_type in {"risk_security_role", "role"}:
            return [
                item.id
                for item in self.session.query(Identity).filter(Identity.role == (stage.approver_value or "super_admin")).all()
            ]
        if stage.approver_type == "fixed_identity":
            raw = [value.strip() for value in stage.approver_value.split(",") if value.strip()]
            approvers: list[int] = []
            for value in raw:
                if value.isdigit():
                    approvers.append(int(value))
                else:
                    identity = self.session.query(Identity).filter(Identity.username == value).first()
                    if identity:
                        approvers.append(identity.id)
            return approvers
        return []

    def _stage_complete(self, stage: ApprovalStage, decisions: list[ApprovalStageDecision]) -> bool:
        completed = [item for item in decisions if item.status == "completed" and item.decision == "approve"]
        if stage.mode == "any":
            return len(completed) >= 1
        return len(completed) >= max(stage.required_count, len(decisions))

    def _resolve_expiry_for_request(self, request: AccessRequest) -> datetime | None:
        if request.end_date:
            return request.end_date if request.end_date.tzinfo else request.end_date.replace(tzinfo=UTC)
        resource_policy = (
            self.session.query(AccessExpiryPolicy)
            .filter(AccessExpiryPolicy.active.is_(True), AccessExpiryPolicy.resource_id == request.resource_id)
            .first()
        )
        if resource_policy:
            return datetime.now(UTC) + timedelta(days=resource_policy.default_duration_days)
        access_policy = (
            self.session.query(AccessPolicy)
            .filter(AccessPolicy.active.is_(True), AccessPolicy.resource_id == request.resource_id)
            .first()
        )
        if access_policy:
            return datetime.now(UTC) + timedelta(days=access_policy.max_duration_days)
        return None

    def _create_follow_up_tasks(self, request: AccessRequest, trigger_event: str) -> None:
        mapping = (
            self.session.query(TaskMapping)
            .filter(
                TaskMapping.resource_id == request.resource_id,
                or_(TaskMapping.trigger_event == trigger_event, TaskMapping.action == "grant"),
            )
            .order_by(TaskMapping.id)
            .first()
        )
        if mapping:
            task_type = mapping.task_type
            owner_role = mapping.default_owner_role
        else:
            task_type = "manual_provision" if trigger_event == "approval_approved" else "manual_follow_up"
            owner_role = "operator"
        task = ProvisioningTask(
            access_request_id=request.id,
            identity_id=request.beneficiary_identity_id,
            resource_id=request.resource_id,
            task_type=task_type,
            owner_role=owner_role,
            status="pending",
            urgency="critical" if trigger_event == "approval_rejected" else request.urgency,
            details=f"Triggered by {trigger_event} for request {request.id}.",
        )
        self.session.add(task)
        self.session.flush()
        if mapping and mapping.provisioning_mode == "automatic":
            self._run_automatic_task(task, mapping)

    def _create_assignment_task(self, assignment: ResourceAssignment, trigger_event: str, details: str) -> None:
        mapping = (
            self.session.query(TaskMapping)
            .filter(
                TaskMapping.resource_id == assignment.resource_id,
                or_(TaskMapping.trigger_event == trigger_event, TaskMapping.task_type == "urgent_deprovision"),
            )
            .first()
        )
        self.session.add(
            ProvisioningTask(
                access_request_id=None,
                identity_id=assignment.identity_id,
                resource_id=assignment.resource_id,
                task_type=mapping.task_type if mapping else "urgent_deprovision",
                owner_role=mapping.default_owner_role if mapping else "operator",
                status="pending",
                urgency="critical",
                details=details,
            )
        )

    def _run_automatic_task(self, task: ProvisioningTask, mapping: TaskMapping) -> None:
        connector = self._require(Connector, mapping.connector_id, "Connector not found.") if mapping.connector_id else None
        if connector is None or not mapping.connector_operation:
            task.status = "failed"
            task.details = f"{task.details}\nAutomatic provisioning is missing connector configuration.".strip()
            return
        payload = self._connector_payload(task, mapping)
        adapter = build_connector(connector.connector_type, json.loads(connector.config_json or "{}"))
        if mapping.connector_operation == "provision":
            result = adapter.provision(payload)
        elif mapping.connector_operation == "deprovision":
            result = adapter.deprovision(payload)
        elif mapping.connector_operation == "group_sync":
            result = adapter.group_sync()
        elif mapping.connector_operation == "reconcile":
            result = adapter.reconcile()
        elif mapping.connector_operation in {"import", "sync"}:
            result = adapter.import_sync()
        else:
            result = adapter.discover()
        run = ConnectorRun(
            connector_id=connector.id,
            operation=mapping.connector_operation,
            status="completed" if result.status == "ok" else "failed",
            dry_run=connector.dry_run,
            summary=result.summary,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        self.session.add(run)
        if result.status == "ok":
            self._complete_task_and_apply_assignment(task, f"Automatic connector run succeeded: {result.summary}")
            return
        task.status = "failed"
        task.details = f"{task.details}\nAutomatic connector run failed: {result.summary}".strip()

    def _complete_task_and_apply_assignment(self, task: ProvisioningTask, notes: str = "") -> None:
        task.status = "completed"
        task.details = f"{task.details}\n{notes}".strip()
        if task.access_request_id and task.resource_id:
            request = self._require(AccessRequest, task.access_request_id, "Access request not found.")
            expires_at = self._resolve_expiry_for_request(request)
            existing = self.session.query(ResourceAssignment).filter_by(
                identity_id=task.identity_id,
                resource_id=task.resource_id,
                status="active",
            ).first()
            if not existing:
                self.session.add(
                    ResourceAssignment(
                        identity_id=task.identity_id,
                        resource_id=task.resource_id,
                        status="active",
                        granted_at=datetime.now(UTC),
                        expires_at=expires_at,
                        source_type=request.source_type,
                        source_id=request.id,
                        risk_score=request.risk_score,
                        governance_state="approved",
                    )
                )
            request.status = "completed"

    def _connector_payload(self, task: ProvisioningTask, mapping: TaskMapping) -> dict:
        template = json.loads(mapping.payload_template_json or "{}")
        template.update(
            {
                "identity_id": task.identity_id,
                "resource_id": task.resource_id,
                "access_request_id": task.access_request_id,
                "task_id": task.id,
                "action": mapping.action,
            }
        )
        return template

    def _match_identity_rule(self, identity: Identity, attribute_name: str, operator: str, expected_value: str) -> bool:
        values = {
            "username": identity.username,
            "full_name": identity.full_name,
            "email": identity.email,
            "role": identity.role,
            "status": identity.status,
            "email_domain": identity.email.split("@", maxsplit=1)[1] if "@" in identity.email else "",
        }
        actual = str(values.get(attribute_name, ""))
        if operator == "equals":
            return actual == expected_value
        if operator == "contains":
            return expected_value in actual
        if operator == "starts_with":
            return actual.startswith(expected_value)
        return False

    def _apply_target_to_identity(self, identity: Identity, target_type: str, target_id: int, source: str) -> dict[str, int]:
        counts = {"business": 0, "technical": 0, "assignments": 0}
        if target_type == "business_role":
            if not self.session.query(BusinessRoleMembership).filter_by(identity_id=identity.id, business_role_id=target_id).first():
                self.session.add(BusinessRoleMembership(identity_id=identity.id, business_role_id=target_id, source=source, status="active"))
                counts["business"] += 1
            for resource_id in self._resource_ids_for_business_role(target_id):
                counts["assignments"] += self._ensure_assignment(identity.id, resource_id, source, target_id)
            return counts
        if target_type == "technical_role":
            if not self.session.query(TechnicalRoleMembership).filter_by(identity_id=identity.id, technical_role_id=target_id).first():
                self.session.add(TechnicalRoleMembership(identity_id=identity.id, technical_role_id=target_id, source=source, status="active"))
                counts["technical"] += 1
            for resource_id in self._resource_ids_for_technical_role(target_id):
                counts["assignments"] += self._ensure_assignment(identity.id, resource_id, source, target_id)
            return counts
        if target_type == "resource":
            counts["assignments"] += self._ensure_assignment(identity.id, target_id, source, target_id)
            return counts
        return counts

    def _ensure_assignment(self, identity_id: int, resource_id: int, source_type: str, source_id: int) -> int:
        existing = self.session.query(ResourceAssignment).filter_by(
            identity_id=identity_id,
            resource_id=resource_id,
            status="active",
        ).first()
        if existing:
            return 0
        expires_at = None
        expiry_policy = self.session.query(AccessExpiryPolicy).filter(
            AccessExpiryPolicy.active.is_(True),
            AccessExpiryPolicy.resource_id == resource_id,
        ).first()
        if expiry_policy:
            expires_at = datetime.now(UTC) + timedelta(days=expiry_policy.default_duration_days)
        self.session.add(
            ResourceAssignment(
                identity_id=identity_id,
                resource_id=resource_id,
                status="active",
                granted_at=datetime.now(UTC),
                expires_at=expires_at,
                source_type=source_type,
                source_id=source_id,
                governance_state="approved",
            )
        )
        return 1

    def _resource_ids_for_business_role(self, role_id: int) -> set[int]:
        direct = {
            item.resource_id
            for item in self.session.query(BusinessRoleResource).filter_by(business_role_id=role_id).all()
        }
        technical = {
            link.technical_role_id
            for link in self.session.query(BusinessRoleTechnicalRole).filter_by(business_role_id=role_id).all()
        }
        for technical_role_id in technical:
            direct.update(self._resource_ids_for_technical_role(technical_role_id))
        return direct

    def _resource_ids_for_technical_role(self, role_id: int) -> set[int]:
        return {
            item.resource_id
            for item in self.session.query(TechnicalRoleResource).filter_by(technical_role_id=role_id).all()
        }

    def _risk_rule_matches(self, rule: RiskRule, request: AccessRequest, actor: Identity, resource: Resource) -> bool:
        if rule.condition_type == "urgency":
            return request.urgency == rule.condition_value
        if rule.condition_type == "system":
            return str(resource.system_id) == rule.condition_value
        if rule.condition_type == "resource":
            return str(resource.id) == rule.condition_value
        if rule.condition_type == "delegated":
            return actor.id != request.beneficiary_identity_id
        return False

    def _active_delegate_for(self, approver_id: int, scope: str) -> int | None:
        now = datetime.now(UTC)
        delegation = (
            self.session.query(Delegation)
            .filter(
                Delegation.delegator_identity_id == approver_id,
                Delegation.scope.in_([scope, "access"]),
                Delegation.status == "active",
                Delegation.starts_at <= now,
                Delegation.ends_at >= now,
            )
            .order_by(Delegation.id.desc())
            .first()
        )
        return delegation.delegate_identity_id if delegation else None

    def _risk_level(self, score: int) -> str:
        if score >= 80:
            return "critical"
        if score >= 50:
            return "high"
        if score >= 20:
            return "medium"
        return "low"

    def _evaluation(
        self,
        request: AccessRequest,
        result_type: str,
        status_value: str,
        score: int,
        severity: str,
        details: str,
    ) -> PolicyEvaluationResult:
        result = PolicyEvaluationResult(
            access_request_id=request.id,
            identity_id=request.beneficiary_identity_id,
            resource_id=request.resource_id,
            result_type=result_type,
            status=status_value,
            score=score,
            severity=severity,
            details=details,
        )
        self.session.add(result)
        return result

    def _sync_business_role_links(self, role_id: int, technical_role_ids: list[int], resource_ids: list[int]) -> None:
        self.session.query(BusinessRoleTechnicalRole).filter_by(business_role_id=role_id).delete()
        self.session.query(BusinessRoleResource).filter_by(business_role_id=role_id).delete()
        for technical_role_id in technical_role_ids:
            self.session.add(BusinessRoleTechnicalRole(business_role_id=role_id, technical_role_id=technical_role_id))
        for resource_id in resource_ids:
            self.session.add(BusinessRoleResource(business_role_id=role_id, resource_id=resource_id))

    def _sync_technical_role_links(self, role_id: int, resource_ids: list[int]) -> None:
        self.session.query(TechnicalRoleResource).filter_by(technical_role_id=role_id).delete()
        for resource_id in resource_ids:
            self.session.add(TechnicalRoleResource(technical_role_id=role_id, resource_id=resource_id))

    def _sync_sod_pairs(self, policy_id: int, resource_pairs: list[list[int]]) -> None:
        self.session.query(SoDPolicyPair).filter_by(sod_policy_id=policy_id).delete()
        for pair in resource_pairs:
            if len(pair) != 2:
                continue
            self.session.add(SoDPolicyPair(sod_policy_id=policy_id, left_resource_id=pair[0], right_resource_id=pair[1]))

    def _sync_approval_stages(self, policy_id: int, stages) -> None:
        self.session.query(ApprovalStage).filter_by(policy_id=policy_id).delete()
        for stage in stages:
            self.session.add(
                ApprovalStage(
                    policy_id=policy_id,
                    stage_order=stage.stage_order,
                    mode=stage.mode,
                    approver_type=stage.approver_type,
                    approver_value=stage.approver_value,
                    required_count=stage.required_count,
                )
            )

    def _approval_policy_read(self, item: ApprovalPolicy) -> ApprovalPolicyRead:
        stages = [
            ApprovalStageRead.model_validate(stage)
            for stage in self.session.query(ApprovalStage).filter_by(policy_id=item.id).order_by(ApprovalStage.stage_order, ApprovalStage.id).all()
        ]
        return ApprovalPolicyRead(
            id=item.id,
            name=item.name,
            scope_type=item.scope_type,
            scope_id=item.scope_id,
            min_risk_score=item.min_risk_score,
            sequential=item.sequential,
            active=item.active,
            stages=[
                {
                    "stage_order": stage.stage_order,
                    "mode": stage.mode,
                    "approver_type": stage.approver_type,
                    "approver_value": stage.approver_value,
                    "required_count": stage.required_count,
                }
                for stage in stages
            ],
        )

    def _business_role_read(self, role: BusinessRole) -> BusinessRoleRead:
        technical_role_ids = [
            item.technical_role_id
            for item in self.session.query(BusinessRoleTechnicalRole).filter_by(business_role_id=role.id).all()
        ]
        resource_ids = [
            item.resource_id
            for item in self.session.query(BusinessRoleResource).filter_by(business_role_id=role.id).all()
        ]
        return BusinessRoleRead(
            id=role.id,
            name=role.name,
            description=role.description,
            requestable=role.requestable,
            risk_level=role.risk_level,
            active=role.active,
            technical_role_ids=technical_role_ids,
            resource_ids=resource_ids,
        )

    def _technical_role_read(self, role: TechnicalRole) -> TechnicalRoleRead:
        resource_ids = [
            item.resource_id
            for item in self.session.query(TechnicalRoleResource).filter_by(technical_role_id=role.id).all()
        ]
        return TechnicalRoleRead(
            id=role.id,
            name=role.name,
            description=role.description,
            requestable=role.requestable,
            active=role.active,
            resource_ids=resource_ids,
        )

    def _audit(self, actor_id: int | None, event_type: str, entity_type: str, entity_id: int | None, details: str, severity: str = "info") -> None:
        record_audit(
            self.session,
            actor_identity_id=actor_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            severity=severity,
            details=details,
        )

    def _require(self, model, entity_id: int, message: str):
        entity = self.session.get(model, entity_id)
        if not entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
        return entity

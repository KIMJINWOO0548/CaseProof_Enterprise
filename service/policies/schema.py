"""Strict synthetic pack registration schema; no insurance-law assertions."""
from datetime import timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, model_validator

from service.api.schemas_v1 import BusinessDate, InputTimestamp, JSONModel, RegisteredId

DateField = Literal['contract_date', 'incident_date', 'claim_date', 'consultation_date']


class Approval(JSONModel):
    recorded_at: InputTimestamp
    status: Literal['DRAFT', 'APPROVED', 'REVOKED']
    evidence_id: RegisteredId


class Source(JSONModel):
    source_id: RegisteredId
    policy_version: RegisteredId
    approval_history: list[Approval] = Field(min_length=1)

    @model_validator(mode='after')
    def ordered_history(self):
        times = [event.recorded_at for event in self.approval_history]
        if times != sorted(set(times)):
            raise ValueError('approval history must be strictly increasing')
        return self


class Workflow(JSONModel):
    workflow: RegisteredId
    date_basis_version: RegisteredId
    date_basis: DateField
    required_dates: list[DateField] = Field(min_length=1)

    @model_validator(mode='after')
    def required_basis(self):
        if self.date_basis not in self.required_dates or len(set(self.required_dates)) != len(self.required_dates):
            raise ValueError('required dates must be unique and include date basis')
        return self


class RetroactivityPolicy(JSONModel):
    policy_id: RegisteredId
    reviewed: bool
    evidence_id: RegisteredId | None

    @model_validator(mode='after')
    def review_evidence(self):
        if self.reviewed and not self.evidence_id:
            raise ValueError('reviewed retroactivity policy requires evidence')
        return self


class Priorities(JSONModel):
    version: RegisteredId
    approved: bool
    evidence_id: RegisteredId | None
    ranks: dict[RegisteredId, int]

    @model_validator(mode='after')
    def approved_evidence(self):
        if self.approved and not self.evidence_id:
            raise ValueError('approved priority requires evidence')
        return self


class Rule(JSONModel):
    rule_id: RegisteredId
    product_id: RegisteredId
    workflow: RegisteredId
    rule_key: RegisteredId
    source_id: RegisteredId
    clause_id: RegisteredId
    valid_from: BusinessDate
    valid_to: BusinessDate | None
    recorded_from: InputTimestamp
    recorded_to: InputTimestamp | None
    rider_code: RegisteredId | None
    priority_key: RegisteredId
    retroactive: bool
    value: int = Field(ge=0, le=9999)
    unit: Literal['days']

    @model_validator(mode='after')
    def intervals(self):
        if self.valid_to is not None and self.valid_from >= self.valid_to:
            raise ValueError('business interval must be increasing')
        if self.recorded_to is not None and self.recorded_from >= self.recorded_to:
            raise ValueError('recorded interval must be increasing')
        return self


class PolicyPack(JSONModel):
    schema_version: Literal['caseproof.policy-pack.v1']
    synthetic: Literal[True]
    tenant_id: RegisteredId
    pack_id: RegisteredId
    pack_version: RegisteredId
    business_timezone: str
    product_ids: list[RegisteredId] = Field(min_length=1)
    workflows: list[Workflow] = Field(min_length=1)
    retroactivity_policy_id: RegisteredId
    retroactivity_policies: list[RetroactivityPolicy] = Field(min_length=1)
    priorities: Priorities
    sources: list[Source] = Field(min_length=1)
    rules: list[Rule] = Field(min_length=1)

    @model_validator(mode='after')
    def references(self):
        try:
            timezone.utc if self.business_timezone == 'UTC' else ZoneInfo(self.business_timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError('unknown business timezone') from exc
        for values in ([s.source_id for s in self.sources], [r.rule_id for r in self.rules],
                       [w.workflow for w in self.workflows], self.product_ids,
                       [p.policy_id for p in self.retroactivity_policies]):
            if len(values) != len(set(values)):
                raise ValueError('duplicate pack identifiers')
        if self.retroactivity_policy_id not in {p.policy_id for p in self.retroactivity_policies}:
            raise ValueError('unregistered retroactivity policy')
        for rule in self.rules:
            if (rule.source_id not in {s.source_id for s in self.sources}
                    or rule.product_id not in self.product_ids
                    or rule.workflow not in {w.workflow for w in self.workflows}
                    or rule.priority_key not in self.priorities.ranks):
                raise ValueError('unregistered rule reference')
        return self

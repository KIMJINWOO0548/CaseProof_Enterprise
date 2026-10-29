from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime, date

Hex64 = str

class ChangeCreate(BaseModel):
    title: str = Field(min_length=5,max_length=160)
    product: str = Field(min_length=1,max_length=80)
    workflow: str = Field(min_length=1,max_length=80)
    rule_key: str = Field(min_length=1,max_length=100)
    dataset_hash: Hex64
    evaluator_hash: Hex64
    source_hash: Hex64
    @field_validator('dataset_hash','evaluator_hash','source_hash')
    @classmethod
    def validate_hash(cls,v):
        if len(v)!=64 or any(x not in '0123456789abcdef' for x in v):
            raise ValueError('must be 64 lowercase sha256 hex chars')
        return v

class EvalRequest(BaseModel):
    claim_days: int = Field(ge=0,le=9999)
    basis_date: date
    rider_codes: list[str] = Field(default_factory=list,max_length=20)
    requested_policy_version: str | None = None
    as_of_recorded: datetime
    @field_validator('as_of_recorded')
    @classmethod
    def recorded_timezone(cls,v):
        if not v.tzinfo or v.utcoffset() is None:
            raise ValueError('as_of_recorded timezone required')
        return v

class Transition(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str = Field(default='',max_length=500)

class Decision(Transition):
    decision: Literal['APPROVE','REJECT']
    @model_validator(mode='after')
    def require_reason(self):
        if len(self.reason.strip()) < 8:
            raise ValueError('reason must contain at least 8 meaningful characters')
        return self

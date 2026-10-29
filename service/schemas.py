import re
from typing import Annotated, Literal
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator
from datetime import datetime, date

Hex64 = str

def positive_revision_header(value):
    # HTTP headers arrive as strings; reject coercible but noncanonical spellings.
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]*', value):
        raise ValueError('X-Expected-Revision must be a canonical positive decimal integer')
    return int(value)


RevisionHeader = Annotated[int, BeforeValidator(positive_revision_header)]


class RequestBody(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ChangeCreate(RequestBody):
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

class EvalRequest(RequestBody):
    claim_days: int = Field(
        strict=True, ge=0, le=9999,
        description='JSON integer only (0–9999); booleans, strings and floats such as 1.0 are rejected at runtime.',
        json_schema_extra={'x-strict-json-integer': True},
    )
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

class Transition(RequestBody):
    expected_revision: int = Field(ge=1, strict=True,
        description='Positive JSON integer only; booleans, strings and floats are rejected.',
        json_schema_extra={'x-strict-json-integer': True})
    reason: str = Field(default='',max_length=500)

class Decision(Transition):
    reason: str = Field(
        min_length=8, max_length=500,
        description='Required reason: both the original and str.strip() result must contain 8–500 Unicode code points; the stripped value is stored.',
    )
    decision: Literal['APPROVE','REJECT']
    @field_validator('reason')
    @classmethod
    def require_reason(cls, value):
        value = value.strip()
        if not 8 <= len(value) <= 500:
            raise ValueError('reason after str.strip() must contain 8–500 Unicode code points')
        return value

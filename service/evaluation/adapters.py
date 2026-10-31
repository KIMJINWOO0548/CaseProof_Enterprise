"""Bounded local numeric adapter. No gold, private metadata, or network access."""
from service.api.schemas_v1 import CaseInput


class FakeDeterministicAdapter:
    def execute(self, case_input):
        case = CaseInput.model_validate(case_input)
        return {'claim_days': case.claim_days}

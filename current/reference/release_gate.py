"""Synthetic RELEASE_FOR_DEMO gate. Does not deploy real systems."""

def check_release(facts: dict):
    blocks = []
    reviews = []
    if facts.get("kill_switch", False): blocks.append("KILL_SWITCH_ACTIVE")
    if facts.get("dataset_hash_mismatch", True): blocks.append("DATASET_SNAPSHOT_MISMATCH")
    if facts.get("evaluator_hash_mismatch", True): blocks.append("EVALUATOR_VERSION_MISMATCH")
    if not facts.get("sources_approved", False): blocks.append("SOURCE_NOT_APPROVED")
    if not facts.get("audit_verified", False): blocks.append("AUDIT_INTEGRITY_FAILURE")
    if facts.get("mandatory_missing", 1) > 0: blocks.append("MANDATORY_TEST_INCOMPLETE")
    if facts.get("new_critical_failures", 1) > 0: blocks.append("CRITICAL_REGRESSION")
    if facts.get("execution_errors", 1) > 0: blocks.append("EXECUTION_INCOMPLETE")
    if facts.get("unmapped_impact", True): reviews.append("UNMAPPED_IMPACT_REVIEW")
    if facts.get("unresolved_review_count", 1) > 0: reviews.append("PENDING_DOMAIN_REVIEW")
    actor = facts.get("requester_id")
    approver = facts.get("approver_id")
    if not actor or not approver or actor == approver:
        blocks.append("SOD_VIOLATION")
    if blocks:
        return {"status":"BLOCKED", "blocking_reasons":blocks, "review_reasons":reviews}
    if reviews:
        return {"status":"PENDING_APPROVAL", "blocking_reasons":[], "review_reasons":reviews}
    return {"status":"APPROVED_FOR_DEMO", "blocking_reasons":[], "review_reasons":[]}

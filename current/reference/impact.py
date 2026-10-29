"""Reference change-impact test planner; not a production graph service."""
from collections import deque


def select_tests(changed_nodes: list[str], edges: list[list[str]], sentinel: list[str], previous_critical: list[str]):
    next_hops = {}
    for src, dst in edges:
        next_hops.setdefault(src, set()).add(dst)
    visited = set(changed_nodes)
    queue = deque(changed_nodes)
    impacted = set()
    unmapped = set()
    while queue:
        node = queue.popleft()
        children = next_hops.get(node, set())
        if not children and not node.startswith("test:"):
            unmapped.add(node)
        for child in children:
            if child not in visited:
                visited.add(child)
                queue.append(child)
            if child.startswith("test:"):
                impacted.add(child[5:])
    selected = impacted | set(sentinel) | set(previous_critical)
    return {
        "selected_test_ids": sorted(selected),
        "directly_impacted_test_ids": sorted(impacted),
        "unmapped_impact_nodes": sorted(unmapped),
        "needs_manual_impact_review": bool(unmapped),
        "selection_reasons": {
            x: (["DEPENDENCY"] if x in impacted else [])
             + (["SENTINEL"] if x in sentinel else [])
             + (["PREVIOUS_CRITICAL"] if x in previous_critical else [])
            for x in sorted(selected)
        },
    }

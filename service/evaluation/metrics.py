"""Exact registered scenario-group paired bootstrap (contract §14)."""
import hashlib
from pathlib import Path


class EvaluationDependencyUnavailable(RuntimeError):
    pass


def paired_ci95(deltas_by_family: dict[str, list[int]], *, lock_path) -> dict:
    groups = sorted(deltas_by_family)
    if not groups or any(not deltas_by_family[group] or
                         any(type(value) is not int or value not in {-1, 0, 1}
                             for value in deltas_by_family[group]) for group in groups):
        raise ValueError("bootstrap requires nonempty groups of paired correctness differences")
    result = dict(interval=None, reason=None, cluster_count=len(groups), seed=20261028,
                  replicates=10000, quantile_method="linear", numpy_version=None,
                  lock_sha256=None, independence_assumption="scenario_family groups are independent")
    if len(groups) < 2:
        result["reason"] = "INSUFFICIENT_CLUSTERS"
        return result
    try:
        import numpy as np
    except ImportError as exc:
        raise EvaluationDependencyUnavailable("NumPy evaluation dependency is unavailable; install the approved hash lock") from exc
    if lock_path is None or not Path(lock_path).is_file():
        raise EvaluationDependencyUnavailable("NumPy dependency lock is required for reproducible evaluation")
    result["numpy_version"] = np.__version__
    result["lock_sha256"] = hashlib.sha256(Path(lock_path).read_bytes()).hexdigest()
    sums = np.array([sum(deltas_by_family[group]) for group in groups], dtype=np.int64)
    sizes = np.array([len(deltas_by_family[group]) for group in groups], dtype=np.int64)
    rng = np.random.Generator(np.random.PCG64(seed=20261028))
    draws = rng.integers(0, len(groups), size=(10000, len(groups)))
    deltas = 100 * sums[draws].sum(axis=1) / sizes[draws].sum(axis=1)
    result["interval"] = np.quantile(deltas, [0.025, 0.975], method="linear").tolist()
    return result

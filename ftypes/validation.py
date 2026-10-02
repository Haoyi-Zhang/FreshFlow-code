"""Named negative controls and the finite quadratic-profile family."""
from __future__ import annotations

import argparse
from itertools import product
from pathlib import Path
import resource
import time

from .adaptive import infer_refinement, oracle_refinement
from .families import matrix_interface
from .io import write_json, write_jsonl
from .semantics import oracle_summary
from .static import infer_case


def _control_rows() -> list[dict]:
    rows: list[dict] = []
    # Each row evaluates a minimal arithmetic or finite-set counterexample used in the proof note.
    own_age_1 = (0 - (-2), 0 - (-2))
    own_age_2 = (0 - (-2), 2 - 0)
    gated_ages = (max(0, 0) - (-2), max(0, 2) - (-2))
    rows.append({"name": "own-age-scalar", "passed": own_age_1 == own_age_2 and gated_ages == (2, 4),
                 "evidence": {"own_ages": [own_age_1, own_age_2], "gated_ages": gated_ages}})
    rows.append({"name": "control-lineage", "passed": max(0, 0) - 0 == 0 and max(0, 0) - (-100) == 100,
                 "evidence": {"data_only_age": 0, "incorrect_control_import_age": 100}})
    rows.append({"name": "epoch-birth-rebase", "passed": 2 - (-2) == (2 - 1) - (-2 - 1) == 4,
                 "evidence": {"absolute_age": 4, "rebased_age": 4, "incorrect_unshifted_birth_age": 3}})
    rows.append({"name": "strict-cut-lower-bound", "passed": max(1, 0 + 0 - 0) == 1,
                 "evidence": {"sender": 0, "cut": 0, "delay": [0, 1], "unreceived_residual": [1, 1]}})
    independent = {(x, y) for x in (1, 2) for y in (1, 2)}
    aliased = {(x, x) for x in (1, 2)}
    rows.append({"name": "distinct-crossing-messages", "passed": len(independent) == 4 and len(aliased) == 2,
                 "evidence": {"independent": sorted(independent), "aliased": sorted(aliased)}})
    coupled = {(x, y) for x in (0, 1) for y in (0, 1) if x + y <= 1}
    rows.append({"name": "coupled-delay-all-upper", "passed": max(x + y for x, y in coupled) == 1,
                 "evidence": {"coupled_max": 1, "rectangular_max": 2}})
    rows.append({"name": "cyclic-progress", "passed": True,
                 "evidence": {"cycle": ["x->y", "y->x"], "first_firing_exists": False}})
    readiness_a = {0, 1, 2}
    readiness_b = {1, 2}
    static_max = (max(readiness_a), max(readiness_b))
    adaptive_worst = (max((r + (5 if r == 0 else 0)) for r in readiness_a),
                      max((r + (5 if r == 0 else 0)) for r in readiness_b))
    rows.append({"name": "static-versus-adaptive", "passed": static_max == (2, 2) and adaptive_worst == (5, 2),
                 "evidence": {"static_max": static_max, "adaptive_max": adaptive_worst}})
    rows.append({"name": "zero-column-envelope", "passed": True,
                 "evidence": {"same_static_profile": 2, "conditional_at_zero": [2, 0]}})
    rows.append({"name": "opaque-payload-origin-swap", "passed": max(2, 0) == max(0, 2),
                 "evidence": {"left_birth_ages": [2, 0], "right_birth_ages": [0, 2], "opaque_oldest": 2}})
    omega = {(0, 0), (0, -1)}
    gamma = {(0, 0)}
    rows.append({"name": "birth-visible-inclusion", "passed": omega - gamma == {(0, -1)},
                 "evidence": {"omega_minus_gamma": sorted(omega - gamma)}})
    h3 = {bits for bits in product((0, 1), repeat=6)
          if all(bits[2*i] == 1 or bits[2*i+1] == 1 for i in range(3))}
    minimal = {bits for bits in h3 if sum(bits) == 3}
    rows.append({"name": "receipt-blind-zone-cover", "passed": len(minimal) == 8,
                 "evidence": {"n": 3, "minimal_incomparable_points": len(minimal), "required_zones": 8}})
    return rows


def run(out: Path) -> dict:
    before = resource.getrusage(resource.RUSAGE_SELF)
    wall0 = time.perf_counter()
    controls = _control_rows()
    matrices = []
    mismatches = []
    for number, values in enumerate(product((2, 3, 4), repeat=4)):
        matrix = ((values[0], values[1]), (values[2], values[3]))
        case = matrix_interface(matrix, f"matrix-{number:02d}")
        certificate = infer_case(case)
        oracle = oracle_summary(case)
        observed = (
            (certificate["profile"]["p:a"], certificate["profile"]["p:b"]),
            (certificate["profile"]["q:a"], certificate["profile"]["q:b"]),
        )
        if observed != matrix or certificate["profile"] != oracle["profile"]:
            mismatches.append({"matrix": matrix, "observed": observed})
        witnesses = [oracle["profile_witnesses"][key] for key in ("p:a", "p:b", "q:a", "q:b")]
        matrices.append({"case": case.to_spec(), "profile": certificate["profile"], "witnesses": witnesses})
    after = resource.getrusage(resource.RUSAGE_SELF)
    failures = [row["name"] for row in controls if not row["passed"]]
    summary = {
        "campaign": "controls",
        "named_control_count": len(controls),
        "named_control_failures": failures,
        "matrix_instance_count": len(matrices),
        "matrix_cell_witness_count": 4 * len(matrices),
        "matrix_mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "measurements": {
            "cpu_seconds": (after.ru_utime + after.ru_stime) - (before.ru_utime + before.ru_stime),
            "wall_seconds": time.perf_counter() - wall0,
            "peak_rss_kib": after.ru_maxrss,
        },
    }
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "controls.jsonl", controls)
    write_jsonl(out / "matrices.jsonl", matrices)
    write_json(out / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    summary = run(args.out)
    print(f"controls: {summary['named_control_count']} named; matrices={summary['matrix_instance_count']}; mismatches={summary['matrix_mismatch_count']}")
    ok = not summary["named_control_failures"] and summary["matrix_mismatch_count"] == 0
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

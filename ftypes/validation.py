"""Named negative controls and the finite quadratic-profile family."""
from __future__ import annotations

import argparse
from itertools import product
from pathlib import Path
from . import measurements as resource
import time

from .adaptive import check_refinement, infer_refinement
from .adaptive_oracle import raw_valuations
from .families import matrix_interface
from .io import write_json, write_jsonl
from .model import ModelError, case_from_spec
from .residual import residualize
from .semantics import enumerate_executions, oracle_summary, prefix_of
from .static import check_case, infer_case


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
    cyclic_spec = matrix_interface(((2, 2), (2, 2)), "cyclic-control").to_spec()
    cyclic_spec["nodes"] = [{"name": "x", "op": "copy", "data": ["y"], "gates": [], "delays": {"y": [0, 0]}},
                            {"name": "y", "op": "copy", "data": ["x"], "gates": [], "delays": {"x": [0, 0]}}]
    rejected = False
    try:
        case_from_spec(cyclic_spec)
    except ModelError:
        rejected = True
    dependencies = {"x": {"y"}, "y": {"x"}}
    enabled = [v for v, preds in dependencies.items() if not preds]
    rows.append({"name": "cyclic-progress", "passed": rejected and not enabled,
                 "evidence": {"input": cyclic_spec, "parser_rejected": rejected, "enabled_first_events": enabled}})
    readiness_a = {0, 1, 2}
    readiness_b = {1, 2}
    static_max = (max(readiness_a), max(readiness_b))
    adaptive_worst = (max((r + (5 if r == 0 else 0)) for r in readiness_a),
                      max((r + (5 if r == 0 else 0)) for r in readiness_b))
    rows.append({"name": "static-versus-adaptive", "passed": static_max == (2, 2) and adaptive_worst == (5, 2),
                 "evidence": {"static_max": static_max, "adaptive_max": adaptive_worst}})
    left_spec = matrix_interface(((2, 2), (2, 2)), "zero-left").to_spec()
    left_spec["zones"][0]["constraints"] = [["r_p", "r_q", 0], ["r_q", "r_p", 0],
                                           ["r_p", "b_a", -2], ["b_a", "r_p", 2],
                                           ["b_a", "b_b", 0], ["b_b", "b_a", 0]]
    right_spec = matrix_interface(((2, 2), (2, 2)), "zero-right").to_spec()
    right_spec["zones"][0]["bounds"]["b_a"] = [0, 0]
    right_spec["zones"][0]["bounds"]["b_b"] = [0, 0]
    right_spec["zones"][0]["constraints"] = [["r_p", "r_q", 0], ["r_q", "r_p", 0]]
    left, right = case_from_spec(left_spec), case_from_spec(right_spec)
    profiles = [infer_case(c)["profile"] for c in (left, right)]
    conditional = [-min(w["b_a"] for w in raw_valuations(c) if w["r_p"] == w["r_q"] == 0) for c in (left, right)]
    rows.append({"name": "zero-column-envelope", "passed": profiles[0] == profiles[1] and conditional == [2, 0],
                 "evidence": {"inputs": [left_spec, right_spec], "profiles": profiles, "conditional_at_zero": conditional}})
    rows.append({"name": "opaque-payload-origin-swap", "passed": max(2, 0) == max(0, 2),
                 "evidence": {"left_birth_ages": [2, 0], "right_birth_ages": [0, 2], "opaque_oldest": 2}})
    omega = {(0, 0), (0, -1)}
    gamma = {(0, 0)}
    rows.append({"name": "birth-visible-inclusion", "passed": omega - gamma == {(0, -1)},
                 "evidence": {"omega_minus_gamma": sorted(omega - gamma)}})
    h3 = {bits for bits in product((0, 1), repeat=6)
          if all(bits[2*i] == 1 or bits[2*i+1] == 1 for i in range(3))}
    minimal = {bits for bits in h3 if sum(bits) == 3}
    minima_outside = all(tuple(min(x, y) for x, y in zip(a, b)) not in h3
                         for a in minimal for b in minimal if a != b)
    cover = set().union(*[{bits for bits in product((0, 1), repeat=6)
                          if all(bits[2*i+choice[i]] == 1 for i in range(3))}
                         for choice in product((0, 1), repeat=3)])
    rows.append({"name": "receipt-blind-zone-cover", "passed": len(minimal) == 8 and minima_outside and cover == h3,
                 "evidence": {"n": 3, "minimal_incomparable_points": len(minimal), "required_zones": 8,
                              "pairwise_minima_outside": minima_outside, "cover_equals_h3": cover == h3}})
    # Exercise the actual interpreter/residual/checkers for the arithmetic controls.
    from .families import make_case
    def fixed(values, name, *, opaque=False):
        spec = make_case(0, 1, 0, small=True, case_id=name).to_spec()
        spec["zones"] = [{"name": name, "bounds": {v: [x, x] for v, x in values.items()}, "constraints": []}]
        if opaque:
            spec["ports"][0]["term"] = "pair(src(a),src(b))"
            spec["outputs"][0]["term"] = "pair(src(a),src(b))"
        return case_from_spec(spec)
    scalar_cases = [fixed(dict(zip(("b_a", "b_b", "r_p", "r_q"), values)), f"scalar-{i}")
                    for i, values in enumerate(((-2, -2, 0, 0), (-2, 0, 0, 2)))]
    scalar_ages = [next(enumerate_executions(c)).outputs[0][3] for c in scalar_cases]
    rows[0]["passed"] &= scalar_ages == [2, 4]
    rows[0]["evidence"]["executed_ages"] = scalar_ages
    lineage_case = fixed({"b_a": 0, "b_b": -100, "r_p": 0, "r_q": 0}, "gate-lineage")
    lineage_run = next(enumerate_executions(lineage_case))
    rows[1]["passed"] &= lineage_run.outputs[0][1:] == ("src(a)", 0, 0)
    rows[1]["evidence"]["executed_output"] = lineage_run.outputs[0]
    rebase_case = fixed({"b_a": -2, "b_b": 0, "r_p": 0, "r_q": 0}, "rebase")
    spec = rebase_case.to_spec()
    spec["nodes"][0]["delays"]["p"] = [2, 2]
    rebase_case = case_from_spec(spec)
    original = next(enumerate_executions(rebase_case))
    residual = residualize(rebase_case, prefix_of(original, 1))
    rebased = next(enumerate_executions(residual.case))
    rows[2]["passed"] &= original.outputs[0][3] == rebased.outputs[0][3] == 4
    rows[2]["evidence"]["original_output"] = original.outputs[0]
    rows[2]["evidence"]["residual_output"] = rebased.outputs[0]
    strict = make_case(0, 0, 1, small=True, case_id="strict").to_spec()
    strict["zones"][0]["bounds"] = {"b_a": [0, 0], "b_b": [0, 0], "r_p": [0, 0], "r_q": [0, 0]}
    strict_case = case_from_spec(strict)
    r = residualize(strict_case, (0, (("p", 0), ("q", 0)), ()))
    observed_interval = list(r.case.zones[0].bounds["r_cross-p-x"])
    rows[3]["passed"] &= observed_interval == [1, 1]
    rows[3]["evidence"]["constructed_interval"] = observed_interval
    twins = strict_case.to_spec()
    twins["id"] = "twins"
    twins["nodes"] = [{"name": name, "op": "copy", "data": ["p"], "gates": [], "delays": {"p": [1, 2]}} for name in ("x", "y")]
    twin_case = case_from_spec(twins)
    twin_residual = residualize(twin_case, (0, (("p", 0), ("q", 0)), ()))
    pairs = {(w["r_cross-p-x"], w["r_cross-p-y"]) for w in raw_valuations(twin_residual.case)}
    rows[4]["passed"] &= pairs == independent
    rows[4]["evidence"]["constructed_pairs"] = sorted(pairs)
    swap_left = fixed({"b_a": -2, "b_b": 0, "r_p": 0, "r_q": 0}, "swap-left", opaque=True)
    swap_right = fixed({"b_a": 0, "b_b": -2, "r_p": 0, "r_q": 0}, "swap-right", opaque=True)
    # Both ports must hide the source-specific metadata in this opaque control.
    swap_cases = []
    for c in (swap_left, swap_right):
        spec = c.to_spec()
        spec["ports"][1]["term"] = "unit"
        swap_cases.append(case_from_spec(spec))
    swaps = [check_refinement(a, b, infer_refinement(a, b))["accepted"] for a, b in (swap_cases, swap_cases[::-1])]
    rows[9]["passed"] &= all(swaps)
    rows[9]["evidence"]["replayed_bidirectional_refinement"] = swaps
    full_difference = [w for w in raw_valuations(swap_cases[0]) if w not in raw_valuations(swap_cases[1])]
    rows[10]["passed"] &= bool(full_difference)
    rows[10]["evidence"]["full_left_only_valuations"] = full_difference
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
        check_case(case, certificate)
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

"""Closed-prefix and exact residual-continuation campaign."""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import resource
import time

from .families import cut_cases
from .io import write_json, write_jsonl
from .residual import compare_prefix
from .semantics import enumerate_executions, future_observation, prefix_of
from .static import check_case, infer_case


def run(out: Path, start: int = 0, stop: int = 32, pilot: bool = False) -> dict:
    cases = list(cut_cases())
    if pilot:
        start, stop = 0, min(2, len(cases))
    if not 0 <= start <= stop <= len(cases):
        raise ValueError("invalid cut case range")
    before = resource.getrusage(resource.RUSAGE_SELF)
    wall0 = time.perf_counter()
    case_rows = []
    prefix_rows = []
    original_assignments = 0
    prefix_visits = 0
    residual_assignments = 0
    policy_checks = 0
    mismatches = []
    for case_index, case in enumerate(cases[start:stop], start=start):
        case_rows.append(case.to_spec())
        executions = list(enumerate_executions(case))
        original_assignments += len(executions)
        groups: dict[tuple, set[tuple]] = defaultdict(set)
        for execution in executions:
            last_output = max(item[2] for item in execution.outputs)
            # Every retained prefix has at least one remaining output.
            for cut in range(0, last_output):
                prefix = prefix_of(execution, cut)
                groups[prefix].add(future_observation(case, execution, cut))
                prefix_visits += 1
        for prefix_index, (prefix, expected) in enumerate(sorted(groups.items(), key=repr)):
            result = compare_prefix(case, prefix, expected, residual_id=f"res-{case_index:02d}-{prefix_index:04d}")
            residual_assignments += result["residual_assignment_count"]
            residual_case = result.pop("residual_case")
            cert = infer_case(__import__("ftypes.model", fromlist=["case_from_spec"]).case_from_spec(residual_case))
            replay = check_case(__import__("ftypes.model", fromlist=["case_from_spec"]).case_from_spec(residual_case), cert)
            policy_checks += 1
            if not result["equal"]:
                mismatches.append({"case": case.case_id, "prefix": prefix_index, "kind": "future-observation"})
            if not replay["admitted"]:
                mismatches.append({"case": case.case_id, "prefix": prefix_index, "kind": "residual-policy"})
            prefix_rows.append({
                "case": case.case_id,
                "prefix_index": prefix_index,
                "cut": prefix[0],
                "events": list(prefix[1]),
                "receipts": list(prefix[2]),
                "comparison": result,
                "residual": residual_case,
                "certificate": cert,
            })
    after = resource.getrusage(resource.RUSAGE_SELF)
    summary = {
        "campaign": "cuts",
        "selection": {"interface_families": 4, "graph_shapes": 8, "start": start, "stop": stop},
        "case_count": stop - start,
        "original_assignment_count": original_assignments,
        "prefix_visit_count": prefix_visits,
        "distinct_prefix_count": len(prefix_rows),
        "residual_assignment_count": residual_assignments,
        "residual_policy_check_count": policy_checks,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "measurements": {
            "cpu_seconds": (after.ru_utime + after.ru_stime) - (before.ru_utime + before.ru_stime),
            "wall_seconds": time.perf_counter() - wall0,
            "peak_rss_kib": after.ru_maxrss,
        },
    }
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "cases.jsonl", case_rows)
    write_jsonl(out / "prefixes.jsonl", prefix_rows)
    write_json(out / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=32)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    summary = run(args.out, args.start, args.stop, args.pilot)
    print(f"cuts: {summary['case_count']} cases; prefixes={summary['distinct_prefix_count']}; mismatches={summary['mismatch_count']}")
    raise SystemExit(0 if summary["mismatch_count"] == 0 else 1)


if __name__ == "__main__":
    main()

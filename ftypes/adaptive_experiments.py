"""Single-zone adaptive-refinement campaign."""
from __future__ import annotations

import argparse
from pathlib import Path
import resource
import time

from .adaptive import check_refinement, infer_refinement, oracle_refinement
from .families import adaptive_interfaces
from .io import write_json, write_jsonl
from .semantics import interface_valuations


def run(out: Path, pilot: bool = False) -> dict:
    interfaces = adaptive_interfaces()
    groups = {group: [case for case in interfaces if case.metadata["group"] == group] for group in range(3)}
    if pilot:
        groups = {0: groups[0][:4]}
        interfaces = groups[0]
    before = resource.getrusage(resource.RUSAGE_SELF)
    wall0 = time.perf_counter()
    comparisons = []
    valuation_count = sum(len(interface_valuations(case)) for case in interfaces)
    accepted = 0
    rejected = 0
    support_rejections = 0
    row_rejections = 0
    conditional_cells = 0
    mismatches = []
    for group, members in groups.items():
        for left in members:
            for right in members:
                certificate = infer_refinement(left, right)
                replay = check_refinement(left, right, certificate)
                oracle = oracle_refinement(left, right)
                conditional_cells += oracle["conditional_cells_checked"]
                if certificate["accepted"]:
                    accepted += 1
                else:
                    rejected += 1
                    support_rejections += certificate.get("reason") == "support"
                    row_rejections += certificate.get("reason") == "row-cover"
                if certificate["accepted"] != oracle["accepted"] or replay["accepted"] != certificate["accepted"]:
                    mismatches.append({"left": left.case_id, "right": right.case_id})
                comparisons.append({
                    "group": group,
                    "left": left.case_id,
                    "right": right.case_id,
                    "certificate": certificate,
                    "oracle": oracle,
                })
    after = resource.getrusage(resource.RUSAGE_SELF)
    summary = {
        "campaign": "adaptive",
        "interface_count": len(interfaces),
        "group_count": len(groups),
        "ordered_comparison_count": len(comparisons),
        "full_clock_valuation_count_sum": valuation_count,
        "conditional_cell_check_count": conditional_cells,
        "accepted_count": accepted,
        "rejected_count": rejected,
        "support_rejection_count": support_rejections,
        "row_cover_rejection_count": row_rejections,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "measurements": {
            "cpu_seconds": (after.ru_utime + after.ru_stime) - (before.ru_utime + before.ru_stime),
            "wall_seconds": time.perf_counter() - wall0,
            "peak_rss_kib": after.ru_maxrss,
        },
    }
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "interfaces.jsonl", [case.to_spec() for case in interfaces])
    write_jsonl(out / "comparisons.jsonl", comparisons)
    write_json(out / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    summary = run(args.out, args.pilot)
    print(f"adaptive: {summary['ordered_comparison_count']} comparisons; accepted={summary['accepted_count']}; mismatches={summary['mismatch_count']}")
    raise SystemExit(0 if summary["mismatch_count"] == 0 else 1)


if __name__ == "__main__":
    main()

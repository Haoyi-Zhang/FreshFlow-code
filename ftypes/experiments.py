"""Fixed-graph exact-analysis campaign."""
from __future__ import annotations

import argparse
from pathlib import Path
import resource
import time

from .families import static_cases
from .io import write_json, write_jsonl
from .semantics import oracle_summary
from .static import check_case, infer_case


def run(out: Path, start: int = 0, stop: int = 128, pilot: bool = False) -> dict:
    cases = list(static_cases())
    if pilot:
        start, stop = 0, min(4, len(cases))
    if not (0 <= start <= stop <= len(cases)):
        raise ValueError("invalid case range")
    chosen = cases[start:stop]
    before = resource.getrusage(resource.RUSAGE_SELF)
    wall0 = time.perf_counter()
    case_rows = []
    certificate_rows = []
    oracle_rows = []
    assignment_count = 0
    valuation_count = 0
    threshold_decisions = 0
    mismatches = []
    for case in chosen:
        certificate = infer_case(case)
        replay = check_case(case, certificate)
        oracle = oracle_summary(case)
        case_rows.append(case.to_spec())
        certificate_rows.append(certificate)
        oracle_rows.append(oracle)
        assignment_count += oracle["assignment_count"]
        valuation_count += oracle["valuation_count"]
        predicted_profile = certificate["profile"]
        if predicted_profile != oracle["profile"]:
            mismatches.append({"case": case.case_id, "kind": "profile"})
        for output in certificate["outputs"]:
            key = output["key"]
            exact = output["exact_worst_age"]
            if exact != oracle["worst_age"][key]:
                mismatches.append({"case": case.case_id, "kind": "age", "key": key})
            if oracle["output_terms"][key] != [output["actual_term"]]:
                mismatches.append({"case": case.case_id, "kind": "term", "key": key})
            for deadline in (max(0, exact - 1), exact, exact + 1):
                threshold_decisions += 1
                predicted = exact <= deadline
                actual = oracle["worst_age"][key] <= deadline
                if predicted != actual:
                    mismatches.append({"case": case.case_id, "kind": "threshold", "deadline": deadline})
        if replay["admitted"] != certificate["admitted"]:
            mismatches.append({"case": case.case_id, "kind": "replay"})
    wall = time.perf_counter() - wall0
    after = resource.getrusage(resource.RUSAGE_SELF)
    summary = {
        "campaign": "static",
        "selection": {
            "interface_families": 8,
            "graph_shapes": 8,
            "delay_widths": 2,
            "start": start,
            "stop": stop,
        },
        "case_count": len(chosen),
        "valuation_count_sum": valuation_count,
        "input_delay_assignment_count": assignment_count,
        "threshold_decision_count": threshold_decisions,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "measurements": {
            "cpu_seconds": (after.ru_utime + after.ru_stime) - (before.ru_utime + before.ru_stime),
            "wall_seconds": wall,
            "peak_rss_kib": after.ru_maxrss,
        },
    }
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "cases.jsonl", case_rows)
    write_jsonl(out / "certificates.jsonl", certificate_rows)
    write_jsonl(out / "oracle.jsonl", oracle_rows)
    write_json(out / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=128)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    summary = run(args.out, args.start, args.stop, args.pilot)
    print(f"static: {summary['case_count']} cases; mismatches={summary['mismatch_count']}")
    raise SystemExit(0 if summary["mismatch_count"] == 0 else 1)


if __name__ == "__main__":
    main()

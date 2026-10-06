#!/usr/bin/env python3
"""Create deterministic LaTeX macros and tables from the shipped validation summaries."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name: str) -> dict:
    return json.loads((ROOT / "results" / name / "summary.json").read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "paper-data", help="output directory")
    args = parser.parse_args()
    target = args.out.resolve()
    target.mkdir(parents=True, exist_ok=True)
    s, a, c, n = (read(x) for x in ("static", "adaptive", "cuts", "controls"))
    values = {
        "StaticCaseCount": s["case_count"],
        "StaticValuationCount": s["valuation_count_sum"],
        "StaticAssignmentCount": s["input_delay_assignment_count"],
        "StaticThresholdCount": s["threshold_decision_count"],
        "StaticThresholdAssignmentCount": s["threshold_input_delay_assignment_count"],
        "AdaptiveInterfaceCount": a["interface_count"],
        "AdaptiveComparisonCount": a["ordered_comparison_count"],
        "AdaptiveAcceptedCount": a["accepted_count"],
        "AdaptiveRejectedCount": a["rejected_count"],
        "AdaptiveSupportRejectionCount": a["support_rejection_count"],
        "AdaptiveRowRejectionCount": a["row_cover_rejection_count"],
        "AdaptiveCellCount": a["conditional_cell_check_count"],
        "AdaptiveValuationCount": a["full_clock_valuation_count_sum"],
        "AdaptiveSeparatorCount": a["separator_execution_check_count"],
        "AdaptiveSeparatorRightCheckCount": a["separator_right_full_valuation_check_count"],
        "CutCaseCount": c["case_count"],
        "CutAssignmentCount": c["original_assignment_count"],
        "CutPrefixVisitCount": c["prefix_visit_count"],
        "CutDistinctPrefixCount": c["distinct_prefix_count"],
        "CutResidualAssignmentCount": c["residual_assignment_count"],
        "CutEmptyOutputPrefixCount": c["empty_output_prefix_count"],
        "CutEmptyOutputPendingPrefixCount": c["empty_output_with_pending_work_prefix_count"],
        "NamedControlCount": n["named_control_count"],
        "MatrixInstanceCount": n["matrix_instance_count"],
        "MatrixWitnessCount": n["matrix_cell_witness_count"],
        "TotalMismatchCount": s["mismatch_count"] + a["mismatch_count"] + c["mismatch_count"] + n["matrix_mismatch_count"] + len(n["named_control_failures"]),
    }
    lines = ["% Generated from results by make_paper_data.py."]
    for key, value in values.items():
        lines.append(f"\\newcommand{{\\{key}}}{{{value:,}}}")
    (target / "validation-macros.tex").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    rows = [
        ("Static graph analysis", s["case_count"], f"{s['input_delay_assignment_count']:,} schedules; {s['threshold_decision_count']:,} threshold decisions", s["mismatch_count"]),
        ("Adaptive refinement", a["ordered_comparison_count"], f"{a['conditional_cell_check_count']:,} conditional cells", a["mismatch_count"]),
        ("Non-quiescent cuts", c["distinct_prefix_count"], f"{c['prefix_visit_count']:,} prefix visits; {c['residual_assignment_count']:,} residual schedules", c["mismatch_count"]),
        ("Negative controls and matrix family", n["named_control_count"] + n["matrix_instance_count"], f"{n['matrix_cell_witness_count']:,} matrix witnesses", n["matrix_mismatch_count"] + len(n["named_control_failures"])),
    ]
    tex = ["% Generated from results by make_paper_data.py.", "\\begin{tabularx}{\\textwidth}{@{}p{.25\\textwidth}rXr@{}}", "\\toprule", "Campaign & Units & Exhaustive checks & Mismatches \\\\", "\\midrule"]
    for name, units, detail, mismatches in rows:
        tex.append(f"{name} & {units:,} & {detail} & {mismatches} \\\\")
    tex.extend(["\\bottomrule", "\\end{tabularx}"])
    (target / "validation-table.tex").write_text("\n".join(tex) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()

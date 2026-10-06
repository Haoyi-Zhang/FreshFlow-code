#!/usr/bin/env python3
"""Regenerate all finite evidence under the documented bounds and compare it with the shipped results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent


def canonical(value: Any) -> Any:
    """Drop environment-dependent timing/memory fields before scientific comparison."""
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items() if k != "measurements"}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    return value


def load_jsonish(path: Path) -> Any:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return json.loads(path.read_text(encoding="utf-8"))


def compare_tree(expected: Path, actual: Path) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    expected_files = sorted(p.relative_to(expected) for p in expected.rglob("*") if p.is_file())
    actual_files = sorted(p.relative_to(actual) for p in actual.rglob("*") if p.is_file())
    if expected_files != actual_files:
        failures.append({"kind": "file-set", "expected": str(expected_files), "actual": str(actual_files)})
        return failures
    for rel in expected_files:
        left = expected / rel
        right = actual / rel
        if rel.suffix in {".json", ".jsonl"}:
            same = canonical(load_jsonish(left)) == canonical(load_jsonish(right))
        else:
            same = left.read_bytes() == right.read_bytes()
        if not same:
            failures.append({"kind": "content", "file": rel.as_posix()})
    return failures


def bounded(record: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "run_bounded.py"), "--record", str(record), "--", *command],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "reproduced")
    parser.add_argument("--keep", action="store_true", help="do not remove an existing output directory")
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT) or out == ROOT or out.is_relative_to(ROOT / "results"):
        parser.error("reproduction output must be a separate directory inside the artifact root")
    if out.exists() and not args.keep:
        parser.error("output already exists; use a new directory or --keep (no deletion is performed)")
    out.mkdir(parents=True, exist_ok=True)

    commands = [
        ("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("static", [sys.executable, "-m", "ftypes.experiments", "--out", str(out / "static")]),
        ("adaptive", [sys.executable, "-m", "ftypes.adaptive_experiments", "--out", str(out / "adaptive")]),
        ("cuts", [sys.executable, "-m", "ftypes.residual_experiments", "--out", str(out / "cuts")]),
        ("controls", [sys.executable, "-m", "ftypes.validation", "--out", str(out / "controls")]),
    ]
    command_rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for name, command in commands:
        record = out / "resource" / f"{name}.json"
        completed = bounded(record, command)
        (out / "logs").mkdir(parents=True, exist_ok=True)
        (out / "logs" / f"{name}.stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (out / "logs" / f"{name}.stderr.txt").write_text(completed.stderr, encoding="utf-8")
        command_rows.append({"name": name, "command": command, "exit_status": completed.returncode})
        if completed.returncode != 0:
            failures.append({"kind": "command", "name": name, "status": str(completed.returncode)})

    for campaign in ("static", "adaptive", "cuts", "controls"):
        if (out / campaign).exists():
            failures.extend(
                {**failure, "campaign": campaign}
                for failure in compare_tree(ROOT / "results" / campaign, out / campaign)
            )

    report = {
        "schema": "freshness-reproduction-1",
        "status": "pass" if not failures else "fail",
        "comparison_policy": "JSON measurements fields are ignored; every other generated value and file is compared.",
        "commands": command_rows,
        "failure_count": len(failures),
        "failures": failures,
    }
    (out / "reproduction.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

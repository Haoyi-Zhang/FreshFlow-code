"""Command-line interface for checking, replay, finite oracle, and refinement."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .adaptive import check_refinement, infer_refinement
from .io import write_json
from .kernel import CertificateError
from .model import ModelError, load_case
from .semantics import OracleLimit, oracle_summary
from .static import check_case, infer_case


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ftypes.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("input", type=Path)
    check.add_argument("--certificate", type=Path)
    replay = sub.add_parser("replay")
    replay.add_argument("input", type=Path)
    replay.add_argument("--certificate", type=Path, required=True)
    oracle = sub.add_parser("oracle")
    oracle.add_argument("input", type=Path)
    refine = sub.add_parser("refine")
    refine.add_argument("left", type=Path)
    refine.add_argument("right", type=Path)
    refine.add_argument("--certificate", type=Path)
    refine_replay = sub.add_parser("refine-replay")
    refine_replay.add_argument("left", type=Path)
    refine_replay.add_argument("right", type=Path)
    refine_replay.add_argument("--certificate", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            case = load_case(args.input)
            certificate = infer_case(case)
            result = check_case(case, certificate)
            if args.certificate:
                write_json(args.certificate, certificate)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["admitted"] else 1
        if args.command == "replay":
            case = load_case(args.input)
            certificate = json.loads(args.certificate.read_text(encoding="utf-8"))
            result = check_case(case, certificate)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["admitted"] else 1
        if args.command == "oracle":
            case = load_case(args.input)
            print(json.dumps(oracle_summary(case), indent=2, sort_keys=True))
            return 0
        left = load_case(args.left)
        right = load_case(args.right)
        if args.command == "refine":
            certificate = infer_refinement(left, right)
            result = check_refinement(left, right, certificate)
            if args.certificate:
                write_json(args.certificate, certificate)
        else:
            certificate = json.loads(args.certificate.read_text(encoding="utf-8"))
            result = check_refinement(left, right, certificate)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["accepted"] else 1
    except (OSError, json.JSONDecodeError, ModelError, CertificateError, OracleLimit, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

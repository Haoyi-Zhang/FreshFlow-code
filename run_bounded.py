#!/usr/bin/env python3
"""Run one command with POSIX resource limits when available and a wall timeout.

Windows uses the wall timeout only; its records explicitly mark other limits
and unavailable child CPU/peak-memory measurements as null.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
try:
    import resource
except ImportError:
    resource = None
import subprocess
import sys
import time


def _limit() -> None:
    allowed = sorted(os.sched_getaffinity(0))
    if allowed:
        os.sched_setaffinity(0, {allowed[0]})
    memory = 3 * 1024**3
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    resource.setrlimit(resource.RLIMIT_CPU, (40, 41))
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    except (ValueError, OSError):
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a command is required after --")
    before = resource.getrusage(resource.RUSAGE_CHILDREN) if resource is not None else None
    wall0 = time.perf_counter()
    try:
        kwargs = {"preexec_fn": _limit} if resource is not None and hasattr(os, "sched_getaffinity") else {}
        completed = subprocess.run(command, timeout=45, check=False, **kwargs)
        status = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired:
        status = 124
        timed_out = True
    after = resource.getrusage(resource.RUSAGE_CHILDREN) if resource is not None else None
    record = {
        "command": command,
        "exit_status": status,
        "timed_out": timed_out,
        "cpu_seconds": None if after is None else (after.ru_utime + after.ru_stime) - (before.ru_utime + before.ru_stime),
        "wall_seconds": time.perf_counter() - wall0,
        "peak_rss_kib": None if after is None else after.ru_maxrss,
        "limits": {"cpus": 1 if kwargs else None, "address_space_bytes": 3 * 1024**3 if kwargs else None,
                   "cpu_seconds": 40 if kwargs else None, "wall_seconds": 45},
        "limit_mode": "posix-resource" if kwargs else "portable-wall-time-only",
    }
    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return status


if __name__ == "__main__":
    raise SystemExit(main())

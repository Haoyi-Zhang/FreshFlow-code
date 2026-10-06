"""Tiny raw-bound reference, independent of DBM closure and envelope helpers.

No producer, closure, support projection, or conditional-row calculation is
called here. Full birth/readiness assignments are filtered by original edges.
"""
from __future__ import annotations

from itertools import product

from .model import Case
from .semantics import OracleLimit
from .terms import format_term, lineage


def raw_valuations(case: Case, *, cap: int = 100_000) -> list[dict[str, int]]:
    result = {}
    candidates = 0
    for zone in case.zones:
        variables = zone.variables[1:]
        volume = 1
        for v in variables:
            lo, hi = zone.bounds[v]
            volume *= hi - lo + 1
        candidates += volume
        if candidates > cap:
            raise OracleLimit("raw valuation Cartesian volume exceeds tiny oracle cap")
        ranges = [range(zone.bounds[v][0], zone.bounds[v][1] + 1) for v in variables]
        for values in product(*ranges):
            w = {"zero": 0, **dict(zip(variables, values))}
            if any(w[f"r_{p.name}"] < 0 or any(w[f"b_{s}"] > w[f"r_{p.name}"]
                   for s in lineage(p.term)) for p in case.ports):
                continue
            if all(w[e.v] - w[e.u] <= e.c for e in zone.constraints):
                result[tuple(w[v] for v in case.variables)] = w
    return [result[k] for k in sorted(result)]


def _fibers(case: Case, valuations: list[dict]) -> dict:
    ready = ("zero",) + tuple(f"r_{p.name}" for p in case.ports)
    fibers = {}
    for w in valuations:
        fibers.setdefault(tuple(w[v] for v in ready), []).append(w)
    return fibers


def _k(case: Case, port: str, fiber: list[dict]) -> int:
    # Directly minimize every original birth in this enumerated fiber.
    return max(-min(w[f"b_{s}"] for w in fiber)
               for s in lineage(case.port_map[port].term))


def oracle_refinement(left: Case, right: Case) -> dict:
    if len(left.zones) != 1 or len(right.zones) != 1:
        raise ValueError("tiny adaptive comparison requires single zones")
    if left.origins != right.origins or [(p.name, p.term) for p in left.ports] != [(p.name, p.term) for p in right.ports]:
        raise ValueError("adaptive oracle metadata mismatch")
    wl, wr = raw_valuations(left), raw_valuations(right)
    fl, fr = _fibers(left, wl), _fibers(right, wr)
    violation = None
    cells = 0
    ready = ("zero",) + tuple(f"r_{p.name}" for p in left.ports)
    for r, fiber in fl.items():
        if r not in fr:
            if violation is None:
                violation = {"reason": "support", "readiness": dict(zip(ready, r))}
            continue
        for port in left.ports:
            if not lineage(port.term):
                continue
            cells += 1
            kl, kr = _k(left, port.name, fiber), _k(right, port.name, fr[r])
            if kl > kr and violation is None:
                violation = {"reason": "envelope", "port": port.name, "readiness": dict(zip(ready, r)),
                             "left_k": kl, "right_k": kr}
    return {"accepted": violation is None, "left_readiness_points": len(fl),
            "right_readiness_points": len(fr), "left_full_valuations": len(wl),
            "right_full_valuations": len(wr), "conditional_cells_checked": cells,
            "violation": violation}


def execute_separator(case: Case, valuation: dict, separator: dict) -> dict:
    """Interpret a public-readiness equality branch and a nonnegative timer."""
    ready = {"zero": 0, **{f"r_{p.name}": valuation[f"r_{p.name}"] for p in case.ports}}
    special = ready == separator["readiness"]
    wait = separator["special_wait"] if special else 0
    if type(wait) is not int or wait < 0:
        raise ValueError("separator wait is not a nonnegative integer")
    port = case.port_map[separator["port"]]
    time = max(ready[f"r_{p.name}"] for p in case.ports) + wait
    birth = min(valuation[f"b_{s}"] for s in lineage(port.term))
    return {"valuation": valuation, "readiness": ready, "port": port.name,
            "term": format_term(port.term), "special": special, "wait": wait,
            "time": time, "oldest_birth": birth, "age": time - birth}


def validate_separator(left: Case, right: Case, certificate: dict) -> dict:
    sep = certificate["separator"]
    wl, wr = raw_valuations(left), raw_valuations(right)
    selected = sep["left_valuation"]
    if selected not in wl:
        raise ValueError("separator witness is not a legal full left valuation")
    witness = execute_separator(left, selected, sep)
    right_runs = [execute_separator(right, w, sep) for w in wr]
    left_special = [execute_separator(left, w, sep) for w in wl
                    if all(w[v] == value for v, value in sep["readiness"].items())]
    if not witness["special"] or witness["readiness"] != certificate["witness"]["readiness"]:
        raise ValueError("separator public readiness does not match the witness")
    if witness["term"] != sep["payload_term"] or witness["time"] != sep["emission_time"] or witness["age"] != sep["left_special_age"]:
        raise ValueError("separator reported left fields do not execute")
    if witness["age"] != max(run["age"] for run in left_special) or witness["age"] <= sep["deadline"]:
        raise ValueError("left witness does not attain a stale special output")
    if sep["branch_observable"] is not True or sep["special_reachable_right"] != any(run["special"] for run in right_runs):
        raise ValueError("separator branch metadata mismatch")
    special_right = [run["age"] for run in right_runs if run["special"]]
    if sep["right_special_age"] != (max(special_right) if special_right else None):
        raise ValueError("right special maximum does not execute")
    baseline = 1 + max(max(w[f"r_{p.name}"] for p in right.ports)
                       - min(w[f"b_{s}"] for s in lineage(right.port_map[sep["port"]].term)) for w in wr)
    if sep["deadline"] != baseline or any(run["age"] > baseline for run in right_runs):
        raise ValueError("separator not safe on every right branch")
    return {"left_execution": witness, "right_valuation_checks": len(right_runs),
            "right_ordinary_checks": sum(not run["special"] for run in right_runs),
            "right_special_checks": len(special_right), "right_max_age": max(run["age"] for run in right_runs),
            "right_all_safe": True, "baseline_from_raw_valuations": baseline}

"""Single-zone observation-sensitive refinement inference and separators."""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .dbm import closure_certificate
from .model import Case, ModelError
from .terms import format_term, lineage


class RefinementError(ValueError):
    """The adaptive refinement query lies outside the supported fragment."""


def _check_pair(left: Case, right: Case) -> None:
    if len(left.zones) != 1 or len(right.zones) != 1:
        raise RefinementError("adaptive decision requires one zone on each side")
    if left.origins != right.origins:
        raise RefinementError("origin metadata differs")
    left_ports = [(p.name, format_term(p.term)) for p in left.ports]
    right_ports = [(p.name, format_term(p.term)) for p in right.ports]
    if left_ports != right_ports:
        raise RefinementError("port metadata differs")
    if not any(lineage(p.term) for p in left.ports):
        raise RefinementError("at least one data-bearing port is required")


def _readiness_variables(case: Case) -> tuple[str, ...]:
    return ("zero",) + tuple(f"r_{p.name}" for p in case.ports)


def _row(closure, origin: str, ready: Iterable[str]) -> dict[str, int]:
    return {i: closure.bound(f"b_{origin}", i) for i in ready}


def _conditional_k(case: Case, closure, port_name: str, readiness: dict[str, int]) -> int:
    port = case.port_map[port_name]
    values = []
    ready = _readiness_variables(case)
    for source in sorted(lineage(port.term)):
        values.append(min(closure.bound(f"b_{source}", i) - readiness[i] for i in ready))
    return max(values)


def _support_points(case: Case) -> list[dict[str, int]]:
    ready = _readiness_variables(case)
    closure = case.zones[0].close()
    bounds = {
        var: (-closure.bound(var, "zero"), closure.bound("zero", var))
        for var in ready[1:]
    }
    from itertools import product

    points = []
    ranges = [range(bounds[v][0], bounds[v][1] + 1) for v in ready[1:]]
    for values in product(*ranges):
        r = {"zero": 0, **dict(zip(ready[1:], values))}
        if all(r[v] - r[u] <= closure.bound(u, v) for u in ready for v in ready):
            points.append(r)
    return points


def _separator(left: Case, right: Case, reason: str, witness_r: dict[str, int], port_name: str) -> dict:
    right_closure = right.zones[0].close()
    left_closure = left.zones[0].close()
    baseline = 1 + max(right_closure.bound(f"b_{s}", f"r_{q.name}")
                       for q in right.ports for s in lineage(right.port_map[port_name].term))
    time = max(witness_r[f"r_{p.name}"] for p in left.ports)
    left_k = _conditional_k(left, left_closure, port_name, witness_r)
    if reason == "support":
        wait = max(0, baseline - time - left_k + 1)
        right_k = None
    else:
        right_k = _conditional_k(right, right_closure, port_name, witness_r)
        wait = baseline - time - right_k
        if wait < 0:
            raise AssertionError("separator delay should be nonnegative")
    ready = _readiness_variables(left)
    # Simultaneous minimal extension at the public readiness vector attains
    # the whole-payload oldest birth, including support-rejection witnesses.
    valuation = {v: max(witness_r[i] - left_closure.bound(v, i) for i in ready)
                 for v in left.variables}
    return {
        "port": port_name,
        "readiness": witness_r,
        "deadline": baseline,
        "special_wait": wait,
        "left_special_age": time + wait + left_k,
        "right_special_age": None if right_k is None else time + wait + right_k,
        "branch_observable": True,
        "special_reachable_right": reason != "support",
        "left_valuation": valuation,
        "payload_term": format_term(left.port_map[port_name].term),
        "emission_time": time + wait,
    }


def infer_refinement(left: Case, right: Case) -> dict:
    _check_pair(left, right)
    left_closure = left.zones[0].close()
    right_closure = right.zones[0].close()
    ready = _readiness_variables(left)
    left_cert = closure_certificate(left.zones[0])
    right_cert = closure_certificate(right.zones[0])

    for i in ready:
        for j in ready:
            dl = left_closure.bound(i, j)
            dr = right_closure.bound(i, j)
            if dl > dr:
                potential = left_closure.potential(i)
                readiness = {v: potential[v] for v in ready}
                port = next(p.name for p in left.ports if lineage(p.term))
                return {
                    "schema": "freshness-adaptive-certificate-1",
                    "left": left.case_id,
                    "right": right.case_id,
                    "left_closure": left_cert,
                    "right_closure": right_cert,
                    "accepted": False,
                    "reason": "support",
                    "witness": {"i": i, "j": j, "left_bound": dl, "right_bound": dr, "readiness": readiness},
                    "separator": _separator(left, right, "support", readiness, port),
                }

    covers: dict[str, dict[str, str]] = defaultdict(dict)
    for port in left.ports:
        sources = sorted(lineage(port.term))
        if not sources:
            continue
        for source in sources:
            left_row = _row(left_closure, source, ready)
            chosen = None
            for target in sources:
                right_row = _row(right_closure, target, ready)
                if all(left_row[i] <= right_row[i] for i in ready):
                    chosen = target
                    break
            if chosen is None:
                separating_columns = {}
                for target in sources:
                    right_row = _row(right_closure, target, ready)
                    separating_columns[target] = next(i for i in ready if left_row[i] > right_row[i])
                potential = left_closure.potential(f"b_{source}")
                readiness = {v: potential[v] for v in ready}
                return {
                    "schema": "freshness-adaptive-certificate-1",
                    "left": left.case_id,
                    "right": right.case_id,
                    "left_closure": left_cert,
                    "right_closure": right_cert,
                    "accepted": False,
                    "reason": "row-cover",
                    "witness": {
                        "port": port.name,
                        "left_origin": source,
                        "separating_columns": separating_columns,
                        "readiness": readiness,
                        "left_k": _conditional_k(left, left_closure, port.name, readiness),
                        "right_k": _conditional_k(right, right_closure, port.name, readiness),
                    },
                    "separator": _separator(left, right, "row-cover", readiness, port.name),
                }
            covers[port.name][source] = chosen
    return {
        "schema": "freshness-adaptive-certificate-1",
        "left": left.case_id,
        "right": right.case_id,
        "left_closure": left_cert,
        "right_closure": right_cert,
        "accepted": True,
        "readiness_pairs": [[i, j, left_closure.bound(i, j), right_closure.bound(i, j)] for i in ready for j in ready],
        "covers": {p: mapping for p, mapping in covers.items()},
    }


def check_refinement(left: Case, right: Case, certificate: dict) -> dict:
    from .adaptive_kernel import replay_refinement

    return replay_refinement(left, right, certificate)


def oracle_refinement(left: Case, right: Case) -> dict:
    """Compatibility entry point; the oracle uses only raw finite constraints."""
    from .adaptive_oracle import oracle_refinement as raw_oracle

    return raw_oracle(left, right)

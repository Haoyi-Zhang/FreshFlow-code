"""Exact residualization at closed event-and-receipt prefixes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .model import Case, case_from_spec
from .semantics import Execution, enumerate_executions, future_observation
from .terms import format_term


class PrefixError(ValueError):
    """A prefix is malformed or infeasible in the finite model."""


@dataclass
class Residual:
    case: Case
    cut: int
    fired: frozenset[str]
    received: frozenset[str]
    crossing_for_edge: dict[str, str]
    original_case: Case


def residualize(case: Case, prefix: tuple, *, residual_id: str = "residual") -> Residual:
    cut, event_items, receipt_items = prefix
    if type(cut) is not int or cut < 0:
        raise PrefixError("cut must be a nonnegative integer")
    events = dict(event_items)
    receipts = dict(receipt_items)
    if len(events) != len(event_items) or len(receipts) != len(receipt_items):
        raise PrefixError("duplicate observed event or receipt")
    known_names = set(case.names)
    if not set(events) <= known_names or any(type(t) is not int or not 0 <= t <= cut for t in events.values()):
        raise PrefixError("observed event is invalid")
    edge_map = {d.edge_id: d for n in case.nodes for d in n.dependencies}
    if not set(receipts) <= set(edge_map) or any(type(t) is not int or not 0 <= t <= cut for t in receipts.values()):
        raise PrefixError("observed receipt is invalid")
    for edge_id, time in receipts.items():
        dep = edge_map[edge_id]
        if dep.source not in events:
            raise PrefixError("receipt has an unfired sender")
        if not dep.lower <= time - events[dep.source] <= dep.upper:
            raise PrefixError("receipt delay is outside its interval")
    for node in case.nodes:
        incoming = {d.edge_id for d in node.dependencies}
        all_received = incoming <= set(receipts)
        if (node.name in events) != all_received:
            raise PrefixError("prefix is not closed at a non-port")
        if node.name in events and events[node.name] != max(receipts[e] for e in incoming):
            raise PrefixError("recorded firing is not the incoming maximum")
    for edge_id, dep in edge_map.items():
        if dep.source in events and edge_id not in receipts and events[dep.source] + dep.upper <= cut:
            raise PrefixError("an overdue receipt is missing")

    additions: list[tuple[str, str, int]] = []
    for port in case.ports:
        variable = f"r_{port.name}"
        if port.name in events:
            t = events[port.name]
            additions.extend((("zero", variable, t), (variable, "zero", -t)))
        else:
            additions.append((variable, "zero", -(cut + 1)))
    conditioned = []
    for zone in case.zones:
        item = zone.with_constraints(additions, name=f"{zone.name}-at-{cut}")
        if item is not None:
            conditioned.append(item)
    if not conditioned:
        raise PrefixError("prefix has no feasible conditioned input zone")

    terms = case.terms
    residual_ports: list[dict[str, Any]] = []
    uncompleted_ports = [p for p in case.ports if p.name not in events]
    for port in uncompleted_ports:
        residual_ports.append({"name": port.name, "term": format_term(port.term)})
    pending = {name for name in case.names if name not in events}
    crossing: dict[str, str] = {}
    crossing_bounds: dict[str, list[int]] = {}
    for node in case.nodes:
        if node.name not in pending:
            continue
        for dep in node.dependencies:
            if dep.source in events:
                name = f"cross-{dep.source}-{node.name}"
                crossing[dep.edge_id] = name
                if dep.edge_id in receipts:
                    interval = [0, 0]
                else:
                    lo = max(1, events[dep.source] + dep.lower - cut)
                    hi = events[dep.source] + dep.upper - cut
                    if lo > hi:
                        raise PrefixError("empty in-flight readiness interval")
                    interval = [lo, hi]
                crossing_bounds[f"r_{name}"] = interval
                residual_ports.append({"name": name, "term": format_term(terms[dep.source])})
    residual_ports.append({"name": "cut-clock", "term": "unit"})

    residual_zones = []
    retained_old = [f"b_{s}" for s in case.origins] + [f"r_{p.name}" for p in uncompleted_ports]
    for zindex, zone in enumerate(conditioned):
        closure = zone.close()
        bounds: dict[str, list[int]] = {}
        for variable in retained_old:
            lower = -closure.bound(variable, "zero") - cut
            upper = closure.bound("zero", variable) - cut
            bounds[variable] = [lower, upper]
        bounds.update(crossing_bounds)
        bounds["r_cut-clock"] = [0, 0]
        constraints: list[list[Any]] = []
        # Closed restriction is the exact difference-zone image after fixed-clock substitution.
        for u in retained_old:
            for v in retained_old:
                if u != v:
                    constraints.append([u, v, closure.bound(u, v)])
        residual_zones.append({"name": f"residual-{zindex}", "bounds": bounds, "constraints": constraints})

    residual_nodes = []
    for node in case.nodes:
        if node.name not in pending:
            continue
        data: list[str] = []
        gates: list[str] = []
        delays: dict[str, list[int]] = {}
        for dep in node.dependencies:
            if dep.source in events:
                source = crossing[dep.edge_id]
                interval = [0, 0]
            else:
                source = dep.source
                interval = [dep.lower, dep.upper]
            (data if dep.role == "data" else gates).append(source)
            delays[source] = interval
        residual_nodes.append({
            "name": node.name,
            "op": node.op,
            "data": data,
            "gates": gates,
            "delays": delays,
            "location": node.location,
            "epoch": node.epoch,
        })
    residual_outputs = [
        {"key": output.key, "node": output.node, "term": format_term(output.term), "deadline": output.deadline}
        for output in case.outputs if output.node in pending
    ]
    if not residual_outputs:
        # A valid terminal residual is represented with an inert proof-only output on an uncompleted
        # data port only when one exists. Campaign prefixes stop before all outputs, so this branch is
        # used solely for malformed external calls.
        raise PrefixError("prefix has no remaining output obligation")
    spec = {
        "id": residual_id,
        "origins": list(case.origins),
        "ports": residual_ports,
        "zones": residual_zones,
        "nodes": residual_nodes,
        "outputs": residual_outputs,
        "metadata": {"cut": cut, "source_case": case.case_id},
    }
    return Residual(case_from_spec(spec), cut, frozenset(events), frozenset(receipts), crossing, case)


def residual_future_observation(residual: Residual, execution: Execution) -> tuple:
    original = residual.original_case
    event_map = dict(execution.event_times)
    receipt_map = dict(execution.receipt_times)
    events = tuple((name, event_map[name]) for name in original.names if name not in residual.fired)
    receipts: list[tuple[str, int]] = []
    for node in original.nodes:
        if node.name in residual.fired:
            continue
        for dep in node.dependencies:
            if dep.source in residual.fired:
                if dep.edge_id in residual.received:
                    continue
                receipts.append((dep.edge_id, event_map[residual.crossing_for_edge[dep.edge_id]]))
            else:
                receipts.append((dep.edge_id, receipt_map[dep.edge_id]))
    outputs = tuple(execution.outputs)
    return (events, tuple(receipts), outputs)


def compare_prefix(case: Case, prefix: tuple, expected: set[tuple], *, residual_id: str) -> dict:
    residual = residualize(case, prefix, residual_id=residual_id)
    executions = list(enumerate_executions(residual.case))
    actual = {residual_future_observation(residual, execution) for execution in executions}
    return {
        "equal": actual == expected,
        "expected_count": len(expected),
        "actual_count": len(actual),
        "residual_assignment_count": len(executions),
        "missing": [repr(x) for x in sorted(expected - actual, key=repr)[:3]],
        "extra": [repr(x) for x in sorted(actual - expected, key=repr)[:3]],
        "residual_case": residual.case.to_spec(),
    }

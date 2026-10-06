"""Exact finite interpreter and exhaustive reference semantics."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable, Iterator

from .model import Case
from .terms import Term, format_term, lineage


class OracleLimit(ValueError):
    """An explicitly bounded exhaustive reference query was too large."""


@dataclass(frozen=True)
class Execution:
    valuation: tuple[tuple[str, int], ...]
    delays: tuple[tuple[str, int], ...]
    event_times: tuple[tuple[str, int], ...]
    receipt_times: tuple[tuple[str, int], ...]
    terms: tuple[tuple[str, str], ...]
    outputs: tuple[tuple[str, str, int, int], ...]

    def valuation_dict(self) -> dict[str, int]:
        return dict(self.valuation)

    def event_dict(self) -> dict[str, int]:
        return dict(self.event_times)

    def receipt_dict(self) -> dict[str, int]:
        return dict(self.receipt_times)


def interface_valuations(case: Case, *, cap: int = 2_000_000) -> list[dict[str, int]]:
    unique: dict[tuple[int, ...], dict[str, int]] = {}
    variables = case.variables
    for zone in case.zones:
        for valuation in zone.enumerate(cap=cap):
            key = tuple(valuation[v] for v in variables)
            unique.setdefault(key, valuation)
            if len(unique) > cap:
                raise OracleLimit("union valuation count exceeds cap")
    return [unique[k] for k in sorted(unique)]


def delay_assignments(case: Case, *, cap: int = 2_000_000) -> Iterator[dict[str, int]]:
    dependencies = [d for node in case.nodes for d in node.dependencies]
    ranges = [range(d.lower, d.upper + 1) for d in dependencies]
    volume = 1
    for r in ranges:
        volume *= len(r)
        if volume > cap:
            raise OracleLimit("delay assignment volume exceeds cap")
    if not dependencies:
        yield {}
        return
    for values in product(*ranges):
        yield {d.edge_id: value for d, value in zip(dependencies, values)}


def execute(case: Case, valuation: dict[str, int], delays: dict[str, int]) -> Execution:
    times: dict[str, int] = {p.name: valuation[f"r_{p.name}"] for p in case.ports}
    terms: dict[str, Term] = {p.name: p.term for p in case.ports}
    receipts: dict[str, int] = {}
    for node in case.nodes:
        incoming: list[int] = []
        for dep in node.dependencies:
            delay = delays[dep.edge_id]
            if not dep.lower <= delay <= dep.upper:
                raise ValueError("illegal delay assignment")
            arrival = times[dep.source] + delay
            receipts[dep.edge_id] = arrival
            incoming.append(arrival)
        times[node.name] = max(incoming)
        if node.op == "copy":
            terms[node.name] = terms[node.data[0]]
        elif node.op == "pair":
            terms[node.name] = ("pair", terms[node.data[0]], terms[node.data[1]])
        else:
            terms[node.name] = ("unit",)
    outputs: list[tuple[str, str, int, int]] = []
    for output in case.outputs:
        term = terms[output.node]
        birth = min(valuation[f"b_{s}"] for s in lineage(term))
        outputs.append((output.key, format_term(term), times[output.node], times[output.node] - birth))
    return Execution(
        tuple(sorted(valuation.items())),
        tuple(sorted(delays.items())),
        tuple(times.items()),
        tuple(receipts.items()),
        tuple((name, format_term(term)) for name, term in terms.items()),
        tuple(outputs),
    )


def enumerate_executions(case: Case, *, cap: int = 2_000_000) -> Iterator[Execution]:
    valuations = interface_valuations(case, cap=cap)
    delays = list(delay_assignments(case, cap=cap))
    if len(valuations) * len(delays) > cap:
        raise OracleLimit("execution count exceeds cap")
    for valuation in valuations:
        for assignment in delays:
            yield execute(case, valuation, assignment)


def oracle_summary(case: Case, *, cap: int = 2_000_000) -> dict:
    profile = {(p.name, s): None for p in case.ports for s in case.origins}
    worst = {o.key: None for o in case.outputs}
    terms: dict[str, set[str]] = {o.key: set() for o in case.outputs}
    assignments = 0
    valuations: set[tuple[tuple[str, int], ...]] = set()
    witnesses: dict[str, dict] = {}
    profile_witnesses: dict[str, dict] = {}
    for execution in enumerate_executions(case, cap=cap):
        assignments += 1
        valuations.add(execution.valuation)
        valuation = dict(execution.valuation)
        events = dict(execution.event_times)
        for p in case.ports:
            for s in case.origins:
                value = events[p.name] - valuation[f"b_{s}"]
                key = (p.name, s)
                if profile[key] is None or value > profile[key]:
                    profile[key] = value
                    profile_witnesses[f"{p.name}:{s}"] = {"valuation": valuation, "value": value}
        for key, term, time, age in execution.outputs:
            terms[key].add(term)
            if worst[key] is None or age > worst[key]:
                worst[key] = age
                witnesses[key] = {
                    "valuation": valuation,
                    "delays": dict(execution.delays),
                    "time": time,
                    "term": term,
                    "age": age,
                }
    return {
        "case": case.case_id,
        "valuation_count": len(valuations),
        "assignment_count": assignments,
        "profile": {f"{p}:{s}": value for (p, s), value in sorted(profile.items())},
        "profile_witnesses": profile_witnesses,
        "worst_age": worst,
        "output_terms": {k: sorted(v) for k, v in terms.items()},
        "witnesses": witnesses,
    }


def prefix_of(execution: Execution, cut: int) -> tuple:
    """Birth-blind age-erased prefix: event and receipt identities/times.

    Completed output keys/terms/times are determined by these events and fixed
    graph metadata. Past output ages are intentionally NOT conditioning facts.
    Future observations below still retain exact ages and original births.
    """
    events = tuple((name, time) for name, time in execution.event_times if time <= cut)
    receipts = tuple((edge, time) for edge, time in execution.receipt_times if time <= cut)
    return (cut, events, receipts)


def future_observation(case: Case, execution: Execution, cut: int) -> tuple:
    events = tuple((name, time - cut) for name, time in execution.event_times if time > cut)
    receipts = tuple((edge, time - cut) for edge, time in execution.receipt_times if time > cut)
    outputs = tuple((key, term, time - cut, age) for key, term, time, age in execution.outputs if time > cut)
    return (events, receipts, outputs)

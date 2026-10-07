"""Certificate-producing fixed-graph freshness analysis."""
from __future__ import annotations

from .dbm import _certificate_from_closure
from .model import Case
from .terms import format_term, lineage


def infer_case(case: Case) -> dict:
    origins = case.origins
    profile: dict[tuple[str, str], int] = {}
    zones = []
    for zone_index, zone in enumerate(case.zones):
        closure = zone.close()
        zone_profile: dict[str, int] = {}
        for port in case.ports:
            for source in origins:
                value = closure.bound(f"b_{source}", f"r_{port.name}")
                zone_profile[f"{port.name}:{source}"] = value
                key = (port.name, source)
                profile[key] = max(profile.get(key, -10**60), value)
        zones.append({
            "index": zone_index,
            "name": zone.name,
            "closure": _certificate_from_closure(closure),
            "profile": zone_profile,
        })
    rows: dict[str, dict[str, int]] = {}
    terms = case.terms
    for port in case.ports:
        rows[port.name] = {s: profile[(port.name, s)] for s in origins}
    for node in case.nodes:
        rows[node.name] = {
            s: max(rows[d.source][s] + d.upper for d in node.dependencies)
            for s in origins
        }
    output_results = []
    admitted = True
    for output in case.outputs:
        actual = terms[output.node]
        actual_string = format_term(actual)
        expected_string = format_term(output.term)
        age = max(rows[output.node][s] for s in lineage(actual))
        term_ok = actual == output.term
        age_ok = age <= output.deadline
        admitted = admitted and term_ok and age_ok
        output_results.append({
            "key": output.key,
            "node": output.node,
            "actual_term": actual_string,
            "expected_term": expected_string,
            "term_ok": term_ok,
            "exact_worst_age": age,
            "deadline": output.deadline,
            "age_ok": age_ok,
        })
    return {
        "schema": "freshness-static-certificate-1",
        "case": case.case_id,
        "zones": zones,
        "profile": {f"{p}:{s}": profile[(p, s)] for p in [x.name for x in case.ports] for s in origins},
        "rows": {name: row for name, row in rows.items()},
        "terms": {name: format_term(term) for name, term in terms.items()},
        "outputs": output_results,
        "admitted": admitted,
    }


def check_case(case: Case, certificate: dict) -> dict:
    from .kernel import replay_static

    return replay_static(case, certificate)

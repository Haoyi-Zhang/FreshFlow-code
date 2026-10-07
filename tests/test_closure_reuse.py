"""Portable finite closure-reuse regressions; no saved or private-stage inputs.

The literal-product references below inspect raw bounds/constraints and complete
delay tuples. They never call closure, inference, the shipped oracles, or replay.
"""
from contextlib import ExitStack
from copy import deepcopy
from itertools import product
import json
import unittest
from unittest.mock import patch

from ftypes.adaptive import infer_refinement
from ftypes.adaptive_kernel import AdaptiveCertificateError, replay_refinement
from ftypes.dbm import (
    Zone, ZoneError, _certificate_from_closure, closure_certificate,
    verify_closure_certificate,
)
from ftypes.families import adaptive_interface, make_case, supplemental_cases
from ftypes.kernel import CertificateError, replay_static
from ftypes.model import case_from_spec
from ftypes.static import infer_case
from ftypes.terms import format_term, lineage


def literal_points(zone, cap=10_000):
    variables = zone.variables[1:]
    volume = 1
    for v in variables:
        lo, hi = zone.bounds[v]
        volume *= hi - lo + 1
    if volume > cap:
        raise ValueError("literal reference cap exceeded")
    points = []
    for values in product(*(range(zone.bounds[v][0], zone.bounds[v][1] + 1)
                            for v in variables)):
        point = {"zero": 0, **dict(zip(variables, values))}
        if all(point[e.v] - point[e.u] <= e.c for e in zone.constraints):
            points.append(point)
    return points


def literal_static(case):
    """Enumerate complete raw assignments, not a max-plus row recurrence."""
    valuations = {}
    for zone in case.zones:
        for point in literal_points(zone):
            valuations[tuple(point[v] for v in case.variables)] = point
    rows = {name: {s: None for s in case.origins} for name in case.names}
    terms = {p.name: p.term for p in case.ports}
    for node in case.nodes:
        if node.op == "copy":
            terms[node.name] = terms[node.data[0]]
        elif node.op == "pair":
            terms[node.name] = ("pair", terms[node.data[0]], terms[node.data[1]])
        else:
            terms[node.name] = ("unit",)
    deps = [d for node in case.nodes for d in node.dependencies]
    worst = {o.key: None for o in case.outputs}
    assignments = 0
    for point in valuations.values():
        for values in product(*(range(d.lower, d.upper + 1) for d in deps)):
            delays = dict(zip((d.edge_id for d in deps), values))
            times = {p.name: point[f"r_{p.name}"] for p in case.ports}
            for node in case.nodes:
                arrivals = [times[d.source] + delays[d.edge_id]
                            for d in node.dependencies]
                times[node.name] = max(arrivals)
            for name in case.names:
                for source in case.origins:
                    age = times[name] - point[f"b_{source}"]
                    previous = rows[name][source]
                    rows[name][source] = age if previous is None else max(age, previous)
            for output in case.outputs:
                age = times[output.node] - min(point[f"b_{s}"]
                                              for s in lineage(terms[output.node]))
                previous = worst[output.key]
                worst[output.key] = age if previous is None else max(age, previous)
            assignments += 1
    return {"rows": rows, "terms": {n: format_term(t) for n, t in terms.items()},
            "worst": worst, "assignments": assignments}


def literal_refinement(left, right):
    """Compare raw readiness fibers by literal whole-payload birth minima."""
    ready = ("zero",) + tuple(f"r_{p.name}" for p in left.ports)
    fibers = []
    for case in (left, right):
        grouped = {}
        for point in literal_points(case.zones[0]):
            grouped.setdefault(tuple(point[v] for v in ready), []).append(point)
        fibers.append(grouped)
    for key, points in fibers[0].items():
        if key not in fibers[1]:
            return False
        for port in left.ports:
            sources = lineage(port.term)
            if sources:
                left_birth = min(min(w[f"b_{s}"] for s in sources) for w in points)
                right_birth = min(min(w[f"b_{s}"] for s in sources)
                                  for w in fibers[1][key])
                if left_birth < right_birth:
                    return False
    return True


def separator_runs(case, separator):
    sources = lineage(case.port_map[separator["port"]].term)
    runs = []
    for point in literal_points(case.zones[0]):
        ready = {"zero": 0, **{f"r_{p.name}": point[f"r_{p.name}"]
                              for p in case.ports}}
        special = ready == separator["readiness"]
        time = max(ready[f"r_{p.name}"] for p in case.ports)
        time += separator["special_wait"] if special else 0
        runs.append({"point": point, "special": special, "time": time,
                     "age": time - min(point[f"b_{s}"] for s in sources)})
    return runs


def named_zones():
    yield Zone.from_spec(("zero", "x", "y", "z"), {
        "name": "direct-tie-and-duplicate", "bounds": {v: [0, 2] for v in ("x", "y", "z")},
        "constraints": [["x", "z", 1], ["x", "y", 0], ["y", "z", 1], ["x", "z", 1]],
    })
    yield Zone.from_spec(("zero", "x", "y"), {
        "name": "negative-and-zero", "bounds": {"x": [-2, -1], "y": [0, 0]},
        "constraints": [["y", "x", -1], ["zero", "y", 0]],
    })
    for index in range(8):
        yield from make_case(index, 0, 0, small=True).zones


def static_fixtures():
    for interface, shape, width in product(range(8), range(8), range(2)):
        yield make_case(interface, shape, width, small=True)
    yield from supplemental_cases()


def adaptive_pairs():
    for group, i, j in product(range(3), (0, 1, 8, 15), (0, 1, 8, 15)):
        yield adaptive_interface(group, i), adaptive_interface(group, j)
    spec = adaptive_interface(1, 0).to_spec()
    spec["zones"][0]["constraints"] = []
    spec["zones"][0]["bounds"] = {
        "b_a": [0, 0], "b_b": [-2, -2], "r_p": [0, 0], "r_q": [0, 0],
    }
    left = case_from_spec(spec)
    spec = deepcopy(spec)
    spec["zones"][0]["bounds"].update({"b_a": [-2, -2], "b_b": [0, 0]})
    right = case_from_spec(spec)
    yield left, right
    yield right, left


class ClosureReuseRegression(unittest.TestCase):
    def test_complete_closure_against_literal_product(self):
        for zone in named_zones():
            points = literal_points(zone)
            closure = zone.close()
            cert = _certificate_from_closure(closure)
            with self.subTest(zone=zone.name):
                self.assertEqual(json.dumps(cert), json.dumps(closure_certificate(zone)))
                self.assertEqual(cert["distance"], [
                    [max(w[v] - w[u] for w in points) for v in zone.variables]
                    for u in zone.variables])
                for potential in cert["potentials"].values():
                    self.assertIn(dict(zip(zone.variables, potential)), points)
                self.assertEqual(verify_closure_certificate(zone, cert), cert["distance"])
        tie = next(named_zones())
        cert = closure_certificate(tie)
        self.assertEqual(cert["paths"][1][3], [0])
        self.assertEqual(len(tie.constraints), 3)

    def test_evidence_isolation_and_no_persistent_cache(self):
        zone = next(named_zones())
        closure = zone.close()
        frozen = deepcopy((closure.dist, closure.paths))
        cert = _certificate_from_closure(closure)
        other = _certificate_from_closure(closure)
        cert["distance"][0][1] += 1
        cert["paths"][0][1].append(999)
        cert["potentials"]["zero"][1] += 1
        self.assertEqual((closure.dist, closure.paths), frozen)
        self.assertEqual(json.dumps(other), json.dumps(closure_certificate(zone)))
        with self.assertRaises(ZoneError):
            verify_closure_certificate(zone, cert)
        mutable = Zone.from_spec(("zero", "x"), {"bounds": {"x": [0, 2]}})
        first = closure_certificate(mutable)
        mutable.bounds["x"] = (0, 1)
        second = closure_certificate(mutable)
        self.assertEqual(first["distance"][0][1], 2)
        self.assertEqual(second["distance"][0][1], 1)

    def test_static_rows_terms_outputs_against_literal_delays(self):
        total = 0
        for case in static_fixtures():
            with self.subTest(case=case.case_id):
                expected = literal_static(case)
                cert = infer_case(case)
                total += expected["assignments"]
                self.assertEqual(cert["rows"], expected["rows"])
                self.assertEqual(cert["terms"], expected["terms"])
                self.assertEqual(cert["profile"], {
                    f"{p.name}:{s}": expected["rows"][p.name][s]
                    for p in case.ports for s in case.origins})
                for row in cert["outputs"]:
                    self.assertEqual(row["exact_worst_age"], expected["worst"][row["key"]])
                self.assertEqual(replay_static(case, cert)["admitted"], cert["admitted"])
        self.assertGreater(total, 0)

    def test_adaptive_fibers_covers_and_executed_separators(self):
        reasons = set()
        for left, right in adaptive_pairs():
            with self.subTest(left=left.case_id, right=right.case_id):
                cert = infer_refinement(left, right)
                self.assertEqual(cert["accepted"], literal_refinement(left, right))
                self.assertEqual(replay_refinement(left, right, cert)["accepted"],
                                 cert["accepted"])
                if cert["accepted"]:
                    continue
                reasons.add(cert["reason"])
                sep = cert["separator"]
                left_runs, right_runs = separator_runs(left, sep), separator_runs(right, sep)
                attained = next(r for r in left_runs if r["point"] == sep["left_valuation"])
                self.assertTrue(attained["special"])
                self.assertEqual(attained["time"], sep["emission_time"])
                self.assertEqual(attained["age"], sep["left_special_age"])
                self.assertEqual(sep["left_special_age"],
                                 max(r["age"] for r in left_runs if r["special"]))
                self.assertGreater(attained["age"], sep["deadline"])
                self.assertTrue(all(r["age"] <= sep["deadline"] for r in right_runs))
                special = [r["age"] for r in right_runs if r["special"]]
                self.assertEqual(sep["special_reachable_right"], bool(special))
                self.assertEqual(sep["right_special_age"], max(special) if special else None)
        self.assertEqual(reasons, {"support", "row-cover"})
        for (left, right), expected in zip(list(adaptive_pairs())[-2:],
                                           ({"a": "a", "b": "a"}, {"a": "b", "b": "a"})):
            cert = infer_refinement(left, right)
            self.assertEqual(cert["covers"]["p"], expected)

    def test_close_counts_and_checker_independence(self):
        original = Zone.close
        calls = []
        def counted(zone):
            calls.append(zone.name)
            return original(zone)
        with patch.object(Zone, "close", counted):
            case = make_case(6, 2, 1, small=True)
        self.assertEqual(len(calls), len(case.zones))  # Ingestion is unchanged.
        calls.clear()
        with patch.object(Zone, "close", counted):
            static = infer_case(case)
        self.assertEqual(len(calls), len(case.zones))
        pairs = [(adaptive_interface(0, 0), adaptive_interface(0, 0)),
                 (adaptive_interface(0, 0), adaptive_interface(0, 1)),
                 (adaptive_interface(1, 0), adaptive_interface(1, 8))]
        certificates = []
        for left, right in pairs:
            calls.clear()
            with patch.object(Zone, "close", counted):
                cert = infer_refinement(left, right)
            self.assertEqual(len(calls), 2)
            certificates.append(cert)
        def forbidden(*args, **kwargs):
            raise AssertionError("producer work reached by independent replay/reference")
        with ExitStack() as stack:
            stack.enter_context(patch.object(Zone, "close", forbidden))
            for target in ("ftypes.dbm._certificate_from_closure",
                           "ftypes.static._certificate_from_closure",
                           "ftypes.static.infer_case", "ftypes.adaptive.infer_refinement",
                           "ftypes.adaptive._certificate_from_closure",
                           "ftypes.adaptive._separator_from_closures"):
                stack.enter_context(patch(target, forbidden))
            self.assertTrue(replay_static(case, static)["admitted"])
            self.assertEqual(literal_static(case)["rows"], static["rows"])
            for (left, right), cert in zip(pairs, certificates):
                self.assertEqual(replay_refinement(left, right, cert)["accepted"],
                                 literal_refinement(left, right))

    def test_caps_and_mutation_rejections_are_preserved(self):
        with self.assertRaisesRegex(ZoneError, "too many clock"):
            Zone.from_spec(("zero",) + tuple(f"x{i}" for i in range(128)), {})
        with self.assertRaisesRegex(ZoneError, "128-bit"):
            Zone.from_spec(("zero", "x"), {"bounds": {"x": [0, 2**128]}})
        with self.assertRaisesRegex(ZoneError, "infeasible"):
            Zone.from_spec(("zero", "x"), {"bounds": {"x": [0, 0]},
                                           "constraints": [["zero", "x", -1]]})
        zone = Zone.from_spec(("zero", "x"), {"bounds": {"x": [0, 1]}})
        self.assertEqual(len(list(zone.enumerate(cap=2))), 2)
        for cap in (0, 1):
            with self.assertRaisesRegex(ZoneError, "exceeds cap"):
                list(zone.enumerate(cap=cap))
        wide = Zone.from_spec(("zero", "x"), {"bounds": {"x": [0, 2**127]}})
        with self.assertRaisesRegex(ZoneError, "exceeds cap"):
            list(wide.enumerate(cap=10))
        closure = closure_certificate(zone)
        closure["distance"][0][1] = 2**256
        with self.assertRaisesRegex(ZoneError, "invalid closure distance"):
            verify_closure_certificate(zone, closure)
        case = make_case(0, 1, 1, small=True)
        static = infer_case(case)
        static["zones"][0]["closure"]["paths"][0][1].append(999)
        with self.assertRaises(CertificateError):
            replay_static(case, static)
        for left, right in ((adaptive_interface(0, 0), adaptive_interface(0, 1)),
                            (adaptive_interface(1, 0), adaptive_interface(1, 8))):
            certificate = infer_refinement(left, right)
            for field in ("deadline", "special_wait", "left_special_age", "emission_time"):
                bad = deepcopy(certificate)
                bad["separator"][field] += 1
                with self.assertRaises(AdaptiveCertificateError):
                    replay_refinement(left, right, bad)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from ftypes.dbm import Zone, ZoneError, closure_certificate, verify_closure_certificate
from ftypes.model import ModelError, case_from_spec
from ftypes.terms import TermError, format_term, lineage, parse_term


class TermsAndZones(unittest.TestCase):
    def test_unit_round_trip(self):
        self.assertEqual(format_term(parse_term("unit")), "unit")

    def test_source_round_trip(self):
        self.assertEqual(format_term(parse_term("src(alpha)")), "src(alpha)")

    def test_pair_lineage(self):
        term = parse_term("pair(src(a),pair(src(b),src(a)))")
        self.assertEqual(lineage(term), {"a", "b"})

    def test_bad_constructor(self):
        with self.assertRaises(TermError):
            parse_term("merge(src(a),src(b))")

    def test_trailing_term(self):
        with self.assertRaises(TermError):
            parse_term("unit unit")

    def test_zone_exact_bound(self):
        z = Zone.from_spec(("zero", "x", "y"), {"bounds": {"x": [0, 2], "y": [0, 3]}, "constraints": [["x", "y", 1]]})
        self.assertEqual(z.close().bound("x", "y"), 1)

    def test_zone_potential_attains(self):
        z = Zone.from_spec(("zero", "x", "y"), {"bounds": {"x": [0, 2], "y": [0, 3]}, "constraints": [["x", "y", 1]]})
        c = z.close()
        p = c.potential("x")
        self.assertEqual(p["y"] - p["x"], c.bound("x", "y"))

    def test_closure_replay(self):
        z = Zone.from_spec(("zero", "x"), {"bounds": {"x": [-2, 3]}, "constraints": []})
        verify_closure_certificate(z, closure_certificate(z))

    def test_closure_mutated_distance(self):
        z = Zone.from_spec(("zero", "x"), {"bounds": {"x": [-2, 3]}, "constraints": []})
        cert = closure_certificate(z)
        cert["distance"][0][1] += 1
        with self.assertRaises(ZoneError):
            verify_closure_certificate(z, cert)

    def test_infeasible_zone(self):
        with self.assertRaises(ZoneError):
            Zone.from_spec(("zero", "x"), {"bounds": {"x": [0, 1]}, "constraints": [["zero", "x", -1]]})

    def test_enumeration(self):
        z = Zone.from_spec(("zero", "x"), {"bounds": {"x": [-1, 1]}, "constraints": []})
        self.assertEqual([v["x"] for v in z.enumerate()], [-1, 0, 1])

    def test_pair_port_causality_order_is_deterministic(self):
        spec = {
            "id": "ordered",
            "origins": ["a", "b"],
            "ports": [{"name": "p", "term": "pair(src(a),src(b))"}],
            "zones": [{
                "bounds": {"b_a": [0, 0], "b_b": [0, 0], "r_p": [0, 0]},
                "constraints": [],
            }],
            "nodes": [],
            "outputs": [{"key": "o", "node": "p", "term": "pair(src(a),src(b))", "deadline": 0}],
        }
        case = case_from_spec(spec)
        self.assertEqual(
            tuple((edge.u, edge.v, edge.c) for edge in case.zones[0].constraints[:2]),
            (("r_p", "b_a", 0), ("r_p", "b_b", 0)),
        )

    def test_missing_dependency_is_rejected(self):
        spec = {"id": "bad", "origins": ["a"], "ports": [{"name": "p", "term": "src(a)"}],
                "zones": [{"bounds": {"b_a": [0, 0], "r_p": [0, 0]}, "constraints": []}],
                "nodes": [{"name": "x", "op": "copy", "data": ["later"], "gates": [], "delays": {"later": [0, 0]}}],
                "outputs": [{"key": "o", "node": "x", "term": "src(a)", "deadline": 0}]}
        with self.assertRaises(ModelError):
            case_from_spec(spec)

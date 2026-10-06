"""Small finite regressions for identifier, enumeration, and witness boundaries."""
from copy import deepcopy
import unittest

from ftypes.adaptive import infer_refinement
from ftypes.adaptive_kernel import AdaptiveCertificateError, replay_refinement
from ftypes.dbm import Zone, ZoneError, closure_certificate
from ftypes.families import adaptive_interface
from ftypes.model import case_from_spec
from ftypes.residual import compare_prefix
from ftypes.semantics import (
    OracleLimit, delay_assignments, enumerate_executions, future_observation,
    oracle_summary, prefix_of,
)
from ftypes.static import check_case, infer_case
from ftypes.terms import TermError, format_term, parse_term


NAMES = ("pairing", "src-data", "unitary", "pair", "src", "unit", "alpha2", "α", "温度")


def named_case(name):
    term = f"src({name})"
    return case_from_spec({
        "id": "named-source", "origins": [name],
        "ports": [{"name": "p", "term": term}],
        "zones": [{"bounds": {f"b_{name}": [-1, 0], "r_p": [0, 1]}}],
        "nodes": [{"name": "out", "op": "copy", "data": ["p"],
                   "gates": [], "delays": {"p": [0, 1]}}],
        "outputs": [{"key": "result", "node": "out", "term": term, "deadline": 3}],
    })


class BoundaryRegressions(unittest.TestCase):
    def test_source_identifier_tokens_are_not_keyword_prefixes(self):
        for name in NAMES:
            with self.subTest(name=name):
                text = f"pair(src({name}),unit)"
                self.assertEqual(format_term(parse_term(text)), text)

    def test_named_models_round_trip_replay_and_residualize(self):
        for name in NAMES:
            with self.subTest(name=name):
                case = named_case(name)
                restored = case_from_spec(case.to_spec())
                certificate = infer_case(case)
                self.assertTrue(check_case(restored, certificate)["admitted"])
                self.assertEqual(certificate["outputs"][0]["exact_worst_age"],
                                 oracle_summary(restored)["worst_age"]["result"])
                self.assertTrue(replay_refinement(case, restored,
                                                 infer_refinement(case, restored))["accepted"])
                executions = list(enumerate_executions(case))
                groups = {}
                for execution in executions:
                    prefix = prefix_of(execution, 0)
                    groups.setdefault(prefix, set()).add(future_observation(case, execution, 0))
                for prefix, expected in groups.items():
                    self.assertTrue(compare_prefix(case, prefix, expected, residual_id="named-cut")["equal"])

    def test_whitespace_is_not_part_of_an_identifier(self):
        self.assertEqual(format_term(parse_term(" \t pair( src(pairing), unit ) \n")),
                         "pair(src(pairing),unit)")
        for text in ("src(a b)", "src(a_b)", "unitary", "pairing(src(a),unit)"):
            with self.subTest(text=text), self.assertRaises(TermError):
                parse_term(text)

    def test_zone_volume_limit_uses_exact_integer_width(self):
        zone = Zone.from_spec(("zero", "x"), {"bounds": {"x": [0, 2**127]}})
        with self.assertRaisesRegex(ZoneError, "exceeds cap"):
            list(zone.enumerate(cap=10))

    def test_delay_volume_limit_uses_exact_integer_width(self):
        spec = named_case("a").to_spec()
        spec["nodes"][0]["delays"]["p"] = [0, 2**127]
        case = case_from_spec(spec)
        with self.assertRaisesRegex(OracleLimit, "exceeds cap"):
            list(delay_assignments(case, cap=10))

    def test_all_unit_query_is_outside_adaptive_replay_fragment(self):
        spec = adaptive_interface(1, 0).to_spec()
        spec["ports"] = [{"name": p["name"], "term": "unit"} for p in spec["ports"]]
        spec["outputs"] = []
        case = case_from_spec(spec)
        closure = closure_certificate(case.zones[0])
        matrix = closure["distance"]
        index = {v: i for i, v in enumerate(case.variables)}
        ready = ("zero", "r_p", "r_q")
        certificate = {
            "schema": "freshness-adaptive-certificate-1", "left": case.case_id,
            "right": case.case_id, "left_closure": closure, "right_closure": closure,
            "accepted": True, "covers": {},
            "readiness_pairs": [[i, j, matrix[index[i]][index[j]], matrix[index[i]][index[j]]]
                                for i in ready for j in ready],
        }
        with self.assertRaisesRegex(AdaptiveCertificateError, "data-bearing"):
            replay_refinement(case, case, certificate)

    def test_any_feasible_same_payload_cover_can_replay(self):
        spec = adaptive_interface(1, 0).to_spec()
        spec["zones"][0]["bounds"] = {"b_a": [-1, 0], "b_b": [-1, 0],
                                     "r_p": [0, 0], "r_q": [0, 0]}
        case = case_from_spec(spec)
        certificate = infer_refinement(case, case)
        alternate = deepcopy(certificate)
        alternate["covers"]["p"] = {"a": "b", "b": "b"}
        self.assertTrue(replay_refinement(case, case, alternate)["accepted"])
        invalid = deepcopy(alternate)
        invalid["covers"]["p"]["a"] = "missing"
        with self.assertRaises(AdaptiveCertificateError):
            replay_refinement(case, case, invalid)

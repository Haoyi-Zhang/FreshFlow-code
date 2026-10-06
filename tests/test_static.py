from __future__ import annotations

from copy import deepcopy
import unittest

from ftypes.families import make_case
from ftypes.kernel import CertificateError
from ftypes.model import case_from_spec
from ftypes.semantics import oracle_summary
from ftypes.static import check_case, infer_case


class StaticAnalysis(unittest.TestCase):
    def setUp(self):
        self.case = make_case(1, 6, 1, small=True, case_id="static-test")
        self.cert = infer_case(self.case)

    def test_replay_accepts(self):
        self.assertTrue(check_case(self.case, self.cert)["admitted"])

    def test_matches_oracle_age(self):
        oracle = oracle_summary(self.case)
        self.assertEqual(self.cert["outputs"][0]["exact_worst_age"], oracle["worst_age"]["result"])

    def test_matches_oracle_profile(self):
        self.assertEqual(self.cert["profile"], oracle_summary(self.case)["profile"])

    def test_term_is_exact(self):
        self.assertEqual(self.cert["outputs"][0]["actual_term"], "pair(src(a),src(b))")

    def test_threshold_below_rejects(self):
        age = self.cert["outputs"][0]["exact_worst_age"]
        spec = self.case.to_spec()
        spec["outputs"][0]["deadline"] = max(0, age - 1)
        case = case_from_spec(spec)
        self.assertFalse(check_case(case, infer_case(case))["admitted"])
        self.assertGreater(oracle_summary(case)["worst_age"]["result"], case.outputs[0].deadline)

    def test_threshold_equal_accepts(self):
        age = self.cert["outputs"][0]["exact_worst_age"]
        spec = self.case.to_spec()
        spec["outputs"][0]["deadline"] = age
        case = case_from_spec(spec)
        self.assertTrue(check_case(case, infer_case(case))["admitted"])

    def test_mutated_profile_rejected(self):
        bad = deepcopy(self.cert)
        bad["profile"]["p:a"] += 1
        with self.assertRaises(CertificateError):
            check_case(self.case, bad)

    def test_mutated_row_rejected(self):
        bad = deepcopy(self.cert)
        bad["rows"]["x"]["a"] += 1
        with self.assertRaises(CertificateError):
            check_case(self.case, bad)

    def test_mutated_term_rejected(self):
        bad = deepcopy(self.cert)
        bad["terms"]["x"] = "src(a)"
        with self.assertRaises(CertificateError):
            check_case(self.case, bad)

    def test_mutated_output_rejected(self):
        bad = deepcopy(self.cert)
        bad["outputs"][0]["exact_worst_age"] += 1
        with self.assertRaises(CertificateError):
            check_case(self.case, bad)

    def test_mutated_potential_rejected(self):
        bad = deepcopy(self.cert)
        bad["zones"][0]["closure"]["potentials"]["b_a"][0] = 1
        with self.assertRaises(CertificateError):
            check_case(self.case, bad)

    def test_all_eight_shapes(self):
        for shape in range(8):
            case = make_case(0, shape, 1, small=True, case_id=f"shape-{shape}")
            cert = infer_case(case)
            self.assertEqual(cert["outputs"][0]["exact_worst_age"], oracle_summary(case)["worst_age"]["result"])

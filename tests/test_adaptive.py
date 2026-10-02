from __future__ import annotations

from copy import deepcopy
import unittest

from ftypes.adaptive import check_refinement, infer_refinement, oracle_refinement
from ftypes.adaptive_kernel import AdaptiveCertificateError
from ftypes.families import adaptive_interface


class AdaptiveRefinement(unittest.TestCase):
    def test_reflexive(self):
        case = adaptive_interface(0, 7)
        cert = infer_refinement(case, case)
        self.assertTrue(check_refinement(case, case, cert)["accepted"])

    def test_support_rejection(self):
        left, right = adaptive_interface(0, 0), adaptive_interface(0, 1)
        cert = infer_refinement(left, right)
        self.assertFalse(cert["accepted"])
        self.assertEqual(cert["reason"], "support")

    def test_row_rejection_exists(self):
        found = None
        for i in range(16):
            for j in range(16):
                cert = infer_refinement(adaptive_interface(1, i), adaptive_interface(1, j))
                if cert.get("reason") == "row-cover":
                    found = (i, j, cert)
                    break
            if found:
                break
        self.assertIsNotNone(found)
        i, j, cert = found
        self.assertFalse(check_refinement(adaptive_interface(1, i), adaptive_interface(1, j), cert)["accepted"])

    def test_oracle_agrees_sample(self):
        for i, j in ((0, 0), (0, 3), (5, 2), (15, 7)):
            left, right = adaptive_interface(2, i), adaptive_interface(2, j)
            self.assertEqual(infer_refinement(left, right)["accepted"], oracle_refinement(left, right)["accepted"])

    def test_separator_stales_left(self):
        left, right = adaptive_interface(0, 0), adaptive_interface(0, 1)
        cert = infer_refinement(left, right)
        self.assertGreater(cert["separator"]["left_special_age"], cert["separator"]["deadline"])

    def test_mutated_accepted_flag(self):
        case = adaptive_interface(0, 3)
        cert = infer_refinement(case, case)
        cert["accepted"] = False
        with self.assertRaises(AdaptiveCertificateError):
            check_refinement(case, case, cert)

    def test_mutated_cover(self):
        case = adaptive_interface(0, 3)
        cert = infer_refinement(case, case)
        cert["covers"]["p"]["a"] = "b"
        with self.assertRaises(AdaptiveCertificateError):
            check_refinement(case, case, cert)

    def test_mutated_support_witness(self):
        left, right = adaptive_interface(0, 0), adaptive_interface(0, 1)
        cert = infer_refinement(left, right)
        cert["witness"]["readiness"]["r_p"] -= 1
        with self.assertRaises(AdaptiveCertificateError):
            check_refinement(left, right, cert)

    def test_opaque_group_reflexive(self):
        case = adaptive_interface(1, 10)
        self.assertTrue(infer_refinement(case, case)["accepted"])

    def test_all_small_pair_decisions(self):
        for i in range(4):
            for j in range(4):
                left, right = adaptive_interface(0, i), adaptive_interface(0, j)
                cert = infer_refinement(left, right)
                self.assertEqual(cert["accepted"], oracle_refinement(left, right)["accepted"])

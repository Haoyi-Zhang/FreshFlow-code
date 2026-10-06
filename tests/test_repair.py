"""Finite benign regression checks for the repaired scientific obligations."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from ftypes.adaptive import check_refinement, infer_refinement, oracle_refinement
from ftypes.adaptive_kernel import AdaptiveCertificateError
from ftypes.adaptive_oracle import raw_valuations, validate_separator
from ftypes.dbm import Zone
from ftypes.families import adaptive_interface, make_case, supplemental_cases
from ftypes.kernel import CertificateError
from ftypes.model import ModelError, case_from_spec
from ftypes.residual import compare_prefix, residualize
from ftypes.semantics import OracleLimit, enumerate_executions, future_observation, prefix_of
from ftypes.static import check_case, infer_case
from ftypes.validation import _control_rows


class RepairRegressions(unittest.TestCase):
    def test_negative_readiness_rejected(self):
        spec = make_case(0, 0, 0, small=True).to_spec()
        spec["zones"][0]["bounds"]["r_p"] = [-1, -1]
        with self.assertRaises(ModelError):
            case_from_spec(spec)

    def test_readiness_intersection_preserves_negative_birth(self):
        spec = make_case(0, 0, 0, small=True).to_spec()
        spec["zones"][0]["bounds"]["r_p"] = [-1, 1]
        case = case_from_spec(spec)
        valuations = raw_valuations(case)
        self.assertTrue(valuations)
        self.assertTrue(all(w["r_p"] >= 0 for w in valuations))
        self.assertTrue(any(w["b_a"] == -1 for w in valuations))

    def test_raw_oracle_does_not_call_producer_helpers(self):
        left, right = adaptive_interface(1, 0), adaptive_interface(1, 8)
        with patch.object(Zone, "close", side_effect=AssertionError("closure called")), \
             patch("ftypes.adaptive._support_points", side_effect=AssertionError("support called")), \
             patch("ftypes.adaptive._conditional_k", side_effect=AssertionError("envelope called")):
            result = oracle_refinement(left, right)
        self.assertFalse(result["accepted"])
        self.assertGreater(result["conditional_cells_checked"], 0)

    def test_raw_oracle_cap(self):
        case = adaptive_interface(0, 0)
        with self.assertRaises(OracleLimit):
            raw_valuations(case, cap=1)

    def test_baseline_no_readiness_enumeration_even_wide_bounds(self):
        left = adaptive_interface(0, 0).to_spec()
        right = adaptive_interface(0, 0).to_spec()
        left["zones"][0]["bounds"]["r_q"] = [0, 10**12]
        right["zones"][0]["bounds"]["r_q"] = [0, 10**12]
        left["zones"][0]["constraints"] = []
        right["zones"][0]["constraints"] = [["zero", "r_p", 1]]
        a, b = case_from_spec(left), case_from_spec(right)
        with patch("ftypes.adaptive._support_points", side_effect=AssertionError("readiness enumerated")):
            cert = infer_refinement(a, b)
        self.assertEqual(cert["separator"]["deadline"], 10**12 + 3)
        self.assertTrue(check_refinement(a, b, cert)["separator_checked"])

    def test_every_reported_separator_field_is_bound(self):
        pairs = [(adaptive_interface(0, 0), adaptive_interface(0, 1)),
                 (adaptive_interface(1, 0), adaptive_interface(1, 8))]
        for left, right in pairs:
            certificate = infer_refinement(left, right)
            sep = certificate["separator"]
            changes = {"port": "missing", "readiness": {**sep["readiness"], "r_p": -1},
                       "deadline": sep["deadline"] + 1, "special_wait": -1,
                       "left_special_age": sep["left_special_age"] + 100,
                       "right_special_age": 0, "branch_observable": False,
                       "special_reachable_right": not sep["special_reachable_right"],
                       "left_valuation": {**sep["left_valuation"], "b_a": 99},
                       "payload_term": "src(b)", "emission_time": sep["emission_time"] + 1}
            for field, value in changes.items():
                with self.subTest(reason=certificate["reason"], field=field):
                    bad = deepcopy(certificate)
                    bad["separator"][field] = value
                    with self.assertRaises(AdaptiveCertificateError):
                        check_refinement(left, right, bad)

    def test_separator_birth_witness_changes_are_rejected_by_raw_path(self):
        left, right = adaptive_interface(1, 0), adaptive_interface(1, 8)
        cert = infer_refinement(left, right)
        cert["separator"]["left_valuation"]["b_a"] = 99
        with self.assertRaises(ValueError):
            validate_separator(left, right, cert)

    def test_right_ordinary_and_special_branches_execute(self):
        left, right = adaptive_interface(1, 0), adaptive_interface(1, 8)
        result = validate_separator(left, right, infer_refinement(left, right))
        self.assertGreater(result["right_ordinary_checks"], 0)
        self.assertGreater(result["right_special_checks"], 0)
        self.assertEqual(result["right_valuation_checks"], len(raw_valuations(right)))

    def test_support_bounds_mutation_rejected(self):
        left, right = adaptive_interface(0, 0), adaptive_interface(0, 1)
        cert = infer_refinement(left, right)
        cert["witness"]["left_bound"] += 1
        with self.assertRaises(AdaptiveCertificateError):
            check_refinement(left, right, cert)

    def test_empty_outputs_keep_nonoutput_events_and_receipts(self):
        case = list(supplemental_cases())[-1]
        groups = {}
        for execution in enumerate_executions(case):
            prefix = prefix_of(execution, 1)
            if all(item[2] <= 1 for item in execution.outputs):
                groups.setdefault(prefix, set()).add(future_observation(case, execution, 1))
        saw_pending = False
        for i, (prefix, expected) in enumerate(groups.items()):
            residual = residualize(case, prefix, residual_id=f"empty-{i}")
            self.assertEqual(residual.case.outputs, ())
            self.assertTrue(check_case(residual.case, infer_case(residual.case))["admitted"])
            self.assertTrue(compare_prefix(case, prefix, expected, residual_id=f"check-{i}")["equal"])
            saw_pending |= bool(residual.case.nodes)
        self.assertTrue(saw_pending)

    def test_fully_terminal_has_exact_empty_future(self):
        case = list(supplemental_cases())[-1]
        execution = next(enumerate_executions(case))
        cut = max(t for _, t in execution.event_times)
        prefix = prefix_of(execution, cut)
        residual = residualize(case, prefix)
        self.assertEqual(residual.case.outputs, ())
        self.assertEqual(residual.case.nodes, ())
        self.assertTrue(compare_prefix(case, prefix, {((), (), ())}, residual_id="completed")["equal"])

    def test_past_ages_erased_future_ages_retained(self):
        spec = list(supplemental_cases())[2].to_spec()
        spec["zones"][0]["bounds"].update({"r_p": [0, 0], "r_q": [1, 1], "b_b": [0, 0]})
        for node in spec["nodes"]:
            node["delays"] = {k: [0, 0] for k in node["delays"]}
        case = case_from_spec(spec)
        executions = list(enumerate_executions(case))
        prefixes = {prefix_of(e, 0) for e in executions}
        self.assertEqual(len(prefixes), 1)
        self.assertEqual({e.outputs[0][3] for e in executions}, {0, 1})
        expected = {future_observation(case, e, 0) for e in executions}
        self.assertGreater(len(expected), 1)
        self.assertTrue(compare_prefix(case, next(iter(prefixes)), expected, residual_id="erased")["equal"])

    def test_buffered_receipt_preserves_positive_max_not_multiset(self):
        spec = make_case(0, 1, 0, small=True).to_spec()
        spec["zones"][0]["bounds"].update({"r_p": [0, 0], "r_q": [0, 0]})
        spec["nodes"][0]["delays"]["q"] = [2, 2]
        case = case_from_spec(spec)
        original = next(enumerate_executions(case))
        prefix = prefix_of(original, 1)
        residual = residualize(case, prefix)
        self.assertEqual(residual.case.zones[0].bounds["r_cross-p-x"], (0, 0))
        self.assertTrue(compare_prefix(case, prefix, {future_observation(case, e, 1) for e in enumerate_executions(case)}, residual_id="buffered")["equal"])

    def test_negative_cross_cell_and_nested_multikey_cases(self):
        cases = list(supplemental_cases())
        self.assertEqual(infer_case(cases[1])["profile"]["p:b"], -1)
        self.assertEqual(len(cases[2].outputs), 3)
        self.assertIn("pair(pair", infer_case(cases[2])["terms"]["x"])

    def test_path_endpoint_and_weight_mutations(self):
        case = make_case(0, 0, 1, small=True)
        cert = infer_case(case)
        for field in ("distance", "paths"):
            bad = deepcopy(cert)
            evidence = bad["zones"][0]["closure"]
            if field == "distance":
                evidence["distance"][0][1] += 1
            else:
                evidence["paths"][0][1] = []
            with self.assertRaises(CertificateError):
                check_case(case, bad)

    def test_changed_key_and_dependency_rejected(self):
        case = make_case(0, 0, 1, small=True)
        cert = infer_case(case)
        spec = case.to_spec()
        spec["outputs"][0]["key"] = "different"
        with self.assertRaises(CertificateError):
            check_case(case_from_spec(spec), cert)
        spec = case.to_spec()
        spec["nodes"][0]["data"] = ["x"]
        spec["nodes"][0]["delays"] = {"x": [0, 1]}
        with self.assertRaises(ModelError):
            case_from_spec(spec)

    def test_controls_are_computed(self):
        controls = _control_rows()
        self.assertEqual(len(controls), 12)
        self.assertTrue(all(row["passed"] for row in controls))

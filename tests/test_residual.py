from __future__ import annotations

from collections import defaultdict
import unittest

from ftypes.families import make_case
from ftypes.residual import PrefixError, compare_prefix, residualize
from ftypes.semantics import enumerate_executions, future_observation, prefix_of


class Residualization(unittest.TestCase):
    def setUp(self):
        self.case = make_case(0, 3, 1, small=True, case_id="cut-test")
        self.executions = list(enumerate_executions(self.case))

    def _first_group(self):
        groups = defaultdict(set)
        for execution in self.executions:
            for cut in range(max(item[2] for item in execution.outputs)):
                prefix = prefix_of(execution, cut)
                groups[prefix].add(future_observation(self.case, execution, cut))
        return next(iter(groups.items()))

    def test_exact_future_set(self):
        prefix, expected = self._first_group()
        self.assertTrue(compare_prefix(self.case, prefix, expected, residual_id="r0")["equal"])

    def test_births_are_rebased(self):
        prefix, _ = self._first_group()
        residual = residualize(self.case, prefix, residual_id="r1")
        cut = prefix[0]
        original = self.case.zones[0].close()
        new = residual.case.zones[0].close()
        self.assertEqual(new.bound("zero", "b_a"), original.bound("zero", "b_a") - cut)

    def test_crossing_ports_are_distinct(self):
        prefix, _ = self._first_group()
        residual = residualize(self.case, prefix, residual_id="r2")
        self.assertEqual(len(residual.crossing_for_edge), len(set(residual.crossing_for_edge.values())))

    def test_cut_clock_is_zero(self):
        prefix, _ = self._first_group()
        residual = residualize(self.case, prefix, residual_id="r3")
        for zone in residual.case.zones:
            self.assertEqual(zone.bounds["r_cut-clock"], (0, 0))

    def test_missing_overdue_receipt_rejected(self):
        # Pick an execution with a fired sender and then delete an observed receipt at a late cut.
        execution = max(self.executions, key=lambda e: max(dict(e.event_times).values()))
        cut = max(dict(execution.event_times).values())
        prefix = prefix_of(execution, cut)
        receipts = list(prefix[2])
        if receipts:
            receipts.pop()
            bad = (cut, prefix[1], tuple(receipts))
            with self.assertRaises(PrefixError):
                residualize(self.case, bad, residual_id="bad")

    def test_duplicate_event_rejected(self):
        prefix, _ = self._first_group()
        if prefix[1]:
            bad = (prefix[0], prefix[1] + (prefix[1][0],), prefix[2])
            with self.assertRaises(PrefixError):
                residualize(self.case, bad, residual_id="bad2")

    def test_sample_prefixes(self):
        groups = defaultdict(set)
        for execution in self.executions:
            for cut in range(max(item[2] for item in execution.outputs)):
                groups[prefix_of(execution, cut)].add(future_observation(self.case, execution, cut))
        for index, (prefix, expected) in enumerate(groups.items()):
            if index >= 8:
                break
            self.assertTrue(compare_prefix(self.case, prefix, expected, residual_id=f"sample-{index}")["equal"])

    def test_nonnegative_residual_event_times(self):
        prefix, _ = self._first_group()
        residual = residualize(self.case, prefix, residual_id="r4")
        for execution in enumerate_executions(residual.case):
            self.assertTrue(all(time >= 0 for _, time in execution.event_times))

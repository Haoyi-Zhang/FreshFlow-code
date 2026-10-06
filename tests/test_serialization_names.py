"""Evidence round trips and collision-free finite residual construction."""
import json
import unittest

from ftypes.adaptive import check_refinement, infer_refinement
from ftypes.families import adaptive_interface, make_case
from ftypes.model import case_from_spec
from ftypes.residual import compare_prefix, residualize
from ftypes.semantics import enumerate_executions, future_observation, prefix_of
from ftypes.static import check_case, infer_case


class SerializationNames(unittest.TestCase):
    def reload(self, case):
        return case_from_spec(json.loads(json.dumps(case.to_spec())))

    def test_static_input_is_idempotent_and_certificate_replays(self):
        case = make_case(0, 0, 0)
        cert = infer_case(case)
        for _ in range(3):
            saved = case.to_spec()
            case = self.reload(case)
            self.assertEqual(saved, case.to_spec())
            self.assertEqual(cert['admitted'], check_case(case, cert)['admitted'])

    def test_adaptive_inputs_reload_with_unchanged_edge_indices(self):
        for group in range(3):
            for variants in ((0, 0), (0, 1), (0, 8)):
                left, right = (adaptive_interface(group, i) for i in variants)
                cert = infer_refinement(left, right)
                replay = check_refinement(self.reload(left), self.reload(right), cert)
                self.assertEqual(cert['accepted'], replay['accepted'])

    def test_duplicate_injected_constraints_are_canonical(self):
        case = make_case(0, 0, 0)
        spec = case.to_spec()
        spec['zones'][0]['constraints'] *= 2
        loaded = case_from_spec(spec)
        self.assertEqual(case.to_spec(), loaded.to_spec())
        self.assertEqual(check_case(case, infer_case(case)),
                         check_case(loaded, infer_case(case)))

    def two_crossings(self, names=('a-b', 'a', 'c', 'b-c')):
        p, q, x, y = names
        return case_from_spec({
            'id': 'crossing-names', 'origins': ['s'],
            'ports': [{'name': p, 'term': 'src(s)'}, {'name': q, 'term': 'src(s)'}],
            'zones': [{'bounds': {'b_s': [0, 0], f'r_{p}': [0, 0], f'r_{q}': [0, 0]}}],
            'nodes': [{'name': x, 'op': 'copy', 'data': [p], 'gates': [], 'delays': {p: [1, 1]}},
                      {'name': y, 'op': 'copy', 'data': [q], 'gates': [], 'delays': {q: [1, 1]}}],
            'outputs': [{'key': 'one', 'node': x, 'term': 'src(s)', 'deadline': 1},
                        {'key': 'two', 'node': y, 'term': 'src(s)', 'deadline': 1}]})

    def check_future(self, case):
        executions = list(enumerate_executions(case))
        prefix = prefix_of(executions[0], 0)
        expected = {future_observation(case, execution, 0) for execution in executions}
        residual = residualize(case, prefix)
        self.assertTrue(compare_prefix(case, prefix, expected, residual_id='checked')['equal'])
        self.assertEqual(len(residual.case.names), len(set(residual.case.names)))
        return residual

    def test_ambiguous_crossing_names_remain_distinct(self):
        residual = self.check_future(self.two_crossings())
        self.assertEqual(2, len(set(residual.crossing_for_edge.values())))

    def test_long_valid_original_names_have_short_fresh_helpers(self):
        residual = self.check_future(self.two_crossings(('a' * 79, 'b' * 79, 'c' * 79, 'd' * 79)))
        self.assertTrue(all(len(name) <= 80 for name in residual.crossing_for_edge.values()))

    def test_original_cut_clock_name_does_not_alias_helper(self):
        case = case_from_spec({'id': 'original-clock', 'origins': ['s'],
            'ports': [{'name': 'cut-clock', 'term': 'src(s)'}],
            'zones': [{'bounds': {'b_s': [0, 0], 'r_cut-clock': [1, 1]}}],
            'nodes': [], 'outputs': [{'key': 'one', 'node': 'cut-clock',
                                     'term': 'src(s)', 'deadline': 1}]})
        residual = self.check_future(case)
        self.assertNotEqual('cut-clock', residual.case.metadata['cut_clock'])

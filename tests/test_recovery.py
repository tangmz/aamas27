import unittest
from recovery.standing import Ledger, verify_finite_examples
from recovery.replay import messages, policy_outputs


class RecoveryTests(unittest.TestCase):
    def test_standing_survives_change_and_deadline_ends_unresolved(self):
        self.assertEqual(verify_finite_examples()['checked_traces'], 13)

    def test_cannot_rewrite_or_resolve_twice(self):
        ledger = Ledger()
        ledger.register('c', 'a', 'A', 'Evidence')
        with self.assertRaises(ValueError): ledger.register('c', 'a', 'B', 'Changed')
        ledger.resolve('c', 'rejected', 'Review finding')
        with self.assertRaises(ValueError): ledger.resolve('c', 'upheld', 'Changed finding')

    def test_support_swap_does_not_change_blind_review(self):
        case = {'problem': {'question': 'q', 'options': {'A':'a','B':'b'}},
                'arguments': [{'answer':'A','reasoning':'r1'}, {'answer':'B','reasoning':'r2'}],
                'hypothetical_support_counts': [4, 1]}
        swapped = {**case, 'hypothetical_support_counts': [1,4]}
        self.assertEqual(messages(case,'blind_review'), messages(swapped,'blind_review'))
        self.assertNotEqual(messages(case,'ordinary'), messages(swapped,'ordinary'))
        with self.assertRaises(ValueError): messages(case,'checkpoint')

    def test_persistent_policy_can_help_or_harm(self):
        a={'answer':'A','confidence':.9}; b={'answer':'B','confidence':.9}
        output=policy_outputs(a,a,a,b)
        self.assertFalse(output['reactive_triggered'])
        self.assertEqual(output['reactive_review'],'A')
        self.assertEqual(output['persistent_review'],'B')
        self.assertEqual(output['persistent_review'],output['always_review'])
        self.assertTrue(policy_outputs(a,b,a,b)['reactive_triggered'])


if __name__ == '__main__': unittest.main()

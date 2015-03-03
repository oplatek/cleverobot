#!/usr/bin/env python
# encoding: utf-8
import unittest
import nlg

class NlgTest(unittest.TestCase):
    def test_action2nlg_select(self):
        n = nlg.Nlg()
        hi = n.action2lang({'type':'greeting'})
        self.assertEqual(hi, 'Hi!')

    def test_indirect_object_q(self):
        # FIXME based on the kb generate some question and compare them to gold standard TODO create
        pass

    def confirm_test(self):
        n = nlg.Nlg()
        answer = n.confirm({'type': 'confirm', 'about': ('Little Richard', None, None)})
        self.assertTrue('Little Richard' in answer)


if __name__ == '__main__':
    unittest.main()


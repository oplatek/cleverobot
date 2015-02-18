#!/usr/bin/env python
# encoding: utf-8
import unittest
import nlg

class NlgTest(unittest.TestCase):
    def test_action2nlg_select(self):
        n = nlg.Nlg()
        hi = n.action2lang({'type':'greeting'})
        self.assertEqual(hi, 'Hi!')


if __name__ == '__main__':
    unittest.main()


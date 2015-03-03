#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from cbot.parse import WordDistance


class TestWordDistance(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestWordDistance, self).__init__(*args, **kwargs)
        self.penalties = (1.0, 2.0, 1.0)
        self.dist_data = [
                ([1, 1 ,1],[0, 0, 0], 6),
                ([0, 1,],[0, 0, 0], 3),
                ([1, 0, 0],[0, 0, 0], 2),
                ([0, 1, 0],[0, 0, 0], 2),
                ([0, 0, 1],[0, 0, 0], 2),
                ]
        self.path_data = [
                ([0,0],[0,0],[(None,None),(None,None)]),
                ([1],[],[(1, None)]),
                ([],[1],[(None, 1)]),
                ([1,1],[0,0],[(1,0),(1,0)]),
                ([1],[0],[(1,0)]),
                ]

    def test_distance(self):
        for s, t, d in self.dist_data:
            wd = WordDistance(s, t, self.penalties)
            d_test = wd.compute_dist()
            self.assertEqual(d_test, d)

    def test_path(self):
        for s, t, gold_path in self.path_data:
            wd = WordDistance(s,t, self.penalties)
            path = wd.best_path()
            self.assertEqual(path, gold_path)


if __name__ == '__main__':
    unittest.main()

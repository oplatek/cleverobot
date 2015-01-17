#!/usr/bin/env python
# encoding: utf-8
import unittest
import run


class RoutingTestCase(unittest.TestCase):

    def setUp(self):
        self.app = run.app.test_client()

    def tearDown(self):
        pass

    def test_routing(self):
        rs = self.app.get('/')
        self.assertEqual(rs.status, '200 OK')
        self.assertIn('<title>Clever robot</title>', rs.data)

if __name__ == '__main__':
    unittest.main()

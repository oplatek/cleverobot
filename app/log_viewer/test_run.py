#!/usr/bin/env python
# encoding: utf-8
import os

__author__ = 'ondrej platek'
import unittest
import app.log_viewer.run as run


class RoutingTestCase(unittest.TestCase):

    def setUp(self):
        log_root = os.path.realpath(os.path.join(os.path.dirname(__file__), 'test_logs'))
        run.root = log_root
        self.client = run.app.test_client()

    def tearDown(self):
        pass

    def test_routing(self):
        rs = self.client.get('/')
        self.assertEqual(rs.status, '200 OK')
        self.assertIn('<title>Clever robot log viewer</title>', rs.data)

    def test_log_views(self):
        rs = self.client.get('/')
        assert 'test_dm_logic.log' in rs.data

    def test_display_recorded_data(self):
        rs = self.client.get('/log?path=test_dm_logic.log')
        assert "Hello" in rs.data  # first user utterance
        assert "Hi" in rs.data  # first original bad system response
        assert "What do? you?" in rs.data  # original bad system

    def test_current_system_reply(self):
        rs = self.client.get('/log?path=test_dm_logic.log')
        current_system = []
        for line in rs.data.split('\n'):
            if "current_system" in line:
                reply = line[line.find(".text(") + 6:-2]
                current_system.append(reply)
        print 'All responses: %s\n' % current_system
        non_none_current_system = [s for s in current_system if s != 'null']
        print 'Non null responses: %s\n' % non_none_current_system
        assert len(non_none_current_system) > 0



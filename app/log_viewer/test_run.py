#!/usr/bin/env python
# encoding: utf-8
import os
from app.cleverobot.run import start_zmq_and_log_processes, shut_down

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
        self.assertIn('test_dm_logic.log', rs.data)



class ReplayingLogTestCase(unittest.TestCase):

    def setUp(self):
        log_root = os.path.realpath(os.path.join(os.path.dirname(__file__), 'test_logs'))
        run.root = log_root
        self.client = run.app.test_client()
        self.log_process, self.forwarder_process_bot, self.forwarder_process_user = start_zmq_and_log_processes(run.ctx, run.bot_input,
                                                                                                 run.bot_output,
                                                                                                 run.user_input,
                                                                                                 run.user_output)

    def tearDown(self):
        shut_down(self.forwarder_process_bot, self.forwarder_process_user, self.log_process)

    def test_display_recorded_data(self):
        rs = self.client.get('/log?path=test_dm_logic.log')
        print rs.data
        self.assertIn("Hello", rs.data)  # first user utterance
        self.assertIn("Hi", rs.data)  # first original bad system response
        self.assertIn("What do? you?", rs.data)  # original bad system

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
        self.assertTrue(len(non_none_current_system) > 0)



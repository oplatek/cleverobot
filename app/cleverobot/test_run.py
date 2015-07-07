#!/usr/bin/env python
# encoding: utf-8
import unittest
import datetime
import app.cleverobot.run as run
import time


class RoutingTestCase(unittest.TestCase):

    def setUp(self):
        self.client = run.app.test_client()

    def tearDown(self):
        pass

    def test_routing(self):
        rs = self.client.get('/')
        self.assertEqual(rs.status, '200 OK')
        self.assertIn('<title>Clever robot</title>', rs.data)


@unittest.skip("TODO")
class TestSocketIO(unittest.TestCase):

    def setUp(self):
        self.client = run.socketio.test_client(run.app)
        self.log_process, self.forwarder_process_bot, self.forwarder_process_user = run.start_zmq_and_log_processes(
            run.ctx, run.bot_input, run.bot_output, run.user_input, run.user_output)

    def tearDown(self):
        self.client.disconnect()
        del self.client
        run.shut_down(self.forwarder_process_bot, self.forwarder_process_user, self.log_process)

    def test_connect(self):
        self.client.emit('begin', {'setup': 'unused'})
        time.sleep(0.2)
        self.client.emit('utterance', {'time_sent': str(datetime.datetime.now()), 'user': 'human', 'utterance': 'Hi'})
        self.client.emit('end', {'time_sent': str(datetime.datetime.now()), 'user': 'human', 'utterance': 'Hi'})
        received = self.client.get_received()
        print received


if __name__ == '__main__':
    unittest.main()

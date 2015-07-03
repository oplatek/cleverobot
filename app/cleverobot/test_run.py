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


class TestSocketIO(unittest.TestCase):

    def setUp(self):
        run.main()
        self.client = run.socketio.test_client(run.app)

    def tearDown(self):
        self.client.disconnect()

    def test_connect(self):
        # self.client.send({'setup': 'unused'}, namespace='/begin')
        self.client.emit('begin', {'setup': 'unused'})
        self.client.emit('utterance', {'time_sent': datetime.datetime.now(), 'user':'human', 'utterance': 'Hi'})
        time.sleep(5)
        received = self.client.get_received()
        print received


if __name__ == '__main__':
    unittest.main()

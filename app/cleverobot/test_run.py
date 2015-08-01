#!/usr/bin/env python
# encoding: utf-8
import logging
import unittest
import datetime
import app.cleverobot.run as run
import time
from cbot.bot.alias import HUMAN


class RoutingTestCase(unittest.TestCase):

    def setUp(self):
        self.client = run.app.test_client()

    def tearDown(self):
        pass

    def test_routing(self):
        rs = self.client.get('/')
        self.assertEqual(rs.status, '200 OK')
        self.assertIn('<title>Clever robot</title>', rs.data)


@unittest.skip("TODO handshake unsuccessful")
class TestSocketIO(unittest.TestCase):

    def setUp(self):
        self.client = run.socketio.test_client(run.app)
        port_offset = len(__file__)  # TODO hack randomize ports
        self.forwarder_process_bot, self.forwarder_process_user = run.start_zmq_processes(
            run.bot_input + port_offset, run.bot_output + port_offset,
            run.user_input + port_offset, run.user_output + port_offset)
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)

    def tearDown(self):
        self.client.disconnect()
        run.shutdown_zmq_processes(self.forwarder_process_bot, self.forwarder_process_user)
        del self.client

    # @unittest.expectedFailure
    def test_connect(self):
        self.client.emit('begin', {'setup': 'unused'})
        time.sleep(0.2)
        self.client.emit('utterance', {'time_sent': str(datetime.datetime.now()), 'name': HUMAN, 'utterance': 'Hi'})
        self.client.emit('end', {'time_sent': str(datetime.datetime.now()), 'name': HUMAN, 'utterance': 'Hi'})
        received = self.client.get_received()
        self.logger.debug(received)


if __name__ == '__main__':
    unittest.main()

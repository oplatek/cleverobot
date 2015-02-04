#!/usr/bin/env python
# encoding: utf-8
import unittest
import zmq.green as zmq
from bot import ChatBot, ChatBotConnector
import time
import datetime
import logging
import sys
import inspect


class ChatBotConnectorTest(unittest.TestCase):
    pass

class ChatBotTest(unittest.TestCase):

    def setUp(self):
        self.input_port = '4000'
        self.output_port = '5000'
        self.context = zmq.Context()
        self.pull_socket = self.context.socket(zmq.PULL)
        self.push_socket = self.context.socket(zmq.PUSH)
        self.pull_socket.connect("tcp://localhost:%s" % self.output_port)
        self.push_socket.connect("tcp://localhost:%s" % self.input_port)
        self.poller = zmq.Poller()
        self.poller.register(self.pull_socket, zmq.POLLIN)
        self.timeout = 3000.0 # ms

    def tearDown(self):
        pass

    def test_is_responding(self):
        message = None
        log = logging.getLogger(inspect.stack()[0][3])  # get logger with the test name
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        log.addHandler(ch)
        log.setLevel(logging.DEBUG)
        bot = ChatBot(self.input_port, self.output_port, logger=log)
        bot.start()
        msg = {'time': str(datetime.datetime.utcnow()), 'user': 'human', 'utterance': 'hi'}
        self.push_socket.send_json(msg)
        socks = dict(self.poller.poll(timeout=self.timeout))
        if self.pull_socket in socks and socks[self.pull_socket] == zmq.POLLIN:
            message = self.pull_socket.recv_json()
        bot.terminate()
        bot.join()
        self.assertIsNotNone(message)
        self.assertItemsEqual(bot.__class__.__name__, message['user'], msg='messageuser %s' % message['user'])


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)
    unittest.main()

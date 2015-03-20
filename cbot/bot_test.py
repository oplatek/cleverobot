#!/usr/bin/env python
# encoding: utf-8
from __future__ import division
import unittest
import logging
import time
import random
from cbot.bot import ChatBot, ChatBotConnector, forwarder_device_start
import datetime
import inspect
import sys
import zmq


def wrap_msg(utt):
    return {'time': time.time(), 'user': 'human', 'utterance': utt}


def send_msg(responses):
    def log_and_append(x):
        print x
        responses.append(x)

    return log_and_append


class BotTest(unittest.TestCase):

    def should_run(self):
        return self.run

    def get_next_utt(self):
        if self.i < len(self.user_utt):
            utt = self.user_utt[self.i]
        else:
            self.run = False
            utt = 'Good bye'
        self.i += 1
        return wrap_msg(utt)

    def setUp(self):
        random.seed(198711)
        self.sent = []
        self.bot = ChatBot(input_port=-6, output_port=-66)
        self.run = True
        self.i = 0
        self.bot.should_run = self.should_run
        self.bot.receive_msg = self.get_next_utt
        self.responses = []
        self.bot.send_msg = send_msg(self.responses)

    def test_loop(self):
        self.user_utt = ['I know Little Richard']
        self.bot.chatbot_loop()
        print self.responses


class ChatBotConnectorTest(unittest.TestCase):

    def test_chatbot_loop(self):
        self.msg = None

        def recv(m):
            print 'receive', m
            self.msg = m

        self.callback = recv
        self.bot_front, self.bot_back, self.user_front, self.user_back = 10001, 10002, 10003, 10004
        self.user_device = forwarder_device_start(self.user_front, self.user_back)
        self.bot_device = forwarder_device_start(self.bot_front, self.bot_back)

        time.sleep(1.0)
        c = ChatBotConnector(self.callback, self.bot_front, self.bot_back, self.user_front, self.user_back)
        c.start()
        print 'cannot sleep just after forking the process because it freezes the forking process'
        time.sleep(1.0)
        print 'after nap'
        c.send(wrap_msg('test'))
        time.sleep(0.1)
        c.send(wrap_msg('test1'))
        time.sleep(1.0)
        # c.join(timeout=1.0)
        # self.assertIsNotNone(self.msg)


class ChatBotTest(unittest.TestCase):

    def setUp(self):
        self.bot_front, self.bot_back, self.user_front, self.user_back = 10001, 10002, 10003, 10004
        self.user_device = forwarder_device_start(self.user_front, self.user_back)
        self.bot_device = forwarder_device_start(self.bot_front, self.bot_back)
        self.context = zmq.Context()
        self.sub_socket = self.context.socket(zmq.SUB)
        self.pub_socket = self.context.socket(zmq.PUB)
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')
        self.sub_socket.connect("tcp://localhost:%d" % self.user_back)
        self.pub_socket.connect("tcp://localhost:%d" % self.bot_front)
        self.poller = zmq.Poller()
        self.poller.register(self.sub_socket, zmq.POLLIN)
        self.timeout = 2000.0  # ms

    def tearDown(self):
        pass

    def test_is_responding(self):
        message = None
        log = logging.getLogger(inspect.stack()[0][3])  # get logger with the test name
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        log.addHandler(ch)
        log.setLevel(logging.DEBUG)
        b = ChatBot(self.bot_back, self.user_front, logger=log)
        b.start()
        time.sleep(0.05)
        msg = {'time': str(datetime.datetime.utcnow()), 'user': 'human', 'utterance': 'hi'}
        self.pub_socket.send_json(msg)
        socks = dict(self.poller.poll(timeout=self.timeout))
        if self.sub_socket in socks and socks[self.sub_socket] == zmq.POLLIN:
            message = self.sub_socket.recv_json()
        b.terminate()
        self.assertIsNotNone(message)
        self.assertItemsEqual(b.__class__.__name__, message['user'], msg='messageuser %s' % message['user'])


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)
    unittest.main()

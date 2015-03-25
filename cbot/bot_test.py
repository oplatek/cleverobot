#!/usr/bin/env python
# encoding: utf-8
from __future__ import division
from multiprocessing import Process
import unittest
import logging
import time
import random
import gevent
from cbot.bot import ChatBot, ChatBotConnector, forwarder_device_start, log_loop, connect_logger
import datetime
import sys
import zmq


def wrap_msg(utt):
    return {'time': time.time(), 'user': 'human', 'utterance': utt}


class ChatBotRunLoopTest(unittest.TestCase):
    @staticmethod
    def send_msg(responses):
        def log_and_append(x):
            print x
            responses.append(x)

        return log_and_append

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
        self.bot = ChatBot(input_port=-6, output_port=-66, name='test chatbot')
        self.run = True
        self.i = 0
        self.bot.should_run = self.should_run
        self.bot.receive_msg = self.get_next_utt
        self.responses = []
        self.bot.send_msg = ChatBotRunLoopTest.send_msg(self.responses)

    def test_loop(self):
        self.user_utt = ['I know Little Richard']
        self.bot.run()
        self.assertTrue(len(self.responses) > 0)
        print self.responses


class LoggerTest(unittest.TestCase):

    def test_process_zmq_logger(self):
        log_process = Process(target=log_loop)
        log_process.start()

        ctx = zmq.Context()
        logger = logging.getLogger('')
        connect_logger(logger, ctx)
        time.sleep(0.2)
        logger.info('Info test')
        time.sleep(0.1)
        logger.debug('Debug test')
        time.sleep(0.1)
        logger.log(logging.CRITICAL, 'log critical test')

        log_process.join(0.1)  # TODO send message to exit the logger
        log_process.terminate()


class ChatBotConnectorTest(unittest.TestCase):
    def setUp(self):
        self.logger_process = Process(target=log_loop)
        self.logger_process.start()
        self.msg = None
        
        def receive(m):
            self.msg = m

        self.callback = receive
        self.bot_front, self.bot_back, self.user_front, self.user_back = 10001, 10002, 10003, 10004
        self.user_device = forwarder_device_start(self.user_front, self.user_back)
        self.bot_device = forwarder_device_start(self.bot_front, self.bot_back)
        time.sleep(2.0)

    def tearDown(self):
        self.user_device.join(0.1)
        self.bot_device.join(0.1)
        self.logger_process.terminate()

    def test_chatbot_loop(self):
        c = ChatBotConnector(self.callback, self.bot_front, self.bot_back, self.user_front, self.user_back)
        print 'cannot sleep just after forking the process because it freezes the forking process'
        time.sleep(3.0)
        print 'after nap'
        c.start()
        gevent.sleep(3.0)
        c.send(wrap_msg('test'))
        # c.run()  # works fine without gevent
        time.sleep(0.1)
        c.send(wrap_msg('test1'))

        self.assertIsNotNone(self.msg)

        c.kill(1.0)


class ChatBotTest(unittest.TestCase):

    def setUp(self):
        self.bot_front, self.bot_back, self.user_front, self.user_back = 10001, 10002, 10003, 10004
        self.user_device = forwarder_device_start(self.user_front, self.user_back)
        self.bot_device = forwarder_device_start(self.bot_front, self.bot_back)
        self.context = zmq.Context()
        self.sub_socket = self.context.socket(zmq.SUB)
        self.pub_socket = self.context.socket(zmq.PUB)
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b'')
        self.sub_socket.connect("tcp://127.0.0.1:%d" % self.user_back)
        self.pub_socket.connect("tcp://127.0.0.1:%d" % self.bot_front)
        self.poller = zmq.Poller()
        self.poller.register(self.sub_socket, zmq.POLLIN)
        self.logger_process = Process(target=log_loop)
        self.logger_process.start()
        self.b = ChatBot(self.bot_back, self.user_front, 'test chatbot')
        self.b.start()
        print 'Initiation finished sleeping for a while'
        time.sleep(3.0)

    def tearDown(self):
        print 'Tearing down sleeping in order to give chance the msg to arrive'
        time.sleep(0.2)
        self.logger_process.terminate()
        self.b.terminate()
        self.user_device.join(0.1)
        self.bot_device.join(0.1)

    def test_is_responding(self):
        message = None
        msg = {'time': str(datetime.datetime.utcnow()), 'user': 'human', 'utterance': 'hi'}
        self.pub_socket.send_json(msg)
        socks = dict(self.poller.poll(timeout=200))
        if self.sub_socket in socks and socks[self.sub_socket] == zmq.POLLIN:
            message = self.sub_socket.recv_json()
        self.assertIsNotNone(message)
        self.assertItemsEqual(self.b.__class__.__name__, message['user'], msg='messageuser %s' % message['user'])


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)
    unittest.main()

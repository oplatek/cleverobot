#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals, division
import json
from multiprocessing import Process
import unittest
import logging
import time
import random
import gevent
from cbot.bot.alias import HUMAN
from cbot.bot.connectors import ChatBotProcess, ChatBotConnector, forwarder_device_start, ChatBot
from cbot.bot.log import connect_logger, wrap_msg, chatbot2file_log_loop
import datetime
import sys
import zmq


class LoggerTest(unittest.TestCase):
    def test_process_zmq_logger(self):
        log_process = Process(target=chatbot2file_log_loop)
        log_process.start()

        ctx = zmq.Context()
        unique_name_for_msg_logger = self.__class__.__name__ + '1234'
        session_id = '1234'
        connect_logger(unique_name_for_msg_logger, session_id, ctx)
        logger = logging.getLogger(unique_name_for_msg_logger)
        time.sleep(0.2)
        logger.info(json.dumps(wrap_msg('Info test')))
        time.sleep(0.1)
        logger.warning('{"name": "test"}')
        time.sleep(0.1)
        logger.debug('{"special debug": "value"}')

        log_process.join(0.1)  # TODO send message to exit the logger
        log_process.terminate()


class ChatBotConnectorTest(unittest.TestCase):
    def setUp(self):
        self.logger_process = Process(target=chatbot2file_log_loop)
        self.logger_process.start()
        self.msg = None

        def receive(m, name):
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

    def test_chatbot_loop(self, interval=0.01, attempts=10):
        log = logging.getLogger(__name__ + '.' + self.__class__.__name__)
        c = ChatBotConnector(self.callback, self.bot_front, self.bot_back, self.user_front, self.user_back)
        c.start()
        log.debug('sending msg')
        self.assertIsNone(self.msg)
        c.send(wrap_msg('test'))
        response_time = 0
        for i in range(attempts):
            if self.msg is not None:
                break
            gevent.sleep(interval)
            response_time += interval
        log.info('Waiting for response %f s.' % response_time)
        self.assertIsNotNone(self.msg)
        c.kill()


class ChatBotOneAnswerTest(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)
        seed = random.randint(0, sys.maxint)
        self.logger.info('Using seed: %d' % seed)
        random.seed(seed)
        self.should_run = True
        self.output, self.input = None, None
        self.test_start = datetime.datetime.now()
        self.timeout = 1.0

        def should_run():
            if not self.should_run:
                return False
            if (datetime.datetime.now() - self.test_start).total_seconds() > self.timeout:
                return False
            return True

        def send(msg):
            self.output = msg

        self.should_run = should_run
        self.cb = ChatBot(self.__class__.__name__, send)

        def receive_msg():
            return {'time': time.time(), 'name': HUMAN, 'utterance': self.input}

        self.receive_msg = receive_msg
        self.logger.debug('Test started at %s with timeout %s' % (self.test_start, self.timeout))
        self.logger.debug("Bot initialized")

    def test_hi(self):
        self.assertIsNone(self.output)
        self.input = 'hi'
        self.logger.info("User: %s" % self.input)
        self.cb.receive_msg(self.receive_msg())
        self.logger.info("System: %s" % self.output)
        self.assertIsNotNone(self.output)

    def test_inform_entity(self):
        self.assertIsNone(self.output)
        self.input = 'I know Little Richard'
        self.logger.info("User: %s" % self.input)
        self.cb.receive_msg(self.receive_msg())
        self.logger.info("System: %s" % self.output)

    def test_test_input(self):
        self.assertIsNone(self.output)
        self.input = 'test'
        self.logger.info("User: %s" % self.input)
        self.cb.receive_msg(self.receive_msg())
        self.logger.info("System: %s" % self.output)


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    unittest.main()

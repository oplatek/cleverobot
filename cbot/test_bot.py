#!/usr/bin/env python
# encoding: utf-8
from __future__ import division
from multiprocessing import Process
import unittest
import logging
import time
import random
import uuid
import gevent
from cbot.bot import ChatBot, ChatBotConnector, forwarder_device_start, log_loop, connect_logger, topic_msg_to_json
import datetime
import sys
import zmq
from zmq.utils import jsonapi


def wrap_msg(utt):
    return {'time': time.time(), 'user': 'human', 'utterance': utt}


class ChatBotRunLoopTest(unittest.TestCase):
    @classmethod
    def send_msg(cls, responses):
        log = logging.getLogger(cls.__name__)

        def log_and_append(x):
            log.debug(x)
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
        log = logging.getLogger(self.__class__.__name__ + '.test_loop')
        self.user_utt = ['I know Little Richard']
        self.bot.run()
        self.assertTrue(len(self.responses) > 0)
        log.info(self.responses)


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
        log = logging.getLogger(str(self.__class__) + '.test_chatbot_loop')
        c = ChatBotConnector(self.callback, self.bot_front, self.bot_back, self.user_front, self.user_back)
        c.start()
        log.debug('sending msg')
        c.send(wrap_msg('test'))
        c.send(wrap_msg('test1'))
        self.assertIsNotNone(self.msg)
        c.kill(1.0)


class ChatBotOneAnswerTest(unittest.TestCase):
    def setUp(self):
        log = logging.getLogger(self.__class__.__name__ + '.setUp')
        seed = random.randint(0, sys.maxint)
        print('Using seed: %d' % seed)
        log.info('Using seed: %d' % seed)
        random.seed(seed)
        self.should_run = True
        self.output, self.input = None, None
        self.test_start = datetime.datetime.now()
        self.timeout = 1.0
        self.bot = ChatBot(name=str(123), input_port=-6, output_port=-66)

        def should_run():
            if not self.should_run:
                return False
            if (datetime.datetime.now() - self.test_start).total_seconds() > self.timeout:
                return False
            return True

        self.bot.should_run = should_run

        def send(msg):
            self.output = msg
            self.should_run = False

        self.bot.send_msg = send

        def receive_msg():
            return {'time': time.time(), 'user': 'human', 'utterance': self.input}

        self.bot.receive_msg = receive_msg
        log.debug('Test started at %s with timeout %s' % (self.test_start, self.timeout))
        self.bot.single_process_init()
        log.debug("Bot initialized")

    def test_hi(self):
        log = logging.getLogger(self.__class__.__name__ + '.setUp')  # TODO
        self.assertIsNone(self.output)
        self.input = 'hi'
        print("User: %s" % self.input)
        self.bot.chatbot_loop()
        self.assertIsNotNone(self.output)
        print("System: %s" % self.output)



if __name__ == '__main__':
    logging.basicConfig(stream=sys.stderr)
    logging.getLogger("ChatBotTest.setUp").setLevel(logging.DEBUG)
    unittest.main()

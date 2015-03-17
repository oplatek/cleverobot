#!/usr/bin/env python
# encoding: utf-8
# from __future__ import unicode_literals
import multiprocessing
import os
import errno
import zmq.green as zmqg
import zmq
from zmq.devices import ProcessDevice
import time
import logging
from gevent import Greenlet
import uuid
from kb_data import data
import dm as dm
import cbot.kb as kb
import sys
import nlg


def get_chatbot_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    logger.addHandler(ch)
    return logger


def setup_logger(id):
    dirname = os.path.dirname(os.path.abspath(__file__))
    logger = logging.getLogger(__name__)
    logdir = os.path.join(dirname, 'logs')
    try:
        os.mkdir(logdir)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise
    name = '%d_%d.log' % (time.time(), id)
    logger.setLevel(logging.DEBUG)
    ch = logging.FileHandler(os.path.join(logdir, name), mode='w', delay=True)
    logger.addHandler(ch)
    return logger


def forwarder_device_start(frontend_port, backend_port):
    forwarder = ProcessDevice(zmq.FORWARDER, zmq.SUB, zmq.PUB)
    forwarder.setsockopt_in(zmq.SUBSCRIBE, b'')

    forwarder.bind_in("tcp://*:%d" % frontend_port)
    forwarder.bind_out("tcp://*:%d" % backend_port)

    forwarder.start()
    return forwarder


class ChatBotConnector(Greenlet):

    def __init__(self, response_cb, robot_front_port, robot_back_port,
                 user_front_port, user_back_port, logger=None):
        super(ChatBotConnector, self).__init__()

        self.context = zmqg.Context()
        self.pub2bot = self.context.socket(zmqg.PUB)
        self.sub2bot = self.context.socket(zmqg.SUB)
        self.pub2bot.connect('tcp://localhost:%d' % robot_front_port)
        self.sub2bot.connect('tcp://localhost:%d' % user_back_port)
        self.poller = zmqg.Poller()
        self.poller.register(self.sub2bot, zmqg.POLLIN)
        self.id = uuid.uuid4()

        if logger is None:
            self.logger = setup_logger(self.id)

        self.response = response_cb
        self.should_run = True  # change is based on the messages
        self.bot = ChatBot(robot_back_port, user_front_port)
        self.bot.start()

    def __del__(self):
        super(ChatBotConnector, self).__init__()
        self.bot.terminate()

    def send(self, msg):
        msg['id'] = str(self.id)
        self.logger.info(msg)
        self.pub2bot.send_json(msg)

    def _run(self):
        while self.should_run:
            socks = dict(self.poller.poll())
            if self.oresender in socks and socks[self.oresender] == zmqg.POLLIN:
                msg = self.oresender.recv_json()
                self.response(msg)
                self.logger.info(msg)

    def finalize(self, msg):
        self.should_run = False


class ChatBot(multiprocessing.Process):
    """Chatbot class organise the communication between
    subtasks processes or implement easy subtask itself.

    If the subtask is:
    a) too time consuming
    b) needs to generate events asynchronously
    it was split it to process and registered using zmq sockets.
    The obvious necessary sockets used are for input and output
    of the chatbot.
    """
    def __init__(self, input_port, output_port, name='ChatBot', logger=None):
        super(ChatBot, self).__init__()
        self.name = name
        # self.daemon = True

        self.input_port = input_port
        self.output_port = output_port

        if logger is None:
            self.should_run = lambda: True
            self.logger = get_chatbot_logger()
        else:
            self.logger = logger
        self.kb = kb.KnowledgeBase()
        self.kb.load_default_models()
        self.kb.add_triplets(data)

        self.state = dm.State(self.logger)
        self.policy = dm.RulebasedPolicy(self.kb, logger=self.logger)
        self.nlg = nlg.Nlg(logger)

        self.timeout = 0.2
        self.should_run = lambda: True
        self.send_msg = self.zmq_send
        self.receive_msg = self.zmq_receive

    def zmq_receive(self):
        # TODO use json validation
        socks = dict(self.poller.poll())
        if self.isocket in socks and socks[self.isocket] == zmq.POLLIN:
            msg = self.isocket.recv_json()
        return msg

    def zmq_send(self, utt):
        msg = {
            'time': time.time(),
            'user': self.__class__.__name__,
            'utterance': utt,
            }
        self.logger.info('Chatbot generated reply\n%s', msg)
        self.osocket.send_json(msg)

    def zmq_init(self):
        self.context = zmq.Context()
        self.isocket = self.context.socket(zmq.SUB)
        self.isocket.setsockopt(zmq.SUBSCRIBE, b'')
        self.osocket = self.context.socket(zmq.PUB)
        self.isocket.connect('tcp://localhost:%d' % self.input_port)
        self.osocket.connect('tcp://localhost:%d' % self.output_port)
        self.poller = zmq.Poller()
        self.poller.register(self.isocket, zmq.POLLIN)

    def run(self):
        self.zmq_init()
        self.chatbot_loop()

    def chatbot_loop(self):
        while self.should_run():
            msg = self.receive_msg()
            if 'user' not in msg or 'utterance' not in msg:
                self.logger.error('user is not in msg: skipping message')
                continue
            if msg['user'].startswith('human'):
                self.logger.info('Chatbot received message from human\n%s', msg)
                known_mentions, unknown_mentions = self.kb.parse_to_kb(msg['utterance'], self.kb)
                self.state.update_state(msg, known_mentions, unknown_mentions)
                self.logger.info('Generating reaction(s)')
                actions = self.policy.act(self.state, self.kb)
                start = time.time()
                while len(actions) > 0 and (time.time() - start) < self.timeout:
                    self.logger.debug(actions)
                    a = actions.pop(0)
                    # one may want to register other surface realisations than NLG
                    response = self.nlg.action2lang(a)
                    if response is None:
                        self.logger.debug('Action %s does not triggered response to user', a)
                    else:
                        self.logger.debug('Action %s triggered response %s', a, response)
                        self.send_msg(response)
            else:
                self.logger.error('Unrecognized user type')


if __name__ == '__main__':
    bot = ChatBot(input_port=-6, output_port=-66)

    def get_msg():
        utt = raw_input("Tell me\n")
        return { 'time': time.time(), 'user': 'human', 'utterance': utt}

    def send_msg(x):
        print('%s\n', x)

    bot.receive_msg = get_msg
    bot.send_msg = send_msg
    bot.chatbot_loop()

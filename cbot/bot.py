#!/usr/bin/env python
# encoding: utf-8
# from __future__ import unicode_literals
import multiprocessing
import os
import errno
import zmq.green as zmq
import time
import logging
from gevent import Greenlet
import uuid
from kb_data import data
import dm
import kb
import sys
import nlg


def get_chatbot_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    logger.addHandler(ch)
    return logger


class ChatBotConnector(Greenlet):

    def __init__(self, response_cb, input_port, output_port, logger=None):
        super(ChatBotConnector, self).__init__()

        self.context = zmq.Context()
        self.iresender = self.context.socket(zmq.PUSH)
        self.oresender = self.context.socket(zmq.PULL)
        self.iresender.connect('tcp://localhost:%s' % input_port)
        self.oresender.connect('tcp://localhost:%s' % output_port)
        self.poller = zmq.Poller()
        self.poller.register(self.oresender, zmq.POLLIN)
        self.id = uuid.uuid4()

        # if logger is None:
        dirname = os.path.dirname(os.path.abspath(__file__))
        logger = logging.getLogger(__name__)
        logdir = os.path.join(dirname, 'logs')
        try:
            os.mkdir(logdir)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise
        name = '%d_%d.log' % (time.time(), self.id)
        logger.setLevel(logging.DEBUG)
        ch = logging.FileHandler(os.path.join(logdir, name), mode='w', delay=True)
        logger.addHandler(ch)
        self.logger = logger

        self.response = response_cb
        self.should_run = True  # change is based on the messages

    def send(self, msg):
        msg['id'] = str(self.id)
        self.logger.info(msg)
        self.iresender.send_json(msg)

    def _run(self):
        while self.should_run:
            socks = dict(self.poller.poll())
            if self.oresender in socks and socks[self.oresender] == zmq.POLLIN:
                msg = self.oresender.recv_json()
                self.response(msg)
                self.logger.info(msg)

    def finalize(self, msg):
        self.should_run = False


class ChatBot(multiprocessing.Process):
    '''Chatbot class organise the communication between
    subtasks processes or implement easy subtask itself.

    If the subtask is:
    a) too time consuming
    b) needs to generate events asynchronously
    it was split it to process and registered using zmq sockets.
    The obvious necessary sockets used are for input and output
    of the chatbot.
    '''
    def __init__(self, input_port, output_port, name='ChatBot', logger=None):
        super(ChatBot, self).__init__()
        self.daemon = True

        self.input_port = input_port
        self.output_port = output_port

        self.should_run = lambda: True
        if logger is None:
            self.logger = get_chatbot_logger()
        else:
            self.logger = logger
        self.kb = kb.KnowledgeBase()
        self.kb.add_triplets(data)

        self.state = dm.State(self.logger)
        self.parse_to_kb = kb.parse_to_kb
        self.policy = dm.Policy(self.logger)
        self.nlg = nlg.Nlg(logger)


    def _after_fork_init(self):
        self.context = zmq.Context()
        self.isocket = self.context.socket(zmq.PULL)
        self.osocket = self.context.socket(zmq.PUSH)
        self.isocket.bind('tcp://*:%s' % self.input_port)
        self.osocket.bind('tcp://*:%s' % self.output_port)
        self.poller = zmq.Poller()
        self.poller.register(self.isocket, zmq.POLLIN)

    def _react(self):
        self.logger.info('Generating reaction(s)')
        actions = self.policy.choose_action(self.state.belief, self.kb, self.nlg)
        self.logger.debug(actions)
        for a in actions:
            self.state.change_state(a)
            response = self.nlg.action2lang(a)
            if response is None:
                self.logger.debug('Action %s does not triggered response to user', a)
            else:
                self.logger.debug('Action %s triggered response %s', a, response)
                self.send_utt(response)

    def run(self):
        self._after_fork_init()

        while self.should_run():
            socks = dict(self.poller.poll())
            if self.isocket in socks and socks[self.isocket] == zmq.POLLIN:
                msg = self.isocket.recv_json()
                # TODO use json validation
                if 'user' not in msg or 'utterance' not in msg:
                    self.logger.error('user is not in msg: skipping message')
                    continue
                if msg['user'].startswith('human'):
                    self.logger.info('Chatbot received message from human\n%s', msg)
                    annotation = self.parse_to_kb(msg['utterance'], self.kb)
                    self.state.update_state(msg, annotation)
                    self._react()
                elif msg['user'].startswith('state'):
                    self.logger.info('Chatbot received message from state changer\n%s' % msg)
                    self.state = self.update_state(msg)
                    self._react()
                else:
                    self.logger.error('Unrecognized user type')

    def send_utt(self, utt):
        msg = {
            'time': time.time(),
            'user': self.__class__.__name__,
            'utterance': utt,
            }
        self.logger.info('Chatbot generated reply\n%s', msg)
        self.osocket.send_json(msg)

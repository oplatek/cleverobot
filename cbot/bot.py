# from __future__ import unicode_literals
import multiprocessing
import zmq.green as zmq
import datetime
import logging
import time
import errno
import gevent
from gevent import Greenlet
import dm
import kb
import sys


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

        if logger is None:
            self.logger = get_chatbot_logger()
        else:
            self.logger = logger

        self.response = response_cb
        self.should_run = True # change is based on the messages


    def send(self, msg):
        self.logger.info('Sending msg to Chatbot: "%s"\n' % msg)
        self.iresender.send_json(msg)

    def _run(self):
        while self.should_run:
            socks = dict(self.poller.poll())
            if self.oresender in socks and socks[self.oresender] == zmq.POLLIN:
                msg = self.oresender.recv_json()
                self.response(msg)

    def finalize(self, msg):
        self.should_run = False


class ChatBot(multiprocessing.Process):
    '''Chatbot class organise the communication between
    subtasks processes or implement easy subtask itself.

    If the subtask is:
    a) too time consuming
    b) needs to generate events asynchronously
    it was splitted it to process and registered using zmq sockets.
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
        self.state = dm.State() 
        self.parse_to_kb = kb.parse_to_kb
        # TODO replace dummy lamda functions with something uselful
        self.update_state = lambda y, x: x
        self.decide_action = lambda x: x
        self.generate_utt = lambda x, kb: x


    def _after_fork_init(self):
        self.context = zmq.Context()
        self.isocket = self.context.socket(zmq.PULL)
        self.osocket = self.context.socket(zmq.PUSH)
        self.isocket.bind('tcp://*:%s' % self.input_port)
        self.osocket.bind('tcp://*:%s' % self.output_port)
        self.poller = zmq.Poller()
        self.poller.register(self.isocket, zmq.POLLIN)

    def run(self):
        self._after_fork_init()

        while self.should_run():
            socks = dict(self.poller.poll())
            if self.isocket in socks and socks[self.isocket] == zmq.POLLIN:
                response = None
                msg = self.isocket.recv_json()
                # TODO use json validation
                if 'user' not in msg or 'utterance' not in msg:
                    self.logger.error('user is not in msg: skipping message')
                    continue
                if msg['user'].startswith('human'):
                    self.logger.info('chatbot received message from human\n%s' % msg)
                    anotation = self.parse_to_kb(msg['utterance'], self.kb)
                    self.state = self.update_state(msg, anotation) 
                    action = self.decide_action(self.state)
                    response = self.generate_utt(action, self.kb)
                elif msg['user'].startswith('state'):
                    self.logger.info('chatbot received message from state changer\n%s' % msg)
                    self.state = self.kick_state(msg) 
                    action = self.decide_action(self.state)
                    response = self.generate_utt(action, self.kb)
                else:
                    self.logger.error('Unrecognized user type')
                self.logger.debug('Response: %s' % str(response))
                if response is not None:
                    self.send_utt(response)

    def send_utt(self, utt):
        msg = {
            'time': str(datetime.datetime.utcnow()),
            'user': self.__class__.__name__,
            'utterance': utt,
            }
        self.logger.info('Chatbot generated reply\n%s' % msg)
        self.osocket.send_json(msg)

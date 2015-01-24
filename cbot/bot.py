# from __future__ import unicode_literals
import multiprocessing
import zmq.green as zmq
import datetime
import logging
import time
import errno
import gevent
from gevent import Greenlet


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


        self.response = response_cb
        self.should_run = True # change is based on the messages


    def send(self, msg):
        print('Sending msg to Chatbot: "%s"\n' % msg)
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
    def __init__(self, input_port, output_port, name='ChatBot'):
        super(ChatBot, self).__init__()

        self.input_port = input_port
        self.output_port = output_port

        self.should_run = lambda: True

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
            # socks = dict(self.poller.poll())
            # if self.isocket in socks and socks[self.isocket] == zmq.POLLIN:
                # msg = self.isocket.recv_json()
            msg = self.isocket.recv_json()
            self.generate_utt(msg)

    def generate_utt(self, msg):
        assert isinstance(msg, dict)  # TODO validate json and return error msg
        self.send_utt('Hi %(user)s, you said "%(utterance)s, right?' % msg)

    def send_utt(self, utt):
        msg = {
            'time': str(datetime.datetime.utcnow()),
            'user': self.__class__.__name__,
            'utterance': utt,
            }
        print 'sending chatbot anwser'
        self.osocket.send_json(msg)

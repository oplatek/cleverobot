#!/usr/bin/env python
# encoding: utf-8
# from __future__ import unicode_literals
import multiprocessing
import os
import sys
import zmq.green as zmqg
import zmq
from zmq.devices import ProcessDevice
import time
import logging
from gevent import Greenlet
import uuid
from zmq.log.handlers import PUBHandler
from kb_data import data
import dm as dm
import cbot.kb as kb
import nlg


LOGGING_ADDRESS = 'tcp://127.0.0.1:6699'


def log_from_subscriber(sub):
    """
    :param sub:socket(zmq.SUB)
    :return:(str, str) logging.LEVEL, log message
    """
    level, msg = sub.recv_multipart()
    if msg.endswith('\n'):
        msg = msg[:-1]
    level = level.lower()
    logf = getattr(logging, level)
    logf(msg)


def log_loop(level=logging.DEBUG, address=LOGGING_ADDRESS, format='%(asctime)s %(message)s'):
    import zmq
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.bind(address)
    sub.setsockopt(zmq.SUBSCRIBE, b'')

    logging.basicConfig(level=level, format=format, filename='test_bot.log')
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(logging.Formatter(format))
    logging.getLogger('').addHandler(console)

    while True:
        log_from_subscriber(sub)


def connect_logger(context, name=None, address=LOGGING_ADDRESS):
    """
    Create logger for zmq.context() which need to taken from process of intended use.
    :return: logging.Logger
    """
    pub = context.socket(zmq.PUB)
    if name is None:
        name = __name__ + str(os.getpid())
    pub.connect(address)
    logger = logging.getLogger(name)
    handler = PUBHandler(pub)
    logger.addHandler(handler)
    # Let the logs be filter at the listener.
    logger.setLevel(logging.DEBUG)
    return logger


def forwarder_device_start(frontend_port, backend_port, logger=None):
    forwarder = ProcessDevice(zmq.FORWARDER, zmq.SUB, zmq.PUB)
    forwarder.setsockopt_in(zmq.SUBSCRIBE, b'')

    if logger is not None:
        logger.debug('forwarder binding in to tcp://*:%d', frontend_port)
        logger.debug('forwarder binding out to tcp://*:%d', backend_port)
    forwarder.bind_in("tcp://*:%d" % frontend_port)
    forwarder.bind_out("tcp://*:%d" % backend_port)

    forwarder.start()
    return forwarder


class ChatBotConnector(Greenlet):
    def __init__(self, response_cb, bot_front_port, bot_back_port,
                 user_front_port, user_back_port):
        super(ChatBotConnector, self).__init__()

        self.context = zmqg.Context()
        self.pub2bot = self.context.socket(zmq.PUB)
        self.sub2bot = self.context.socket(zmq.SUB)
        self.sub2bot.setsockopt(zmq.SUBSCRIBE, b'')
        self.pub2bot.connect('tcp://127.0.0.1:%d' % bot_front_port)
        self.sub2bot.connect('tcp://127.0.0.1:%d' % user_back_port)
        self.poller = zmqg.Poller()
        self.poller.register(self.sub2bot, zmq.POLLIN)
        self.id = uuid.uuid4()

        self.logger = connect_logger(self.context, self.__class__.__name__ + str(self.id))
        self.response = response_cb
        self.should_run = True  # change is based on the messages

        self.bot = ChatBot(bot_back_port, user_front_port)
        self.bot.start()
        print 'bot started'

    def send(self, msg):
        msg['id'] = str(self.id)
        self.logger.debug('chatbotconnector %s', msg)
        self.pub2bot.send_json(msg)

    def _run(self):
        self.logger.debug('connector run started')
        try:
            while self.should_run:
                self.logger.debug('CONNECTOR BEFORE POLL')
                socks = dict(self.poller.poll())
                self.logger.debug('CONNECTOR AFTER POLL')
                if self.sub2bot in socks and socks[self.sub2bot] == zmq.POLLIN:
                    msg = self.sub2bot.recv_json()
                    self.logger.debug('ChatBotConnector received bot msg %s' % msg)
                    self.response(msg)
        finally:
            self.logger.debug("ChatbotConnector finished")
            self.bot.terminate()

    def finalize(self, msg):
        # TODO set up control socket and use it in the poller to interrupt the loop
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

    def __init__(self, input_port, output_port, name='ChatBot'):
        super(ChatBot, self).__init__()
        self.name = name

        self.input_port = input_port
        self.output_port = output_port

        self.timeout = 0.2
        self.should_run = lambda: True
        self.send_msg = self.zmq_send
        self.receive_msg = self.zmq_receive

        self.state = dm.State()

        print 'ChatBot initiated partially see Process run method'
        self.logger, self.kb, self.policy, self.nlg = None, None, None, None

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
        self.logger.debug('Chatbot generated reply\n%s', msg)
        self.osocket.send_json(msg)

    def zmq_init(self):
        self.context = zmq.Context()
        self.isocket = self.context.socket(zmq.SUB)
        self.isocket.setsockopt(zmq.SUBSCRIBE, b'')
        self.osocket = self.context.socket(zmq.PUB)
        self.isocket.connect('tcp://127.0.0.1:%d' % self.input_port)
        self.osocket.connect('tcp://127.0.0.1:%d' % self.output_port)
        self.poller = zmq.Poller()
        self.poller.register(self.isocket, zmq.POLLIN)

    def run(self):
        self.zmq_init()
        self.logger = connect_logger(self.context, self.__class__.__name__ + str(self.name))

        self.logger.debug('Runs with input_port: %d' % self.input_port)
        self.logger.debug('Runs with output_port: %d' % self.output_port)

        self.kb = kb.KnowledgeBase()
        self.kb.load_default_models()
        self.kb.add_triplets(data)
        self.logger.debug('KB loaded')

        self.policy = dm.RulebasedPolicy(self.kb, self.logger)
        self.nlg = nlg.Nlg(self.logger)
        self.logger.debug('All components initiated')

        self.chatbot_loop()

    def chatbot_loop(self):
        self.logger.debug('entering loop')
        while self.should_run():
            self.logger.debug('Chatbot BEFORE POLL')
            msg = self.receive_msg()
            self.logger.debug('Chatbot AFTER POLL')
            if 'user' not in msg or 'utterance' not in msg:
                self.logger.error('user is not in msg: skipping message')
                continue
            if msg['user'].startswith('human'):
                self.logger.info('Chatbot received message from human\n%s', msg)
                known_mentions, unknown_mentions = self.kb.parse_to_kb(msg['utterance'], self.kb)
                self.state.update_state(msg, known_mentions, unknown_mentions)
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
        return {'time': time.time(), 'user': 'human', 'utterance': utt}

    def send_msg(x):
        print('%s\n', x)

    bot.receive_msg = get_msg
    bot.send_msg = send_msg
    bot.chatbot_loop()

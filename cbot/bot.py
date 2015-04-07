#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals
import multiprocessing
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
import cbot.nlg as nlg
from zmq.utils import jsonapi
import os
import errno


LOGGING_ADDRESS = 'tcp://127.0.0.1:6699'


def topic_msg_to_json(topic_msg):
    json0 = topic_msg.find('{')
    topic = topic_msg[0:json0].strip()
    msg = jsonapi.loads(topic_msg[json0:])
    return topic, msg


def create_local_logging_handler(name):
    dir_name = os.path.dirname(os.path.abspath(__file__))
    logger = logging.getLogger(__name__)
    log_dir = os.path.join(dir_name, 'logs')
    try:
        os.mkdir(log_dir)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise
    logger.setLevel(logging.DEBUG)
    h = logging.FileHandler(os.path.join(log_dir, name + '.log'), mode='w', delay=True)
    h.setLevel(logging.INFO)
    return h


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


def log_loop(level=logging.DEBUG, address=LOGGING_ADDRESS, log_form='%(asctime)s %(message)s',log_name='common.log'):
    import zmq
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.bind(address)
    sub.setsockopt_string(zmq.SUBSCRIBE, '')

    # TODO refactor all related logging functions to logging module
    logging.basicConfig(level=level, format=log_form, filename=log_name)  # TODO rotating handler
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(logging.Formatter(log_form))
    logging.getLogger('').addHandler(console)

    while True:
        log_from_subscriber(sub)


def connect_logger(logger, context, address=LOGGING_ADDRESS):
    """
    Create logger for zmq.context() which need to taken from process of intended use.
    :return: logging.Logger
    """
    pub = context.socket(zmq.PUB)
    pub.connect(address)
    handler = PUBHandler(pub)
    PUBHandler.formatters[logging.DEBUG] = logging.Formatter(
        "%(levelname)s %(filename)s:%(lineno)d %(funcName)s:\n\t%(message)s\n")
    logger.addHandler(handler)
    
    # Let the logs be filter at the listener.
    logger.setLevel(logging.DEBUG)


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
                 user_front_port, user_back_port, ctx=None):
        super(ChatBotConnector, self).__init__()
        if ctx is not None:
            self.context = ctx
        else:
            self.context = zmqg.Context()
        self.pub2bot = self.context.socket(zmq.PUB)
        self.sub2bot = self.context.socket(zmq.SUB)
        self.id = uuid.uuid4()
        self.sub2bot.setsockopt_string(zmq.SUBSCRIBE, '%s' % self.id)
        self.pub2bot.connect('tcp://127.0.0.1:%d' % bot_front_port)
        self.sub2bot.connect('tcp://127.0.0.1:%d' % user_back_port)
        self.poller = zmqg.Poller()
        self.poller.register(self.sub2bot, zmq.POLLIN)

        self.logger = logging.getLogger(self.__class__.__name__ + str(self.id))
        connect_logger(self.logger, self.context)
        self.response = response_cb
        self.should_run = True  # change is based on the messages

        self.bot = ChatBot(bot_back_port, user_front_port, str(self.id))
        self.bot.start()

    def send(self, msg):
        msg['user'] = 'human'
        msg['time'] = time.time()
        msg['session'] = str(self.id)
        self.logger.debug('ChatBotConnector %s', msg)
        self.pub2bot.send_string('%s %s' % (self.id, jsonapi.dumps(msg)))

    def _run(self):
        self.logger.debug('connector run started')
        try:
            while self.should_run:
                self.logger.debug('ChatBotConnector before poll')
                socks = dict(self.poller.poll())
                self.logger.debug('ChatBotConnector after poll')
                if self.sub2bot in socks and socks[self.sub2bot] == zmq.POLLIN:
                    _, msg = topic_msg_to_json(self.sub2bot.recv())
                    self.logger.debug('ChatBotConnector %s received bot msg %s', self.id, msg)
                    self.response(msg, self.id)
        finally:
            self.pub2bot.send_string('die die')
            self.bot.terminate()
            self.logger.debug("ChatBotConnector finished")

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

    def __init__(self, input_port, output_port, name):
        super(ChatBot, self).__init__()
        self.name = name

        self.input_port = input_port
        self.output_port = output_port

        self.timeout = 0.2
        self.should_run = True

        self.state = dm.State()

        self.logger, self.kb, self.policy, self.nlg = None, None, None, None

    def receive_msg(self):
        # TODO use json validation
        socks = dict(self.poller.poll())
        # Normal conversation
        if self.isocket in socks and socks[self.isocket] == zmq.POLLIN:
            _, msg = topic_msg_to_json(self.isocket.recv())
            self.logger.info('%s,', jsonapi.dumps(msg))

            # hacks TODO move to hancrafted - control policy
            if msg['utterance'].lower() == 'your id' or msg['utterance'].lower() == 'your id, please!':
                self.send_msg(self.name)
                return None
            self.logger.debug('len(history) %d' % len(self.state.history))
            if len(self.state.history) == 16:
                self.send_msg("Thanks for chatting with me! Finally someone talkative.")
            return msg
        else:  # Hacks
            if self.godot in socks and socks[self.godot] == zmq.POLLIN:
                self.should_run = False
            if self.req_stat in socks and socks[self.req_stat] == zmq.POLLIN:
                _, stat_req = self.req_stat.recv().split()
                assert stat_req == 'request', 'stat_req %s' % stat_req
                stats = {
                    'time': time.time(),
                    'history_len': len(self.state.history)
                }
                self.logger.debug('ChatBot %s received stats request', self.name)
                self.osocket.send_string('stat_%s %s' % (self.name, jsonapi.dumps(stats)))
            return None

    def send_msg(self, utt):
        msg = {
            'utterance': utt,
            'time': time.time(),
            'user': self.__class__.__name__,
            'session': self.name,
        }
        self.logger.info('%s,', jsonapi.dumps(msg))
        self.osocket.send_string('%s %s' % (self.name, jsonapi.dumps(msg)))

    def zmq_init(self):
        self.context = zmq.Context()
        self.isocket = self.context.socket(zmq.SUB)
        self.isocket.setsockopt_string(zmq.SUBSCRIBE, '%s' % self.name)
        self.osocket = self.context.socket(zmq.PUB)
        self.req_stat = self.context.socket(zmq.SUB)
        self.req_stat.setsockopt_string(zmq.SUBSCRIBE, 'stat_%s' % self.name)
        self.godot = self.context.socket(zmq.SUB)
        self.godot.setsockopt_string(zmq.SUBSCRIBE, 'die')
        self.isocket.connect('tcp://127.0.0.1:%d' % self.input_port)
        self.req_stat.connect('tcp://127.0.0.1:%d' % self.input_port)
        self.osocket.connect('tcp://127.0.0.1:%d' % self.output_port)
        self.poller = zmq.Poller()
        self.poller.register(self.isocket, zmq.POLLIN)
        self.poller.register(self.req_stat, zmq.POLLIN)

    def run(self):
        self.zmq_init()
        self.logger = logging.getLogger(self.__class__.__name__ + str(self.name))
        self.logger.addHandler(create_local_logging_handler('%s_%s' % (time.time(), self.name)))
        connect_logger(self.logger, self.context)

        self.logger.debug('Runs with input_port: %d, output_port %d' % (self.input_port, self.output_port))

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
        while self.should_run:
            msg = self.receive_msg()
            if msg is None:
                continue

            known_mentions, unknown_mentions = self.kb.parse_to_kb(msg['utterance'], self.kb)
            self.state.history.append(self.state.belief)
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

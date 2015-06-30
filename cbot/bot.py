#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals
import multiprocessing
import time
import logging
import uuid
import os
import errno

import zmq.green as zmqg
import zmq
from zmq.devices import ProcessDevice
from gevent import Greenlet
from zmq.log.handlers import PUBHandler
from zmq.utils import jsonapi

from cbot.kb.kb_data import data
from cbot.dm.state import SimpleTurnState, Utterance
from cbot.dm.policy import RuleBasedPolicy
import cbot.kb as kb
from cbot.lu.pos import PerceptronTagger


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
        name = str(int(uuid.uuid4()))
        self.pub2bot = self.context.socket(zmq.PUB)
        self.pub2bot.sndhwm = 1100000  # set SNDHWM, so we don't drop messages for slow subscribers
        self.sub2bot = self.context.socket(zmq.SUB)
        self.sub2bot.setsockopt_string(zmq.SUBSCRIBE, '%s' % name)
        self.init_sync_signal = self.context.socket(zmq.SUB)
        self.init_sync_signal.setsockopt_string(zmq.SUBSCRIBE, 'init_sync_%s' % name)
        self.poller = zmqg.Poller()
        self.poller.register(self.sub2bot, zmq.POLLIN)
        self.poller.register(self.init_sync_signal, zmq.POLLIN)
        self.pub2bot.connect('tcp://127.0.0.1:%d' % bot_front_port)
        self.sub2bot.connect('tcp://127.0.0.1:%d' % user_back_port)
        self.init_sync_signal.connect('tcp://127.0.0.1:%d' % user_back_port)

        self.logger = logging.getLogger(self.__class__.__name__ + str(name))
        connect_logger(self.logger, self.context)
        self.response = response_cb
        self.should_run = lambda: True  # change is based on the messages

        self.bot = ChatBot(name, bot_back_port, user_front_port)
        self.bot.start() # TODO should I move it to _run()
        if self._init_handshake():
            self.logger.debug('Connector2bot synchronised with ChatBot.')
        else:
            self.finalize()

    def _init_handshake(self, num_handshakes=10, interval=10):
        waiting_time = 0
        for i in range(num_handshakes):
            init_msg = 'init_sync_%s probing connection' % self.name
            self.logger.debug('cbc sending msg: %s' % init_msg)
            self.pub2bot.send_string(init_msg)
            socks = dict(self.poller.poll(timeout=interval))
            if self.init_sync_signal in socks and socks[self.init_sync_signal] == zmq.POLLIN:
                self.init_sync_signal.recv()
                self.logger.debug('init handshake successful after %d ms' % waiting_time)
                return True
            waiting_time += interval
        self.logger.debug('init handshake unsuccessful after %d ms' % waiting_time)
        return False

    @property
    def name(self):
        return self.bot.name

    def send(self, msg):
        assert 'utterance' in msg
        msg['user'] = 'human'
        msg['time'] = time.time()
        msg['session'] = self.name
        self.logger.debug('ChatBotConnector %s', msg)
        self.pub2bot.send_string('%s %s' % (self.name, jsonapi.dumps(msg)))

    def _run(self):
        self.logger.debug('%s started listening for ChatBot msgs ' % str(self.__class__.__name__) + self.name)
        try:
            while self.should_run():
                self.logger.debug('ChatBotConnector before poll')
                socks = dict(self.poller.poll())
                self.logger.debug('ChatBotConnector after poll')
                if self.sub2bot in socks and socks[self.sub2bot] == zmq.POLLIN:
                    _, msg = topic_msg_to_json(self.sub2bot.recv())
                    self.logger.debug('ChatBotConnector %s received bot msg %s', self.name, msg)
                    self.response(msg, self.name)
        except Exception as e:
            self.logger.exception(e)
        finally:
            self.finalize()

    def finalize(self):
        self.should_run = lambda: False
        self.pub2bot.send_string('die_%s die' % self.name)
        self.bot.terminate()
        self.logger.debug("ChatBotConnector finished")


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

    def __init__(self, name, input_port, output_port):
        super(self.__class__, self).__init__()
        self.name = str(int(name))
        assert isinstance(input_port, int) and isinstance(output_port, int)
        self.input_port, self.output_port = input_port, output_port

        self.should_run = lambda: True
        self.logger, self.kb, self.policy = None, None, None

    def __repr__(self):
        super_info = super(self.__class__).__str__()
        str_repr = '%s: %s' % (str(self.__class__), self.name)
        str_repr += '\n input - output ports: %d - %d\n' % (self.input_port, self.output_port)
        str_repr += super_info
        return str_repr

    def receive_msg(self):
        # TODO use json validation
        socks = dict(self.poller.poll())
        # Normal conversation
        if self.isocket in socks and socks[self.isocket] == zmq.POLLIN:
            _, msg = topic_msg_to_json(self.isocket.recv())
            self.logger.info('%s,', jsonapi.dumps(msg))
            # hack - control signal from user
            if msg['utterance'].lower() == 'your id' or msg['utterance'].lower() == 'your id, please!':
                self.send_msg(self.name)
                return None
            return msg
        # Control signals
        if self.die_signal in socks and socks[self.die_signal] == zmq.POLLIN:
            self.should_run = lambda: False
            self.die_signal.recv()
        if self.init_sync_signal in socks and socks[self.init_sync_signal] == zmq.POLLIN:
            self.init_sync_signal.recv()
            self.logger.debug('Sync_init msg received. Sending confirmation.')
            self.osocket.send_string('init_sync_%s sync_confirmation' % self.name)
        if self.req_stat in socks and socks[self.req_stat] == zmq.POLLIN:
            _, stat_req = self.req_stat.recv().split()
            assert stat_req == 'request', 'stat_req %s' % stat_req
            self.logger.debug('ChatBot %s received stats request', self.name)
            stats = {'time': time.time(), 'history_len': len(self.policy.state.history)}
            self.osocket.send_string('stat_%s %s' % (self.name, jsonapi.dumps(stats)))
        return None

    def send_msg(self, utt):
        if utt is not None:
            msg = {
                'utterance': utt,
                'time': time.time(),
                'user': self.__class__.__name__,
                'session': self.name,
            }
            self.logger.info('ChatBot %s,', jsonapi.dumps(msg))
            self.osocket.send_string('%s %s' % (self.name, jsonapi.dumps(msg)))

    def zmq_init(self):
        self.context = zmq.Context()
        self.isocket = self.context.socket(zmq.SUB)
        self.isocket.setsockopt_string(zmq.SUBSCRIBE, '%s' % self.name)
        self.osocket = self.context.socket(zmq.PUB)
        self.req_stat = self.context.socket(zmq.SUB)
        self.req_stat.setsockopt_string(zmq.SUBSCRIBE, 'stat_%s' % self.name)
        self.die_signal = self.context.socket(zmq.SUB)
        self.die_signal.setsockopt_string(zmq.SUBSCRIBE, 'die_%s' % self.name)
        self.init_sync_signal = self.context.socket(zmq.SUB)
        self.init_sync_signal.setsockopt_string(zmq.SUBSCRIBE, 'init_sync_%s' % self.name)
        self.isocket.connect('tcp://127.0.0.1:%d' % self.input_port)
        self.req_stat.connect('tcp://127.0.0.1:%d' % self.input_port)
        self.init_sync_signal.connect('tcp://127.0.0.1:%d' % self.input_port)
        self.die_signal.connect('tcp://127.0.0.1:%d' % self.input_port)
        self.osocket.connect('tcp://127.0.0.1:%d' % self.output_port)
        self.poller = zmq.Poller()
        self.poller.register(self.isocket, zmq.POLLIN)
        self.poller.register(self.req_stat, zmq.POLLIN)
        self.poller.register(self.init_sync_signal, zmq.POLLIN)
        self.poller.register(self.die_signal, zmq.POLLIN)

    def single_process_init(self):
        self.logger = logging.getLogger(self.__class__.__name__ + str(self.name))
        self.logger.addHandler(create_local_logging_handler('%s_%s' % (time.time(), self.name)))

        self.kb = kb.KnowledgeBase()
        self.kb.load_default_models()
        self.kb.add_triplets(data)

        dat_trans_prob = None  # TODO load transition probabilities, update them online for well accepted dialogues
        self.policy = RuleBasedPolicy(self.kb, SimpleTurnState(dat_trans_prob))

    def run(self):
        self.single_process_init()
        self.logger.debug('Starting zmq_init synchronisation.')
        self.zmq_init()
        self.logger.debug('Connect zmq logger')
        connect_logger(self.logger, self.context)
        self.logger.debug('Chatbot properties:\n%s' % str(self))
        self.chatbot_loop()

    def chatbot_loop(self):
        self.logger.info('Entering ChatBot loop: waiting for user input')
        while self.should_run():
            msg = self.receive_msg()
            if msg is None:
                continue
            self.policy.update_state(Utterance(msg['utterance']))
            response = self.policy.act()
            self.send_msg(response)


if __name__ == '__main__':
    """Chatbot demo without zmq and multiprocessing."""
    bot = ChatBot(name=str(123), input_port=-6, output_port=-66)

    def get_msg():
        utt = raw_input("Tell me\n")
        return {'time': time.time(), 'user': 'human', 'utterance': utt}

    def send_msg(x):
        print('%s\n', x)

    bot.receive_msg = get_msg
    bot.send_msg = send_msg
    bot.single_process_init()
    bot.chatbot_loop()

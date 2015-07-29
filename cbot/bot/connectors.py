#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals
from greenlet import GreenletExit
import multiprocessing
import time
import logging
from cbot.bot.alias import BELIEF_STATE, SYSTEM, HUMAN
import cbot.bot.log as cblog
import uuid

import zmq.green as zmqg
import zmq
from zmq.devices import ProcessDevice
from gevent import Greenlet
from zmq.utils import jsonapi

from cbot.kb.kb_data import data
from cbot.dm.state import SimpleTurnState, Utterance
from cbot.dm.policy import RuleBasedPolicy
import cbot.kb as kb
from gevent.event import AsyncResult


class ChatBot(object):
    def __init__(self, name, send_reply):
        self.send_reply = send_reply
        self.name = str(name)

        self.logger = logging.getLogger(str(self.name))
        name = '%s_%s' % (time.time(), self.name)
        self.logger.addHandler(cblog.create_local_logging_handler(name, suffix='dm_logic', log_level=logging.INFO))
        self.logger.addHandler(
            cblog.create_local_logging_handler(name, suffix='input_output', log_level=logging.WARNING))

        self.kb = kb.KnowledgeBase()
        self.kb.load_default_models()
        self.kb.add_triplets(data)

        dat_trans_prob = None  # TODO load transition probabilities, update them online for well accepted dialogues
        self.policy = RuleBasedPolicy(self.kb, SimpleTurnState(dat_trans_prob))

    def receive_msg(self, msg):
        # TODO use gevent.AsyncResult to make it asynchronous
        assert msg is not None and 'utterance' in msg and 'name' in msg, 'Broken msg: %s' % msg
        self.logger.warning('%s', jsonapi.dumps(msg))

        self.policy.update_state(Utterance(msg['utterance']))
        response = self.policy.act()
        self.logger.info(self.policy.state)

        # TODO REMOVE DUPLICATE name and user
        m = {'utterance': response,
             'time': time.time(),
             'user': SYSTEM,
             'name': SYSTEM,
             'session': self.name, }
        self.send_reply(m)
        self.logger.warning('%s', jsonapi.dumps(m))


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
        cblog.connect_logger(self.logger, self.context)
        self.bot = ChatBotProcess(name, bot_back_port, user_front_port)
        self.bot.start()

        self.response = response_cb
        self.should_run = lambda: True  # change is based on the messages
        self.initialized = AsyncResult()

        if self._init_handshake():
            self.logger.debug('Connector2bot synchronised with ChatBot.')
            self.initialized.set(True)
        else:
            self.initialized.set(False)
            self.finalize()

    def _init_handshake(self, num_handshakes=10, interval=10):
        waiting_time = 0
        for _ in range(num_handshakes):
            init_msg = 'init_sync_%s probing connection' % self.name
            self.logger.debug('cbc sending msg: %s', init_msg)
            self.pub2bot.send_string(init_msg)
            socks = dict(self.poller.poll(timeout=interval))
            if self.init_sync_signal in socks and socks[self.init_sync_signal] == zmq.POLLIN:
                self.init_sync_signal.recv()
                self.logger.debug('init handshake successful after %d ms', waiting_time)
                return True
            waiting_time += interval
        self.logger.debug('init handshake unsuccessful after %d ms', waiting_time)
        return False

    @property
    def name(self):
        return self.bot.name

    def send(self, msg):
        assert self.initialized.get()  # May block if not initialized
        assert 'utterance' in msg
        msg['user'] = 'human'
        msg['time'] = time.time()
        msg['session'] = self.name
        self.logger.debug('send(): %s', msg)
        self.pub2bot.send_string('%s %s' % (self.name, jsonapi.dumps(msg)))

    def _run(self):
        self.logger.debug('%s started listening for ChatBot msgs ' % str(self.__class__.__name__) + self.name)
        try:
            while self.should_run():
                assert self.initialized.get()
                self.logger.debug('before poll')
                socks = dict(self.poller.poll())
                self.logger.debug('after poll')
                if self.sub2bot in socks and socks[self.sub2bot] == zmq.POLLIN:
                    _, msg = cblog.topic_msg_to_json(self.sub2bot.recv())
                    self.logger.debug('_run(): %s', self.name, msg)
                    self.response(msg, self.name)
        except Exception as e:
            self.logger.exception(e)
        finally:
            self.finalize()

    def finalize(self):
        self.logger.debug("Finishing ChatBotConnector")
        self.initialized.set(False)
        self.should_run = lambda: False
        self.pub2bot.send_string('die_%s die' % self.name)
        self.bot.terminate()

    def kill(self, exception=GreenletExit, block=True, timeout=None):
        self.finalize()
        super(ChatBotConnector, self).kill(exception=exception, block=block, timeout=timeout)


class ChatBotProcess(multiprocessing.Process):
    def __init__(self, name, input_port, output_port):
        super(self.__class__, self).__init__()
        self.name = str(int(name))
        assert isinstance(input_port, int) and isinstance(output_port, int)
        self.input_port, self.output_port = input_port, output_port
        self.logger = logging.getLogger(str(name))
        self.should_run = lambda: True

    def __repr__(self):
        super_info = super(self.__class__).__str__()
        str_repr = '%s: %s' % (str(self.__class__), self.name)
        str_repr += '\n input - output ports: %d - %d\n' % (self.input_port, self.output_port)
        str_repr += super_info
        return str_repr

    def receive_msg(self, chatbot):
        # TODO use json validation
        socks = dict(self.poller.poll())
        # Normal conversation
        if self.isocket in socks and socks[self.isocket] == zmq.POLLIN:
            _, msg = cblog.topic_msg_to_json(self.isocket.recv())
            # hack - control signal from user
            if msg['utterance'].lower() == 'your id' or msg['utterance'].lower() == 'your id, please!':
                self.osocket.send_string('%s %s' % (self.name, jsonapi.dumps(cblog.wrap_msg(self.name))))
            else:
                if 'name' not in msg and 'user' in msg:
                    msg['name'] = msg['user']  # TODO HACK for backward compatibility
                chatbot.receive_msg(msg)  # Normal conversation
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

    def send_msg(self, msg):
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

    def run(self):
        self.logger = logging.getLogger(str(self.name))  # reinitializing after fork
        chatbot = ChatBot(self.name, self.send_msg)
        self.logger.debug('Starting zmq_init synchronisation.')
        self.zmq_init()
        self.logger.debug('Connect zmq logger')
        cblog.connect_logger(self.logger, self.context)
        self.logger.debug(str(self))
        while self.should_run():
            self.receive_msg(chatbot)


if __name__ == '__main__':
    print("""ChatBot demo without zmq and multiprocessing.""")


    def send_msg(x):
        print('Bot > %s\n' % x)


    def get_msg():
        utt = raw_input("\nYou > ")
        return {'time': time.time(), 'name': HUMAN, 'utterance': utt}


    cb = ChatBot("Command line bot", send_msg)
    msg = {'utterance': None, 'name': None, 'time': None}

    while msg['utterance'] != 'end':
        msg = get_msg()
        cb.receive_msg(msg)

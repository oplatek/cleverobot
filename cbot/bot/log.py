from __future__ import unicode_literals, division
import json
import time
import os
import errno
from zmq.log.handlers import PUBHandler
from zmq.utils import jsonapi
import logging
import zmq
from cbot.bot.alias import LOGGING_ADDRESS
from cbot.dm.actions import BaseAction


class ChatBotJsonEncoder(json.JSONEncoder):
    def encode(self, obj):

        def flatten(d):
            # flat dictionaries
            if isinstance(d, dict):
                if len(d) == 0:
                    return "EmptyDict"
                d = dict(d)  # copy
                non_str_keys = [k for k in d if not (isinstance(k, str) or isinstance(k, unicode))]
                for k in non_str_keys:
                    v = d[k]
                    del d[k]
                    d[str(k)] = v
                for k, v in d.iteritems():
                    d[k] = flatten(v)
                return d
            elif isinstance(d, BaseAction):
                return repr(d)
            else:
                return d

        flat_obj = flatten(obj)
        return super(self.__class__, self).encode(flat_obj)


def wrap_msg(utt):
    return {'time': time.time(), 'user': 'human', 'utterance': utt}


def topic_msg_to_json(topic_msg):
    json0 = topic_msg.find('{')
    topic = topic_msg[0:json0].strip()
    msg = jsonapi.loads(topic_msg[json0:])
    return topic, msg


def create_local_logging_handler(name, log_level=logging.WARNING, suffix="input_output"):
    dir_name = os.path.dirname(os.path.abspath(__file__))
    logger = logging.getLogger(__name__)
    log_dir = os.path.join(dir_name, 'logs')
    try:
        os.mkdir(log_dir)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise
    logger.setLevel(logging.DEBUG)
    h = logging.FileHandler(os.path.join(log_dir, '%s_%s.log' % (name, suffix)), mode='w', delay=True)
    h.setLevel(log_level)
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
    f = logging.Formatter("%(levelname)s %(filename)s:%(lineno)d %(funcName)s:\n\t%(message)s\n")
    # FIXME hack -> rewrite nicely
    PUBHandler.formatters[logging.DEBUG] = f
    PUBHandler.formatters[logging.WARNING] = f
    PUBHandler.formatters[logging.INFO] = f
    logger.addHandler(handler)

    # Let the logs be filter at the listener.
    logger.setLevel(logging.DEBUG)

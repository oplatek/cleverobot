from __future__ import unicode_literals, division
import json
from logging.handlers import TimedRotatingFileHandler
import time
import os
import errno
from zmq.log.handlers import PUBHandler
from zmq.utils import jsonapi
import logging
from logging.config import dictConfig
import zmq
from cbot.bot.alias import LOGGING_ADDRESS, HUMAN, BASIC_JSON_MSG_SCHEMA, CHATBOT_MSG_LOGGER
from cbot.dm.actions import BaseAction
import jsonschema
from jsonschema.exceptions import ValidationError


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


def setup_logging(config_path, default_level=logging.INFO):
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
            dictConfig(config)
    else:
        logging.basicConfig(level=default_level)


def wrap_msg(utt, user=HUMAN):
    return {'time': time.time(), 'name': user, 'user': user, 'utterance': utt}


def topic_msg_to_json(topic_msg):
    json0 = topic_msg.find('{')
    topic = topic_msg[0:json0].strip()
    msg = jsonapi.loads(topic_msg[json0:])
    return topic, msg


def log_from_subscriber(sub, logger):
    level, msg = sub.recv_multipart()
    level, msg = level.lower(), msg.strip()
    try:
        jsonschema.validate(msg, BASIC_JSON_MSG_SCHEMA)
        d = json.loads(msg)

        adapter = SessionAdapter(logging.getLogger(__name__), d)
        log_adapter = getattr(adapter, level)
        log_adapter(msg)

        logger_sess_handler = getattr(logger, level)
        logger_sess_handler(msg)

    except (ValidationError, ValueError) as e:
        logging.critical('level: %s; msg: %s', level, str(msg))
        logging.exception(e)
        print msg
        raise e


class SessionAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return '[%s %s]\n%s' % (self.extra['session'], self.extra['name'], msg), kwargs


class SessionHandler(logging.Handler):
    def __init__(self, dir_name=os.path.dirname(os.path.abspath(__file__))):
        super(self.__class__, self).__init__()
        self.log_dir = os.path.join(dir_name, 'logs')
        try:
            os.mkdir(self.log_dir)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise

    def emit(self, record):
        try:
            msg = json.loads(record.msg)
            if getattr(logging, record.levelname) == logging.INFO:
                log_file = msg['session'] + 'dm_logic.log'
            elif getattr(logging, record.levelname) == logging.WARNING:
                log_file = msg['session'] + 'input_output.log'
            else:
                raise ValueError("Unsupported logging level for ChatBot msgs!")
            with open(os.path.join(self.log_dir, log_file), 'a') as w:
                w.write(record.msg + '\n')
                w.flush()
        except Exception as e:
            logging.exception(e)


def chatbot2file_log_loop(address=LOGGING_ADDRESS, log_name='all_messages_cbot_msg.log'):
    logger = logging.getLogger(__name__ + '.' + CHATBOT_MSG_LOGGER)
    ctx = zmq.Context()
    sub = ctx.socket(zmq.SUB)
    sub.bind(address)
    sub.setsockopt_string(zmq.SUBSCRIBE, '')

    fh = TimedRotatingFileHandler(log_name, when='W0', interval=1)
    logger.addHandler(fh)
    logger.addHandler(SessionHandler())
    logger.setLevel(logging.DEBUG)

    while True:
        log_from_subscriber(sub, logger)


class ChatBotPUBHandler(PUBHandler):
    def __init__(self, publish_socket, session):
        super(self.__class__, self).__init__(publish_socket)
        self.session = session

    def emit(self, record):
        jsonschema.validate(record.msg, BASIC_JSON_MSG_SCHEMA)
        msg = json.loads(record.msg)
        if 'session' not in msg:
            msg['session'] = self.session
        record.msg = json.dumps(msg, sort_keys=True, indent=4, separators=(',', ': '))
        super(self.__class__, self).emit(record)


def connect_logger(logger_name, session_name, context, address=LOGGING_ADDRESS):
    logger = logging.getLogger(logger_name)
    pub = context.socket(zmq.PUB)
    pub.connect(address)
    handler = ChatBotPUBHandler(pub, session_name)
    f = logging.Formatter("%(message)s\n")
    # special logic for ChatBot TODO define my own logging levels
    PUBHandler.formatters[logging.DEBUG] = f
    PUBHandler.formatters[logging.WARNING] = f
    PUBHandler.formatters[logging.INFO] = f
    logger.addHandler(handler)

    logger.setLevel(logging.DEBUG)  # filtering will be done at the listener side

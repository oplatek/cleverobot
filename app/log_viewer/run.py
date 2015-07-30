#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals, division
import argparse
from collections import defaultdict, OrderedDict
from itertools import izip_longest
import json
import logging
import os
from datetime import datetime
from zmq.utils import jsonapi
from app.cleverobot.run import start_zmq_and_log_processes, shut_down
import zmq.green as zmqg
from flask import Flask, render_template, request, Response, stream_with_context
import functools
import cbot
from cbot.bot.connectors import ChatBotConnector
from cbot.bot.log import wrap_msg, topic_msg_to_json, setup_logging
from cbot.bot.alias import HUMAN, BELIEF_STATE, SYSTEM, REPLAYED, BELIEF_STATE_REPLAY, LOGGING_ADDRESS
from gevent.queue import Queue, Empty

app = Flask(__name__)
app.secret_key = 12345  # TODO
root = os.path.realpath(os.path.join(os.path.dirname(__file__), '../../cbot/bot/logs'))
log_name = 'logs.cleverobot.log'
log_config = os.path.realpath(os.path.join(os.path.dirname(cbot.__file__), 'logging.json'))
bot_input, bot_output = 6665, 7776
user_input, user_output = 8887, 9998
host, port = '0.0.0.0', 4000
ctx = zmqg.Context()

FLAT_EMPTY_TURN = OrderedDict([(k, None) for k in [HUMAN, SYSTEM, BELIEF_STATE]])
PICK_VALUES_TURN = {BELIEF_STATE: 'attributes', SYSTEM: 'utterance', HUMAN: 'utterance'}
EXTENDED_VALUES_TURN = [HUMAN, SYSTEM, BELIEF_STATE, REPLAYED, BELIEF_STATE_REPLAY]
EXTENDED_VALUES_TURN = OrderedDict([(k, k.replace('_', ' ').capitalize()) for k in EXTENDED_VALUES_TURN])


def normalize_path(path):
    abs_path = os.path.realpath(os.path.join(root, path))
    if os.path.commonprefix([abs_path, root]) != root:
        raise KeyError("Invalid argument: do not try to access files above the root.")
    return abs_path


def with_path(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        werkzeug_logger = logging.getLogger('werkzeug')
        try:
            if 'path' not in request.args:
                rp = root
            else:
                rp = request.args.get('path')
            werkzeug_logger.info("Requested path %s\n" % rp)
            np = normalize_path(rp)
            werkzeug_logger.debug("Normalized path %s\n" % np)
            request.normalized_path = np
        except Exception as e:
            werkzeug_logger.exception(e)
        return f(*args, **kwargs)

    return wrapper


@app.before_request
def log_request():
    app.logger.debug('Request: %s %s', request.method, request.url)


@app.after_request
def log_response(res):
    app.logger.debug('Response: %s', res.status_code)
    return res


@app.route('/index')
@app.route('/')
@with_path
def index():
    abs_path = request.normalized_path
    content = os.listdir(abs_path)
    name_paths = [(n, os.path.join(abs_path, n)) for n in content]
    name_paths = [(n, p, True) if os.path.isdir(p) else (n, p, False) for n, p in name_paths]
    name_paths = [(n, os.path.relpath(p, root), d) for n, p, d in name_paths]
    # FIXME use url_for
    dirs = [('/?path=%s' % p, n) for n, p, d in name_paths if d]
    logs = [('/log?path=%s' % p, n) for n, p, d in name_paths if not d and p.endswith('log')]

    app.logger.debug('Rendering list of logs')
    return render_template('index.html', dirs=dirs, logs=logs)


def _stream_template(template_name, **context):
    # http://flask.pocoo.org/docs/patterns/streaming/#streaming-from-templates
    app.update_template_context(context)
    t = app.jinja_env.get_template(template_name)
    rv = t.stream(context)
    return rv


def turnify_conversation(msgs):
    previous, last = 'Previous', 'Last'
    turns, flat = [], FLAT_EMPTY_TURN.copy()
    for m in msgs:
        if 'name' not in m and 'user' in m:
            m['name'] = m['user']  # TODO HACK FOR BACKWARD COMPATIBILITY
        assert 'name' in m, 'Broken msg: %s' % m
        previous, last = last, m['name']
        flat[last] = str(m[PICK_VALUES_TURN[last]])  # extract content based on the type from the wrapper message
        assert last in FLAT_EMPTY_TURN, 'last %s not in FLAT_EMPTY_TURN %s' % (last, FLAT_EMPTY_TURN)
        if previous == last or all([v is not None for v in flat.values()]):
            turns.append(flat)
            flat = FLAT_EMPTY_TURN.copy()

    not_none = [v is not None for v in flat.values()]
    if last != 'Last' and previous != last and not all(not_none) and any(not_none):
        turns.append(flat)
    app.logger.debug(
        'Created %d turns from %d msgs: %.2f msg per turn (expected 3)' % (len(turns), len(msgs), len(msgs) / len(turns)))
    return turns


def _read_conversation(abs_path):
    with open(abs_path, 'r') as r:
        msgs = []
        for line in r:
            try:
                msgs.append(jsonapi.loads(line))
            except ValueError as e:
                app.logger.warning('Skipping utterance %s cannot parse as json (Exception: %s)' % (line, e))
    return msgs


def _just_logging(msg, chatbot_id):
    app.logger.info('ChatBot[%s] replied %s' % (chatbot_id, msg))


def _get_answers_and_states(sub_sock, poller, timeout):
    raw_answers = [wrap_msg('ahoj'), wrap_msg('ahoj2')]
    raw_belief_states = [{'name': BELIEF_STATE, 'attributes': "state1"}, {'name': BELIEF_STATE, 'attributes': "state2"}]
    # TODO asserts about names SYSTEM and BELIEF_STATE

    raw_answers, raw_belief_states = [], []
    start = datetime.now()
    while (datetime.now() - start).total_seconds() < timeout:
        app.logger.debug('seconds remaining till timeout %f', (datetime.now() - start).total_seconds())
        remaining = (datetime.now() - start).total_seconds() - timeout
        socks = dict(poller.poll(timeout=remaining))
        app.logger.debug('after poll')
        if sub_sock in socks and socks[sub_sock] == zmqg.POLLIN:
            _, msg = topic_msg_to_json(sub_sock.recv())
            assert 'name' in msg, 'Broken msg %s' % msg
            if msg['name'] == SYSTEM:
                raw_answers.append(msg)
            elif msg['name'] == BELIEF_STATE:
                raw_belief_states.append(msg)
            else:
                app.logger.warning('Unknown message from ChatBot')
    answers = [m['utterance'] for m in raw_answers]
    belief_states = [bs['attributes'] for bs in raw_belief_states]

    return answers, belief_states


def _gen_data(cbc, recorded_ms, replay_listener, poller, timeout=2.1):
    recorded_turns = turnify_conversation(recorded_ms)
    i = 0
    while i < len(recorded_turns):
        if recorded_turns[i][HUMAN] is not None:
            d = recorded_turns[i]
            app.logger.debug('Sending msg to replay bot %s' % d[HUMAN])
            cbc.send(wrap_msg(d[HUMAN]))
            try:
                anws, bss = _get_answers_and_states(replay_listener, poller, timeout)
                for j, (a, b) in enumerate(izip_longest(anws, bss)):
                    if j == 0:
                        d[REPLAYED], d[BELIEF_STATE_REPLAY] = a, b
                        i += 1
                        yield d
                    else:  # j >= 1
                        # More answer for one input
                        if i < len(recorded_turns) and recorded_turns[i][HUMAN] is None:
                            # If the recorded answers had more answers too
                            recorded_turns[i][REPLAYED], recorded_turns[i][BELIEF_STATE_REPLAY] = a, b
                            yield recorded_turns[i]
                            i += 1
                        else:
                            new_d = FLAT_EMPTY_TURN.copy()
                            new_d[REPLAYED], new_d[BELIEF_STATE_REPLAY] = a, b
                            yield new_d
            except Empty:
                app.logger.warning('System not responded to "%s"' % d[HUMAN])
        else:
            i += 1
            yield d
    cbc.kill()


def _replay_log(abs_path):
    cbc = ChatBotConnector(_just_logging, bot_input, bot_output, user_input, user_output, ctx=ctx)
    cbc.start()
    replay_listener = ctx.socket(zmqg.SUB)
    replay_listener.setsockopt_string(zmqg.SUBSCRIBE, '')
    poller = zmqg.Poller()
    poller.register(replay_listener, zmqg.POLLIN)
    replay_listener.connect(LOGGING_ADDRESS)

    # TODO fix handlers so it does not polute the logs with user human interactive communication
    if not cbc.initialized.get():
        res = render_template("error.html", msg="Chatbot not initialized")
    else:
        msgs = _read_conversation(abs_path)
        res = Response(stream_with_context(
            _stream_template('log.html',
                             headers=EXTENDED_VALUES_TURN,
                             data=_gen_data(cbc, msgs, replay_listener, poller))))
    return res


@app.route('/log')
@with_path
def replay_log_path():
    return _replay_log(request.normalized_path)


@app.errorhandler(404)
def page_not_found(e):
    app.logger.error('Page not found 404: %s' % e)
    return render_template("error.html", error='404', msg=e), 404


@app.errorhandler(500)
def internal_server_err(e):
    app.logger.error('Internal server error 500: %s', e)
    return render_template("error.html", error='500', msg=e), 500


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='cleverobot app')
    parser.add_argument('-p', '--port', type=int, default=port)
    parser.add_argument('-t', '--host', default=host)
    parser.add_argument('-d', '--debug', dest='debug', action='store_true')
    parser.add_argument('--no-debug', dest='debug', action='store_false')
    parser.set_defaults(debug=True)
    parser.add_argument('-l', '--log', default=log_name)
    parser.add_argument('-r', '--root', default=root)
    parser.add_argument('--bot-input', type=int, default=bot_input)
    parser.add_argument('--bot-output', type=int, default=bot_output)
    parser.add_argument('--user-input', type=int, default=user_input)
    parser.add_argument('--user-output', type=int, default=user_output)
    parser.add_argument('--log-config', default=log_config)
    args = parser.parse_args()

    bot_input, bot_output = args.bot_input, args.bot_output
    user_input, user_output = args.user_input, args.user_output
    host, port, log_name, log_config = args.host, args.port, args.log, args.log_config

    root = os.path.realpath(args.root)
    if not os.path.isdir(root):
        raise KeyError("argument root is not a directory: %s" % root)

    setup_logging(log_config)
    log_process, forwarder_process_bot, forwarder_process_user = start_zmq_and_log_processes(bot_input, bot_output,
                                                                                             user_input, user_output)
    try:
        app.run(host=host, port=port, debug=args.debug, use_reloader=False)
    except Exception as e:
        app.logger.exception(e)
        app.logger.error("Top level exception", exc_info=True)
        if app.debug:
            raise e
    finally:
        shut_down(forwarder_process_bot, forwarder_process_user, log_process)

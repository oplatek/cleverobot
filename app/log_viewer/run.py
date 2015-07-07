import argparse
import logging
import os
import gevent
from zmq.utils import jsonapi
from app.cleverobot.run import start_zmq_and_log_processes, shut_down
import zmq.green as zmqg
from flask import Flask, render_template, current_app, request, Response, stream_with_context
import functools
from cbot.bot import ChatBotConnector, wrap_msg
from gevent.queue import Queue, Empty

app = Flask(__name__)
app.secret_key = 12345  # TODO
root = os.path.realpath(os.path.join(os.path.dirname(__file__), '../../cbot/logs'))
log_name = 'logs.cleverobot.log'
bot_input, bot_output = 6665, 7776
user_input, user_output = 8887, 9998
host, port = '0.0.0.0', 4000
ctx = zmqg.Context()


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
            werkzeug_logger.info("Normalized path %s\n" % np)
            request.normalized_path = np
        except Exception as e:
            werkzeug_logger.exception(e)
        return f(*args, **kwargs)
    return wrapper


@app.before_request
def log_request():
    current_app.logger.debug('Request: %s %s', request.method, request.url)


@app.after_request
def log_response(res):
    current_app.logger.debug('Response: %s', res.status_code)
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
    # return "Log viewer"


def _stream_template(template_name, **context):
    # http://flask.pocoo.org/docs/patterns/streaming/#streaming-from-templates
    app.update_template_context(context)
    t = app.jinja_env.get_template(template_name)
    rv = t.stream(context)
    # uncomment if you don't need immediate reaction
    ##rv.enable_buffering(5)
    return rv


def _read_conversation(abs_path):
    with open(abs_path, 'r') as r:
        msgs = []
        for line in r:
            try:
                user_input, original_system, current_system = None, None, None
                msg = jsonapi.loads(line)
                assert 'user' in msg
                assert 'utterance' in msg
                if msg['user'] == 'human':
                    msgs.append((True, msg['utterance']))
                else:
                    msgs.append((False, msg['utterance']))
            except ValueError as e:
                app.logger.warning('Skipping utterance %s cannot parse as json (Exception: %s)' % (line, e))
    return msgs



def _replay_log(abs_path, timeout=2.5):

    answers = Queue()

    def store_to_queue(msg, chatbot_id):
        print 'debug 222'
        app.logger.debug('Received answer %s from %s' % (msg, chatbot_id))
        answers.put(msg)

    cbc = ChatBotConnector(store_to_queue, bot_input, bot_output, user_input, user_output, ctx=ctx)
    cbc.start()
    cbc.initialized.wait(timeout)

    msgs = _read_conversation(abs_path)

    def g(ms):
        original_response, user_said, current_system = None, None, None
        for is_user, utt in ms:
            if is_user:
                user_said = utt
                cbc.send(wrap_msg(utt))
                try:
                    gevent.sleep(0)
                    current_system = answers.get(timeout=timeout)
                except Empty:
                    app.logger.debug('System not responded to "%s"' % utt)
                    current_system = None
            else:
                original_response = utt

            if current_system is not None or original_response is not None:
                yield user_said, original_response, current_system
                original_response, user_said, current_system = None, None, None

            while not answers.empty():
                _cur_sys = answers.get()
                yield None, None, _cur_sys
        print 'debug 102', cbc.initialized, str(cbc)
        cbc.kill()

    print 'debug 101', cbc.initialized, str(cbc)
    return Response(stream_with_context(_stream_template('log.html', data=g(msgs))))


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
    args = parser.parse_args()

    bot_input, bot_output = args.bot_input, args.bot_output
    user_input, user_output = args.user_input, args.user_output
    host, port, log_name = args.host, args.port, args.log

    root = os.path.realpath(args.root)
    if not os.path.isdir(root):
        raise KeyError("argument root is not a directory: %s" % root)

    log_process, forwarder_process_bot, forwarder_process_user = start_zmq_and_log_processes(ctx, bot_input, bot_output, user_input, user_output)
    try:
        app.run(host=host, port=port, debug=args.debug, use_reloader=False)
    except Exception as e:
        app.logger.exception(e)
        app.logger.error("Top level exception", exc_info=True)
        if app.debug:
            raise e
    finally:
        shut_down(forwarder_process_bot, forwarder_process_user, log_process)

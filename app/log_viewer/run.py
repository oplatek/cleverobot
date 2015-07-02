import argparse
from multiprocessing import Process
import logging
import os
import time
from cbot.bot import log_loop, connect_logger, forwarder_device_start
import zmq.green as zmqg
import zmq
from flask import Flask, render_template, current_app, request, jsonify, url_for, Response, stream_with_context
import functools

app = Flask(__name__)
app.secret_key = 12345  # TODO


def normalize_path(path):
    abs_path = os.path.realpath(os.path.join(app.root, path))
    if os.path.commonprefix([abs_path, app.root]) != app.root:
        raise KeyError("Invalid argument: do not try to access files above the root.")
    return abs_path


def with_path(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        werkzeug_logger = logging.getLogger('werkzeug')
        try:
            if 'path' not in request.args:
                rp = app.root
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
    name_paths = [(n, os.path.relpath(p, app.root), d) for n, p, d in name_paths]
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


def _replay_log(abs_path):
    # TODO
    def g(abs_path):
        with open(abs_path, 'r') as r:
            for line in r:
                time.sleep(0.1)
                app.logger.debug("sending threetimes: %s" % line)
                # TODO escape
                yield line, line, line

    return Response(stream_with_context(_stream_template('log.html', data=g(abs_path))))


@app.route('/log')
@with_path
def replay_log_path():
    return _replay_log(request.normalized_path)


# @app.route('/log/<log_id>')
# def replay_log_rest(log_id):
#     norm_path = normalize_path(log_id)
#     return replay_log(norm_path)

@app.errorhandler(404)
def page_not_found(e):
    app.logger.error('Page not found 404: %s' % e)
    return render_template("error.html", error='404', msg=e), 404


@app.errorhandler(500)
def internal_server_err(e):
    app.logger.error('Internal server error 500: %s', e)
    return render_template("error.html", error='500', msg=e), 500

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='cleverobot log viewer')
    parser.add_argument('-p', '--port', type=int, default=8080)
    parser.add_argument('-t', '--host', default='0.0.0.0')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true')
    parser.add_argument('--no-debug', dest='debug', action='store_false')
    parser.set_defaults(debug=True)
    parser.add_argument('-l', '--log', default='logs.cleverobot.log')
    parser.add_argument('--bot-input', type=int, default=6665)
    parser.add_argument('--bot-output', type=int, default=7776)
    parser.add_argument('--log-input', type=int, default=8887)
    parser.add_argument('--log-output', type=int, default=9998)
    parser.add_argument('-root', type=str, default='../../cbot/logs', help='root directory of logs.')
    args = parser.parse_args()

    app.root = os.path.realpath(args.root)
    if not os.path.isdir(app.root):
        raise KeyError("argument root is not a directory: %s" % app.root)
    log_process = Process(target=log_loop, kwargs={'log_name': args.log})
    forwarder_process_bot, forwarder_process_log = None, None
    try:
        # log_process.start()
        # ctx = zmqg.Context()
        # connect_logger(app.logger, ctx)
        werkzeug_logger = logging.getLogger('werkzeug')
        # connect_logger(werkzeug_logger, ctx)
        #
        # forwarder_process_bot = forwarder_device_start(args.bot_input, args.bot_output, app.logger)
        # forwarder_process_log = forwarder_device_start(args.log_input,
        #                                                 args.log_output,
        #                                                 app.logger)
        #
        # pub2bot = ctx.socket(zmq.PUB)
        # pub2bot.connect('tcp://127.0.0.1:%d' % args.bot_input)

        app.logger.info('args: %s', args)
        app.run(host=args.host, port=args.port, debug=args.debug)

    except Exception, e:
        app.logger.error("Top level exception", exc_info=True)
        raise
    finally:
        if forwarder_process_bot is not None:
            forwarder_process_bot.join(timeout=0.1)
        if forwarder_process_log is not None:
            forwarder_process_log.join(timeout=0.1)
        # log_process.terminate()
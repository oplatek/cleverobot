#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals
import logging
import time
from flask import Flask, render_template, current_app, request, jsonify
import flask.ext.socketio as fsocketio
import argparse
from cbot.bot import ChatBotConnector, log_loop, connect_logger, topic_msg_to_json, LOGGING_ADDRESS
from cbot.bot import forwarder_device_start
import cbot.bot_exceptions as botex
from multiprocessing import Process
import zmq.green as zmqg
import zmq


app = Flask(__name__)
app.secret_key = 12345  # TODO
socketio = fsocketio.SocketIO(app)


@app.before_request
def log_request():
    current_app.logger.debug('Request: %s %s', request.method, request.url)


@app.after_request
def log_response(res):
    current_app.logger.debug('Response: %s', res.status_code)
    return res


@app.route('/index')
@app.route('/')
def index():
    app.logger.debug('Rendering index')
    return render_template('index.html')


@app.route('/stats/<chatbot_id>')
def request_stats(chatbot_id):
    context = zmqg.Context()
    current_app.logger.debug('sent stats req to %s' % chatbot_id)
    async_stat_sub = context.socket(zmq.SUB)
    async_stat_sub.setsockopt_string(zmq.SUBSCRIBE, 'stat_%s' % chatbot_id)
    async_stat_sub.connect('tcp://127.0.0.1:%d' % args.user_output)
    poller = zmqg.Poller()
    poller.register(async_stat_sub, zmqg.POLLIN)
    time.sleep(0.1)
    pub2bot.send_string('stat_%s request' % chatbot_id)
    socks = dict(poller.poll(timeout=2000))
    app.logger.debug('sockets %s' % socks)
    if async_stat_sub in socks and socks[async_stat_sub] == zmqg.POLLIN:
        topic, msg = topic_msg_to_json(async_stat_sub.recv())
        assert topic == 'stat_%s' % chatbot_id
        app.logger.debug('sending back requested stats %s' % str(msg))
        return jsonify(msg), 200
    else:
        return jsonify({'response': 'Chatbot %s unknown' % chatbot_id}), 200


@app.errorhandler(404)
def page_not_found(e):
    app.logger.error('Page not found 404: %s' % e)
    return render_template("error.html", error='404', msg=e), 404


@app.errorhandler(500)
def internal_server_err(e):
    app.logger.error('Internal server error 500: %s', e)
    return render_template("error.html", error='500', msg=e), 500


@socketio.on('begin')
def begin_dialog(msg):
    try:
        cbc = fsocketio.session['chatbot'] = ChatBotConnector(web_response,
                                                        args.bot_input,
                                                        args.bot_output,
                                                        args.user_input,
                                                        args.user_output,
                                                        ctx=ctx)
        cbc.start()
        fsocketio.join_room(cbc.name)
        app.logger.debug('ChatbotConnector initiated')
    except botex.BotNotAvailableException as exp:
        err_msg = {'status': 'error', 'message': 'Chatbot not available'}
        socketio.emit('server_error', err_msg)
        app.logger.error('Error: %s\nInput config %s\nSent to client %s', exp, msg, err_msg)
    except botex.BotSendException as exp:
        err_msg = {'status': 'error', 'message': 'Chatbot cannot send messages'}
        socketio.emit('server_error', err_msg)
        app.logger.error('Error: %s\nSent to client %s', exp, err_msg)
        del fsocketio.session['chatbot']


@socketio.on('utterance')
def process_utt(msg):
    if 'chatbot' in fsocketio.session:
        try:
            cbc = fsocketio.session['chatbot']
            cbc.send(msg)
        except botex.BotSendException as exp:
            err_msg = {'status': 'error', 'message': 'Chatbot lost'}
            socketio.emit('server_error', err_msg)
            app.logger.error('Error: %s\nInput config %s\nSent to client %s', exp, msg, err_msg)
            del fsocketio.session['chatbot']
    else:
        err_msg = {'status': 'error', 'message': 'Internal server error'}
        socketio.emit('server_error', err_msg)
        app.logger.error('Chatbot not found. Incoming input %s\nSent to client %s', msg, err_msg)
        return


@socketio.on('end')
def end_recognition(msg):
    try:
        cbc = fsocketio.session['chatbot']
        fsocketio.leave_room(cbc.name)
        fsocketio.close_room(cbc.name)
        cbc.terminate()  # TODO
    except botex.BotEndException as exp:
        app.logger.error('Error on end: %s\n%s', exp, msg)
    finally:
        del fsocketio.session['chatbot']


def web_response(msg, room_id):
    socketio.emit('socketbot', msg, room=room_id)
    app.logger.debug('sent: %s to %s', msg, room_id)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='cleverobot app')
    parser.add_argument('-p', '--port', type=int, default=3000)
    parser.add_argument('-t', '--host', default='0.0.0.0')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true')
    parser.add_argument('--no-debug', dest='debug', action='store_false')
    parser.set_defaults(debug=True)
    parser.add_argument('-l', '--log', default='cleverobot.log')
    parser.add_argument('--bot-input', type=int, default=6666)
    parser.add_argument('--bot-output', type=int, default=7777)
    parser.add_argument('--user-input', type=int, default=8888)
    parser.add_argument('--user-output', type=int, default=9999)
    args = parser.parse_args()

    log_process = Process(target=log_loop, kwargs={'log_name': args.log})
    forwarder_process_bot, forwarder_process_user = None, None
    try:
        log_process.start()
        ctx = zmqg.Context()
        connect_logger(app.logger, ctx)
        werkzeug_logger = logging.getLogger('werkzeug')
        connect_logger(werkzeug_logger, ctx)

        forwarder_process_bot = forwarder_device_start(args.bot_input, args.bot_output, app.logger)
        forwarder_process_user = forwarder_device_start(args.user_input,
                                                        args.user_output,
                                                        app.logger)

        pub2bot = ctx.socket(zmq.PUB)
        pub2bot.connect('tcp://127.0.0.1:%d' % args.bot_input)

        app.logger.info('args: %s', args)
        socketio.run(app, host=args.host, port=args.port, use_reloader=False,)

        # use nginx instead
        # key_dir_path = os.path.realpath(os.path.join(os.path.dirname(capp.__path__[0]), 'keys'))
        # key_path = os.path.join(key_dir_path, 'exploited.key')
        # cert_path = os.path.join(key_dir_path, 'exploited.crt')
        # socketio.run(app, host=args.host, port=args.port, use_reloader=False, keyfile=key_path, certfile=cert_path)
    except Exception, e:
        app.logger.error("Top level exception", exc_info=True)
        raise
    finally:
        if forwarder_process_bot is not None:
            forwarder_process_bot.join(timeout=0.1)
        if forwarder_process_user is not None:
            forwarder_process_user.join(timeout=0.1)
        log_process.terminate()

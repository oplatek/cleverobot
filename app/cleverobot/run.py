#!/usr/bin/env python
# encoding: utf-8
import multiprocessing
import logging
import time
from flask import Flask, render_template
import flask.ext.socketio as fsocketio
import argparse
from cbot.bot import ChatBotConnector, connect_logger, log_loop
from cbot.bot import forwarder_device_start
import cbot.bot_exceptions as botex
from multiprocessing import Process

app = Flask(__name__)
app.secret_key = 12345  # TODO
socketio = fsocketio.SocketIO(app)


@app.route('/index')
@app.route('/')
def index():
    app.logger.debug('Rendering index')
    return render_template('index.html')


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
        fsocketio.session['chatbot'] = ChatBotConnector(web_response,
                                                        args.bot_input,
                                                        args.bot_output,
                                                        args.user_input,
                                                        args.user_output,)
        fsocketio.session['chatbot'].start()
        app.logger.debug('ChatbotConnector initiated')
    except botex.BotNotAvailableException as e:  # TODO more specific error handling
        err_msg = {'status': 'error', 'message': 'Chatbot not available'}
        socketio.emit('server_error', err_msg)
        app.logger.error('Error: %s\nInput config %s\nSent to client %s', e, msg, err_msg)
    except botex.BotSendException as e:
        err_msg = {'status': 'error', 'message': 'Chatbot cannot send messages'}
        socketio.emit('server_error', err_msg)
        app.logger.error('Error: %s\nSent to client %s', e, err_msg)
        del fsocketio.session['chatbot']


@socketio.on('utterance')
def process_utt(msg):
    if 'chatbot' in fsocketio.session:
        try:
            msg['time'] = time.time()
            fsocketio.session['chatbot'].send(msg)
        except botex.BotSendException as e:  # TODO more specific error handling
            err_msg = {'status': 'error', 'message': 'Chatbot lost'}
            socketio.emit('server_error', err_msg)
            app.logger.error('Error: %s\nInput config %s\nSent to client %s', e, msg, err_msg)
            del fsocketio.session['chatbot']
    else:
        err_msg = {'status': 'error', 'message': 'Internal server error'}
        socketio.emit('server_error', err_msg)
        app.logger.error('Chatbot not found. Incoming input %s\nSent to client %s', msg, err_msg)
        return


@socketio.on('end')
def end_recognition(msg):
    try:
        # fsocketio.session['chatbot'].finalize(msg)
        fsocketio.session['chatbot'].terminate() # TODO
    except botex.BotEndException as e:  # TODO more specific error handling
        app.logger.error('Error on end: %s\n%s', e, msg)
    finally:
        del fsocketio.session['chatbot']


def web_response(msg):
    socketio.emit('socketbot', msg)
    app.logger.debug('sent: %s', msg)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='cleverobot app')
    parser.add_argument('-p', '--port', type=int, default=3000)
    parser.add_argument('-t', '--host', default='0.0.0.0')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true')
    parser.add_argument('--no-debug', dest='debug', action='store_false')
    parser.set_defaults(debug=True)
    parser.add_argument('-l', '--log', default='cleverbot.log')
    parser.add_argument('--bot-input', type=int, default=6666)
    parser.add_argument('--bot-output', type=int, default=7777)
    parser.add_argument('--user-input', type=int, default=8888)
    parser.add_argument('--user-output', type=int, default=9999)
    args = parser.parse_args()

    log_process = Process(target=log_loop)
    forwarder_process_bot, forwarder_process_user = None, None
    try:
        log_process.start()
        # app.logger = get_logger('webserver')
        # app.logger.info('args: %s', args)

        forwarder_process_bot = forwarder_device_start(args.bot_input,
                                                       args.bot_output,
                                                       app.logger)
        forwarder_process_user = forwarder_device_start(args.user_input,
                                                        args.user_output,
                                                        app.logger)
        socketio.run(app, host=args.host, port=args.port)
    finally:
        if forwarder_process_bot is not None:
            forwarder_process_bot.join(timeout=0.1)
        if forwarder_process_user is not None:
            forwarder_process_user.join(timeout=0.1)
        log_process.terminate()

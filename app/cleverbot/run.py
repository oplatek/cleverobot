#!/usr/bin/env python
# encoding: utf-8
from flask import Flask, render_template
from flask.ext.socketio import SocketIO, emit, session
import os
import zmq.green as zmq
import argparse
import logging
from cbot.bot import ChatBotConnector
from cbot.bot_exceptions import *

app = Flask(__name__)
app.secret_key = 12345  # TODO
socketio = SocketIO(app)

@app.route('/index')
@app.route('/')
def index():
    app.logger.debug('Rendering index')
    return render_template('index.html')


@app.errorhandler(404)
def page_not_found(e):
    app.logger.error('Page not found 404: %s' % e)
    return render_template("error.html",error='404', msg=e), 404


@app.errorhandler(500)
def internal_server_err(e):
    app.logger.error('Internal server error 500: %s' % e)
    return render_template("error.html",error='500', msg=e), 500


@socketio.on('begin')
def begin_dialog(msg):
    try:
        session['chatbot'] = ChatBotConnector(web_response,
                                                cbot_input,
                                                cbot_output,
                                                )
        session['chatbot'].start()
        app.logger.debug('ChatbotConnector initiated')
    except BotNotAvailableException as e:  # TODO more specific error handling
        err_msg = {'status': 'error', 'message': 'Chatbot not available'}
        emit('server_error', err_msg)
        app.logger.error('Error: %s\nInput config %s\nSent to client %s' % (e,  msg, err_msg))
    except BotSendException as e:
        err_msg = {'status': 'error', 'message': 'Chatbot cannot send messages'}
        emit('server_error', err_msg)
        app.logger.error('Error: %s\nSent to client %s' % (e, err_msg))
        del session['chatbot']


@socketio.on('utterance')
def process_utt(msg):
    if 'chatbot' in session:
        try:
            session['chatbot'].send(msg)
            app.logger.debug('Message resent to Chatbot %s' % msg)
        except BotSendException as e:  # TODO more specific error handling
            err_msg = {'status': 'error', 'message': 'Chatbot lost'}
            emit('server_error', err_msg)
            app.logger.error('Error: %s\nInput config %s\nSent to client %s' % (e,  msg, err_msg))
            del session['chatbot']
    else:
        err_msg = {'status': 'error', 'message': 'Internal server error'}
        emit('server_error', err_msg)
        app.logger.error('Chatbot not found. Incoming input %s\nSent to client %s' % (msg, err_msg))
        return


@socketio.on('end')
def end_recognition(msg):
    try:
        session['chatbot'].finalize(msg)
    except BotEndException as e:  # TODO more specific error handling
        app.logger.error('Error on end: %s\n%s' % (e, msg))
    finally:
        del session['chatbot']


def web_response(msg):
    socketio.emit('socketbot', msg)
    app.logger.debug('sent: %s' % str(msg))


if __name__ == '__main__':
    global cbot_input, cbot_output
    parser = argparse.ArgumentParser(description='cleverbot app')
    parser.add_argument('-p', '--port', type=int, default=80)
    parser.add_argument('-t', '--host', default='0.0.0.0')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true')
    parser.add_argument('--no-debug', dest='debug', action='store_false')
    parser.set_defaults(debug=True)
    parser.add_argument('-l', '--log', default='cleverbot.log')
    parser.add_argument('--bot-input',default='6666')
    parser.add_argument('--bot-output',default='7777')
    args = parser.parse_args()
    
    print 'args: %s' % args

    cbot_input = args.bot_input
    cbot_output = args.bot_output
    assert(cbot_output != cbot_input)

    file_handler = logging.FileHandler(args.log, encoding='utf8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s [%(pathname)s:%(lineno)d]: \n%(message)s '))
    file_handler.setLevel(logging.DEBUG)

    app.logger.addHandler(file_handler)
    app.config['DEBUG'] = args.debug

    socketio.run(app, host=args.host, port=args.port)

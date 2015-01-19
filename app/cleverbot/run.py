#!/usr/bin/env python
# encoding: utf-8
from flask import Flask, render_template
from flask.ext.socketio import SocketIO, emit, session
import os
import zmq.green as zmq
from zmq.green.eventloop import zmqstream
import argparse
import logging

from cbot.bot import ChatBot

app = Flask(__name__)
app.secret_key = 12345  # TODO
socketio = SocketIO(app)
CBOT_INPUT='tcp://127.0.0.1:6666'
CBOT_OUTPUT='tcp://127.0.0.1:7777' 

class BotEndException:
    pass


class BotSendException:
    pass


class BotNotAvailableException:
    pass

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
def page_not_found(e):
    app.logger.error('Internal server error 500: %s' % e)
    return render_template("error.html",error='500', msg=e), 500


@socketio.on('begin')
def begin_dialog(msg):
    try:
        session['chatbot'] = ChatbotConnector(web_response,
                                                CBOT_INPUT, 
                                                CBOT_OUTPUT)
        app.logger.debug('TODO setup msg %s' % msg)
    except BotNotAvailableException as e:  # TODO more specific error handling
        err_msg = {'status': 'error', 'message': 'Chatbot not available'}
        emit('server_error', err_msg)
        app.logger.error('Error: %s\nInput config %s\nSent to client %s' % (e,  msg, err_msg))


@socketio.on('utterance')
def process_utt(msg):
    try:
        if 'chatbot' not in session:
            err_msg = {'status': 'error', 'message': 'Internal server error'}
            emit('server_error', err_msg)
            app.logger.error('Chatbot not found. Incoming input %s\nSent to client %s' % (msg, err_msg))
            return

        session['chatbot'].send(msg)
        app.logger.debug('Message resent to Chatbot %s' % msg)
    except BotSendException as e:  # TODO more specific error handling
        err_msg = {'status': 'error', 'message': 'Chatbot lost'}
        emit('server_error', err_msg)
        app.logger.error('Error: %s\nInput config %s\nSent to client %s' % (e,  msg, err_msg))
        del session['chatbot']


@socketio.on('end')
def end_recognition(msg):
    try:
        session['chatbot'].finalize(msg)
    except BotEndException as e:  # TODO more specific error handling
        app.logger.error('Error on end: %s\n%s' % (e, msg))
    finally:
        del session['chatbot']


def web_response(msg):
    emit('socketbot', msg)
    app.logger.debug('sent: %s' % str(msg))


class ChatbotConnector:

    def __init__(self, response_cb, input_add, output_add):
        self.response = response_cb
        self.context = zmq.Context()
        self.iresender = self.context.socket(zmq.PUSH)
        self.oresender = self.context.socket(zmq.PULL)
        self.iresender.bind(input_add)
        self.oresender.bind(output_add)
        stream_pull = zmqstream.ZMQStream(self.oresender)
        stream_pull.on_recv(response_cb)

        app.logger.debug('input_add: %s \noutput_add: %s\n' % (input_add, output_add))
        self.bot = ChatBot(input_add, output_add)
        # self.bot.start()

        # TODO do I need to start the loop like here?: http://learning-0mq-with-pyzmq.readthedocs.org/en/latest/pyzmq/multisocket/tornadoeventloop.html 

    def send(self, msg):
        app.logger.debug('Sending msg to Chatbot: "%s"\n' % msg)
        self.iresender.send_json(msg)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='cleverbot app')
    parser.add_argument('-p', '--port', type=int, default=80)
    parser.add_argument('-t', '--host', default='0.0.0.0')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true')
    parser.add_argument('--no-debug', dest='debug', action='store_false')
    parser.set_defaults(debug=True)
    parser.add_argument('-l', '--log', default='cleverbot.log')
    args = parser.parse_args()

    # TODO how to use arguments and initialize Cbot with the right address
    # parser.add_argument('--bot-input',default=CBOT_INPUT) 
    # parser.add_argument('--bot-output',default=CBOT_OUTPUT) 
    # CBOT_INPUT = args.bot_input
    # CBOT_OUTPUT = args.bot_output
    # assert(CBOT_OUTPUT != CBOT_INPUT)

    file_handler = logging.FileHandler(args.log, encoding='utf8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s [%(pathname)s:%(lineno)d]: \n%(message)s '))
    file_handler.setLevel(logging.DEBUG)
    
    app.logger.addHandler(file_handler)
    app.config['DEBUG'] = args.debug

    socketio.run(app, host=args.host, port=args.port)

#!/usr/bin/env python
# encoding: utf-8
from flask import Flask, render_template
from flask.ext.socketio import SocketIO, emit, session
import zmq.green as zmq
import argparse
import logging

from cbot.bot import ChatBot

app = Flask(__name__)
app.secret_key = 12345  # TODO
socketio = SocketIO(app)


@app.route('/index')
@app.route('/')
def index():
    socketio.logger.debug('Rendering index')
    return render_template('index.html')


@app.error_handler(404)
def page_not_found(e):
    socketio.logger.error('Page not found 404: %s' % e)
    return render_template("error.html",error='404', msg=e), 404


@app.error_handler(500)
def page_not_found(e):
    socketio.logger.error('Internal server error 500: %s' % e)
    return render_template("error.html",error='500', msg=e), 500


@socketio.on('begin')
def begin_dialog(msg):
    try:
        session['chatbot'] = ChatbotConnector(response_cb,
                                    os.environ['CBOT_INPUT'],
                                    os.environ['CBOT_OUTPUT'])
        secketio.logger.debug('TODO setup msg %s' % msg)
    except Exception as e:  # TODO more specific error handling
        err_msg = {'status': 'error', 'message': 'Chatbot not available'}
        socketio.logger.error('Error: %s\nInput config %s\nSend to client %s' % (e,  msg, err_msg)
        emit('server_error', err_msg)


@socketio.on('utterance')
def process_utt(msg):
    try:
        if 'chatbot' not in session:
            err_msg = {'status': 'error', 'message': 'Internal server error'}
            emit('server_error', msg)
            socketio.logger.error('Chatbot not found. Incoming input %s\nSent to client %s' % (msg, err_msg))
        session['chatbot'].send(msg)
        socketio.logger.debug('Message resent to Chatbot %s' % msg)
    except Exception as e:  # TODO more specific error handling
        err_msg = {'status': 'error', 'message': 'Chatbot lost'}
        socketio.logger.error('Error: %s\nInput config %s\nSend to client %s' % (e,  msg, err_msg))
        emit('server_error', err_msg)
        del session['chatbot']


@socketio.on('end')
def end_recognition(msg):
    try:
        session['chatbot'].finalize(msg)
    except Exception as e:  # TODO more specific error handling
        socketio.logger.error('Error on end: %s\n%s' % (e, msg))
    finally:
        del session['chatbot']


def web_response(msg):
    emit('socketbot', msg)
    socketio.logger.debug('sent: %s' % str(msg))


class ChatbotConnector:

    def __init__(self, response_cb, input_add, output_add):
        self.response = response_cb
        self.bot = Chatbot(input_add, output_add)
        self.bot.start()
        self.context = zmq.Context()
        self.iresender = self.socket(zmq.PUSH)
        self.oresender = self.socket(zmq.PULL)
        self.iresender.bind(input_add)
        self.oresender.bind(output_add)
        stream_pull = zmq.eventloop.zmstream.ZMQStream(self.oresender)
        stream_pull.on_recv(response_cb)
        # TODO do I need to start the loop like here?: http://learning-0mq-with-pyzmq.readthedocs.org/en/latest/pyzmq/multisocket/tornadoeventloop.html 

    def send(self, msg):
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

    file_handler = logging.FileHandler(args.log, encoding='utf8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s [%(pathname)s:%(lineno)d]: \n%(message)s '))
    file_handler.setLevel(logging.DEBUG)
    socketio.logger.addHandler(file_handler)

    socketio.run(host=args.host, port=args.port, debug=args.debug)

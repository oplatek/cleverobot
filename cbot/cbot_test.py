#!/usr/bin/env python
# encoding: utf-8
import unittest
import zmq.green as zmq
from bot import ChatBot, ChatBotConnector
import time
import datetime


def client(input_port, output_port):
    context = zmq.Context()
    socket = context.socket(zmq.PUSH)
    socket.bind("tcp://*:%s" % output_port)
    socket_pull = context.socket(zmq.PULL)
    socket_pull.bind("tcp://*:%s" % input_port)
    # Initialize poll set
    poller = zmq.Poller()
    poller.register(socket_pull, zmq.POLLIN)

    # Work on requests from both server and publisher
    should_continue = True
    while should_continue:
        print 'before poll'
        socks = dict(poller.poll())
        print 'after poll' 
        if socket_pull in socks and socks[socket_pull] == zmq.POLLIN:
            message = socket_pull.recv()
            print "Client received command: %s" % message
            if message == "Exit":
                print "Recieved exit command, client will stop recieving messages"
                should_continue = False
                socket.send('Exit')
            else:
                socket.send('client: continueing')


class ChatBotConnectorTest(unittest.TestCase):
    pass

class ChatBotTest(unittest.TestCase):

    def setUp(self):
        self.input_port = '4000'
        self.output_port = '5000'
        self.context = zmq.Context()
        self.pull_socket = self.context.socket(zmq.PULL)
        self.push_socket = self.context.socket(zmq.PUSH)
        self.pull_socket.connect("tcp://localhost:%s" % self.output_port)
        self.push_socket.connect("tcp://localhost:%s" % self.input_port)
        self.poller = zmq.Poller()
        self.poller.register(self.pull_socket, zmq.POLLIN)
        self.timeout = 300.0 # ms


    def tearDown(self):
        pass

    def test_is_responding(self):
        message = None
        from multiprocessing import Process
        # bot = Process(target=client, args=(self.input_port, self.output_port))
        bot = ChatBot(self.input_port, self.output_port)
        bot.start()
        # self.push_socket.send_json({'test':{'status':'unknow'}})
        msg = {'time': str(datetime.datetime.utcnow()), 'user': 'test', 'utterance': 'hi'}
        self.push_socket.send_json(msg)
        socks = dict(self.poller.poll(timeout=self.timeout))
        if self.pull_socket in socks and socks[self.pull_socket] == zmq.POLLIN:
            message = self.pull_socket.recv_json()
        bot.terminate()
        bot.join()
        self.assertIsNotNone(message)
        self.assertItemsEqual(bot.__class__.__name__, message['user'], msg='messageuser %s' % message['user'])


if __name__ == '__main__':
    unittest.main()

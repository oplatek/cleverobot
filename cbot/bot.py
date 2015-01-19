from __future__ import unicode_literals
import multiprocessing
import zmq
import datetime


class ChatBot(multiprocessing.Process):
    '''Chatbot class organise the communication between 
    subtasks processes or implement easy subtask itself.

    If the subtask is:
    a) too time consuming
    b) needs to generate events asynchronously
    it was splitted it to process and registered using zmq sockets.
    The obvious necessary sockets used are for input and output
    of the chatbot.
    '''
    def __init__(self, url_input, url_output, name='ChatBot'):

        self.context = zmq.Context()
        self.isocket = context.socket(zmq.PULL)
        self.osocket = context.socket(zmq.PUSH)
        self.isocket.bind(url_input)
        self.osocket.bind(url_output)
        self.state = ('not_started', datetime.datetime.utcnow()) 
        self.should_run = lambda: True
        
        self.poller = zmq.Poller() 
        self.poller.register(self.isocket, zmq.POLLIN)

    def run(self):
        while self.should_run():
            messages = self.poller.poll()
            if seff.isocket in messages:
                msg = self.isocket.recv_json()
                self.update_state(msg)
                self.generate_utt(msg)

    def update_state(self, msg):
        state_type = None
        if self.state == ('not_started', _):
            state_type = ('started', datetime.datetime.utcnow())

    def generate_utt(self, msg):
        assert(msg is dict)
        self.send_utt('Hi %(user)s, you said "%(utterance)s, right?' % msg)

    def send_utt(self, utt):
        msg = { 
            'time': datetime.datetime.utcnow(),
            'user': self.name,
            'utterance': utt,
            }
        self.osocket.send_json(msg)

#!/usr/bin/env python
# encoding: utf-8
import unittest
import bot
import time
import random


def wrap_msg(utt):
    return {'time': time.time(), 'user': 'human', 'utterance': utt}


def send_msg(responses):
    def log_and_append(x):
        print x
        responses.append(x)

    return log_and_append


class BotTest(unittest.TestCase):

    def should_run(self):
        return self.run

    def get_next_utt(self):
        if self.i < len(self.user_utt):
            utt = self.user_utt[self.i]
        else:
            self.run = False
            utt = ''
        self.i += 1
        return wrap_msg(utt)

    def setUp(self):
        random.seed(1987)
        self.sent = []
        self.bot = bot.ChatBot(input_port=-6, output_port=-66)
        self.run = True
        self.bot.should_run = self.should_run

    def test_loop(self):
        self.user_utt = ['hi', 'how are you']
        self.i = 0
        responses = []
        self.bot.receive_msg = self.get_next_utt
        self.bot.send_msg = send_msg(responses)
        self.bot.chatbot_loop()
        print responses

if __name__ == '__main__':
    unittest.main()


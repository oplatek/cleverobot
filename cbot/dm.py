#!/usr/bin/env python
# encoding: utf-8
import datetime
from random import random

import cbot.bot


class State(object):
    form = {'phase': ['greeting', 'elisa', 'asking'], 'history': {}}
    greetings = {'Hi', "Hey", "Hello"}

    def __init__(self, logger=None):
        if logger is None:
            self.logger = cbot.bot.get_chatbot_logger()
        else:
            self.logger = logger

        self.belief = {'phase': 'greeting', 'history': []}
        self._validate_state()

    def _validate_state(self):
        # TODO validate json schema of state
        pass

    def update_state(self, msg, annotation):
        timestamp, user_id = msg['time'], msg['user']
        utterance, tokens, tags = annotation
        bag_of_words = set(tokens)
        greeting_words = bag_of_words & State.greetings
        if len(greeting_words) > 0:
            self.belief['phase'] = 'greeting'
            for w in greeting_words:
                self.belief['history'].append((user_id, timestamp, w))
        for w, t in tags:
            if 'NN' == t:  # FIXME check if it is noun more clearly
                self.belief['history'].append(('mention', user_id, timestamp, w, t))
        self._validate_state()

    def change_state(self, action):
        timestamp = datetime.datetime.now()

        if action['type'] == 'greeting':
            self.logger.debug('after action greeting changing state to elisa')
            self.belief['phase'] = 'elisa'
        self.belief['history'].append(('action', timestamp, action))

        phase = self.belief['phase']
        if phase == 'asking' or phase =='elisa':
            change = random()
            if change < 0.3:
                if phase == 'asking':
                    phase = 'elisa'
                else:
                    phase = 'asking'
                self.logger.info('Changing from %s to %s' % (self.belief['phase'], phase))
            self.belief['phase'] = phase


class Policy(object):
    def __init__(self, logger=None):
        self.model = None
        self.reply_timeout = datetime.timedelta(days=0, seconds=2)
        if logger is None:
            self.logger = cbot.bot.get_chatbot_logger()
        else:
            self.logger = logger

    # def get_feedback(self, score, action_id):
    #     """It is probably more efficient split the training into another file """

    def choose_action(self, state):
        """TODO work with time and implement simple model of needs and attention:

        Need is gradually increasing until its fulfilled and reset.
        Think hunger, sex, thirst, ...

        Attention is highest just after sensing a stimulus and fades away.
        The stimuli must vary to keep attention.
        """
        actions = []
        phase = state['phase']
        if phase == 'greeting':
            actions.append({'type':'greeting'})
            self.logger.info('Choose greeting action')
        elif phase == 'elisa':
            history = state['history']
            for t in history[::-1]:
                if t[0] == 'mention':
                    user_id, timestamp, w, tags = t[1:]
                    if datetime.datetime.utcnow() - datetime.datetime.fromtimestamp(timestamp) < self.reply_timeout:
                        actions.append({'type':'ask','about': (w, None, None), 'context': {'tags': tags}})
                        break  # FIXME choose only first action -> some smarter way of choosing actions
        elif phase == 'asking':
            "Pursue your own goal: get knowledge about something"
            actions.append({'type': 'confirm', 'about': ('California', 'IsCapital', None)})
        else:
            self.logger.error('Unknow phase type')
        return actions

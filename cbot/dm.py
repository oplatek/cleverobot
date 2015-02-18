#!/usr/bin/env python
# encoding: utf-8
import datetime
import random

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
        self._change_prob_t = 0.0

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
            self.belief['phase'] = 'asking'
            self.logger.debug('after action greeting changing state to %s', self.belief['phase'])
        self.belief['history'].append(('action', timestamp, action))

        phase = self.belief['phase']
        if phase == 'asking' or phase == 'elisa':
            change = random.random()
            if change < self._change_prob_t:
                if phase == 'asking':
                    phase = 'elisa'
                else:
                    phase = 'asking'
                self.logger.info('Changing from %s to %s', self.belief['phase'], phase)
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

    def choose_action(self, state, kb, nlg):
        """TODO work with time and implement simple model of needs and attention:

        Need is gradually increasing until its fulfilled and reset.
        Think hunger, sex, thirst, ...

        Attention is highest just after sensing a stimulus and fades away.
        The stimuli must vary to keep attention.
        """
        phase = state['phase']
        if phase == 'greeting':
            self.logger.info('Choose greeting action')
            return [{'type':'greeting'}]
        elif phase == 'elisa':
            return self._elisa_actions(state)
        elif phase == 'asking':
            return self._ask_actions(state, kb, nlg)
        else:
            self.logger.error('Unknown phase type')
            return []

    def _ask_actions(self, state, kb, nlg):
        actions = []
        self.logger.debug("Pursue your own goal: get knowledge about something")
        # get fact to ask about FIXME interesting choice for user
        nodes = kb.get_nodes()
        rand_node = random.sample(nodes, 1)[0]
        self.logger.debug('Sample node %s', rand_node)
        rand_rel = random.sample(kb.get_neighbours(rand_node), 1)[0]
        qs = ['ask', 'confirm']
        for q in qs:
            assert q in nlg.nlgf
        action_type = random.sample(qs, 1)[0]
        actions.append({'type': action_type, 'about': rand_rel})
        return actions

    def _elisa_actions(self, state):
        actions = []
        history = state['history']
        for t in history[::-1]:
            if t[0] == 'mention':
                user_id, timestamp, w, tags = t[1:]
                if datetime.datetime.utcnow() - datetime.datetime.fromtimestamp(timestamp) < self.reply_timeout:
                    actions.append({'type':'ask','about': (w, None, None), 'context': {'tags': tags, 'user': user_id}})
                    break  # FIXME choose only first action -> some smarter way of choosing actions
        return actions

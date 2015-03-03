#!/usr/bin/env python
# encoding: utf-8
import datetime
import random

import cbot.bot


class State(object):
    form = {'phase': ['greeting', 'elisa', 'asking'], 'history': []}
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

    def update_state(self, msg, known_mentions, unknown_mentions):
        timestamp, user_id = msg['time'], msg['user']
        greeting_words = set(msg['utterance'].split()) & State.greetings
        if len(greeting_words) > 0 and len(known_mentions) == 0:
            self.belief['phase'] = 'greeting'
            for w in greeting_words:
                self.belief['history'].append((user_id, timestamp, w))

        self._validate_state()


class Policy(object):
    def __init__(self, logger=None):
        self.model = None
        self.reply_timeout = datetime.timedelta(days=0, seconds=2)
        if logger is None:
            self.logger = cbot.bot.get_chatbot_logger()
        else:
            self.logger = logger
        self._change_prob_t = 0.0

    # def get_feedback(self, score, action_id):
    # """It is probably more efficient split the training into another file """

    def act(self, belief, kb):
        """TODO work with time and implement simple model of needs and attention:

        Need is gradually increasing until its fulfilled and reset.
        Think hunger, sex, thirst, ...

        Attention is highest just after sensing a stimulus and fades away.
        The stimuli must vary to keep attention.
        """
        actions = []
        if belief['phase'] == 'update':
            # special symbol does not directly generate action, but the act method continues after that!
            new_belief_values = belief['new_belief_values']
            for k, v in new_belief_values:
                belief[k] = v

        # From now on we do not change the belief directly, action need to be generated
        phase = belief['phase']
        if phase == 'greeting':
            self.logger.info('Choose greeting action')
            belief['phase'] = 'asking'
            self.logger.debug('after action greeting changing belief to %s', belief['phase'])
            return [{'type': 'greeting'}]
        elif phase == 'elisa':
            return self._elisa_actions(belief)
        elif phase == 'asking':
            return self._ask_actions(belief, kb)
        else:
            self.logger.error('Unknown phase type')
            return []

    def _ask_actions(self, state, kb):
        actions = []
        self.logger.debug("Pursue your own goal: get knowledge about something")
        # get fact to ask about FIXME interesting choice for user
        nodes = kb.get_nodes()
        rand_node = random.sample(nodes, 1)[0]
        self.logger.debug('Sample node %s', rand_node)
        rand_rel = random.sample(kb.get_neighbours(rand_node), 1)[0]
        mask = [random.randrange(0, 2) for _ in xrange(3)]
        rand_rel = tuple([x if m == 0 else None for x, m in zip(rand_rel, mask)])
        qs = ['ask', 'confirm']
        action_type = random.sample(qs, 1)[0]
        assert action_type in cbot.nlg.Nlg.get_default_actions()
        actions.append({'type': action_type, 'about': rand_rel})
        return actions

    def _elisa_actions(self, state):
        actions = []
        history = state['history']
        for t in history[::-1]:
            if t[0] == 'mention':
                user_id, timestamp, w, tags = t[1:]
                if datetime.datetime.utcnow() - datetime.datetime.fromtimestamp(timestamp) < self.reply_timeout:
                    actions.append(
                        {'type': 'ask', 'about': (w, None, None), 'context': {'tags': tags, 'user': user_id}})
                    break  # FIXME choose only first action -> some smarter way of choosing actions
        return actions

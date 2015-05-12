#!/usr/bin/env python
# encoding: utf-8
from __future__ import division, unicode_literals
from collections import OrderedDict
from cbot.parse.pos import PerceptronTagger, POSR


class Utterance(str):
    pos_tagger = PerceptronTagger()
    pos_tagger.load()

    def __init__(self, raw_utt):
        self._tokens, self._pos = None, None
        self.prob = 1.0
        super(Utterance, self).__init__(raw_utt)

    @property
    def tokens(self):
        if self._tokens is None:
            self._tokens = self.strip().split()
        return self._tokens

    @property
    def pos(self):
        if self._pos is None:
            self._pos = Utterance.pos_tagger.tag(self._tokens)
        return self._pos

    def svo(self):
        """subject verb object position"""
        subj, verb, obj = None, None, None
        for i, pos in enumerate(self.pos):
            if pos == POSR['pronoun'] or pos == POSR['proper noun'] or pos == POSR['noun']:
                if subj is None:
                    subj = i
                else:
                    obj = i
            if pos == POSR['verb']:
                verb = i
        return subj, verb, obj


class SimpleTurnState(object):
    # TODO state where I can decide what to keep and what to throw away
    # Action may remove the "feature from state" e.g.
    # ('request', 'food', 'chinese') & (inform, location, London) &
    # & action: inform about cheap chinese restaurant in London
    #
    # The SLU understanding should be capable of mapping to the same  n

    def __init__(self):
        # (k, v) dictionary: k = incremental, v
        self._k_max = 0
        self.belief = {}

        # Indexes to state structure - low level features
        self.current_user_utterance = Utterance("")
        self.history = []
        self.mentions = OrderedDict()  # ((fact, relation, fact2), (probability, [action]) dictionary
        self.system_actions = OrderedDict()  # Keys are action type == class_names
        self.user_actions = OrderedDict()  # Keys are action type == class_names
        self.user_actions_unprocessed = OrderedDict()
        # self.system_actions_intended = OrderedDict()  # TODO is it that much useful store explicitly considered choices?

    def add_belief(self, b):
        # TODO implement class with property id (throw exception if used and not set before or set twice)
        # TODO derive all objects stored in self.belief from that class
        b.id = self._k_max
        self._k_max += 1
        self.belief[b.id] = b

    @property
    def last_system_action(self):
        return reversed(self.system_actions).next()

    @property
    def last_user_action(self):
        return reversed(self.user_actions).next()

    @property
    def last_mention(self):
        return reversed(self.mentions).next()

    @property
    def last_user_action(self):
        pass

    @property
    def last_system_action(self):
        pass

    def last_mentions(self):
        return reversed(self.mentions)

    def update_state(self, msg, known_mentions, unknown_mentions):
        if len(self.history) > 1000:  # FIXME handle history in more robust way
            self.history.pop(0)
        self.history.append(self.belief)
        TODO

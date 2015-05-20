#!/usr/bin/env python
# encoding: utf-8
from __future__ import division, unicode_literals
from collections import OrderedDict
import sys
from cbot.dm.actions import BaseAction
from cbot.lu.pos import PerceptronTagger, POSR
from collections import defaultdict
from sys.float_info import epsilon


class Utterance(str):
    pos_tagger = PerceptronTagger()
    pos_tagger.load()

    def __init__(self, raw_utt):
        super(Utterance, self).__init__(raw_utt)
        self._tokens, self._pos = None, None
        self.prob = 1.0

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

    def __init__(self, trans_datmat=None):
        # (k, v) dictionary: k = incremental, v
        self._k_max = 0
        self.belief = {}

        # Indexes to state structure - low level features
        self.history = {}
        self._current_user_utterance = Utterance("")

        # ((fact, relation, fact2), probability) dictionary simple bayesian update:
        # See Comparison of Bayesian Discriminative and Generative Models for Dialogue State Tracking
        # Lukáš Žilka,David Marek,Matěj Korvas, Filip Jurčíček; equation (5)
        self.mentions = defaultdict(int)
        self.system_actions = OrderedDict()  # Keys are action type == class_names
        self.user_actions = OrderedDict()  # Keys are action type == class_names

        self._backup_attributes = ['current_user_utterance', 'mentions', 'system_actions', 'user_actions']

        self._trans_prob_mentions = 0.0  # P(triplet is mentioned|triplet was mention)
        if trans_datmat is not None:
            trans_datmat = defaultdict(trans_datmat)
        else:
            self._trans_datmat = defaultdict(int) # DAT(Dialogue Act Type) transition matrix: P(d_t | d_(t-1))
            dat_len = len(BaseAction.__subclasses__())
            for dat1 in BaseAction.__subclasses__():
                for dat2 in BaseAction.__subclasses__():
                    self._trans_datmat = 1.0 / (dat_len * dat_len)
        # validate
        for dat1 in BaseAction.__subclasses__():
            out_prob = 0
            for dat2 in BaseAction.__subclasses__():
                t_prob = self._trans_datmat[(dat1, dat2)]
                assert 0 <= t_prob <= 1.0
                out_prob += t_prob
            assert abs(out_prob - 1.0) <= 1 + epsilon


    def add_belief(self, b):
        # TODO implement class with property id (throw exception if used and not set before or set twice)
        # TODO derive all objects stored in self.belief from that class
        b.id = self._k_max
        self._k_max += 1
        self.belief[b.id] = b

    @property
    def num_turns(self):
        return len(self.history)

    @property
    def current_user_utterance(self):
        return self._current_user_utterance

    @property.setter
    def current_user_utterance(self, value):
        if isinstance(value, str):
            self._current_user_utterance = Utterance(value)
        elif isinstance(value, Utterance):
            self._current_user_utterance = value
        else:
            raise ValueError()

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

    def update_state_user(self, mentions, dats, utterances, dat_utt_probs):
        # TODO We do not model interaction between action and triplets nor change of topic.
        # TODO In general some actions should boost similar mentions YesNoAsk & Confirm, Ask & Inform
        # TODO Inform & Ask may introduce more uncertainty -> shallow distributions etc
        # TODO Change of topic if confirm should stop propagating probabilities from previous turns.
        # TODO we can smooth the history back and forth and detect mutually exclusive actions (Hard)
        # TODO implement forgetting by discriminating between high and low probable distribution
        #       - something like if max_prob = 1.1 * max_prob & normalize others

        # simple discriminative bayesian update for mentions
        for triplet, probability in mentions.iteritems():
            if probability == 0.0:
                self.mentions.pop(triplet, 0.0)
                continue
            self.mentions[triplet] = probability + (1 - probability) * self._trans_prob_mentions


        # DAT (Dialogue Action Type)
        # Assumption - all mentions have same type.
        # TODO action detection, and action separation (too simplistic one utterance = one dat)
        for dat in dats:
            unnormalized = defaultdict(int)
            for utt in utterances:
                unnormalized[utt] = dat_utt_probs[(dat,utt)] * utt.prob
            norm = sum(unnormalized.values())






            self.user_actions[action] = (action_types_prob[action] / norm, action_types_list[action])

        snapshot = {}
        for att in self._backup_attributes:
            snapshot[att] = getattr(self, att)
        self.history[self.num_turns + 1] = snapshot

    def update_state_system(self, action):
        pass

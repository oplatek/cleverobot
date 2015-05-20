#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals, division
import logging
import numpy as np
from cbot.dm.actions import NoOp, BaseAction
from cbot.dm.state import Utterance
from cbot.lu.pos import POSR


def sample(items, probabilities, n=1):
    assert len(items) == len(probabilities)
    norm = sum(probabilities)
    norm_prob = [p / norm for p in probabilities]
    return np.random.choice(items, n, norm_prob, replace=False)



class RuleBasedPolicy(object):

    def __init__(self, kb, state):
        self.kb = kb
        self.state = state
        # self.logger = logging.getLogger(self.__module__)  # TODO self class/module
        self.logger = logging.getLogger(self.__class__)  # TODO self class/module

    def act(self):
        """TODO work with time and implement simple model of needs and attention:

        Need is gradually increasing until its fulfilled and reset.
        Think hunger, sex, thirst, ...

        Attention is highest just after sensing a stimulus and fades away.
        The stimuli must vary to keep attention.
        """



        winner = NoOp(self.state, "system")  # TODO remove
        return winner

    def _extract_mentions(utt):
        assert isinstance(utt, Utterance)
        svo_prob = 0.7
        mentions = []
        while all(i is not None for i in utt.svo()):
            s, v, o = [utt.tokens[i] for i in utt.svo()]  # Subject Verb Object
            min_i, max_i = min(utt.svo()), max(utt.svo())
            if "not" in utt.tokens[min_i, max_i]:
                svo_prob = 1.0 - svo_prob  # negation detected
            mentions.append((s, v, o), svo_prob)
            utt = utt[max_i + 1:]
        # TODO boost probability for known facts, relations
        return mentions

    def update_state(self, utt):
        """Perform NLU preprocessing before updating the state"""
        # TODO bayesian udpate for facts
        # TODO HMM for dialogue act types based on facts and used generative model for NLG
        actions = []
        for action_type in BaseAction.__subclasses__():
            actions.extend(action_type.user_action_detection_factory())
        TODO update



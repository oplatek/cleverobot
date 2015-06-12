#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals, division
import logging
from scipy import stats
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
        actions = []
        for action_type in BaseAction.__subclasses__():
            actions.extend(action_type.reaction_factory())

        probabilities = [a.value for a in actions]

        action_index_distribution = stats.rv_discrete(name='custm', values=(range(len(actions)), probabilities))
        sample_a = actions[action_index_distribution.rvs(size=1)]

        self.state.update_system_action(sample_a)
        sample_a.act()

    def update_state(self, utt):
        """Perform NLU preprocessing before updating the state"""

        # TODO ?implement interface? - so far this order is fixed
        self.state.update_mentions(utt)
        actions = self.state.update_dat(utt)
        self.state.update_user_action(actions)

#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals, division
import cbot.dm.actions as act
import numpy as np


def sample(items, probabilities, n=1):
    assert len(items) == len(probabilities)
    norm = sum(probabilities)
    norm_prob = [p / norm for p in probabilities]
    return np.random.choice(items, n, norm_prob, replace=False)


class RuleBasedPolicy(object):

    def __init__(self, kb, logger):
        self.greeting = act.Greeting()
        self.goodbye = act.Goodbye()
        self.elisaask = act.ElisaAsk()
        self.kbrandomask = act.KBRandomAsk(kb)
        self.kbmenttionask = act.KBMentionAsk(kb)
        self.displayimage = act.DisplayImage()
        self.logger = logger

    def act(self, state, kb):
        """TODO work with time and implement simple model of needs and attention:

        Need is gradually increasing until its fulfilled and reset.
        Think hunger, sex, thirst, ...

        Attention is highest just after sensing a stimulus and fades away.
        The stimuli must vary to keep attention.
        """
        belief = state.belief
        actions = []
        if self.greeting.compatibility_probability(state) > 0.5:
            actions.extend(self.greeting.act(state))
        if self.displayimage.need_probability(state) > 0.5:
            actions.extend(self.displayimage.act(state))
        if len(belief['known_mentions']) > 0:
            actions.extend(self.kbmenttionask.act(state))
        elif len(belief['unknown_mentions']) > 0:
            actions.extend(self.elisaask.act(state))
        elif len(belief['known_mentions']) == 0 and len(belief['unknown_mentions']) == 0:
            actions.extend(self.kbrandomask.act(state))
        return actions

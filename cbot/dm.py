#!/usr/bin/env python
# encoding: utf-8


class State(object):
    form = { 'phase' : ['greeting', 'elisa', 'asking'] }

    def __init__(self):
        self.values = { 'phase': 'greeting' }
        # TODO validate json schema of state

    def update_state(self, msg, anotation):
        pass


class Strategy(object):
    def __init__(self):
        self.model = None

    def get_feedback(self, score, action_id):
        '''It is probably more eficient split the training into another file'''
        pass

    def choose_action(self):
        '''TODO work with time and implement simple model of needs and attention:

        Need is gradually increasing until its fullfilled and reseted. 
        Think hunger, sex, thirst, ...

        Attention is highest just after sensing a stimulus and fades away.
        The stimuli must vary to keep attention.
        '''

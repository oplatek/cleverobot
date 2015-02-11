#!/usr/bin/env python
# encoding: utf-8
from parsing import parse


class KnowledgeBase(object):
    def __init__(self):
        self._facts = set([]) 
        self._trip = {}  # set of triples (a, r, c)
        self._rtrip = {}  # the same triples reverse (c, r, a)

    def get(self, arg1, arg2=None, arg3=None):
        pass

    def add_fact(self, ent):
        self._facts.add(ent)

    def add_triplet(self, entA, rel, entB):
        self._trip[entA] = (entA, rel, entB)
        self._rtrip[entB] = (entA, rel, entB)
        self._facts.add(entA)
        self._facts.add(entB)


def parse_to_kb(utterance, kb):
    ''' 
    TODO also use time and user specific information
    '''
    tokens, tags = parse(utterance)
    annotation = (utterance, tokens, tags)
    return annotation

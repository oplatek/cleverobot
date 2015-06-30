#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals

import pickle
from cbot.kb.kb_data import data
from collections import defaultdict


class KnowledgeBase(object):
    def __init__(self):
        self._trip = defaultdict(set)  # set of triples (a, r, c)
        self._rtrip = defaultdict(set)  # the same triples reverse (c, r, a)

    def load_default_models(self):
        self.add_triplets(data)

    def get_nodes(self):
        return self._trip.keys()

    def get_neighbours(self, node, reverse=False):
        if reverse:
            return self._rtrip[node]
        else:
            return self._trip[node]

    def is_head(self, f):
        if len(self.get_neighbours(f)) > 0:
            return True
        else:
            return False

    def is_tail(self, f):
        if len(self.get_neighbours(f, reverse=True)) > 0:
            return True
        else:
            return False

    def add_triplet(self, entA, rel, entB):
        self._trip[entA].add((entA, rel, entB))
        self._rtrip[entB].add((entA, rel, entB))

    def add_triplets(self, triplets):
        for a, r, b in triplets:
            self.add_triplet(a, r, b)

    def extract_triples(self):
        triples = set([])
        for trips in self._trip.itervalues():
            triples = triples | trips
        return triples

    def dump(self, file_name):
        triples = self.extract_triples()
        pickle.dump(triples, file_name)

    def load(self, file_name):
        while True:
            try:
                triples = pickle.load(file_name)
            except EOFError:
                break
            else:
                self.add_triplets(triples)


def generate_subseqs(s):
    subs = []
    for d in range(len(s), 0, -1):
        for i in range(len(s) - d + 1):
            subs.append((s[i:i + d], i, i + d))
    return subs

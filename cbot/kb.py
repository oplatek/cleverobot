#!/usr/bin/env python
# encoding: utf-8

# require POS trained model
from parse.pos import PerceptronTagger

import pickle
from kb_data import data
from collections import defaultdict


class KnowledgeBase(object):
    def __init__(self):
        self._facts = set([])
        self._trip = defaultdict(set)  # set of triples (a, r, c)
        self._rtrip = defaultdict(set)  # the same triples reverse (c, r, a)

        self.tagger = PerceptronTagger()

    def _load_default_models(self):
        self.add_triplets(data)
        self.tagger.load()

    def get_nodes(self):
        return self._trip.keys()

    def get_neighbours(self, node, reverse=False):
        if reverse:
            return self._rtrip[node]
        else:
            return self._trip[node]

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

    def dump(self, file):
        triples = self.extract_triples()
        pickle.dump(triples, file)

    def load(self, file):
        while True:
            try:
                triples = pickle.load(file)
            except EOFError:
                break
            else:
                self.add_triplets(triples)

    def parse_to_kb(self, utterance, kb):
        """TODO also use time and user specific information."""
        tokens = utterance.strip().split()
        tags = self.tagger.tag(tokens)
        annotation = (utterance, tokens, tags)
        return annotation


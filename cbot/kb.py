#!/usr/bin/env python
# encoding: utf-8

# Required data files are:
#   * maxent_treebank_pos_tagger" in Models
import nltk
import pickle
from kb_data import data
from collections import defaultdict


class KnowledgeBase(object):
    def __init__(self):
        self._trip = defaultdict(set)  # set of triples (a, r, c)
        self._rtrip = defaultdict(set)  # the same triples reverse (c, r, a)
        # add basic data

    def get_nodes(self):
        return self._trip.keys()

    def get_neighbours(self, node, rev=False):
        """
        :type rev: Boolean
        """
        if rev:
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

    def load(self,file):
        while True:
            try:
                triples = pickle.load(file)
            except EOFError:
                break
            else:
                self.add_triplets(triples)


def parse(utterance):
    annotation = []
    tokens = nltk.wordpunct_tokenize(utterance)
    tags = nltk.pos_tag(tokens)
    assert len(tags) == len(tokens)
    return (tokens, tags) 


def parse_to_kb(utterance, kb):
    ''' 
    TODO also use time and user specific information
    '''
    tokens, tags = parse(utterance)
    annotation = (utterance, tokens, tags)
    return annotation


def generate_utt(action, kb):
    pass

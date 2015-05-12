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

    def known_mentions(self, tokens, tags):
        """TODO also use time and user specific information.
        Work with negation for start just store it when negation detected (let ask user for the focus).
        """

        TODO
        phrases = generate_subseqs(tokens)
        facts_in_sentence = []
        for p, start, end in phrases:
            p_string = ' '.join(p)
            if self.is_head(p_string) or self.is_tail(p_string):
                facts_in_sentence.append((start, end, p_string))
        # FIXME detect verbs/NE in more robust way
        verbs = dict([(i, tokens[i]) for i, t in enumerate(tags) if t == 'VERB'])
        nouns = dict([(i, tokens[i]) for i, t in enumerate(tags) if t == 'NOUN' or t == 'PROPN'])

        known_mentions = []
        for sstart, send, sf in facts_in_sentence:
            compat_facts = [(s, f) for s, e, f in facts_in_sentence if s >= send]
            compat_verbs_trip = []
            for end_start, end_fact in compat_facts:
                for k in verbs:
                    if send <= k < end_start:
                        compat_verbs_trip.append((sf, verbs[k], end_fact))  # FIXME add distance as feature?
            if not compat_facts:
                known_mentions.append((sf, None, None))
            elif not compat_verbs_trip:
                known_mentions.extend([(sf, None, ef) for _, ef in compat_facts])
            else:
                known_mentions.extend(compat_facts)

        return known_mentions


def generate_subseqs(s):
    subs = []
    for d in range(len(s), 0, -1):
        for i in range(len(s) - d + 1):
            subs.append((s[i:i + d], i, i + d))
    return subs

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
        """TODO also use time and user specific information.
        Work with negation for start just store it when negation detected (let ask user for the focus).
        """

        tokens = utterance.strip().split()
        tags = self.tagger.tag(tokens)
        phrases = generate_subseqs(tokens)
        facts_in_sentence = []
        for p, start, end in phrases:
            p_string = ' '.join(p)
            if p_string in self._facts:
                facts_in_sentence.append((start, end, p_string))
        # FIXME detect verbs/NE in more robust way
        verbs = dict([(i, tokens[i]) for i, t in enumerate(tags) if t == 'VERB'])
        nouns = dict([(i, tokens[i]) for i, t in enumerate(tags) if t == 'NOUN'])

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

        unknown_mentions = []
        noun_pairs_keys = [(i, j) for i, j in zip(nouns.keys(), nouns.keys()) if i < j]
        for i, j in noun_pairs_keys:
            unknown_mentions.extend([(nouns[i], verbs[k], nouns[j]) for k in verbs.keys() if i < k < j])

        return known_mentions, unknown_mentions


def generate_subseqs(s):
    subs = []
    for d in range(len(s), 0, -1):
        for i in range(len(s) - d + 1):
            subs.append((s[i:i + d], i, i + d))
    return subs

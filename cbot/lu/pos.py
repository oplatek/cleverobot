#!/usr/bin/env python
# encoding: utf-8
# source: https://github.com/sloria/textblob-aptagger/blob/master/textblob_aptagger/taggers.py
# MIT license
from __future__ import division, unicode_literals
from itertools import izip
import os
import random
import pickle
from collections import defaultdict
from perceptron import Perceptron
import logging


START = ['-START-', '-START2-']
END = ['-END-', '-END2-']

# Use universal dependencies pos - assumed elsewhere
# See http://universaldependencies.github.io/docs/
POS = {
    'adj': 'adjective',
    'ADP': 'adposition',
    'ADV': 'adverb',
    'AUX': 'auxiliary verb',
    'CONJ': 'coordinating conjunction',
    'DET': 'determiner',
    'INTJ': 'interjection',
    'NOUN': 'noun',
    'NUM': 'numeral',
    'PART': 'particle',
    'PRON': 'pronoun',
    'PROPN': 'proper noun',
    'PUNCT': 'punctuation',
    'SCONJ': 'subordinating conjunction',
    'SYM': 'symbol',
    'VERB': 'verb',
    'X': 'other',
}


POSR = {y:x for x, y in POS.iteritems()}


class DefaultList(list):
    """A list that returns a default value if index out of bounds."""

    def __init__(self, default=None):
        self.default = default
        list.__init__(self)

    def __getitem__(self, index):
        try:
            return list.__getitem__(self, index)
        except IndexError:
            return self.default


class PerceptronTagger(object):
    """Greedy Averaged Perceptron tagger"""
    model_loc = os.path.join(os.path.dirname(__file__), 'tagger.pickle')  # TODO make it symmetric for store/load

    def __init__(self, classes=None, load=True):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)
        self.tagdict = {}
        if classes:
            self.classes = classes
        else:
            self.classes = set()
        self.model = Perceptron(self.classes)
        if load:
            self.load(PerceptronTagger.model_loc)

    def tag(self, words):
        prev, prev2 = START
        tags = DefaultList('')
        context = START + [self._normalize(w) for w in words] + END
        for i, word in enumerate(words):
            tag = self.tagdict.get(word)
            if not tag:
                features = self._get_features(i, word, context, prev, prev2)
                tag = self.model.predict(features)
            tags.append(tag)
            prev2, prev = prev, tag
        return tags

    def train(self, sentences, nr_iter=5):
        '''Train a model from sentences, and save it at save_loc. nr_iter
        controls the number of Perceptron training iterations.'''
        self._make_tagdict(sentences)
        self.model = Perceptron(self.classes)

        for iter_ in range(nr_iter):
            c, t = 0, 0
            for words, tags in sentences:
                sc, st = self.train_one(words, tags)
                c, t = c + sc, t + st
            random.shuffle(sentences)
            self.logger.debug("Iter {0}: {1}/{2}={3}".format(iter_, c, t, c / t))

    def save(self, loc=None):
        if loc is None:
            loc = PerceptronTagger.model_loc
        # Pickle as a binary file
        pickle.dump((self.model.weights, self.tagdict, self.classes),
                    open(loc, 'wb'), -1)

    def train_one(self, words, tags):
        prev, prev2 = START
        context = START + [self._normalize(w) for w in words] + END
        c, t = 0, 0
        for i, word in enumerate(words):
            guess = self.tagdict.get(word)
            if not guess:
                feats = self._get_features(i, word, context, prev, prev2)
                guess = self.model.predict(feats)
                self.model.update(tags[i], guess, feats)
            c, t = c + (guess == tags[i]), t + 1
            prev2, prev = prev, guess
        return c, t

    def load(self, loc=None):
        if loc is None:
            loc = PerceptronTagger.model_loc
        w_td_c = pickle.load(open(loc, 'rb'))
        self.model.weights, self.tagdict, self.classes = w_td_c
        self.model.classes = self.classes

    def _normalize(self, word):
        if '-' in word and word[0] != '-':
            return '!HYPHEN'
        elif word.isdigit() and len(word) == 4:
            return '!YEAR'
        elif word[0].isdigit():
            return '!DIGITS'
        else:
            return word.lower()

    def _get_features(self, i, word, context, prev, prev2):
        '''Map tokens into a feature representation, implemented as a
        {hashable: float} dict. If the features change, a new model must be
        trained.'''

        def add(name, *args):
            features[' '.join((name,) + tuple(args))] += 1

        i += len(START)
        features = defaultdict(int)
        # It's useful to have a constant feature, which acts sort of like a prior
        add('bias')
        add('i suffix', word[-3:])
        add('i pref1', word[0])
        add('i-1 tag', prev)
        add('i-2 tag', prev2)
        add('i tag+i-2 tag', prev, prev2)
        add('i word', context[i])
        add('i-1 tag+i word', prev, context[i])
        add('i-1 word', context[i - 1])
        add('i-1 suffix', context[i - 1][-3:])
        add('i-2 word', context[i - 2])
        add('i+1 word', context[i + 1])
        add('i+1 suffix', context[i + 1][-3:])
        add('i+2 word', context[i + 2])
        return features

    def _make_tagdict(self, sentences):
        '''Make a tag dictionary for single-tag words.'''
        counts = defaultdict(lambda: defaultdict(int))
        for sent in sentences:
            for word, tag in zip(sent[0], sent[1]):
                counts[word][tag] += 1
                self.classes.add(tag)
        freq_thresh = 20
        ambiguity_thresh = 0.97
        for word, tag_freqs in counts.items():
            tag, mode = max(tag_freqs.items(), key=lambda item: item[1])
            n = sum(tag_freqs.values())
            # Don't add rare words to the tag dictionary
            # Only add quite unambiguous words
            if n >= freq_thresh and (mode / n) >= ambiguity_thresh:
                self.tagdict[word] = tag

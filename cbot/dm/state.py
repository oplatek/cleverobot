#!/usr/bin/env python
# encoding: utf-8
from __future__ import division, unicode_literals
from collections import OrderedDict
import operator
from cbot.dm.actions import BaseAction
from cbot.lu.pos import PerceptronTagger, POSR
from collections import defaultdict
epsilon = 0.00000001


class Utterance(str):
    pos_tagger = PerceptronTagger()
    pos_tagger.load()

    def __init__(self, raw_utt):
        super(Utterance, self).__init__(raw_utt)
        self._tokens, self._pos = None, None
        self.prob = 1.0

    @property
    def tokens(self):
        if self._tokens is None:
            self._tokens = self.strip().split()
        return self._tokens

    @property
    def pos(self):
        if self._pos is None:
            self._pos = Utterance.pos_tagger.tag(self._tokens)
        return self._pos

    def svo(self):
        """subject verb object position"""
        subj, verb, obj = None, None, None
        for i, pos in enumerate(self.pos):
            if pos == POSR['pronoun'] or pos == POSR['proper noun'] or pos == POSR['noun']:
                if subj is None:
                    subj = i
                else:
                    obj = i
            if pos == POSR['verb']:
                verb = i
        return subj, verb, obj


class SimpleTurnState(object):
    # TODO state where I can decide what to keep and what to throw away
    # Action may remove the "feature from state" e.g.
    # ('request', 'food', 'chinese') & (inform, location, London) &
    # & action: inform about cheap chinese restaurant in London
    #
    # The SLU understanding should be capable of mapping to the same  n

    def __init__(self, dat_trans_prob):
        # Indexes to state structure - low level features
        self.history = {}
        self._current_user_utterance = Utterance("")

        self._trans_prob_mentions = 0.0  # P(triplet is mentioned|triplet was mention)
        self.dat_trans_prob = dat_trans_prob  # TODO use LM or HMM for modeling transition probabilities

        self.user_vs_system_history = []  #
        self.system_actions = OrderedDict()  # Keys are action type == class_names
        self.user_dat = defaultdict(int)  # P(d_t | utt_t, d_{t-1}, utt_{t-1}, d_{t-2}, utt_{t-2}, ...)
        self.user_mentions = defaultdict(int)
        self.user_actions = OrderedDict()  # Keys are action type == class_names
        self._dat_ngrams = [defaultdict(int)] * self.dat_ngrams_n  # P(d_t, d_{t-1}, d_{t-2} | utt_t, utt_{t-1}, utt_{t-2})

        self._backup_attributes = ['current_user_utterance', 'user_mentions', 'system_actions', 'user_dat', '']

    def dat_lm(self, ngram_tuple):
        # TODO LM modeling of tuples using self.dat_trans_prob
        dat_len = len(BaseAction.__subclasses__())
        return 1.0 / (dat_len * dat_len)

    @property
    def dat_ngrams_n(self):
        # TODO estimate from self.dat_trans_prob
        return 3

    @property
    def num_turns(self):
        return len(self.history)

    @property
    def current_user_utterance(self):
        return self._current_user_utterance

    @property.setter
    def current_user_utterance(self, value):
        if isinstance(value, str):
            self._current_user_utterance = Utterance(value)
        elif isinstance(value, Utterance):
            self._current_user_utterance = value
        else:
            raise ValueError()

    @property
    def last_system_action(self):
        return reversed(self.system_actions).next()

    @property
    def last_user_action(self):
        return reversed(self.user_actions).next()

    @property
    def last_mention(self):
        return reversed(self.user_mentions).next()

    @property
    def last_user_action(self):
        pass

    @property
    def last_system_action(self):
        pass

    def last_mentions(self):
        return reversed(self.user_mentions)

    @staticmethod
    def extract_mentions(utt):
        assert isinstance(utt, Utterance)
        svo_prob = 0.7
        mentions = []
        while all(i is not None for i in utt.svo()):
            s, v, o = [utt.tokens[i] for i in utt.svo()]  # Subject Verb Object
            min_i, max_i = min(utt.svo()), max(utt.svo())
            if "not" in utt.tokens[min_i, max_i]:
                svo_prob = 1.0 - svo_prob  # negation detected
            mentions.append((s, v, o), svo_prob)
            utt = utt[max_i + 1:]
        # TODO boost probability for known facts, relations
        return mentions

    def update_mentions(self, utt):
        """SLU task of extracting user_mentions from utterance"""
        # TODO Inform & Ask may introduce more uncertainty -> shallow distributions etc
        # TODO Change of topic if confirm should stop propagating probabilities from previous turns.
        # TODO we can smooth the history back and forth and detect mutually exclusive actions (Hard)
        # TODO implement forgetting by discriminating between high and low probable distribution
        #       - something like if max_prob = 1.1 * max_prob & normalize others
        mentions = self.__class__.extract_mentions(utt)
        # simple discriminative bayesian update for user_mentions in this context for SLU
        # ((fact, relation, fact2), probability) dictionary simple bayesian update:
        # See Comparison of Bayesian Discriminative and Generative Models for Dialogue State Tracking
        # Lukáš Žilka,David Marek,Matěj Korvas, Filip Jurčíček; equation (5)
        for triplet, probability in mentions.iteritems():
            if probability == 0.0:
                self.user_mentions.pop(triplet, 0.0)
                continue
            self.user_mentions[triplet] = probability + (1 - probability) * self._trans_prob_mentions

    def update_dat(self, utt, alpha=0.5):
        """SLU task of determining Dialogue Act Types (DAT) for utterance.
        Assumes that utt is a sentence or another chunk of words which has unique DAT."""
        actions = []
        for action_type in BaseAction.__subclasses__():
            actions.extend(action_type.user_action_detection_factory())

        # heuristics
        dat_types_likelihood = defaultdict(int)
        for act in actions:
            dat_types_likelihood[type(act)] += act.value
        norm = sum(dat_types_likelihood.values())
        for t in dat_types_likelihood:
            dat_types_likelihood[t] /= norm
        # keeping all ngrams with probabilities
        n = len(self._dat_ngrams)
        self._dat_ngrams.pop(0)
        self._dat_ngrams.append(dat_types_likelihood)
        assert (len(self._dat_ngrams) == n)
        # computing new probabilties of DAT based on ngrams probabilities(observation & LM) from scratch
        finished, indexes, items_count = False, [0] * n, [len(dat_ngrams) for dat_ngrams in self._dat_ngrams]
        dat_ngrams = [dat_ngrams.iteritems() for dat_ngrams in self._dat_ngrams]
        while not finished:
            ngram_obs_probs = (dat_ngrams[i][indexes[i]] for i in range(n))
            overflow_check, i = True, 0
            while overflow_check:
                if indexes[i] == items_count[i]:
                    if i == len(indexes) - 1:
                        assert (indexes[-1] == items_count[-1])
                        finished = True
                        break
                    indexes[i], indexes[i + 1], i = 0, indexes[i + 1] + 1, i + 1
                else:
                    overflow_check = False
            ngram_obs_prob, ngram = zip(*ngram_obs_probs)
            ngram_obs_prob = sum(ngram_obs_prob)
            ngram_prob = self.dat_lm(ngram)
            self.user_dat[ngram[-1]] += ngram_prob * ngram_obs_prob
        norm = sum((prob for prob in self.user_dat.itervalues()))
        for d in self.user_dat:
            self.user_dat[d] /= norm
        return actions

    def update_user_action(self, actions):
        # Just reranker right now # TODO fix
        # First extract best DAT
        best_d, d_prob = max(self.user_dat, key=operator.itemgetter(1))  # argmax
        assert(best_d is not None)
        matching_d_actions = [a for a in actions if isinstance(a, best_d)]
        assert(len(matching_d_actions) > 0)

        def score_mult_args(scores):
            return max(scores) + (sum(scores) / len(scores))

        # score a based on its arguments
        actions_scored = {}
        for a in matching_d_actions:
            scores = (self.user_mentions[triplet] for triplet in a.args.itervalues() if triplet in self.user_mentions)
            actions_scored[a] = score_mult_args(scores)
        best_a = max(actions_scored, key=operator.itemgetter(1))
        self.user_actions.append(best_a)

        # TODO Force consistency  e.g. confirm(X) & reject(X) is not allowed, also it should be mostly handled by the LM
        # TODO under assumption of common arguments X

        self.user_vs_system_history.append(True)  # user input
        assert(len(self.user_actions) + len(self.system_actions) == len(self.user_vs_system_history))

    def update_system_action(self, action):
        self.system_actions.append(action)
        self.user_vs_system_history.append(False)  # user input
        assert(len(self.user_actions) + len(self.system_actions) == len(self.user_vs_system_history))

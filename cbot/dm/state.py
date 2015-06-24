#!/usr/bin/env python
# encoding: utf-8
from __future__ import division, unicode_literals
from collections import OrderedDict
import operator
from cbot.dm.actions import BaseAction, Reject, Hello, Deny, NoOp
from cbot.lu.pos import PerceptronTagger, POSR
from collections import defaultdict
epsilon = 0.00000001


class Utterance(str):
    pos_tagger = PerceptronTagger()
    pos_tagger.load()

    def __init__(self, raw_utt):
        super(Utterance, self).__init__(raw_utt)
        self._svo, self._tokens, self._pos = None, None, None
        self.prob = 1.0

    def __repr__(self):
        return super(Utterance, self).__str__()

    @property
    def tokens(self):
        if self._tokens is None:
            self._tokens = self.strip().split()
        return self._tokens

    @property
    def pos(self):
        if self._pos is None:
            self._pos = Utterance.pos_tagger.tag(self.tokens)
        return self._pos

    @property
    def svo(self):
        """subject verb object position"""
        if self._svo is None:
            subj, verb, obj = None, None, None
            for i, pos in enumerate(self.pos):
                if pos == POSR['pronoun'] or pos == POSR['proper noun'] or pos == POSR['noun']:
                    if subj is None:
                        subj = i
                    else:
                        obj = i
                if pos == POSR['verb']:
                    verb = i
            self._svo = (subj, verb, obj)
        return self._svo


class SimpleTurnState(object):
    # TODO add KB to the state because
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
        self.user_dat = defaultdict(float)  # P(d_t | utt_t, d_{t-1}, utt_{t-1}, d_{t-2}, utt_{t-2}, ...)
        self.user_mentions = defaultdict(float)
        self.system_mentions = []
        self.user_actions = OrderedDict()  # Keys are action type == class_names, values instances
        self._dat_ngrams = [{NoOp: 1.0}] * self.dat_ngrams_n  # P(d_t, d_{t-1}, d_{t-2} | utt_t, utt_{t-1}, utt_{t-2})

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

    @current_user_utterance.setter
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

    @staticmethod
    def extract_mentions(utt, user_mentions, system_mentions):
        assert isinstance(utt, Utterance)
        svo_prob = 0.7
        mentions = OrderedDict()
        while all(i is not None for i in utt.svo):
            s, v, o = [utt.tokens[i] for i in utt.svo]  # Subject Verb Object
            min_i, max_i = min(utt.svo), max(utt.svo)
            if "not" in utt.tokens[min_i:max_i]:
                svo_prob = 1.0 - svo_prob  # negation detected
            mentions[(s, v, o)] = svo_prob
            utt = Utterance(' '.join(utt.tokens[max_i + 1:]))  # rest of utterance
        # boost probability for known facts, relations based on user_mentions & system_mentions
        for triplet in mentions:
            if triplet in user_mentions or triplet in system_mentions:
                mentions[triplet] = 1.0
        return mentions

    def update_mentions(self):
        """SLU task of extracting user_mentions from utterance"""
        # TODO Inform & Ask may introduce more uncertainty -> shallow distributions etc
        # TODO Change of topic if confirm should stop propagating probabilities from previous turns.
        # TODO we can smooth the history back and forth and detect mutually exclusive actions (Hard)
        # TODO implement forgetting by discriminating between high and low probable distribution
        #       - something like if max_prob = 1.1 * max_prob & normalize others
        mentions = self.__class__.extract_mentions(self.current_user_utterance, self.user_mentions, self.system_mentions)
        # simple discriminative bayesian update for user_mentions in this context for SLU
        # ((fact, relation, fact2), probability) dictionary simple bayesian update:
        # See Comparison of Bayesian Discriminative and Generative Models for Dialogue State Tracking
        # Lukáš Žilka,David Marek,Matěj Korvas, Filip Jurčíček; equation (5)
        for triplet, probability in mentions.items():
            if probability == 0.0:
                del self.user_mentions[triplet]
                continue
            self.user_mentions[triplet] = probability + (1 - probability) * self._trans_prob_mentions

    def update_dat(self, alpha=0.5):
        """SLU task of determining Dialogue Act Types (DAT) for utterance.
        Assumes that utt is a sentence or another chunk of words which has unique DAT."""

        def propagate_overflow(indexes, num_items):
            """Return True if overflowes over highest dimension"""
            assert len(indexes) == len(num_items)
            overflow_check, i = True, len(indexes) - 1
            while overflow_check:
                if indexes[i] == num_items[i]:
                    if i == 0:
                        assert(indexes[0] == num_items[0])
                        return True
                    indexes[i], indexes[i - 1], i = 0, indexes[i - 1] + 1, i - 1
                else:
                    overflow_check = False
            return False

        actions = []
        for action_type in BaseAction.__subclasses__():
            actions.extend(action_type.user_action_detection_factory(self))

        # heuristics
        dat_types_likelihood = defaultdict(float)
        for act in actions:
            dat_types_likelihood[type(act)] += act.value
        norm = sum(dat_types_likelihood.values())
        for t in dat_types_likelihood:
            dat_types_likelihood[t] /= norm
        # keeping all ngrams with probabilities
        n = len(self._dat_ngrams)
        self._dat_ngrams.pop(0)
        self._dat_ngrams.append(dat_types_likelihood)
        assert len(self._dat_ngrams) == n
        # computing new probabilties of DAT based on ngrams probabilities(observation & LM) from scratch
        finished, indexes, items_count = False, [0] * n, [len(dat_ngrams) for dat_ngrams in self._dat_ngrams]
        dat_ngrams = [dat_ngrams.items() for dat_ngrams in self._dat_ngrams]
        while not finished:
            ngram_obs_probs = (dat_ngrams[i][indexes[i]] for i in range(n))  # TODO index out of range
            ngram, ngram_obs_probs = zip(*list(ngram_obs_probs))
            ngram_obs_prob = sum(ngram_obs_probs)
            ngram_prob = self.dat_lm(ngram)
            self.user_dat[ngram[-1]] += ngram_prob * ngram_obs_prob
            indexes[-1] += 1
            finished = propagate_overflow(indexes, items_count)
        norm = sum((prob for prob in self.user_dat.itervalues()))
        for d in self.user_dat:
            self.user_dat[d] /= norm
        # TODO the actions has strange value (equally normalized)
        return actions

    def update_user_action(self, actions):
        # Just reranker right now
        # First extract best DAT
        actions_types = set([type(a) for a in actions])
        user_dat_filtered = [(action_type, prob) for action_type, prob in self.user_dat.iteritems() if action_type in actions_types]
        best_d, d_prob = max(user_dat_filtered, key=operator.itemgetter(1))  # argmax
        assert(best_d is not None)
        matching_d_actions = [a for a in actions if isinstance(a, best_d)]
        assert(len(matching_d_actions) > 0)

        def score_mult_args(scores):
            if len(scores) == 0:
                return 0.5
            max_scores = max(scores)
            assert max_scores <= 1.0
            return max_scores + (sum(scores) / len(scores))

        # score a based on its arguments
        actions_scored = {}
        for a in matching_d_actions:
            scores = [self.user_mentions[triplet] for triplet in a.args.itervalues() if triplet in self.user_mentions]
            actions_scored[a] = score_mult_args(scores)
        best_a, best_a_prob = max(actions_scored.iteritems(), key=operator.itemgetter(1))

        # TODO Force some consistency and reinterpretation
        # TODO use probabilistic attitude e.g. Subtract some probability mass from Reject and distribute it to deny.
        if isinstance(best_a, Reject):
            try:
                last_mention, deny_who = (self.user_mentions[-1], 'deny_user') if self.user_vs_system_history[-1] else (self.system_mentions[-1], 'deny_system')
            except IndexError:
                last_mention = None  # at the beginning
            if len(best_a.args) == 0:
                # Infer the args from last action
                if last_mention is not None:
                    best_a.args = {deny_who: last_mention}
                else:
                    best_a = Hello()  # we are at the beginning so understand Hello() # TODO hack
            else:
                common_mentions = set(best_a.args.values() & (set(self.user_mentions) | set(self.system_mentions)))
                if len(common_mentions) > 0:
                    best_a = Deny()
                    best_a.args = dict([(k, v) for k, v in best_a.args if v in common_mentions])
                else:
                    pass   # keep Reject

        self.user_actions[type(best_a)] = best_a
        self.user_vs_system_history.append(True)  # user input

    def update_system_action(self, action):
        self.system_actions[type(action)] = action
        self.user_vs_system_history.append(False)  # system input
        self.system_mentions.extend(action.args.values())

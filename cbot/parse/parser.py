"""A simple implementation of a greedy transition-based parser. Released under BSD license."""
from itertools import izip
from os import path

import os
from collections import defaultdict
import random
from cbot.parse.perceptron import Perceptron
from cbot.parse.pos import PerceptronTagger, DefaultList
from dependencygraph import DependencyGraph, Node

SHIFT = 0;
RIGHT = 1;
LEFT = 2;
MOVES = (SHIFT, RIGHT, LEFT)

class NonProjectiveException(Exception):
    pass


class Parse(object):
    def __init__(self, n):
        self.n = n
        self.heads = [None] * (n - 1)
        self.labels = [None] * (n - 1)
        self.lefts = []
        self.rights = []
        for i in range(n + 1):
            self.lefts.append(DefaultList(0))
            self.rights.append(DefaultList(0))

    def add(self, head, child, label=None):
        self.heads[child] = head
        self.labels[child] = label
        if child < head:
            self.lefts[head].append(child)
        else:
            self.rights[head].append(child)


class Parser(object):
    def __init__(self, load=True):
        model_dir = os.path.dirname(__file__)
        self.model = Perceptron(MOVES)
        if load:
            self.model.load(path.join(model_dir, 'parser.pickle'))
        self.tagger = PerceptronTagger(load=load)
        self.confusion_matrix = defaultdict(lambda: defaultdict(int))

    def save(self):
        self.model.save(path.join(os.path.dirname(__file__), 'parser.pickle'))
        self.tagger.save()

    def parse(self, words):
        n = len(words)
        i = 2;
        stack = [1];
        parse = Parse(n)
        tags = self.tagger.tag(words)
        while stack or (i + 1) < n:
            features = extract_features(words, tags, i, n, stack, parse)
            scores = self.model.score(features)
            valid_moves = get_valid_moves(i, n, len(stack))
            guess = max(valid_moves, key=lambda move: scores[move])
            i = transition(guess, i, stack, parse)
        return tags, parse.heads

    def train_one(self, itn, words, gold_tags, gold_heads):
        n = len(words)
        i = 2;
        stack = [1];
        parse = Parse(n)
        tags = self.tagger.tag(words)
        while stack or (i + 1) < n:
            features = extract_features(words, tags, i, n, stack, parse)
            scores = self.model.score(features)
            valid_moves = get_valid_moves(i, n, len(stack))
            gold_moves = get_gold_moves(i, n, stack, parse.heads, gold_heads)
            guess = max(valid_moves, key=lambda move: scores[move])
            if len(gold_moves) == 0:
                raise NonProjectiveException('%s is non projective sentence' % words)
            best = max(gold_moves, key=lambda move: scores[move])
            self.model.update(best, guess, features)
            i = transition(guess, i, stack, parse)
            self.confusion_matrix[best][guess] += 1
        return len([i for i in range(n - 1) if parse.heads[i] == gold_heads[i]])

    def train(self, sentences, nr_iter):
        self.tagger.start_training(sentences)
        for itn in range(nr_iter):
            corr = 0;
            total = 0
            random.shuffle(sentences)
            for words, gold_tags, gold_parse, gold_label in sentences:
                corr += self.train_one(itn, words, gold_tags, gold_parse)
                if itn < 5:
                    self.tagger.train_one(words, gold_tags)
                total += len(words)
            print itn, '%.3f' % (float(corr) / float(total))
            if itn == 4:
                self.tagger.model.average_weights()
        print 'Averaging weights'
        self.model.average_weights()


def transition(move, i, stack, parse):
    if move == SHIFT:
        stack.append(i)
        return i + 1
    elif move == RIGHT:
        parse.add(stack[-2], stack.pop())
        return i
    elif move == LEFT:
        parse.add(i, stack.pop())
        return i
    assert move in MOVES


def get_valid_moves(i, n, stack_depth):
    moves = []
    if (i + 1) < n:
        moves.append(SHIFT)
    if stack_depth >= 2:
        moves.append(RIGHT)
    if stack_depth >= 1:
        moves.append(LEFT)
    return moves


def get_gold_moves(n0, n, stack, heads, gold):
    def deps_between(target, others, gold):
        for word in others:
            if gold[word] == target or gold[target] == word:
                return True
        return False

    valid = get_valid_moves(n0, n, len(stack))
    if not stack or (SHIFT in valid and gold[n0] == stack[-1]):
        return [SHIFT]
    if gold[stack[-1]] == n0:
        return [LEFT]
    costly = set([m for m in MOVES if m not in valid])
    # If the word behind s0 is its gold head, Left is incorrect
    if len(stack) >= 2 and gold[stack[-1]] == stack[-2]:
        costly.add(LEFT)
    # If there are any dependencies between n0 and the stack,
    # pushing n0 will lose them.
    if SHIFT not in costly and deps_between(n0, stack, gold):
        costly.add(SHIFT)
    # If there are any dependencies between s0 and the buffer, popping
    # s0 will lose them.
    if deps_between(stack[-1], range(n0 + 1, n - 1), gold):
        costly.add(LEFT)
        costly.add(RIGHT)
    return [m for m in MOVES if m not in costly]


def extract_features(words, tags, n0, n, stack, parse):
    def get_stack_context(depth, stack, data):
        if depth >= 3:
            return data[stack[-1]], data[stack[-2]], data[stack[-3]]
        elif depth >= 2:
            return data[stack[-1]], data[stack[-2]], ''
        elif depth == 1:
            return data[stack[-1]], '', ''
        else:
            return '', '', ''

    def get_buffer_context(i, n, data):
        if i + 1 >= n:
            return data[i], '', ''
        elif i + 2 >= n:
            return data[i], data[i + 1], ''
        else:
            return data[i], data[i + 1], data[i + 2]

    def get_parse_context(word, deps, data):
        if word == -1:
            return 0, '', ''
        deps = deps[word]
        valency = len(deps)
        if not valency:
            return 0, '', ''
        elif valency == 1:
            return 1, data[deps[-1]], ''
        else:
            return valency, data[deps[-1]], data[deps[-2]]

    features = {}
    # Set up the context pieces --- the word (W) and tag (T) of:
    # S0-2: Top three words on the stack
    # N0-2: First three words of the buffer
    # n0b1, n0b2: Two leftmost children of the first word of the buffer
    # s0b1, s0b2: Two leftmost children of the top word of the stack
    # s0f1, s0f2: Two rightmost children of the top word of the stack

    depth = len(stack)
    s0 = stack[-1] if depth else -1

    Ws0, Ws1, Ws2 = get_stack_context(depth, stack, words)
    Ts0, Ts1, Ts2 = get_stack_context(depth, stack, tags)

    Wn0, Wn1, Wn2 = get_buffer_context(n0, n, words)
    Tn0, Tn1, Tn2 = get_buffer_context(n0, n, tags)

    Vn0b, Wn0b1, Wn0b2 = get_parse_context(n0, parse.lefts, words)
    Vn0b, Tn0b1, Tn0b2 = get_parse_context(n0, parse.lefts, tags)

    Vn0f, Wn0f1, Wn0f2 = get_parse_context(n0, parse.rights, words)
    _, Tn0f1, Tn0f2 = get_parse_context(n0, parse.rights, tags)

    Vs0b, Ws0b1, Ws0b2 = get_parse_context(s0, parse.lefts, words)
    _, Ts0b1, Ts0b2 = get_parse_context(s0, parse.lefts, tags)

    Vs0f, Ws0f1, Ws0f2 = get_parse_context(s0, parse.rights, words)
    _, Ts0f1, Ts0f2 = get_parse_context(s0, parse.rights, tags)

    # Cap numeric features at 5? 
    # String-distance
    Ds0n0 = min((n0 - s0, 5)) if s0 != 0 else 0

    features['bias'] = 1
    # Add word and tag unigrams
    for w in (Wn0, Wn1, Wn2, Ws0, Ws1, Ws2, Wn0b1, Wn0b2, Ws0b1, Ws0b2, Ws0f1, Ws0f2):
        if w:
            features['w=%s' % w] = 1
    for t in (Tn0, Tn1, Tn2, Ts0, Ts1, Ts2, Tn0b1, Tn0b2, Ts0b1, Ts0b2, Ts0f1, Ts0f2):
        if t:
            features['t=%s' % t] = 1

    # Add word/tag pairs
    for i, (w, t) in enumerate(((Wn0, Tn0), (Wn1, Tn1), (Wn2, Tn2), (Ws0, Ts0))):
        if w or t:
            features['%d w=%s, t=%s' % (i, w, t)] = 1

    # Add some bigrams
    features['s0w=%s,  n0w=%s' % (Ws0, Wn0)] = 1
    features['wn0tn0-ws0 %s/%s %s' % (Wn0, Tn0, Ws0)] = 1
    features['wn0tn0-ts0 %s/%s %s' % (Wn0, Tn0, Ts0)] = 1
    features['ws0ts0-wn0 %s/%s %s' % (Ws0, Ts0, Wn0)] = 1
    features['ws0-ts0 tn0 %s/%s %s' % (Ws0, Ts0, Tn0)] = 1
    features['wt-wt %s/%s %s/%s' % (Ws0, Ts0, Wn0, Tn0)] = 1
    features['tt s0=%s n0=%s' % (Ts0, Tn0)] = 1
    features['tt n0=%s n1=%s' % (Tn0, Tn1)] = 1

    # Add some tag trigrams
    trigrams = ((Tn0, Tn1, Tn2), (Ts0, Tn0, Tn1), (Ts0, Ts1, Tn0),
                (Ts0, Ts0f1, Tn0), (Ts0, Ts0f1, Tn0), (Ts0, Tn0, Tn0b1),
                (Ts0, Ts0b1, Ts0b2), (Ts0, Ts0f1, Ts0f2), (Tn0, Tn0b1, Tn0b2),
                (Ts0, Ts1, Ts1))
    for i, (t1, t2, t3) in enumerate(trigrams):
        if t1 or t2 or t3:
            features['ttt-%d %s %s %s' % (i, t1, t2, t3)] = 1

    # Add some valency and distance features
    vw = ((Ws0, Vs0f), (Ws0, Vs0b), (Wn0, Vn0b))
    vt = ((Ts0, Vs0f), (Ts0, Vs0b), (Tn0, Vn0b))
    d = ((Ws0, Ds0n0), (Wn0, Ds0n0), (Ts0, Ds0n0), (Tn0, Ds0n0),
         ('t' + Tn0 + Ts0, Ds0n0), ('w' + Wn0 + Ws0, Ds0n0))
    for i, (w_t, v_d) in enumerate(vw + vt + d):
        if w_t or v_d:
            features['val/d-%d %s %d' % (i, w_t, v_d)] = 1
    return features


def _pc(n, d):
    return (float(n) / d) * 100


def read_pos(loc):
    for line in open(loc):
        if not line.strip():
            continue
        words = DefaultList('')
        tags = DefaultList('')
        for token in line.split():
            if not token:
                continue
            word, tag = token.rsplit('/', 1)
            # words.append(normalize(word))
            words.append(word)
            tags.append(tag)
        pad_tokens(words);
        pad_tokens(tags)
        yield words, tags


def read_conll(loc):
    for sent_str in open(loc).read().strip().split('\n\n'):
        lines = [line.split() for line in sent_str.split('\n')]
        words = DefaultList('');
        tags = DefaultList('')
        heads = [None];
        labels = [None]
        for i, (word, pos, head, label) in enumerate(lines):
            words.append(intern(word))
            # words.append(intern(normalize(word)))
            tags.append(intern(pos))
            heads.append(int(head) + 1 if head != '-1' else len(lines) + 1)
            labels.append(label)
        pad_tokens(words);
        pad_tokens(tags)
        yield words, tags, heads, labels


def depgraph_to_pos(dgs):
    return ((words, tags) for words, tags, _, _ in depgraph_to_headlabels(dgs))


def depgraph_to_headlabels(dgs):
    for g in dgs:
        tags, words, heads, labels = [], [], [None], [None]
        for node in g.nodes:
            if node.id == 0:
                assert (node.form is None and node.cpostag == 'root')
                continue
            words.append(node.form)
            tags.append(node.cpostag)
            labels.append(node.deprel)
            heads.append(node.head)
        pad_tokens(words)
        pad_tokens(tags)
        yield words, tags, heads, labels


def heads_to_depgraph(heads, tags, words):
    assert len(tags) == len(words), '%d vs %d' % (len(tags), len(words))
    assert len(heads) + 1 == len(tags), '%d vs %d' % (len(heads), len(tags))
    g = DependencyGraph(n=len(words) - 2)
    for i, (w, h, t) in enumerate(izip(words, heads, tags)):
        if i == 0 and w == '<start>' and h is None:
            # Keep the default node intact
            continue
        else:
            assert (i != 0)
            if words[h] == 'ROOT' or words[h] == 'root':
                h = 0
            n = Node(id=i, form=w, head=h, cpostag=t)
            g.update_node(n)
    return g


def pad_tokens(tokens):
    tokens.insert(0, '<start>')
    tokens.append('ROOT')

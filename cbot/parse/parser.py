"""A simple implementation of a greedy transition-based parser. Released under BSD license."""
from itertools import izip
from os import path

import os
from collections import defaultdict
import random
from cbot.parse.perceptron import Perceptron
from cbot.parse.pos import PerceptronTagger, DefaultList
from dependencygraph import DependencyGraph, Node
import logging

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

def tags_to_dg(words, tags):
    assert len(words) == len(tags)
    dg = DependencyGraph(n=len(words))
    for i, (w, t) in enumerate(izip(words, tags), start=1):
        n = Node(id=i, form=w, cpostag=t)
        dg.update_node(n)
    return dg

class Parser(object):
    def __init__(self, tagger, load=True):
        model_dir = os.path.dirname(__file__)
        self.model = Perceptron(MOVES)
        if load:
            self.model.load(path.join(model_dir, 'parser.pickle'))
        self.tagger = tagger
        self.confusion_matrix = defaultdict(lambda: defaultdict(int))

    def save(self):
        self.model.save(path.join(os.path.dirname(__file__), 'parser.pickle'))
        self.tagger.save()

    def parse(self, words):
        n, i, stack = len(words), 2, [1]
        parse = Parse(n)
        tags = self.tagger.tag(words)
        dg = tags_to_dg(words, tags)
        while stack or (i + 1) < n:
            features = extract_features(dg, i, n, stack, parse)
            scores = self.model.score(features)
            valid_moves = get_valid_moves(i, n, len(stack))
            guess = max(valid_moves, key=lambda move: scores[move])
            i = transition(guess, i, stack, parse)
        # FIXME updating the dependencies from parse -> remove parse and heads
        dg.nodes = [dg.nodes[0]] + dg.nodes[2:-1]  # FIXME discard <start> and <ROOT> from POS
        for child, head in enumerate(parse.heads):
            if head is not None:
                # FIXME <ROOT> was the last element, and we removed 2
                if head == len(dg.nodes) + 1:
                    head = 0
                dg.update_dependency(head, child)
        dg.children_from_nodes()
        return dg

    def train_one(self, itn, gold_graph):
        n = len(gold_graph.nodes - 1)
        i = 2;
        stack = [1];
        parse = Parse(n)
        while stack or (i + 1) < n:
            features = extract_features(gold_graph, i, n, stack, parse)
            scores = self.model.score(features)
            valid_moves = get_valid_moves(i, n, len(stack))
            gold_moves = get_gold_moves(i, n, stack, parse.heads, gold_heads)
            guess = max(valid_moves, key=lambda move: scores[move])
            if len(gold_moves) == 0:
                raise NonProjectiveException('%s is non projective sentence' % gold_graph)
            best = max(gold_moves, key=lambda move: scores[move])
            self.model.update(best, guess, features)
            i = transition(guess, i, stack, parse)
            self.confusion_matrix[best][guess] += 1
        return len([i for i in range(n - 1) if parse.heads[i] == gold_heads[i]])

    def train(self, dep_graphs, nr_iter):
        for itn in range(nr_iter):
            corr = 0;
            total = 0
            random.shuffle(dep_graphs)
            for gold_graph in dep_graphs:
                corr += self.train_one(itn, gold_graph)
                total += len(gold_graph.nodes) - 1
            print itn, '%.3f' % (float(corr) / float(total))
        logging.info('Averaging weights')
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


def extract_features(dg, n0, n, stack, parse):
    def get_stack_context(depth, stack, nodes, att):
        if depth >= 3:
            return getattr(nodes[stack[-1]], att), getattr(nodes[stack[-2]], att), getattr(nodes[stack[-3]], att)
        elif depth >= 2:
            return getattr(nodes[stack[-1]], att), getattr(nodes[stack[-2]], att), ''
        elif depth == 1:
            return getattr(nodes[stack[-1]], att), '', ''
        else:
            return '', '', ''

    def get_buffer_context(i, n, nodes, att):
        if i + 1 >= n:
          return getattr(nodes[i], att), '', ''
        elif i + 2 >= n:
            return getattr(nodes[i], att), getattr(nodes[i + 1], att), ''
        else:
            return getattr(nodes[i], att), getattr(nodes[i + 1], att), getattr(nodes[i + 2], att)

    def get_parse_context(word, deps, nodes, att):
        if word == -1:
            return 0, '', ''
        deps = deps[word]
        valency = len(deps)
        if not valency:
            return 0, '', ''
        elif valency == 1:
            return 1, getattr(nodes[deps[-1]], att), ''
        else:
            return valency, getattr(nodes[deps[-1]], att), getattr(nodes[deps[-2]], att)
    assert len(dg.nodes) == n + 1

    features = {}
    # Set up the context pieces --- the word (W) and tag (T) of:
    # S0-2: Top three words on the stack
    # N0-2: First three words of the buffer
    # n0b1, n0b2: Two leftmost children of the first word of the buffer
    # s0b1, s0b2: Two leftmost children of the top word of the stack
    # s0f1, s0f2: Two rightmost children of the top word of the stack

    depth = len(stack)
    s0 = stack[-1] if depth else -1

    Ws0, Ws1, Ws2 = get_stack_context(depth, stack, dg.nodes, 'form')
    Ts0, Ts1, Ts2 = get_stack_context(depth, stack, dg.nodes, 'cpostag')

    Wn0, Wn1, Wn2 = get_buffer_context(n0, n, dg.nodes, 'form')
    Tn0, Tn1, Tn2 = get_buffer_context(n0, n, dg.nodes, 'cpostag')

    Vn0b, Wn0b1, Wn0b2 = get_parse_context(n0, parse.lefts, dg.nodes, 'form')
    Vn0b, Tn0b1, Tn0b2 = get_parse_context(n0, parse.lefts, dg.nodes, 'cpostag')

    # Vn0f, Wn0f1, Wn0f2 = get_parse_context(n0, parse.rights, dg.nodes, 'form')

    _, Tn0f1, Tn0f2 = get_parse_context(n0, parse.rights, dg.nodes, 'cpostag')

    Vs0b, Ws0b1, Ws0b2 = get_parse_context(s0, parse.lefts, dg.nodes, 'form')
    _, Ts0b1, Ts0b2 = get_parse_context(s0, parse.lefts, dg.nodes, 'cpostag')

    Vs0f, Ws0f1, Ws0f2 = get_parse_context(s0, parse.rights, dg.nodes, 'form')
    _, Ts0f1, Ts0f2 = get_parse_context(s0, parse.rights, dg.nodes, 'cpostag')

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


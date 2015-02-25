#!/usr/bin/env python
# encoding: utf-8

from __future__ import unicode_literals
from __future__ import division
from itertools import izip
from nltk.parse.dependencygraph import DependencyGraph
from nltk.parse.evaluate import DependencyEvaluator
from nltk.parse.nonprojectivedependencyparser import ProbabilisticNonprojectiveParser as Parser
from nltk.parse.nonprojectivedependencyparser import NaiveBayesDependencyScorer
from textblob_aptagger import PerceptronTagger
import argparse
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
parser = argparse.ArgumentParser('Training the dependency parsing')
parser.add_argument('--train-file', default='universal-dependencies-1.0/en/en-ud-train-small.conllu')
parser.add_argument('--dev-file', default='universal-dependencies-1.0/en/en-ud-test-small.conllu')
parser.add_argument('--test-file', default='universal-dependencies-1.0/en/en-ud-test-small.conllu')
parser.add_argument('--test-parsed-file', default='test_parsed.conllu')
args = parser.parse_args()
train_file = args.train_file
dev_file = args.dev_file
test_file = args.test_file
test_parsed_file = args.test_parsed_file
test_gold_portion_file = test_parsed_file + '.gold'


def load_graphs(filename):
    graphs = []
    with open(filename, 'r') as rt:
        data = rt.read()
        data = data.replace('root', 'ROOT')
        graphs = [DependencyGraph(sentence) for sentence in data.split('\n\n') if sentence]
    return graphs


def save_graphs(filename, graphs):
    with open(filename, 'w') as wp:
        conll_sentences = [g.to_conll(10) for g in graphs]
        wp.write('\n'.join(conll_sentences))


logger.info('Loading conllu for training')
train_graphs = load_graphs(train_file)

pos_train_graphs = train_graphs
logger.info('Train POS')
tagged_sentences = []
for g in pos_train_graphs:
    # k == 0 TOP artificial node
    sentence = sorted([(k, n['word'], n['tag']) for k, n in g.nodes.iteritems() if k != 0])
    ws = [w for (_, w, _) in sentence]
    ts = [t for (_, _, t) in sentence]
    tagged_sentences.append((ws, ts))
tgr = PerceptronTagger(load=False)
tgr.train(tagged_sentences)
logger.info('TODO save trained model e.g. by pickling')
logger.info('POS trained')

logger.info('Train DepParse on %d sentences' % len(train_graphs))
npp = Parser()
npp.train(train_graphs, NaiveBayesDependencyScorer())
logger.info('TODO save trained model e.g. by pickling')
logger.info('DepParse trained')

logger.info('Loading conllu for testing')
test_graphs_gold = load_graphs(test_file)
test_sentences = []
for g in test_graphs_gold:
    # k == 0 TOP artificial node
    sentence = sorted([(k, n['word'], n['tag']) for k, n in g.nodes.iteritems() if k != 0])
    ws = [w for (_, w, _) in sentence]
    ts = [t for (_, _, t) in sentence]
    test_sentences.append((ws, ts))

logger.info("Testing todo")
test_graphs_parsed = []
test_graphs_gold_eval = []
skipped = 0
for (ws, ts), gg in izip(test_sentences, test_graphs_gold):
    dgs = npp.parse(ws, ts)
    for dg in dgs:
        test_graphs_parsed.append(dg)
        test_graphs_gold_eval.append(gg)
        break  # FIXME take only the first tree

logger.info("Save decoded")
save_graphs(test_gold_portion_file, test_graphs_gold_eval)
save_graphs(test_parsed_file, test_graphs_parsed)


with open('test_gold.svg', 'w') as w:
    w.write(test_graphs_gold_eval[0]._repr_svg_())
with open('test.svg', 'w') as w:
    w.write(test_graphs_parsed[0]._repr_svg_())

lg = len(test_graphs_gold)
parsed = lg - skipped
logger.info('Evaluating %d / %d (%0.2f %%) of sentences' % (parsed, lg, 100 * parsed / lg))
if parsed > 0:
    ev = DependencyEvaluator(test_graphs_gold_eval, test_graphs_parsed)
    las, uas = ev.eval()
    logger.info('Labeled attachment score (LAS): %s\nUnlabeled attachment score (UAS) %s\n' % (las, uas))

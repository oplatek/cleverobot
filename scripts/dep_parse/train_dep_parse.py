#!/usr/bin/env python
# encoding: utf-8

from __future__ import unicode_literals
from __future__ import division
from itertools import izip
from cbot.parse.dependencygraph import DependencyGraph
from cbot.parse.evaluate import DependencyEvaluator
from cbot.parse.parser import Parser, depgraph_to_pos, depgraph_to_headlabels, heads_to_depgraph, NonProjectiveException
import argparse
import logging

logger = logging.getLogger(__name__)
h = logging.StreamHandler()
logger.addHandler(h)
logger.setLevel(logging.DEBUG)
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


npp = Parser(load=False)
logger.info('Loading conllu for training')
train_graphs = DependencyGraph.load(train_file)
with open('train.svg', 'w') as w:
    w.write(train_graphs[0]._repr_svg_())
sentences = list(depgraph_to_headlabels(train_graphs))

logger.info('Train DepParse on %d sentences' % len(train_graphs))

non_projective = 0
try:
    npp.train(sentences, nr_iter=15)
except NonProjectiveException as e:
    non_projective += 1
logger.info("Skipped non %d non-projective sentences" % non_projective)
npp.save()
logger.info('DepParse trained')

logger.info('Loading conllu for testing')
test_graphs_gold = DependencyGraph.load(test_file)
# test_graphs_gold = train_graphs  # TODO evaulate on training data should be almost accurate
test_sentences = list(depgraph_to_pos(test_graphs_gold))
test_graphs_parsed = []
logger.info("Testing")
for ws, gold_tags in test_sentences:
    tags, heads = npp.parse(ws)
    dg = heads_to_depgraph(heads, tags, ws)
    test_graphs_parsed.append(dg)
logger.info("Saving decoded dependency trees")
DependencyGraph.save_conll(test_gold_portion_file, test_graphs_gold)
DependencyGraph.save_conll(test_parsed_file, test_graphs_parsed)

with open('test_gold.svg', 'w') as w:
    w.write(test_graphs_gold[0]._repr_svg_())
with open('test.svg', 'w') as w:
    w.write(test_graphs_parsed[0]._repr_svg_())
print 'gold', [(n.cpostag, n.form) for n in test_graphs_gold[0].nodes]
print 'parsed', [(n.cpostag, n.form) for n in test_graphs_parsed[0].nodes]

gold_len = len(test_graphs_gold)
parsed_len = gold_len  # TODO we suppose that parsing is robust and each sentence is parsed
logger.info('Evaluating %d / %d (%0.2f %%) of sentences' % (parsed_len, gold_len, 100 * parsed_len / gold_len))
if parsed_len > 0:
    ev = DependencyEvaluator(test_graphs_parsed, test_graphs_gold)
    uas, las = ev.eval()
    pos_acc = ev.pos_accuracy()
    logger.info('Labeled attachment score (LAS): %.03f\n'
                'Unlabeled attachment score (UAS) %.03f\n'
                'for POS accuracy %.03f\n' % (las, uas, pos_acc))

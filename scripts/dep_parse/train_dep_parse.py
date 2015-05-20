#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals, division
from itertools import izip
from cbot.lu.dependencygraph import DependencyGraph
from cbot.lu.evaluate import DependencyEvaluator
from cbot.lu.parser import Parser, NonProjectiveException
from cbot.lu.pos import PerceptronTagger
import argparse
import logging

logging.basicConfig(level=logging.DEBUG)
parser = argparse.ArgumentParser('Training the dependency parsing')
parser.add_argument('--train-file', default='universal-dependencies-1.0/en/en-ud-train-small.conllu')
parser.add_argument('--dev-file', default='universal-dependencies-1.0/en/en-ud-test-small.conllu')
parser.add_argument('--test-file', default='universal-dependencies-1.0/en/en-ud-test-small.conllu')
parser.add_argument('--test-parsed-file', default='test_parsed.conllu')
parser.add_argument('--save-model', default=False, action='store_true')
parser.add_argument('--load-pos', default=False, action='store_true')
args = parser.parse_args()
train_file = args.train_file
dev_file = args.dev_file
test_file = args.test_file
test_parsed_file = args.test_parsed_file
test_gold_portion_file = test_parsed_file + '.gold'


train_graphs = DependencyGraph.load(train_file)
test_graphs_gold = DependencyGraph.load(test_file)

pos = PerceptronTagger()
args.load_pos = False
args.save_model = True
# FIXME the same POS model get worse after reloading: 91.5 - > 64.4
if args.load_pos:
    pos.load()
else:
    pos.train([(g.get_words_att('form'), g.get_words_att('cpostag')) for g in train_graphs])
pos_gold = [g.get_words_att('cpostag') for g in test_graphs_gold]
pos_decoded = [pos.tag(g.get_words_att('form')) for g in test_graphs_gold]
c, t = 0, 0
for ds, gs in izip(pos_decoded, pos_gold):
    for d, g in izip(ds, gs):
        c, t = c + (d == g), t + 1
logging.info('POS accuracy %f' % (c / t))
if args.save_model:
    pos.save()

logging.info('Train DepParse on %d sentences' % len(train_graphs))
npp = Parser(pos, load=False)
non_projective = 0
try:
    npp.train(train_graphs, nr_iter=15)
except NonProjectiveException as e:
    non_projective += 1
logging.info("Skipped non %d non-projective sentences" % non_projective)
if args.save_model:
    npp.save()

logging.info("Decoding")
test_graphs_parsed = []
for g in test_graphs_gold:
    words = [n.form for n in g.nodes[1:]]
    dg = npp.parse(words)
    test_graphs_parsed.append(dg)


logging.info("Saving decoded dependency trees")
DependencyGraph.save_conll(test_gold_portion_file, test_graphs_gold)
DependencyGraph.save_conll(test_parsed_file, test_graphs_parsed)
with open('test_gold.svg', 'w') as w:
    w.write(test_graphs_gold[0]._repr_svg_())
with open('test.svg', 'w') as w:
    w.write(test_graphs_parsed[0]._repr_svg_())
print 'gold', [(n.cpostag, n.form) for n in test_graphs_gold[0].nodes]
print 'parsed', [(n.cpostag, n.form) for n in test_graphs_parsed[0].nodes]

logging.info('Evaluating')
gold_len = len(test_graphs_gold)
parsed_len = gold_len  # TODO we suppose that parsing is robust and each sentence is parsed
logging.info('Parsed sentences %d / %d (%0.2f %%)' % (parsed_len, gold_len, 100 * parsed_len / gold_len))
if parsed_len > 0:
    ev = DependencyEvaluator(test_graphs_parsed, test_graphs_gold)
    uas, las = ev.eval()
    pos_acc = ev.pos_accuracy()
    logging.info('Labeled attachment score (LAS): %.03f\n'
                'Unlabeled attachment score (UAS) %.03f\n'
                'for POS accuracy %.03f\n' % (las, uas, pos_acc))

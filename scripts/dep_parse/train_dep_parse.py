#!/usr/bin/env python
# encoding: utf-8

from __future__ import unicode_literals
from nltk.parse.dependencygraph import DependencyGraph
from nltk.parse.nonprojectivedependencyparser import ProbabilisticNonprojectiveParser
from nltk.parse.nonprojectivedependencyparser import NaiveBayesDependencyScorer
from textblob_aptagger import PerceptronTagger


train_file = 'universal-dependencies-1.0/en/en-ud-train-small.conllu'

print('Loading conllu')
train_graphs = []
with open(train_file, 'r') as rt:
    train_data = rt.read()
    train_data = train_data.replace('root', 'ROOT')
    train_graphs = [DependencyGraph(sentence) for sentence in train_data.split('\n\n') if sentence]

print('Train POS')
tagged_sentences = []
for g in train_graphs:
    # k == 0 TOP artificial node
    sentence = sorted([(k, n['word'], n['tag']) for k, n in g.nodes.iteritems() if k != 0])

    ws = [w for (_, w, _) in sentence]
    ts = [t for (_, _, t) in sentence]
    tagged_sentences.append((ws, ts))
tgr = PerceptronTagger(load=False)
tgr.train(tagged_sentences)
print('POS trained')



print('Train DepParse')
npp = ProbabilisticNonprojectiveParser()
npp.train(train_graphs, NaiveBayesDependencyScorer())
print('DepParse trained')


print("Testing todo")
for parse_graph in npp.parse(['Cathy', 'zag', 'hen', 'zwaaien', '.'], ['N', 'V', 'Pron', 'Adj', 'N', 'Punc']):
    print parse_graph

print("Eval todo")

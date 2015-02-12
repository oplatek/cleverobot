#!/usr/bin/env python
# encoding: utf-8

# Required data files are:
#   * maxent_treebank_pos_tagger" in Models
import nltk


def parse(utterance):
    '''
    POS https://www.ling.upenn.edu/courses/Fall_2003/ling001/penn_treebank_pos.html
    '''
    annotation = []
    tokens = nltk.wordpunct_tokenize(utterance)
    tags = nltk.pos_tag(tokens)
    assert len(tags) == len(tokens)
    return (tokens, tags) 

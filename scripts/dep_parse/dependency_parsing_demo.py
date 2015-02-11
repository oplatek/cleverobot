#!/usr/bin/env python
# encoding: utf-8
from utils import download_nltkdata
import logging
import nltk
import os
from nltk.parse.malt import MaltParser

if not "MALT_PARSER" in os.environ:
 os.environ["MALT_PARSER"]='maltparser-1.8'
if not os.path.exists(os.path.join(os.environ["MALT_PARSER"], 'maltparser-1.8.jar')):
    raise ImportError('Maltparser java jar not found')

# nltk.download('punkt')
# nltk.download('maxent_treebank_pos_tagger')

logger = logging.getLogger(__name__)
ch = logging.StreamHandler()
logger.addHandler(ch)
logger.setLevel(logging.INFO)

# same tagger as in nltk.pos_tag
# TODO report bug in nltk with working_dir the mco is not moved there
dep_parser = MaltParser(tagger=nltk.tag.load(nltk.tag._POS_TAGGER),
        mco='engmalt.linear-1.7',
        working_dir='.',
        additional_java_args=['-Xmx1024m'])



# FIXME move to cbot & import from cbot
def parse(utterance):
    '''
    POS https://www.ling.upenn.edu/courses/Fall_2003/ling001/penn_treebank_pos.html
    '''
    tokens = nltk.wordpunct_tokenize(utterance)
    tags = nltk.pos_tag(tokens)
    assert len(tags) == len(tokens)
    return tokens, tags


def dependency_parse(utterance):
    _, tags = parse(utterance)
    deps = dep_parser.tagged_parse(tags)
    return deps


def parsing_demo(utterance=None):
    if utterance is None:
        utterance = 'Hi how are you?'
    print dependency_parse(utterance)
    


if __name__ == '__main__':
    parsing_demo()

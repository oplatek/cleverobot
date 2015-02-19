#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals
from utils import download_nltkdata
import logging
import nltk
import os
from nltk.parse.malt import MaltParser
from nltk.parse import DependencyGraph

# single word prepositions according http://en.wikipedia.org/wiki/List_of_English_prepositions
prepositions = ['a', 'abaft', 'abeam', 'aboard', 'about', 'above', 'absent', 'across', 'afore', 'after', 'against', 'along', 'alongside', 'amid', 'amidst', 'among', 'amongst', 'an', 'anenst', 'apropos', 'apud', 'around', 'as', 'aside', 'astride', 'at', 'athwart', 'atop', 'barring', 'before', 'behind', 'below', 'beneath', 'beside', 'besides', 'between', 'beyond', 'but', 'by', 'chez', 'circa', 'concerning', 'despite', 'down', 'during', 'except', 'excluding', 'failing', 'following', 'for', 'forenenst', 'from', 'given', 'in', 'including', 'inside', 'into', 'like', 'mid', 'midst', 'minus', 'modulo', 'near', 'next', 'notwithstanding', 'o', 'of', 'off', 'on', 'onto', 'opposite', 'out', 'outside', 'over', 'pace', 'past', 'per', 'plus', 'pro', 'qua', 'regarding', 'round', 'sans', 'save', 'since', 'than', 'through', 'thru', 'throughout', 'thruout', 'till', 'times', 'to', 'toward', 'towards', 'under', 'underneath', 'unlike', 'until', 'unto', 'up', 'upon', 'versus', 'via', 'vice', 'vis-à-vis', 'with', 'within', 'without', 'worth',]

ptb_verb_tags = {'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ'}


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
    rtype: [(tokens, POS)]
    '''
    tokens = nltk.wordpunct_tokenize(utterance)
    tags = nltk.pos_tag(tokens)
    assert len(tags) == len(tokens)
    return tags


def dependency_parse(utterance):
    '''
    More abotu DEPREL tags: http://nlp.stanford.edu/software/dependencies_manual.pdf
    rtype: DependencyGraph =
            =[{'ctag':TOP, etc}, {address:1, head:int, rel:str(DEPREL), tag:str(pos),word:str, ...}, ...]
    '''
    tags = parse(utterance)
    dep_graph = dep_parser.tagged_parse(tags)
    return dep_graph


def display_graph(dg):
    import pln_inco.syntax_trees
    import pln_inco.graphviz as gv
    from IPython.display import Image
    from IPython.display import display_png
    dep_tree=pln_inco.syntax_trees.dependency_to_dot(dg)
    tree_png=Image(data=gv.generate(dep_tree,format='png'))
    return display_png(tree_png)


def detect_vp_node(dg):
    assert isinstance(dg, DependencyGraph)
    dg = dg.nodelist
    verbs = [n for n in dg if n['ctag'] in ptb_verb_tags and n['rel'] == 'null']
    if len(verbs) == 1:
        return verbs[0]
    elif verbs > 1:
        logging.warning('Multiple verb roots detected: %s', ' '.join([n['word'] for n in verbs]))
    else:
        logging.warning('No verb root detected in sentence %s', ' '.join([n['word'] for n in dg]))
    return None


def dg2triplet(dg):
    '''
    TODO ignoring/excluding very important
        - neg
        - aux
    rtype: (str, str, str) or None
    '''
    assert isinstance(dg, DependencyGraph)
    vn = detect_vp_node(dg)
    dg = dg.nodelist
    deps = vn['deps']
    if len(deps) == 2:
        a, b = dg[deps[0]], dg[deps[1]]
        if b['rel'] == 'nsubj':
            a, b = b, a
        if a['rel'] == 'nsubj':
            if b['rel'] == 'dobj':
                logging.debug('Returning subj verb obj')
                return a['word'], vn['word'], b['word']
            if b['rel'] == 'prep' and len(b['deps']) == 1:
                pobj = dg[b['deps'][0]]
                if pobj['rel'] == 'pobj':
                    logging.debug('Returning subj verb prep obj')
                    return a['word'], vn['word'] + b['word'].capitalize(), pobj['word']
                else:
                    logging.debug('Unexpected after prep %s not pobj %s', b['word'], pobj['word'])
    return None


def parsing_demo(utterance=None):
    if utterance is None:
        utterance = 'Hi how are you?'
    print dependency_parse(utterance)


if __name__ == '__main__':
    parsing_demo()

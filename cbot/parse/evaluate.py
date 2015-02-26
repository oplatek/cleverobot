# Natural Language Toolkit: evaluation of dependency parser
#
# Author: Long Duong <longdt219@gmail.com>
#
# Copyright (C) 2001-2015 NLTK Project
# URL: <http://nltk.org/>
# For license information, see LICENSE.TXT

from __future__ import division, unicode_literals
from itertools import izip

import unicodedata


class DependencyEvaluator(object):
    """
    Class for measuring labelled and unlabelled attachment score for
    dependency parsing. Note that the evaluation ignores punctuation.
    """

    def __init__(self, parsed_sents, gold_sents):
        """
        :param parsed_sents: the list of parsed_sents as the output of parser
        :type parsed_sents: list(DependencyGraph)
        """
        self._parsed_sents = parsed_sents
        self._gold_sents = gold_sents

    def _remove_punct(self, inStr):
        """
        Function to remove punctuation from Unicode string.
        :param input: the input string
        :return: Unicode string after remove all punctuation
        """
        punc_cat = set(["Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po"])
        return "".join(x for x in inStr if unicodedata.category(x) not in punc_cat)

    def pos_accuracy(self):
        total, corr = 0, 0

        for parsed, gold in izip(self._parsed_sents, self._gold_sents):
            assert len(parsed.nodes) == len(gold.nodes), "Sentences must have equal length."
            for parsed_node in parsed.nodes:
                if parsed_node.id == 0:
                    continue  # skipping the root node
                gold_node = gold.nodes[parsed_node.id]
                total += 1
                if parsed_node.cpostag == gold_node.cpostag:
                    corr += 1

        return corr / total

    def eval(self):
        """
        Return the Labeled Attachment Score (LAS) and Unlabeled Attachment Score (UAS)

        :return : tuple(float,float)
        """
        if (len(self._parsed_sents) != len(self._gold_sents)):
            raise ValueError(" Number of parsed sentence is different with number of gold sentence.")

        corr, corrL, total = 0, 0, 0

        for parsed, gold in izip(self._parsed_sents, self._gold_sents):
            assert len(parsed.nodes) == len(gold.nodes), "Sentences must have equal length."

            for parsed_node in parsed.nodes:
                gold_node = gold.nodes[parsed_node.id]

                if parsed_node.form is None:
                    continue
                if parsed_node.form != gold_node.form:
                    raise ValueError("Sentence sequence is not matched.")

                # Ignore if word is punctuation by default
                # if (parsed_sent[j]["word"] in string.punctuation):
                if self._remove_punct(parsed_node.form) == "":
                    continue

                total += 1
                if parsed_node.head == gold_node.head:
                    corr += 1
                    if parsed_node.deprel == gold_node.deprel:
                        corrL += 1

        return corr / total, corrL / total


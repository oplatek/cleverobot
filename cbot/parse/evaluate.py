# Natural Language Toolkit: evaluation of dependency parser
#
# Author: Long Duong <longdt219@gmail.com>
#
# Copyright (C) 2001-2015 NLTK Project
# URL: <http://nltk.org/>
# For license information, see LICENSE.TXT

from __future__ import division

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

    def eval(self):
        """
        Return the Labeled Attachment Score (LAS) and Unlabeled Attachment Score (UAS)

        :return : tuple(float,float)
        """
        if (len(self._parsed_sents) != len(self._gold_sents)):
            raise ValueError(" Number of parsed sentence is different with number of gold sentence.")

        corr = 0
        corrL = 0
        total = 0

        for i in range(len(self._parsed_sents)):
            parsed_sent_nodes = self._parsed_sents[i].nodes
            gold_sent_nodes = self._gold_sents[i].nodes

            if (len(parsed_sent_nodes) != len(gold_sent_nodes)):
                raise ValueError("Sentences must have equal length.")

            for parsed_node_address, parsed_node in parsed_sent_nodes.items():
                gold_node = gold_sent_nodes[parsed_node_address]

                if parsed_node["word"] is None:
                    continue
                if parsed_node["word"] != gold_node["word"]:
                    raise ValueError("Sentence sequence is not matched.")

                # Ignore if word is punctuation by default
                # if (parsed_sent[j]["word"] in string.punctuation):
                if self._remove_punct(parsed_node["word"]) == "":
                    continue

                total += 1
                if parsed_node["head"] == gold_node["head"]:
                    corr += 1
                    if parsed_node["rel"] == gold_node["rel"]:
                        corrL += 1

        return corr / total, corrL / total


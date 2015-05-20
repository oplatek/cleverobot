#!/usr/bin/env python
# encoding: utf-8
#
# Ondrej Platek 2015 Apache 2.0 License
# based on
# Natural Language Toolkit: Dependency Grammars
#
# Copyright (C) 2001-2015 NLTK Project
# Author: Jason Narad <jason.narad@gmail.com>
# Steven Bird <stevenbird1@gmail.com> (modifications)
#
# URL: <http://nltk.org/>
# For license information, see LICENSE.TXT

"""
Tools for reading and writing dependency trees.
Mainly:
    http://universaldependencies.github.io/docs/format.html
    http://stp.lingfil.uu.se/~nivre/research/MaltXML.html).
"""
from __future__ import print_function, unicode_literals, division

from collections import defaultdict, namedtuple
from pprint import pformat
import subprocess


class DependencyGraphError(Exception):
    pass


class Node(
    namedtuple('Node', ['id', 'form', 'lemma', 'cpostag', 'tag', 'feats', 'head', 'deprel', 'deps', 'misc',])):
    def __new__(cls, id, form=None, lemma=None, cpostag=None, tag=None, feats=None,
                head=None, deprel=None, deps=None, misc=None):
        # FIXME parse featurures, deps
        if head is not None:
            head = int(head)
        return super(Node, cls).__new__(cls, int(id), form, lemma, cpostag, tag, feats, head, deprel, deps, misc)


class DependencyGraph(object):
    """
    A container for the nodes and labelled edges of a dependency structure.

    Node is inspired by
    http://universaldependencies.github.io/docs/format.html

    """

    @staticmethod
    def load(filename, cell_separator=None):
        with open(filename) as infile:
            return [DependencyGraph(tree_str, cell_separator=cell_separator)
                    for tree_str in infile.read().strip().split('\n\n')]

    @staticmethod
    def save_conll(filename, graphs, columns=10):
        with open(filename, 'w') as wp:
            conll_sentences = [g.to_conll(columns) for g in graphs]
            wp.write('\n\n'.join(conll_sentences))


    def __init__(self, tree_str=None, n=None, cell_extractor=None, cell_separator=None):
        """Dependency graph.

        A dummy `ROOT` node has always the index 0,
        and is the artificial root of the Dependency Graph representing a sentence.

        For each node should hold nodes[i].id == i
        """

        self.nodes = [Node(id=0, cpostag='root')]
        self.children = []  # TODO change it to default list with set
        if tree_str:
            self._parse(tree_str, cell_extractor=cell_extractor, cell_separator=cell_separator, )
            if n is not None and (n + 1) != len(self.nodes):
                raise ValueError('The loaded tree is expected to have %d nodes but has %d' % (n, len(self.nodes)))
        elif n is not None:
            self.nodes += [None] * n
            self.children = [set([]) for _ in self.nodes]

    def update_node(self, node):
        assert isinstance(node, Node)
        assert 0 <= node.id < len(self.nodes)
        orig = self.nodes[node.id]
        if orig is not None and orig.head is not None and node.head != orig.head:
            self.children[orig.head].remove(orig.id)
            if node.head is not None:
                self.children[node.head].add(node.id)
        self.nodes[node.id] = node

    def get_words_att(self, att, exclude_root=True):
        if exclude_root:
            nodes = self.nodes[1:]
        else:
            nodes = self.nodes
        return [getattr(node, att) for node in nodes]

    def update_dependency(self, head, dep):
        """Updates new dependency arc to new head and new label.
        """
        assert 0 <= head < len(self.nodes)
        assert 0 <= dep < len(self.nodes)
        dep_head = self.nodes[dep].head
        if dep_head is not None:
            self.children[self.nodes[dep].head].remove(dep)
        self.children[head].add(dep)
        new_dep_node = self.nodes[dep]._replace(head=head)
        self.nodes[dep] = new_dep_node

    def remove_dependencies(self):
        for i, node in enumerate(self.nodes):
            self.nodes[i] = node._replace(head=None)
            self.children[i] = set([])

    def to_dot(self):
        """
        Returns a dot representation suitable for using with Graphviz
        @rtype C{String}
        """
        # Start the digraph specification
        s = 'digraph G{\n'
        s += 'edge [dir=forward]\n'
        s += 'node [shape=plaintext]\n'
        # Draw the remaining nodes
        for node in self.nodes:
            s += '\n%s [label="%s (%s)"]' % (node.id, node.id, node.form)
            dep_rel = sorted([(dep.id, dep.deprel) for dep in self.nodes if dep.head == node.id])
            for dep_id, rel in dep_rel:
                if rel is not None:
                    s += '\n%s -> %s [label="%s"]' % (node.id, dep_id, rel)
                else:
                    s += '\n%s -> %s ' % (node.id, dep_id)
        s += "\n}"
        return s

    def _repr_svg_(self):
        """Ipython magic: show SVG representation of the transducer"""
        dot_string = self.to_dot()
        img_format = 'svg'
        try:
            process = subprocess.Popen(['dot', '-T%s' % img_format], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError:
            raise Exception('Cannot find the dot binary from Graphviz package')
        out, err = process.communicate(dot_string)
        if err:
            raise Exception(
                'Cannot create %s representation by running dot from string\n:%s' % (img_format, dot_string))
        return out

    def __str__(self):
        return pformat(self.nodes)

    def __repr__(self):
        return "<DependencyGraph with {0} nodes>".format(len(self.nodes))

    def _parse(self, input_, cell_extractor=None, cell_separator=None):
        """Parse a sentence.
        Returns True for success

        :param extractor: a function that given a tuple of cells returns a Node

        :param str cell_separator: the cell separator. If not provided, cells
        are split by whitespace.
        """
        none_values = {'_'}

        def extract_3_cells(cells, index):
            cells = [c if c not in none_values or i == 0 else None for i, c in enumerate(cells)]
            form, tag, head = cells
            if head == 0:
                rel = 'root'
            else:
                rel = None
            return Node(id=index, form=form, cpostag=tag, head=head, deprel=rel)

        def extract_4_cells(cells, index):
            cells = [c if c not in none_values or i == 0 else None for i, c in enumerate(cells)]
            form, tag, head, rel = cells
            return Node(id=index, form=form, cpostag=tag, head=head, deprel=rel)

        def extract_10_cells(cells, index):
            # TODO extract deprel format and feats
            cells = [c if (c not in none_values or i == 1) else None for i, c in enumerate(cells)]
            id, form, lemma, cpostag, tag, feats, head, deprel, deps, misc = cells
            result = Node(id, form, lemma, cpostag, tag, feats, head, deprel, deps, misc)
            assert result.id == index
            return result

        extractors = {
            3: extract_3_cells,
            4: extract_4_cells,
            10: extract_10_cells,
        }
        if isinstance(input_, basestring):
            input_ = (line for line in input_.split('\n'))

        lines = (l.rstrip() for l in input_)
        lines = [l for l in lines if l]

        if len(lines) > 0:
            cell_number = len(lines[0].split(cell_separator))
        else:
            return False

        if cell_extractor is None:
            cell_extractor = extractors[cell_number]

        self.nodes += [None] * len(lines)
        self.children = [set([]) for _ in self.nodes]
        assert len(self.children) == len(lines) + 1

        for index, line in enumerate(lines, start=1):
            cells = [c for c in line.split(cell_separator)]
            assert cell_number == len(cells), '%d vs %d' % (cell_number, len(cells))
            try:
                self.update_node(cell_extractor(cells, index))
                assert self.nodes[index].form is not None, str(cells)
            except KeyError:
                raise ValueError('Extraction not supported for tab-delimited fields %d and %s'
                                 % (cell_number, cell_extractor))
        self.children_from_nodes()
        return True

    def children_from_nodes(self):
        for n in self.nodes:
            if n is None:
                raise ValueError("Nodes of the graph should be populated to derive children from head relation")
            if n.head is not None:
                self.children[n.head].add(n.id)

    def to_conll(self, style, empty_str='_'):
        if style == 3:
            template = '{form}\t{cpostag}\t{head}\n'
        elif style == 4:
            template = '{form}\t{cpostag}\t{head}\t{deprel}\n'
        elif style == 10:
            template = '{id}\t{form}\t{lemma}\t{cpostag}\t{tag}\t{feats}\t{head}\t{deprel}\t{deps}\t{misc}'
        else:
            raise ValueError(
                'Number of tab-delimited fields ({0}) not supported by '
                'CoNLL(10) or Malt-Tab(4) format'.format(style)
            )
        node_dicts = [n._asdict() for n in self.nodes if n.id != 0]
        for n in node_dicts:
            for k, v in n.iteritems():
                if v is None:
                    n[k] = empty_str

        return '\n'.join(template.format(**n) for n in node_dicts)

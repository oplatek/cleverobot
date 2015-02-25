# Natural Language Toolkit: Dependency Grammars
#
# Copyright (C) 2001-2015 NLTK Project
# Author: Jason Narad <jason.narad@gmail.com>
#         Steven Bird <stevenbird1@gmail.com> (modifications)
#
# URL: <http://nltk.org/>
# For license information, see LICENSE.TXT
#

"""
Tools for reading and writing dependency trees.
The input is assumed to be in Malt-TAB format
(http://stp.lingfil.uu.se/~nivre/research/MaltXML.html).
"""
from __future__ import print_function, unicode_literals, division

from collections import defaultdict
from pprint import pformat
import subprocess


class DependencyGraphError(Exception):
    pass

class DependencyGraph(object):
    """
    A container for the nodes and labelled edges of a dependency structure.
    """

    @staticmethod
    def load(filename, zero_based=False, cell_separator=None):
        with open(filename) as infile:
            return [
                DependencyGraph(
                    tree_str,
                    zero_based=zero_based,
                    cell_separator=cell_separator,
                    )
                for tree_str in infile.read().strip().split('\n\n')
            ]

    @staticmethod
    def save_conll(filename, graphs, columns=10):
        with open(filename, 'w') as wp:
            conll_sentences = [g.to_conll(columns) for g in graphs]
            wp.write('\n'.join(conll_sentences))


    @staticmethod
    def get_default_node():
        return {
            'address': None,
            'word': None,
            'lemma': None,
            'ctag': None,
            'tag': None,
            'feats': None,
            'head': None,
            'deps': defaultdict(list),
            'rel': None,
            }

    def __init__(self, tree_str=None, cell_extractor=None, zero_based=False, cell_separator=None):
        """Dependency graph.

        We place a dummy `TOP` node with the index 0, since the root node is
        often assigned 0 as its head. This also means that the indexing of the
        nodes corresponds directly to the Malt-TAB format, which starts at 1.

        If zero-based is True, then Malt-TAB-like input with node numbers
        starting at 0 and the root node assigned -1 (as produced by, e.g.,
        zpar).
        """
        self.nodes = defaultdict(DependencyGraph.get_default_node)
        self.nodes[0].update(
            {
                'ctag': 'TOP',
                'tag': 'TOP',
                'rel': 'ROOT',
                'address': 0,
            }
        )

        if tree_str:
            self._parse(
                tree_str,
                cell_extractor=cell_extractor,
                zero_based=zero_based,
                cell_separator=cell_separator,
            )

    def add_arc(self, head_address, mod_address):
        """
        Adds an arc from the node specified by head_address to the
        node specified by the mod address.
        """
        relation = self.nodes[mod_address]['rel']
        self.nodes[head_address]['deps'].setdefault(relation, [])
        self.nodes[head_address]['deps'][relation].append(mod_address)


    def connect_graph(self):
        """
        Fully connects all non-root nodes.  All nodes are set to be dependents
        of the root node.
        """
        for node1 in self.nodes.values():
            for node2 in self.nodes.values():
                if node1['address'] != node2['address'] and node2['rel'] != 'TOP':
                    relation = node2['rel']
                    node1['deps'].setdefault(relation, [])
                    node1['deps'][relation].append(node2['address'])
                    #node1['deps'].append(node2['address'])

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
        for address, node in sorted(self.nodes.iteritems()):
            s += '\n%s [label="%s (%s)"]' % (address, address, node['word'])
            dep_rel = []
            for rel, deps in node['deps'].iteritems():
                for dep in deps:
                    dep_rel.append((dep, rel))
            dep_rel.sort()
            for dep, rel in dep_rel:
                if rel != None:
                    s += '\n%s -> %s [label="%s"]' % (node['address'], dep, rel)
                else:
                    s += '\n%s -> %s ' % (node['address'], dep)
        s += "\n}"
        return s

    def _repr_svg_(self):
        """Ipython magic: show SVG representation of the transducer"""
        dot_string = self.to_dot()
        format = 'svg'
        try:
            process = subprocess.Popen(['dot', '-T%s' % format], stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError:
            raise Exception('Cannot find the dot binary from Graphviz package')
        out, err = process.communicate(dot_string)
        if err:
            raise Exception('Cannot create %s representation by running dot from string\n:%s' % (format, dot_string))
        return out

    def __str__(self):
        return pformat(self.nodes)

    def __repr__(self):
        return "<DependencyGraph with {0} nodes>".format(len(self.nodes))

    def left_children(self, node_index):
        """
        Returns the number of left children under the node specified
        by the given address.
        """
        children = self.nodes[node_index]['deps']
        index = self.nodes[node_index]['address']
        return sum(1 for c in children if c < index)

    def right_children(self, node_index):
        """
        Returns the number of right children under the node specified
        by the given address.
        """
        children = self.nodes[node_index]['deps']
        index = self.nodes[node_index]['address']
        return sum(1 for c in children if c > index)

    def add_node(self, node):
        if not self.contains_address(node['address']):
            self.nodes[node['address']].update(node)

    def _parse(self, input_, cell_extractor=None, zero_based=False, cell_separator=None):
        """Parse a sentence.

        :param extractor: a function that given a tuple of cells returns a
        7-tuple, where the values are ``word, lemma, ctag, tag, feats, head,
        rel``.

        :param str cell_separator: the cell separator. If not provided, cells
        are split by whitespace.

        """

        def extract_3_cells(cells):
            word, tag, head = cells
            return word, word, tag, tag, '', head, ''

        def extract_4_cells(cells):
            word, tag, head, rel = cells
            return word, word, tag, tag, '', head, rel

        def extract_10_cells(cells):
            _, word, lemma, ctag, tag, feats, head, rel, _, _ = cells
            return word, lemma, ctag, tag, feats, head, rel

        extractors = {
            3: extract_3_cells,
            4: extract_4_cells,
            10: extract_10_cells,
        }

        if isinstance(input_, basestring):
            input_ = (line for line in input_.split('\n'))

        lines = (l.rstrip() for l in input_)
        lines = (l for l in lines if l)

        cell_number = None
        for index, line in enumerate(lines, start=1):
            cells = line.split(cell_separator)
            if cell_number is None:
                cell_number = len(cells)
            else:
                assert cell_number == len(cells)

            if cell_extractor is None:
                try:
                    cell_extractor = extractors[cell_number]
                except KeyError:
                    raise ValueError(
                        'Number of tab-delimited fields ({0}) not supported by '
                        'CoNLL(10) or Malt-Tab(4) format'.format(cell_number)
                    )

            word, lemma, ctag, tag, feats, head, rel = cell_extractor(cells)
            if rel == 'root':
                rel = 'ROOT'

            head = int(head)
            if zero_based:
                head += 1

            self.nodes[index].update(
                {
                    'address': index,
                    'word': word,
                    'lemma': lemma,
                    'ctag': ctag,
                    'tag': tag,
                    'feats': feats,
                    'head': head,
                    'rel': rel,
                }
            )

            # Make sure that he fake root node has labeled dependencies.
            if (cell_number == 3) and (head == 0):
                rel = 'ROOT'
            self.nodes[head]['deps'][rel].append(index)

        if not self.nodes[0]['deps']['ROOT']:
            raise DependencyGraphError(
                "The graph does'n contain a node "
                "that depends on the root element."
            )
        root_address = self.nodes[0]['deps']['ROOT'][0]

    def contains_cycle(self):
        distances = {}

        for node in self.nodes.values():
            for dep in node['deps']:
                key = tuple([node['address'], dep])
                distances[key] = 1

        for _ in self.nodes:
            new_entries = {}

            for pair1 in distances:
                for pair2 in distances:
                    if pair1[1] == pair2[0]:
                        key = tuple([pair1[0], pair2[1]])
                        new_entries[key] = distances[pair1] + distances[pair2]

            for pair in new_entries:
                distances[pair] = new_entries[pair]
                if pair[0] == pair[1]:
                    path = self.get_cycle_path(self.get_by_address(pair[0]), pair[0])
                    return path

        return []

    def get_cycle_path(self, curr_node, goal_node_index):
        for dep in curr_node['deps']:
            if dep == goal_node_index:
                return [curr_node['address']]
        for dep in curr_node['deps']:
            path = self.get_cycle_path(self.get_by_address(dep), goal_node_index)
            if len(path) > 0:
                path.insert(0, curr_node['address'])
                return path
        return []

    def to_conll(self, style):
        if style == 3:
            template = '{word}\t{tag}\t{head}\n'
        elif style == 4:
            template = '{word}\t{tag}\t{head}\t{rel}\n'
        elif style == 10:
            template = '{i}\t{word}\t{lemma}\t{ctag}\t{tag}\t{feats}\t{head}\t{rel}\t_\t_\n'
        else:
            raise ValueError(
                'Number of tab-delimited fields ({0}) not supported by '
                'CoNLL(10) or Malt-Tab(4) format'.format(style)
            )
        return ''.join(template.format(i=i, **node) for i, node in sorted(self.nodes.items()) if node['tag'] != 'TOP')


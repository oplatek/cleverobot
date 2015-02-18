#!/usr/bin/env python
# encoding: utf-8
import unittest
import tempfile
import os
import kb
import StringIO
import pickle


class KbTest(unittest.TestCase):

    def setUp(self):
        self.tmpf, self.tmpf_name = tempfile.mkstemp()
        self.triples = {('a', '1', 'c'), ('c', '2', 'd')}

    def tearDown(self):
        os.close(self.tmpf)
        os.remove(self.tmpf_name)

    def test_dump(self):
        k = kb.KnowledgeBase()
        with open(self.tmpf_name, 'w') as f:
            k.dump(f)

    def load_triples(self):
        k = kb.KnowledgeBase()
        with open(self.tmpf_name, 'w') as w:
            pickle.dump(self.triples, w)
        with open(self.tmpf_name, 'r') as r:
            k.load(r)
        return k

    def test_load(self):
        ext_triples = self.load_triples().extract_triples()
        self.assertEqual(self.triples, ext_triples)

    def test_neighbours(self):
        k = self.load_triples()
        trip = k.get_neighbours('c')
        self.assertEqual(trip,{('c','2', 'd')})

    def test_get_nodes(self):
        k = kb.KnowledgeBase()
        k.add_triplets(self.triples)
        keys = [a for a, b, c in self.triples]
        self.assertEqual(keys.sort(), k.get_nodes().sort())



if __name__ == '__main__':
    unittest.main()

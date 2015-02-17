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

    def tearDown(self):
        os.close(self.tmpf)
        os.remove(self.tmpf_name)

    def test_dump(self):
        k = kb.KnowledgeBase()
        with open(self.tmpf_name, 'w') as f:
            k.dump(f)

    def test_load(self):
        k = kb.KnowledgeBase()
        triples = {('a', '1', 'c'), ('c', '2', 'd')}
        with open(self.tmpf_name, 'w') as w:
            pickle.dump(triples, w)
        with open(self.tmpf_name, 'r') as r:
            k.load(r)
        ext_triples = k.extract_triples()
        self.assertEqual(triples, ext_triples)



if __name__ == '__main__':
    unittest.main()



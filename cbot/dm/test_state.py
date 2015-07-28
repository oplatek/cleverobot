import json
import unittest
from cbot.dm.state import SimpleTurnState


class TestLogging(unittest.TestCase):
    def setUp(self):
        self.utts = ['', 'Hi how are you?', 'I like Little Richard']

    def test_repr_json(self):
        s = SimpleTurnState(None)
        for utt in self.utts:
            s.current_user_utterance = utt
            s.update_mentions()
            rep = repr(s)
            d = json.loads(rep)
            self.assertIsInstance(d, dict,
                                  msg="Current representation:%s\nfor utterance %s\nis not dict:%s" % (rep, utt, d))


if __name__ == '__main__':
    unittest.main()

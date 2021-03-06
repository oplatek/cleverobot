#!/usr/bin/env python
# encoding: utf-8
from __future__ import unicode_literals
import logging


class Nlg(object):
    _default_nlg_acton = lambda a: 'nlg action %s' % a

    @classmethod
    def get_default_actions(cls):
        return {
            'ask': cls._default_nlg_acton,
            'confirm': cls._default_nlg_acton,
            'inform': cls._default_nlg_acton,
            'greeting': cls._default_nlg_acton,
            'silence': cls._default_nlg_acton,
        }

    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.' + self.__class__.__name__)
        self.nlgf = Nlg.get_default_actions()
        self.nlgf.update({
            'raw': lambda action: action['raw'],
            'ask': self.open_questions,
            'confirm': self.confirm,
            'inform': self.inform,
            'greeting': lambda action: 'Hi!',
            'silence': lambda action: '...',
        })

    def action2lang(self, action):
        type = action['type']
        if type in self.nlgf:
            return self.nlgf[type](action)
        else:
            self.logger.warning('Generated of natural language not supported for type %s', action)
        return None

    def open_questions(self, action):
        about = action['about']
        assert isinstance(about, tuple) and len(about) == 3, 'we model triplets only'
        if about[0] is not None and about[1] is None and about[2] is None:
            question = 'Can you tell me more about %s ?' % about[0]
        elif about[0] is None and about[1] is not None and about[2] is None:
            question = 'What kind of action is %s ?' % about[1]
        elif about[0] is not None and about[1] is not None and about[2] is None:
            question = indirect_object_q(about)
        elif about[0] is not None and about[1] is not None and about[2] is not None:
            question = 'Tell me more facts about %s %s %s ?' % about
        else:
            question = 'What do you think right now?'
        self.logger.debug('For action %s generated question %s', action, question)
        return question

    def confirm(self, action):
        about = action['about']
        assert isinstance(about, tuple) and len(about) == 3, 'We model triplets only.'
        assertion = None
        if about[0] is not None and about[1] is None and about[2] is None:
            assertion = 'Have you mentioned %s?' % about[0]
        elif about[0] is None and about[1] is not None and about[2] is None:
            assertion = 'Is %s an action or property?' % about[1]
        elif about[0] is not None and about[1] is not None and about[2] is None:
            assertion = 'Is it possible that %s %s' % (about[0], about[1])
        elif about[0] is not None and about[1] is not None and about[2] is not None:
            assertion = 'Is it true that %s %s %s?' % about
        else:
            assertion = 'Really?'
        self.logger.debug('For action %s confirming by %s?', action, assertion)
        return assertion

    def inform(self, action):
        about = action['about']
        assert isinstance(about, tuple) and len(about) == 3, 'we model triplets only'
        assert about[1] is not None and about[1] is not None and about[2] is not None
        inform = ' '.join(about)
        self.logger.debug('For action %s informing by %s', inform)
        return inform


def indirect_object_q(triple):
    assert(isinstance(triple, tuple) and len(triple) == 3)
    assert(triple[0] is not None and triple[1] is not None and triple[2] is None)
    s, v, o = triple
    # TODO detect preposition
    prep = ''
    # FIXME improve according types
    return 'What %s does %s %s?' % (prep, s, v)

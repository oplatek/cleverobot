#!/usr/bin/env python
# encoding: utf-8
import bot


class Nlg(object):
    def __init__(self, logger=None):
        if logger is None:
            self.logger = bot.get_chatbot_logger()
        else:
            self.logger = logger
        self.nlgf = {
            'ask': self.open_questions,
            'confirm': self.confirm,
            'inform': self.inform,
            'greeting': lambda action: 'Hi!',
            'silence': lambda action: '...',
        }

    def action2lang(self, action):
        type = action['type']
        if type in self.nlgf:
            return self.nlgf[type](action)
        else:
            self.logger.error('Generated of natural language not supported for type %s', action)
        return None

    def open_questions(self, action):
        about = action['about']
        question = None
        assert isinstance(about, tuple) and len(about) == 3, 'we model triplets only'
        if about[0] is not None and about[1] is None and about[2] is None:
            question = 'Can you tell me more about %s ?' % about[0]
        elif about[0] is None and about[1] is not None and about[2] is None:
            question = 'What kind of action is %s ?' % about[1]
        elif about[0] is not None and about[1] is not None and about[2] is None:
            question = 'Tell me more about %s having %s ?' % (about[0], about[1])
        elif about[0] is not None and about[1] is not None and about[2] is not None:
            question = 'Tell me more facts about %s %s %s ?' % about
        else:
            question = 'What about do you think right now?'
        self.logger.debug('For action %s generated question %s', action, question)
        return question

    def confirm(self, action):
        about = action['about']
        assert isinstance(about, tuple) and len(about) == 3, 'We model triplets only.'
        assertion = None
        if about[1] is not None and about[1] is None and about[2] is None:
            assertion = 'Do you mean %s?' % about[1]
        elif about[0] is None and about[1] is not None and about[2] is None:
            assertion = 'What kind of action is %s' % about[1]
        elif about[0] is not None and about[1] is not None and about[2] is None:
            assertion = 'Tell me more about %s having %s' % (about[0], about[1])
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

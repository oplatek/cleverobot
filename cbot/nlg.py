#!/usr/bin/env python
# encoding: utf-8
import bot


class Nlg(object):
    def __init__(self, logger=None):
        if logger is None:
            self.logger = bot.get_chatbot_logger()
        else:
            self.logger = logger

    def action2lang(self, action):
        type = action['type']
        if type == 'ask':
            return self.open_questions(action)
        elif type == 'confirm':
            return self.confirm(action)
        elif type == 'inform':
            return self.inform(action)
        elif type == 'greeting':
            return 'Hi!'
        elif type == 'silence':
            return ' ... '
        else:
            self.logger.error('Generated of natural language not supported for type %s' % action)

    def open_questions(self, action):
        about = action['about']
        question = None
        assert isinstance(about, tuple) and len(about) == 3, 'we model triplets only'
        if about[1] is not None and about[1] is None and about[2] is None:
            question = 'Can you tell me more about %s ?' % about[1]
        elif about[0] is None and about[1] is not None and about[2] is None:
            question = 'What kind of action is %s ?' % about[1]
        elif about[0] is not None and about[1] is not None and about[2] is None:
            question = 'Tell me more about %s having %s ?' % (about[0], about[1])
        else:
            question = 'Really?'
        self.logger.debug('For action %s generated question %s' % (action, question))
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
        self.logger.debug('For action %s confirming by %s' % (action, assertion))
        return assertion

    def inform(self, action):
        about = action['about']
        assert isinstance(about, tuple) and len(about) == 3, 'we model triplets only'
        assert about[1] is not None and about[1] is not None and about[2] is not None
        inform = ' '.join(about)
        self.logger.debug('For action %s informing by %s' % inform)
        return inform

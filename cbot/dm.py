#!/usr/bin/env python
# encoding: utf-8
import abc
import random
import urllib2
import simplejson
import time
import cbot.bot
from nlg import Nlg


class State(object):
    form = {'phase': ['greeting', 'elisa', 'asking'], 'history': []}
    greetings = {'Hi', "Hey", "Hello"}

    def __init__(self):
        self.belief = {'phase': 'greeting', 'known_mentions': [], 'unknown_mentions': []}
        self.history = []
        self._validate_state()

    def _validate_state(self):
        # TODO validate json schema of state
        pass

    def update_state(self, msg, known_mentions, unknown_mentions):
        if len(self.history) > 100:  # FIXME handle history in more robust way
            self.history.pop(0)
        self.history.append(self.belief)
        self.belief['utterance'] = msg['utterance']
        self.belief['known_mentions'] = known_mentions
        self.belief['unknown_mentions'] = unknown_mentions
        self.belief.update(msg)
        self._validate_state()


class BaseAction(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self._name = self.__class__.__name__

    @property
    def name(self):
        return self._name

    def scores(self, state):
        return [self.repeated_probability(state),
                self.compatibility_probability(state),
                self.repeated_probability(state),
                self.need_probability(state)]

    def requested_probability(self, state):
        return 0.0

    @abc.abstractmethod
    def compatibility_probability(self, state):
        return 0.0

    def repeated_probability(self, state):
        return 0.0

    # @abc.abstractmethod
    def need_probability(self, state):
        return 0.0

    @abc.abstractmethod
    def act(self, state):
        """Return messages for actions
        based on state of dialogue
        and other resources e.g. KnowledgeBase
        which are provided to constructor of action"""
        return []


class ElisaAsk(BaseAction):
    def __init__(self):
        super(ElisaAsk, self).__init__()

    def compatibility_probability(self, state):
        # TODO return high probability if detected SVO sentence and O can be returned
        return 0.0

    def act(self, state):
        # TODO return O from SVO sentence
        w = 'Todo-california'
        return [{'type': 'ask', 'about': (w, None, None)}]


class KBRandomAsk(BaseAction):
    def __init__(self, kb):
        super(KBRandomAsk, self).__init__()
        self.kb = kb

    def compatibility_probability(self, state):
        return 1.0

    def act(self, state):
        actions = []
        # self.logger.debug("Pursue your own goal: get knowledge about something")
        # get fact to ask about FIXME interesting choice for user
        nodes = self.kb.get_nodes()
        rand_node = random.sample(nodes, 1)[0]
        # self.logger.debug('Sample node %s', rand_node)
        neighbours = self.kb.get_neighbours(rand_node)
        if len(neighbours) == 0:
            rand_rel = (rand_node, None, None)
        else:
            rand_rel = random.sample(neighbours, 1)[0]
            mask = [random.randrange(0, 2) for _ in xrange(3)]
            rand_rel = tuple([x if m == 0 else None for x, m in zip(rand_rel, mask)])
        qs = ['ask', 'confirm']
        action_type = random.sample(qs, 1)[0]
        assert action_type in Nlg.get_default_actions()
        actions.append({'type': action_type, 'about': rand_rel})
        return actions


class KBMentionAsk(BaseAction):
    def __init__(self, kb, ):
        super(KBMentionAsk, self).__init__()
        self.kb = kb
        self.limit = 2

    def compatibility_probability(self, state):
        # TODO
        return 1.0

    def act(self, state):
        actions = []
        kb_mentions = state.belief['known_mentions']
        for m in kb_mentions:
            actions.append({'type': 'confirm', 'about': m})
            if len(actions) > self.limit:
                break
        return actions


class Greeting(BaseAction):
    def __init__(self):
        super(Greeting, self).__init__()

    def compatibility_probability(self, state):
        # TODO extract from state if the user was greeted or wants to greeted again
        greeting_words = set(state.belief['utterance'].split()) & State.greetings
        if len(greeting_words) > 0:
            return 1.0
        else:
            return 0.0

    def act(self, state):
        greeting_num = 0
        return [{'type': 'greeting', 'greeting_number': greeting_num}]


class Goodbye(BaseAction):
    def __init__(self):
        super(Goodbye, self).__init__()

    def compatibility_probability(self, state):
        return 0.0

    def act(self, state):
        goodbye_num = 0
        return [{'goodbye': goodbye_num}]


class DisplayImage(BaseAction):

    @staticmethod
    def get_image_urls(search_term):
        url = 'https://ajax.googleapis.com/ajax/services/search/images?v=1.0&q=%s&start=0&userip=MyIP' % search_term
        request = urllib2.Request(url, None, {'Referer': 'testing'})
        response = urllib2.urlopen(request)

        # Get results using JSON
        results = simplejson.load(response)
        data_info = results['responseData']['results']

        urls = [u['unescapedUrl'] for u in data_info]
        return urls

    def __init__(self):
        super(DisplayImage, self).__init__()
        self.last_display = time.time()
        self.last_state = None
        self.last_url = None

    def compatibility_probability(self, state):
        # TODO detect facts and if any search relevant images
        return 0.0

    def need_probability(self, state):
        known_mentions = state.belief['known_mentions']
        if len(known_mentions) == 0:
            return 0.0
        else:
            best_mention = known_mentions[0]
            urls = DisplayImage.get_image_urls(best_mention)
            if len(urls) > 0:
                self.last_url = urls[0]
                return 1.0
            else:
                0.0

    def act(self, state):
        # default values
        best_mention, url = 'smiley', 'http://cleverobot.com/static/img/smiley.png'
        if state == self.last_state:
            url = self.last_url
        else:
            known_mentions = state.belief['known_mentions']
            if len(known_mentions) > 0:
                best_mention = known_mentions[0]
                urls = DisplayImage.get_image_urls(best_mention)
                if len(urls) > 0:
                    url = urls[0]
        image_tag = '<img src="%s" alt="%s height="40" width="40">' % (url, best_mention)
        return [{'type': 'raw', 'raw': "Let's see if I can find and Image"}, {'type': 'raw', 'raw': image_tag}]


class RulebasedPolicy(object):

    def __init__(self, kb, logger):
        self.greeting = Greeting()
        self.goodbye = Goodbye()
        self.elisaask = ElisaAsk()
        self.kbrandomask = KBRandomAsk(kb)
        self.kbmenttionask = KBMentionAsk(kb)
        self.displayimage = DisplayImage()
        self.logger = logger

    def act(self, state, kb):
        """TODO work with time and implement simple model of needs and attention:

        Need is gradually increasing until its fulfilled and reset.
        Think hunger, sex, thirst, ...

        Attention is highest just after sensing a stimulus and fades away.
        The stimuli must vary to keep attention.
        """
        belief = state.belief
        actions = []
        if self.greeting.compatibility_probability(state) > 0.5:
            return self.greeting.act(state)
        if self.displayimage.need_probability(state) > 0.5:
            actions.extend(self.displayimage.act(state))
        if len(belief['known_mentions']) > 0:
            actions.extend(self.kbmenttionask.act(state))
        elif len(belief['unknown_mentions']) > 0:
            actions.extend(self.elisaask.act(state))
        elif len(belief['known_mentions']) == 0 and len(belief['unknown_mentions']) == 0:
            actions.extend(self.kbrandomask.act(state))
        return actions

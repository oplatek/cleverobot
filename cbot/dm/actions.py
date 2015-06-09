#!/usr/bin/env python
# encoding: utf-8
"""
Previous actions and their arguments (including actor)
together with (text) user input, and system output
define the dialogue belief state.

Dialogue state update is done
based on user input with corresponding intended action,
and system output with corresponding intended action.

Recognizing one action from user input boost
probabilities for some actions, and diminishes for other actions.
Similarly, choosing one system action increase probability of
some actions (both human, and system), decreases probabilities of others because their incompatibility.
"""
from __future__ import division, unicode_literals
import abc
from copy import deepcopy
from cbot.dm.state import SimpleTurnState
# TODO add reasons for the NLU and DM outputs
# TODO implement reasons for actions


class BaseAction(object):
    """Actions represent intentions.
    Wrapper for information about actions
    One should interpret them not only at semantic level,
    but also on the pragmatic level.
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, state, actor, **properties):
        """
        Actor can be the human or the system.
        """
        assert isinstance(state, SimpleTurnState)
        assert actor == "human" or "system"
        self.name = self.__class__.__name__
        self.actor = actor
        self.state = state
        self.why_features = []
        self.args = {}
        self.reward = 1.0
        self.value = 1.0  # consider it probability during SLU # TODO fix
        self.surface_form = None
        # Override possibly the default values by
        for key, value in properties.items():
            setattr(self, key, value)

    @classmethod
    @abc.abstractmethod
    def user_action_detection_factory(cls, state):
        """SLU factored according actions suggest if there is any"""
        return []

    @classmethod
    @abc.abstractmethod
    def reaction_factory(cls, state, n=10, probability_threshold=0.0):
        """Return list of instances of the class which can be generated from the arguments
        Dialogue state update part: proposing actions. Act method
        """
        return []

    @abc.abstractmethod
    def description(self):
        return 'An %s action' % self._name

    # @property
    # def exp_time(self):
    # """It is used for value function, it penalize actions which cannot be
    # run very soon. This should be updated so the long running actions can be selected
    # if they are still convenient after one-two turns."""

    @abc.abstractmethod
    def act(self):
        """
        For user "User" said give response (said something) or changed her state (mind)
        System return response (say something) or change the state (change system's mind)

        TODO NLG can be seen as non deterministic process which does get us to the intended state.
        Value function should take this into account
        """
        pass

    def __str__(self):
        if self.surface_form is not None:
            return str(self.surface_form)
        else:
            return self.get_description()


class NoOp(BaseAction):
    @classmethod
    def user_action_detection_factory(cls, state):
        if not state.current_user_utterance:
            return NoOp(state, "human")
        else:
            return []

    @classmethod
    def reaction_factory(cls, state, n=10, probability_threshold=0.0):
        return [NoOp(state,
                     "system",
                     why_features=[state.user_actions[NoOp.__class__]], )
                ]

    def act(self):
        return

    def description(self):
        return "I just do nothing."


class Inform(BaseAction):
    @classmethod
    def user_action_detection_factory(cls, state):
        informs = []
        cuu = state.current_user_utterance
        if cuu.svo[1] < cuu.svo[0]:  # svo subject, verb, object
            return []  # Question
        svo = dict(zip(('subj', 'verb', 'obj'), (cuu.tokens[i] for i in cuu.svo)))
        svo_expanded = [(w, 'has_pos', pos) for pos, w in svo.iteritems()]

        # Informing about previously asked triple
        asked_actions = [a for a in state.system_actions.values() if isinstance(a, WhatAsk)]
        for a in asked_actions:
            why_features = []
            for r, w in svo.iteritems():
                if w in a.args:
                    why_features.extend(
                        [('I', 'choose_action', str(a)), (str(a), 'has_argument', w), ('you', 'said', w)])
                    why_features.extend(svo_expanded)
            if len(why_features) > 0:
                informs.append((Inform(state, "human", args=svo, why_features=why_features)))
        # Informing from unknown reason
        if len(informs) < 6:  # heuristics 3! == 6 however action may ask about the same one argument
            if None not in svo.items():
                informs.append(Inform(state, "human", args=svo, why_features=svo_expanded, value=0.5))
        # Tuning value manually
        forbidden_found = any((c in cuu for c in ['!', '?', 'ask', 'you']))  # questions are not in inform style
        welcome_found = any((c in cuu for c in ['she', 'they', 'is', 'was']))  # 3rd persona is inform style
        for act in informs:
            if forbidden_found:
                act.value /= 2
            if welcome_found:
                act.value = max(1.0, act.value * 2.0)
        return informs

    @classmethod
    def reaction_factory(cls, state, n=10, probability_threshold=0.0):
        informs = []
        for i, triplet in enumerate(state.last_mentions()):
            # FIXME TODO use knowledge base end extract missing operands for triplets
            # for example (sacramento, is_capital, ?) -> (sacramento, is_capital, California)
            if any((c is not None for c in triplet)):
                informs.append(Inform(state, "system", args=triplet))
        return informs

    def description(self):
        return "Inform about %s" % self.args.values()

    def act(self):
        # TODO nlg
        return str(self.args.values())


class WhatAsk(BaseAction):  # TODO
    @classmethod
    def user_action_detection_factory(cls, state):
        pass

    @classmethod
    def reaction_factory(cls, state, n=10, probability_threshold=0.0):
        pass

    def description(self):
        return "Ask about open question about %s", self.args

    def act(self):
        pass


class YesNoAsk(BaseAction):
    @classmethod
    def user_action_detection_factory(cls, state):
        questions = []
        cuu = state.current_user_utterance
        subj, verb, _ = cuu.svo
        if verb is not None and subj is not None and verb == 0:
            svo = dict(zip(('subj', 'verb', 'obj'), (cuu.tokens[i] for i in cuu.svo)))
            questions.append(YesNoAsk(state, "human", args=svo))
        return questions

    @classmethod
    def reaction_factory(cls, state, n=10, probability_threshold=0.0):
        # TODO
        # have you said? // problem with understanding
        # is it correct to say // problem with nlg
        # should I do // problem with action selection
        # TODO store in triplet format all the actions
        # TODO confirm some of the fact from knowledgebase
        questions = [YesNoAsk(state, "system", args=('You', 'did', state.last_user_action)),
                     YesNoAsk(state, "system", args=('Sacramento', 'isCapitalOf', 'California'))]
        return questions

    def act(self):
        # TODO nlg
        s, r, o = self.args
        return ' '.join([str(i) for i in (r, s, o, '?')]).title()

    def description(self):
        return 'Ask yes no questions about %s' % self.args


class Confirm(BaseAction):
    @classmethod
    def user_action_detection_factory(cls, state):
        def confirming_surface_form(utt):
            # TODO move to NL module.
            # TODO NL module should be symmetric NLU and NLG so it can learn.
            utt = utt.lower()
            positive_words = ['yes', 'sure', 'why not', 'yeah', 'anything', 'every time']
            return any(i in utt for i in positive_words)

        confirms = []
        if isinstance(state.last_system_action, YesNoAsk) \
                and confirming_surface_form(state.current_user_utterance):
            confirms.append(Confirm(state, "human",
                                    args=state.last_system_action.args,
                                    why_features=[state.current_user_utterance, state.last_system_action]))
        return confirms

    @classmethod
    def reaction_factory(cls, state, n=10, probability_threshold=0.0):
        informs = Inform.reaction_factory(state)
        confirms = []
        for i in informs:
            # TODO check this hack
            c = deepcopy(i)
            c.__class__ = Inform
            confirms.append(c)
        return confirms

    def act(self):
        # TODO nlg
        return "Can you confirm that %s" % self.args

    def description(self):
        return "Confirm %s." % self.args


class Reject(BaseAction):
    @classmethod
    def user_action_detection_factory(cls, state):
        def rejecting_surface_form(utt):
            # TODO move to NL module
            utt = utt.lower()
            reject_words = ['no', 'never', 'nothing']
            return any(i in utt for i in reject_words)

        rejects = []
        # TODO one may reject also request
        if isinstance(state.last_system_action, YesNoAsk) \
                and rejecting_surface_form(state.current_user_utterance):
            rejects.append(Reject(state, "human",
                                  args=state.last_system_action.args,
                                  why_features=[state.current_user_utterance, state.last_system_action]))

    @classmethod
    def reaction_factory(cls, state, n=10, probability_threshold=0.0):
        informs = Inform.reaction_factory(state)
        rejects = []
        for i in informs:
            # TODO check this hack
            c = deepcopy(i)
            c.__class__ = Reject
            rejects.append(c)
        return rejects

    def description(self):
        return "Reject %s" % self.args

    def act(self):
        return "Reject %s" % self.args


class Hello(BaseAction):
    @classmethod
    def user_action_detection_factory(cls, state):
        greetings = []
        # TODO simplistic use nlg variations or classification
        if 'hi' in state.current_user_utterance.lower():
            greetings.append(Hello(state, "human"))


    @classmethod
    def reaction_factory(cls, state, n=1, probability_threshold=0.0):
        greetings = []
        if len(state.user_actions) < 5:
            greetings.append(Hello(state, "system"))
        if Hello.__class__ in state.system_actions:
            for act in greetings:
                act.value /= 2
        if Hello.__class__ in state.user_actions:
            for act in greetings:
                act.value = min(1.0, (act.value * 2) + 0.3)
        return greetings

    def description(self):
        return "I said hello to you. In fact I said: '%s'" % self.surface_form

    def act(self):
        # TODO use nlg module, sample from more greetings, enable propagate propagation to NLG module
        self.surface_form = 'Hi!'


class GoodBye(BaseAction):
    @classmethod
    def user_action_detection_factory(cls, state):
        goodbyes = []
        # TODO very very simplistic detect bye
        if "bye" in state.current_user_utterance:
            goodbyes.append(GoodBye(state, "human"))
        return goodbyes

    @classmethod
    def reaction_factory(cls, state, n=10, probability_threshold=0.0):
        goodbyes = []
        if GoodBye.__class__ in state.user_actions:
            goodbyes.append(GoodBye(state, "system"))
        if NoOp.__class__ in state.user_actions:
            goodbyes.append(GoodBye(state, "system",
                                    why_features=[state.user_actions[NoOp.__class__]],
                                    value=0.5))
        return goodbyes

    def description(self):
        # TODO use nlg for the description
        return "I said goodbye. I used the words '%s'" % self.surface_form

    def act(self):
        # TODO nlg
        return "Goodbye"


# class IConfirm(BaseAction):
#     pass


# class Request(BaseAction):
#     pass


# class EncourageAsk(BaseAction):
#     pass
#
#
# class Complain(BaseAction):
#     pass
#
#
# class Compliment(BaseAction):
#     pass

# # TODO how to use action - where I do not understand nothing
# class Unknown(BaseAction):
#     pass

# class SelectionAsk(BaseAction):
# pass


############# Actions which still not implemented ###########
# # Strange - TODO something like Agenda based DS
# class StartTopic(BaseAction):
# class ConfirmTopic(BaseAction)


# class DisplayImage(BaseAction):
# TODO system only
#
# @staticmethod
#     def get_image_urls(search_term):
#         assert isinstance(search_term, tuple) and len(search_term) == 3
#         search_term = ' '.join([t for t in search_term if t is not None]).replace(' ', '%20')
#         url = "https://ajax.googleapis.com/ajax/services/search/images?v=1.0&q=%s&start=0&userip=MyIP" % search_term
#         print url
#         request = urllib2.Request(url, None, {'Referer': 'testing'})
#         response = urllib2.urlopen(request)
#
#         # Get results using JSON
#         results = simplejson.load(response)
#         data_info = results['responseData']['results']
#
#         urls = [u['unescapedUrl'] for u in data_info]
#         return urls
#
#     def __init__(self):
#         super(DisplayImage, self).__init__()
#         self.last_display = time.time()
#         self.last_state = None
#         self.last_url = None
#
#     def compatibility_probability(self, state):
#         # TODO detect facts and if any search relevant images
#         return 0.0
#
#     def need_probability(self, state):
#         known_mentions = state.belief['known_mentions']
#         if len(known_mentions) == 0:
#             return 0.0
#         else:
#             best_mention = known_mentions[0]
#             urls = DisplayImage.get_image_urls(best_mention)
#             if len(urls) > 0:
#                 self.last_url = urls[0]
#                 return 1.0
#             else:
#                 0.0
#
#     def act(self, state):
#         # default values
#         best_mention, url = 'smiley', 'http://cleverobot.com/static/img/smiley.png'
#         if state == self.last_state:
#             url = self.last_url
#         else:
#             known_mentions = state.belief['known_mentions']
#             if len(known_mentions) > 0:
#                 best_mention = known_mentions[0]
#                 urls = DisplayImage.get_image_urls(best_mention)
#                 if len(urls) > 0:
#                     url = urls[0]
#         image_tag = '<img src="%s" alt="%s height="40" width="40">' % (url, best_mention)
#         return [{'type': 'raw', 'raw': "Let's see if I can find and Image"}, {'type': 'raw', 'raw': image_tag}]

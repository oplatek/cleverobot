LOGGING_ADDRESS = 'tcp://127.0.0.1:6699'
BELIEF_STATE = 'belief_state'
HUMAN = 'human'
SYSTEM = 'chat_bot'  # using just string because of circular dependencies TODO change to something sensible
REPLAYED = 'replayed'
BELIEF_STATE_REPLAY = BELIEF_STATE + '_' + REPLAYED

BASIC_JSON_MSG_SCHEMA = {
    "name": "string",
    "session": "string"
}

CHATBOT_MSG_LOGGER = 'ChatBotZMQ_messages'

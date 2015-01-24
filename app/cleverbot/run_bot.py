import argparse
from cbot.bot import ChatBot
from cbot.bot_exceptions import *

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='cleverbot backend')
    parser.add_argument('--bot-input',default='6666')
    parser.add_argument('--bot-output',default='7777')
    args = parser.parse_args()
    bot = ChatBot(args.bot_input, args.bot_output)
    bot.start()

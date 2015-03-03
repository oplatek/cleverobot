import argparse
import signal
from cbot.bot import ChatBot

bot = None


def quit_gracefully(*args):
    if bot is not None:
        bot.terminate()
        bot.join()

if __name__ == '__main__':
    signal.signal(signal.SIGINT, quit_gracefully)
    try:
        parser = argparse.ArgumentParser(description='cleverbot backend')
        parser.add_argument('--bot-input',default='6666')
        parser.add_argument('--bot-output',default='7777')
        args = parser.parse_args()
        bot = ChatBot(args.bot_input, args.bot_output)
        bot.start()
        bot.join()
    finally:
        quit_gracefully()

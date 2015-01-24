#!/bin/sh

PYTHONPATH=../../:$PYTHONPATH python run.py --host 127.0.0.1 --port 3000 --bot-input 6666 --bot-output 7777 &
echo "Launched webapp in background. PID: $!"

PYTHONPATH=../../PYTHONPATH=../../:$PYTHONPATH python run_bot.py --bot-input 6666 --bot-output 7777

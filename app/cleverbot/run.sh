#!/bin/sh

PYTHONPATH=../../PYTHONPATH=../../:$PYTHONPATH python run_bot.py --bot-input 6666 --bot-output 7777 &
PID="$!"
echo "Launched chatbot in background. PID: $PID"

PYTHONPATH=../../:$PYTHONPATH python run.py --host 127.0.0.1 --port 3000 --bot-input 6666 --bot-output 7777 

echo "Keyboard interrup to chatbot backend $PID"
kill -SIGINT $PID

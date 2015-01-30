
all: build


test: unit-test

integration-test:
	echo 'TODO integration tests'

run_native:
	cd app/cleverbot; bash run.sh


unit-test:
	PYTHONPATH=cbot nosetests -e test_factory app/cleverbot/
	PYTHONPATH=cbot nosetests -e test_factory cbot

build:
	docker build -t oplatek/cleverobot .

pull:
	docker pull docker pull  oplatek/cleverobot

run_docker:
	docker run -p 3000:3000 -i -t --rm oplatek/cleverobot /bin/bash -c 'cd app/cleverbot; PYTHONPATH=../../PYTHONPATH=../../:$$PYTHONPATH python run_bot.py --bot-input 6666 --bot-output 7777 & PID="$$!"; echo "Launched chatbot in background. PID: $$PID" ; PYTHONPATH=../../:$$PYTHONPATH python run.py --host 0.0.0.0 --port 3000 --bot-input 6666 --bot-output 7777 --no-debug; echo "Keyboard interrup to chatbot backend $$PID" ; kill -SIGINT $$PID'

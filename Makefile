PORT=3000
DEBUG='--no-debug'  # [--no-debug|--debug]
# DATA_VOLUMES=${CURDIR} # TODO and copy out logs and recorded dialogues
VOLUMES=-v ${CURDIR}:/opt/cleverobot

RUN_BOT=export NLTK_DATA=`pwd`/nltk_data; export PYTHONPATH=`pwd`:$PYTHONPATH; cd app/cleverbot; python run_bot.py --bot-input 6666 --bot-output 7777 & PID="$$!"; echo "Launched chatbot in background. PID: $$PID" ; python run.py --host $$ADDRESS --port $(PORT) --bot-input 6666 --bot-output 7777 $(DEBUG); echo "Keyboard interrup to chatbot backend $$PID" ; kill -SIGINT $$PID


all: build


test: unit-test

integration-test:
	echo 'TODO integration tests'


unit-test:
	PYTHONPATH=cbot nosetests -e test_factory app/cleverbot/
	PYTHONPATH=cbot nosetests -e test_factory cbot

build:
	docker build -t oplatek/cleverobot .

pull:
	docker pull docker pull oplatek/cleverobot

run: nltk_data
	export ADDRESS=127.0.0.1; $(RUN_BOT)

nltk_data:
	export NLTK_DATA=$(CURDIR)/nltk_data;  python scripts/download_nlt_data.py 
	@echo 'Makefile does not check content of $@ only of exists'

run_docker: nltk_data
	echo TODO fix me
	docker run $(VOLUMES) -e ADDRESS=0.0.0.0 -p $(PORT):$(PORT) -i -t --rm oplatek/cleverobot /bin/bash -c '$(RUN_BOT)'

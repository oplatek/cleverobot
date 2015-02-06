PORT=3000
DEBUG='--no-debug'  # [--no-debug|--debug]
# DATA_VOLUMES=${CURDIR} # TODO and copy out logs and recorded dialogues
VOLUMES=-v ${CURDIR}:/opt/cleverobot



all: build



build:
	docker build -t oplatek/cleverobot .

pull:
	docker pull docker pull oplatek/cleverobot


nltk_data:
	export NLTK_DATA=$(CURDIR)/nltk_data;  python scripts/download_nlt_data.py 
	@echo 'Makefile does not check content of $@ only of exists'

#### run ####
RUN_BOT=export NLTK_DATA=`pwd`/nltk_data; export PYTHONPATH=`pwd`:$$PYTHONPATH; cd app/cleverbot; python run_bot.py --bot-input 6666 --bot-output 7777 & PID="$$!"; echo "Launched chatbot in background. PID: $$PID" ; python run.py --host $$ADDRESS --port $(PORT) --bot-input 6666 --bot-output 7777 $(DEBUG); echo "Keyboard interrup to chatbot backend $$PID" ; kill -SIGINT $$PID

run: nltk_data
	export ADDRESS=127.0.0.1; $(RUN_BOT)
run_docker: nltk_data
	docker run $(VOLUMES) -e ADDRESS=0.0.0.0 -p $(PORT):$(PORT) -i -t --rm oplatek/cleverobot /bin/bash -c '$(RUN_BOT)'

#### tests ####
TEST_BOT='export PYTHONPATH=cbot:$$PYTHONPATH; nosetests -e test_factory app/cleverbot/; nosetests -e test_factory cbot'
test: unit-test
integration-test:
	echo 'TODO integration tests'
unit-test:
	docker run $(VOLUMES) -i -t --rm oplatek/cleverobot /bin/bash -c '$(TEST_BOT)'

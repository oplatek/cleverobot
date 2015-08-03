SHELL=/bin/bash
PORT=3000
DEBUG='--no-debug'  # [--no-debug|--debug]
# DATA_VOLUMES=${CURDIR} # TODO and copy out logs and recorded dialogues
VOLUMES=-v ${CURDIR}:/opt/cleverobot
MODEL_PREFIX_URL=http://vystadial.ms.mff.cuni.cz/download/cleverobot


all: build

#### Docker support####
docker-build:
	docker build -t oplatek/cleverobot .

docker-pull:
	docker pull oplatek/cleverobot

docker-stop:
	docker kill oplatek/cleverobot
	docker rm oplatek/cleverobot

nltk_data:
	export NLTK_DATA=$(CURDIR)/nltk_data;  python scripts/download_nltk_data.py 
	@echo 'Makefile does not check content of $@ only of exists'

#### run ####
RUN_BOT=export NLTK_DATA=`pwd`/nltk_data; export PYTHONPATH=`pwd`/cbot:$$PYTHONPATH; python app/cleverobot/run.py --host $$ADDRESS --port $(PORT) $(DEBUG);

run: nltk_data
	export ADDRESS=127.0.0.1; $(RUN_BOT)
docker-run: nltk_data
	docker run $(VOLUMES) -e ADDRESS=0.0.0.0 -p $(PORT):$(PORT) -i -t --rm oplatek/cleverobot /bin/bash -c '$(RUN_BOT)'

#### tests ####
UNIT_TEST=export NLTK_DATA=`pwd`/nltk_data; nosetests --with-coverage cbot
INTEGRATION_TEST=echo "SKIPPING integration tests TODO single instance expected: FAILING export NLTK_DATA=`pwd`/nltk_data; nosetests app"

test: unit-test integration-test
unit-test: download_models
	$(UNIT_TEST)
integration-test: download_models
	$(INTEGRATION_TEST)
docker-test: docker-unit-test docker-integration-test
docker-integration-test:
	docker run $(VOLUMES) -i -t --rm oplatek/cleverobot /bin/bash -c '$(INTEGRATION_TEST)'
docker-unit-test:
	docker run $(VOLUMES) -i -t --rm oplatek/cleverobot /bin/bash -c '$(UNIT_TEST)'

# TODO probably will fail if lot of logs stored (bash expansion will fail)
get-production-logs:
	scp -C -p root@147.251.253.222:/var/cache/openafs/code/cleverobot/cbot/logs/*.log .

# FIXME not working
# production-logs2ufal:
# 	scp -C root@147.251.253.222:/var/cache/openafs/code/cleverobot/cbot/logs/*.log oplatek@shrek.ms.mff.cuni.cz:/net/projects/vystadial/data/chat/

download_models: cbot/lu/tagger.pickle

cbot/lu/tagger.pickle:
	wget $(MODEL_PREFIX_URL)/$@ -O $@

logs2ufal:
	scp -C -p cbot/logs/*.log oplatek@shrek.ms.mff.cuni.cz:/net/projects/vystadial/data/chat/new

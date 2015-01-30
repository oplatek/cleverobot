


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
	docker run -p 3000:3000 -i -t --rm oplatek/cleverobot /bin/bash -c 'make -C /opt/cleverobot run_native'

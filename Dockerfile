FROM      ubuntu:14.04
MAINTAINER ONDREJ PLATEK <ondrej.platek@gmail.com>

# TODO create base Dockerfile from this file and function specific inherited files

RUN apt-get update
RUN apt-get install -y wget build-essential python python-dev python-distribute python-pip libzmq3 libzmq3-dev

ADD . /opt/cleverobot/
WORKDIR /opt/cleverobot/
RUN pip install -r bot-requirements.txt -r app-requirements.txt

RUN make test

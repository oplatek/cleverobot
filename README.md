# cleverobot
"Cleverobot", a chatbot so clever that cannot even spell two words correctly

[![Build Status](https://travis-ci.org/oplatek/cleverobot.svg?branch=master)](https://travis-ci.org/oplatek/cleverobot) 
[![Health](https://landscape.io/github/oplatek/cleverobot/master/landscape.png)](https://landscape.io/github/oplatek/cleverobot/master)
[![Coverage Status](https://coveralls.io/repos/oplatek/cleverobot/badge.svg)](https://coveralls.io/r/oplatek/cleverobot)

## Style and libraries used
* Flask-SocketIO for webapp
   - Each user has private room with its own ChatBot
* PyZMQ:
    * zmq.green for webapp ChatBotConnector, and zmq for ChatBot
    * Each ChatBot runs in separate process and receive and sends messages to webapp user session via _publish/subscribe_ device 


#!/usr/bin/env python
# encoding: utf-8
from flask import Flask, render_template
import argparse

app = Flask(__name__)
app.secret_key = 12345  # TODO


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='cleverbot app')
    parser.add_argument('-p', '--port', type=int, default='5000')
    parser.add_argument('-t', '--host', default='127.0.0.1')
    parser.add_argument('-d', '--debug', dest='debug', action='store_true')
    parser.add_argument('--no-debug', dest='debug', action='store_false')
    parser.set_defaults(debug=True)
    args= parser.parse_args()

    app.run(host=args.host, port=args.port, debug=args.debug)

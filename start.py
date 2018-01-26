from flask import Flask, current_app
import logging
import os
import sys
import json
from kafka import KafkaConsumer, TopicPartition
from threading import Thread
import eventlet
import requests

from context import app, security

from pages import pages_blueprint

from services.explgbk import explgbk_blueprint
from flask_socket_util import socket_service

import dal.explgbk

__author__ = 'mshankar@slac.stanford.edu'


# Initialize application.
app = Flask("explgbk")
# Set the expiration for static files
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300;

app.secret_key = "This is a secret key that is somewhat temporary."
app.debug = bool(os.environ.get('DEBUG', "False"))

if app.debug:
    print("Sending all debug messages to the console")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    logging.getLogger('kafka').setLevel(logging.INFO)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)

logger = logging.getLogger(__name__)

# Register routes.
app.register_blueprint(pages_blueprint)
app.register_blueprint(explgbk_blueprint)

socket_service.init_app(app, security, kafkatopics = ["experiment", "elog", "runs"])

dal.explgbk.init_app(app)

logger.info("Server initialization complete")

if __name__ == '__main__':
    print("Please use gunicorn for development as well.")
    sys.exit(-1)

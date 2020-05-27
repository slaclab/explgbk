from flask import Flask, current_app
import logging
import os
import sys
import json
from kafka import KafkaConsumer, TopicPartition
from threading import Thread
import eventlet
import requests
import urllib3

from context import app, security

from pages import pages_blueprint

from services.explgbk import explgbk_blueprint
from flask_socket_util import socket_service

import dal.exp_cache

__author__ = 'mshankar@slac.stanford.edu'


# Initialize application.
app = Flask("explgbk")
# Set the expiration for static files
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 300;

app.secret_key = "This is a secret key that is somewhat temporary."
app.debug = bool(os.environ.get('DEBUG', "False"))

@app.template_filter('json')
def jinga2_jsonfilter(value):
    return json.dumps(value)


if app.debug:
    print("Sending all debug messages to the console")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    logging.getLogger('kafka').setLevel(logging.INFO)
    logging.getLogger('engineio').setLevel(logging.WARN)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)

logger = logging.getLogger(__name__)

# Turn off a RFC compliance warning; remove this once we get a SSL cert that works with requests.
urllib3.disable_warnings(urllib3.exceptions.SubjectAltNameWarning)


# Register routes.
app.register_blueprint(pages_blueprint)
app.register_blueprint(explgbk_blueprint)

socket_service.init_app(app, security, kafkatopics = ["experiments", "elog", "runs", "shifts", "samples", "file_catalog", "workflow_jobs"])

dal.exp_cache.init_app(app)

logger.info("Server initialization complete")

if __name__ == '__main__':
    print("Please use gunicorn for development as well.")
    sys.exit(-1)

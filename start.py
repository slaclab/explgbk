from flask import Flask, current_app
import logging
import os
import sys
import json
from kafka import KafkaConsumer, TopicPartition
from threading import Thread
import eventlet
import requests

from context import app, logbook_db, security

from pages import pages_blueprint

from services.business_service import business_service_blueprint
from flask_socket_util import socket_service

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


# Register routes.
app.register_blueprint(pages_blueprint, url_prefix="")
app.register_blueprint(business_service_blueprint, url_prefix="/ws/business")

socket_service.init_app(app, security, kafkatopics = ["elog"])

logbook_db.init_app(app)

if __name__ == '__main__':
    print("Please use gunicorn for development as well.")
    sys.exit(-1)

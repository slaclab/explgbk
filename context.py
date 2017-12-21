import json
import logging
import os

from pymongo import MongoClient

from flask_mysql_util import MultiMySQL
from flask_authnz import FlaskAuthnz, MongoDBRoles, UserGroups

from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)

__author__ = 'mshankar@slac.stanford.edu'

# Application context.
app = None

# Set up connections to the databases
logbook_db = MultiMySQL(prefix="LOGBOOK")

# Set up the security manager
mongorolereaderclient = MongoClient(host="localhost", port=27017, username="roleReader", password="slac123", authSource="admin")
security = FlaskAuthnz(MongoDBRoles(mongorolereaderclient, UserGroups()), "LogBook")

def __getKafkaProducer():
    if os.environ.get("SKIP_KAFKA_CONNECTION", False):
        return None
    else:
        return KafkaProducer(bootstrap_servers=[os.environ.get("KAFKA_BOOTSTRAP_SERVER", "localhost:9092")], value_serializer=lambda m: json.dumps(m).encode('utf-8'))

kafka_producer = __getKafkaProducer()

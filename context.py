import json
import logging
import os

from pymongo import MongoClient

from flask_authnz import FlaskAuthnz, MongoDBRoles, UserGroups

from kafka import KafkaProducer
from kafka.errors import KafkaError

from dal.utils import JSONEncoder


logger = logging.getLogger(__name__)

__author__ = 'mshankar@slac.stanford.edu'

# Application context.
app = None


# Set up the security manager
mongorolereaderclient = MongoClient(host="localhost", port=27017, username="roleReader", password="slac123", authSource="admin")
usergroups = UserGroups()
security = FlaskAuthnz(MongoDBRoles(mongorolereaderclient, usergroups), "LogBook")

logbookclient = MongoClient(host="localhost", port=27017, username="admin", password="slac123", authSource="admin")


def __getKafkaProducer():
    if os.environ.get("SKIP_KAFKA_CONNECTION", False):
        return None
    else:
        return KafkaProducer(bootstrap_servers=[os.environ.get("KAFKA_BOOTSTRAP_SERVER", "localhost:9092")], value_serializer=lambda m: JSONEncoder().encode(m).encode('utf-8'))

kafka_producer = __getKafkaProducer()

imagestoreurl = "http://localhost:9333/"
if not imagestoreurl.endswith("/"):
    imagestoreurl = imagestoreurl + "/"

# Instrument scientist run table definitions/descriptions/categoris are typically defined in a JSON file external to this project
# We load this from the file if it exists and create a reverse mapping from PV -> Category/Description
# There is a per instrument breakdown in this file and a all-instrument section called "HEADER" which I presume we add to all instruments
instrument_scientists_run_table_defintions = {}
if os.path.exists("/reg/g/psdm/web/ws/prod/appdata/runtablePVs/sections.json"):
    def reverse_mapping_for_section(section):
        return { x["name"]: {"section" : section["SECTION"], "title": section["TITLE"], "pv": x["name"], "description": x["descr"]} for x in section["PARAMS"] }
    with open("/reg/g/psdm/web/ws/prod/appdata/runtablePVs/sections.json", 'r') as f:
        isdefs = json.load(f)
        for instrument, sections in isdefs.items():
            instrument_scientists_run_table_defintions[instrument] = {}
            for section in sections:
                instrument_scientists_run_table_defintions[instrument].update(reverse_mapping_for_section(section))

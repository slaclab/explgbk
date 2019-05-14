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

MONGODB_HOST=os.environ.get('MONGODB_HOST', "localhost")
MONGODB_PORT=int(os.environ.get('MONGODB_PORT', 27017))
MONGODB_HOSTS=os.environ.get("MONGODB_HOSTS", None)
if MONGODB_HOSTS:
    MONGODB_HOSTS = MONGODB_HOSTS.split(",")
else:
    MONGODB_HOSTS = [ MONGODB_HOST + ":" + str(MONGODB_PORT) ]
MONGODB_USERNAME=os.environ['MONGODB_USERNAME'] or 'roleReader'
MONGODB_PASSWORD=os.environ['MONGODB_PASSWORD'] or 'slac123'

MONGODB_ADMIN_USERNAME=os.environ['MONGODB_ADMIN_USERNAME'] or 'admin'
MONGODB_ADMIN_PASSWORD=os.environ['MONGODB_ADMIN_PASSWORD'] or 'slac123'

# This identifies the current deployment site.
# Functionality that depends on the deployment location is based off this variable.
# For example, use LCLS for LCLS, Cryo for Cryo.
LOGBOOK_SITE = os.environ.get('LOGBOOK_SITE', 'test')

# Support for serving previews from the web server. Previews can get quite large and having python serve them is sometimes not practical.
# Add run parms using ws/ext_preview. This preview_prefix will then be prepended to the path to serve the image.
# A hash is added as part of the URL hashed with the PREVIEW_PREFIX_SHARED_SECRET
PREVIEW_PREFIX = os.environ.get('PREVIEW_PREFIX', '../../..')
PREVIEW_PREFIX_SHARED_SECRET = os.environ.get('PREVIEW_PREFIX_SHARED_SECRET', "SLACExpLgBk")


# Set up the security manager
mongorolereaderclient = MongoClient(host=MONGODB_HOSTS, username=MONGODB_USERNAME, password=MONGODB_PASSWORD, authSource="admin", tz_aware=True)
usergroups = UserGroups()
roleslookup = MongoDBRoles(mongorolereaderclient, usergroups)
security = FlaskAuthnz(roleslookup, "LogBook")
ldapadminsecurity = FlaskAuthnz(roleslookup, "LDAP")

logbookclient = MongoClient(host=MONGODB_HOSTS, username=MONGODB_ADMIN_USERNAME, password=MONGODB_ADMIN_PASSWORD, authSource="admin", tz_aware=True)


def __getKafkaProducer():
    if os.environ.get("SKIP_KAFKA_CONNECTION", False):
        return None
    else:
        return KafkaProducer(bootstrap_servers=[os.environ.get("KAFKA_BOOTSTRAP_SERVER", "localhost:9092")], value_serializer=lambda m: JSONEncoder().encode(m).encode('utf-8'))

kafka_producer = __getKafkaProducer()

imagestoreurl = os.environ.get("IMAGE_STORE_URL", "http://localhost:9333/")
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

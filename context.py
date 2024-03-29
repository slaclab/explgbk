import json
import logging
import os
import datetime

from queue import Queue

from pymongo import MongoClient, ReadPreference

from flask_authnz import FlaskAuthnz, MongoDBRoles, UserGroups

from kafka import KafkaProducer
from kafka.errors import KafkaError

from dal.utils import JSONEncoder
import jwt

logger = logging.getLogger(__name__)

__author__ = 'mshankar@slac.stanford.edu'

# Application context.
app = None

MONGODB_HOST=os.environ.get('MONGODB_HOST', "localhost")
MONGODB_PORT=int(os.environ.get('MONGODB_PORT', 27017))
MONGODB_HOSTS=os.environ.get("MONGODB_HOSTS", None)
if not MONGODB_HOSTS:
    MONGODB_HOSTS = MONGODB_HOST + ":" + str(MONGODB_PORT)
MONGODB_URL=os.environ.get("MONGODB_URL", None)
if not MONGODB_URL:
    MONGODB_URL = "mongodb://" + MONGODB_HOSTS + "/admin"

MONGODB_USERNAME=os.environ['MONGODB_USERNAME']
MONGODB_PASSWORD=os.environ['MONGODB_PASSWORD']


# This identifies the current deployment site.
# Functionality that depends on the deployment location is based off this variable.
# For example, use LCLS for LCLS, Cryo for Cryo.
LOGBOOK_SITE = os.environ.get('LOGBOOK_SITE', 'test')

# Use this information to get basic information from URAWI.
URAWI_URL = os.environ.get("URAWI_EXPERIMENT_LOOKUP_URL", None)

# Support for serving previews from the web server. Previews can get quite large and having python serve them is sometimes not practical.
# Add run parms using ws/ext_preview. This preview_prefix will then be prepended to the path to serve the image.
# A hash is added as part of the URL hashed with the PREVIEW_PREFIX_SHARED_SECRET
PREVIEW_PREFIX = os.environ.get('PREVIEW_PREFIX', '../../..')
PREVIEW_PREFIX_SHARED_SECRET = os.environ.get('PREVIEW_PREFIX_SHARED_SECRET', "SLACExpLgBk")


# Set up the security manager
mongorolereaderclient = MongoClient(host=MONGODB_URL, username=MONGODB_USERNAME, password=MONGODB_PASSWORD, tz_aware=True, read_preference=ReadPreference.SECONDARY_PREFERRED)
usergroups = UserGroups()
roleslookup = MongoDBRoles(mongorolereaderclient, usergroups)
security = FlaskAuthnz(roleslookup, "LogBook")

logbookclient = MongoClient(host=MONGODB_URL, username=MONGODB_USERNAME, password=MONGODB_PASSWORD, tz_aware=True, read_preference=ReadPreference.PRIMARY_PREFERRED)

local_kafka_events = Queue()

class MyKafkaProducer(KafkaProducer):
    def __init__(self, *args, **kwargs):
        super(MyKafkaProducer, self).__init__(*args, **kwargs)
    def send(self, topic, value, *args, **kwargs):
        local_kafka_events.put({"topic": topic, "value": JSONEncoder().encode(value).encode('utf-8')})
        super(MyKafkaProducer, self).send(topic, value, *args, **kwargs)

def __getKafkaProducer():
    misc_params = {}
    if os.environ.get("SKIP_KAFKA_CONNECTION", False):
        return None
    else:
        # if LOGBOOK_SITE=="CryoEM":
        #     misc_params["acks"] = 0
        return MyKafkaProducer(bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVER", "localhost:9092").split(","), value_serializer=lambda m: JSONEncoder().encode(m).encode('utf-8'), **misc_params)

kafka_producer = __getKafkaProducer()

imagestoreurl = os.environ.get("IMAGE_STORE_URL", "http://localhost:9333/")
if not imagestoreurl.endswith("/"):
    imagestoreurl = imagestoreurl + "/"

MAX_ATTACHMENT_SIZE = float(os.environ.get("MAX_ATTACHMENT_SIZE", "6291456"))

# Instrument scientist run table definitions/descriptions/categoris are typically defined in a JSON file external to this project
# We load this from the file if it exists and create a reverse mapping from PV -> Category/Description
# There is a per instrument breakdown in this file and a all-instrument section called "HEADER" which I presume we add to all instruments
instrument_scientists_run_table_defintions = {}
run_table_secions_json = os.environ.get("RUNTABLE_SECTIONS_JSON", None)

def load_sections_json():
    if run_table_secions_json and os.path.exists(run_table_secions_json):
        logger.info("Loading run table instrument scientist descriptions from %s", run_table_secions_json)
        new_instrument_scientists_run_table_defintions = {}
        def reverse_mapping_for_section(section):
            return { x["name"]: {"section" : section["SECTION"], "title": section["TITLE"], "pv": x["name"]} for x in section["PARAMS"] }
        with open(run_table_secions_json, 'r') as f:
            isdefs = json.load(f)
            for instrument, sections in isdefs.items():
                new_instrument_scientists_run_table_defintions[instrument] = {}
                for section in sections:
                    new_instrument_scientists_run_table_defintions[instrument].update(reverse_mapping_for_section(section))
        global instrument_scientists_run_table_defintions
        instrument_scientists_run_table_defintions.clear()
        instrument_scientists_run_table_defintions.update(new_instrument_scientists_run_table_defintions)

load_sections_json()

# Cache some of the instrument definitions.
instrument_definitions = {}
def load_instrument_definitions():
    global instrument_definitions
    instrument_definitions.clear()
    instrument_definitions.update({ x["_id"]: x for x in logbookclient["site"]["instruments"].find() })

load_instrument_definitions()

def reload_named_caches(cache_name):
    if cache_name == "instrument_scientists_run_table_defintions":
        logger.info("Reloading the instrument_scientists_run_table_defintions named cache")
        load_sections_json()
    elif cache_name == "instrument_defintions":
        logger.info("Reloading the instrument_defintions named cache")
        load_instrument_definitions()


def generateArpToken(userid, experiment_name, token_duration_in_mins=10):
    if "WFLOW_TRIG_ARP_PRIVATE_KEY" not in os.environ:
        raise Exception("Please specify the ARP private key in the environment variable WFLOW_TRIG_ARP_PRIVATE_KEY")
    with open(os.environ["WFLOW_TRIG_ARP_PRIVATE_KEY"], "rb") as f:
        private_key = f.read()
    return jwt.encode({"user": userid, "experiment_name": experiment_name, "expires": (datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(minutes=token_duration_in_mins)).timestamp()}, private_key, algorithm="RS256")

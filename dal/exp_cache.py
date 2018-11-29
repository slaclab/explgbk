import os
import json
import datetime
import logging
import re

import requests
import threading
import sched

from pymongo import ASCENDING, DESCENDING
from bson import ObjectId

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from context import logbookclient, imagestoreurl, instrument_scientists_run_table_defintions

__author__ = 'mshankar@slac.stanford.edu'

logger = logging.getLogger(__name__)

all_experiment_names = set()

def init_app(app):
    if 'experiments' not in list(logbookclient['explgbk_cache'].collection_names()):
        logbookclient['explgbk_cache']['experiments'].create_index( [("name", "text" ), ("description", "text" ), ("instrument", "text" ), ("contact_info", "text" )] );
    scheduler = sched.scheduler()
    __establish_kafka_consumers()

    def __periodic(scheduler, interval, action, actionargs=()):
        # This is the function that runs periodically
        scheduler.enter(interval, 1, __periodic, (scheduler, interval, action, actionargs))
        action(*actionargs)

    def __kickoff_cache_update_thread():
        # This runs in a background thread; the scheduler.run is blocking and will block forever.
        __periodic(scheduler, 24*60*60, __update_experiments_info)
        scheduler.run()

    __cache_update_thread = threading.Thread(target=__kickoff_cache_update_thread)
    __cache_update_thread.start()


def reload_cache():
    """
    Reload the experiment cache from the database.
    Use only if you make changes directly in the database bypassing the app.
    If you are using to recover from invalid cache issues; please do generate a bug report.
    """
    __update_experiments_info()

def get_experiments():
    """
    Get a list of experiments from the database.
    Returns basic information and also some info on the first and last runs.
    """
    return list(logbookclient['explgbk_cache']['experiments'].find({}))

def does_experiment_exist(experiment_name):
    """
    Checks for the existence of the experiment_name.
    This is meant mostly for validation of the experiment_name; we assume that this is going to be called many times.
    So, we are avoiding a hit to the database by caching just the names themselves in memory.
    """
    global all_experiment_names
    if experiment_name in all_experiment_names: # Check the cache first.
        return True
    expdb = logbookclient[experiment_name]
    collnames = list(expdb.collection_names())
    if 'info' in collnames:
        return True

    return False

def text_search_for_experiments(search_terms):
    """
    Search the experiment cache for experiments matching the search terms.
    Use search terms separated by spaces. The backslash escapes the space for literal searches.
    Use the minus character to suppress a word.
    """
    matching_entries = list(logbookclient['explgbk_cache']['experiments'].find({ "$text": { "$search": search_terms }}))
    return sorted(matching_entries, key=lambda x : x["name"])


def __update_experiments_info():
    """
    Since we are using an database per experiment, getting basic information that spans experiments can take some time.
    We cache this information in a 'explgbk_cache' database.
    We update this using Kafka; but we also periodically do a full reload of this information
    """
    logger.info("Updating the experiment info cached in 'explgbk_cache'.")
    database_names = list(logbookclient.database_names())
    for experiment_name in database_names:
        __update_single_experiment_info(experiment_name)

def __update_single_experiment_info(experiment_name, crud="Update"):
    """
    Load a single experiment's info and return the info as a dict
    """
    global all_experiment_names
    if crud == "Delete":
        all_experiment_names.remove(experiment_name)
        logbookclient['explgbk_cache']['experiments'].delete_one({"_id": experiment_name})
        return
    logger.debug("Gathering the experiment info cached in 'explgbk_cache' for experiment %s", experiment_name)
    expdb = logbookclient[experiment_name]
    collnames = list(expdb.collection_names())
    if 'info' in collnames:
        all_experiment_names.add(experiment_name)
        expinfo = { "_id": experiment_name }
        info = expdb["info"].find_one({}, {"latest_setup": 0})
        roles = [x for x in expdb["roles"].find()]
        all_players = set()
        list(map(lambda x : all_players.update(x.get('players', [])), roles))
        expinfo["players"] = list(all_players)
        if 'runs' in collnames:
            run_count = expdb["runs"].count()
            expinfo['run_count'] = run_count
            if run_count:
                last_run =  expdb["runs"].find({}, { "num": 1, "begin_time": 1, "end_time": 1 } ).sort([("begin_time", -1)]).limit(1)[0]
                first_run = expdb["runs"].find({}, { "num": 1, "begin_time": 1, "end_time": 1 } ).sort([("begin_time",  1)]).limit(1)[0]
                expinfo["first_run"] = { "num": first_run["num"],
                        "begin_time": first_run["begin_time"],
                        "end_time": first_run["end_time"]
                    }
                expinfo["last_run"] =  { "num": last_run["num"],
                        "begin_time": last_run["begin_time"],
                        "end_time": last_run["end_time"]
                    }
        else:
            logger.debug("No runs in experiment " + experiment_name)
        if 'file_catalog' in collnames:
            dataSummary = [x for x in expdb['file_catalog'].aggregate([ { "$group" :
                { "_id" : None,
                    "totalDataSize": { "$sum": { "$divide": ["$size", 1024*1024*1024*1.0 ] } },
                    "totalFiles": { "$sum": 1 }
                }
            } ])]
            if dataSummary:
                expinfo['totalDataSize'] = dataSummary[0]['totalDataSize']
                expinfo['totalFiles'] = dataSummary[0]['totalFiles']

        expinfo.update(info)
        logbookclient['explgbk_cache']['experiments'].update({"_id": experiment_name}, expinfo, upsert=True)
        logger.info("Updated the experiment info cached in 'explgbk_cache' for experiment %s", experiment_name)
    else:
        logger.debug("Skipping non-experiment database " + experiment_name)


def __establish_kafka_consumers():
    """
    Establish Kafka consumers that listen to new experiments and runs and updates the cache.
    """
    def subscribe_kafka():
        consumer = KafkaConsumer(bootstrap_servers=[os.environ.get("KAFKA_BOOTSTRAP_SERVER", "localhost:9092")])
        consumer.subscribe(["runs", "experiments", "roles"])

        for msg in consumer:
            logger.info("Message from Kafka %s", msg)
            info = json.loads(msg.value)
            logger.info("JSON from Kafka %s", info)
            message_type = msg.topic
            experiment_name = info['experiment_name']
            crud = info.get("CRUD", "Update")
            # No matter what the message type is, we reload the experiment info.
            __update_single_experiment_info(experiment_name, crud=crud)

    # Create thread for kafka consumer
    kafka_client_thread = threading.Thread(target=subscribe_kafka)
    kafka_client_thread.start()

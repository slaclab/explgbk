import os
import json
import datetime
import logging
import re

import requests
import threading

from pymongo import ASCENDING, DESCENDING
from bson import ObjectId

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from context import logbookclient, imagestoreurl, instrument_scientists_run_table_defintions

__author__ = 'mshankar@slac.stanford.edu'

logger = logging.getLogger(__name__)

__cached_experiments = {}

def init_app(app):
    global __cached_experiments
    __load_experiments()
    logger.info("Loaded %s experiments from the database ", len(__cached_experiments))
    __establish_kafka_consumers()

def get_experiments():
    """
    Get a list of experiments from the database.
    Returns basic information and also some info on the first and last runs.
    """
    global __cached_experiments
    return list(__cached_experiments.values())

def __load_single_experiment(experiment_name):
    """
    Load a single experiment's info and return the info as a dict
    """
    logger.debug("Loading experiment cache for experiment %s", experiment_name)
    expdb = logbookclient[experiment_name]
    collnames = expdb.collection_names()
    expinfo = {}
    info = expdb["info"].find_one({}, {"latest_setup": 0})
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
        logger.debug("No runs in experiment " + database)
    expinfo.update(info)
    return expinfo

def __load_experiments():
    """
    Load the experiments from the database into the cache.
    """
    global __cached_experiments

    logger.info("Reloading experiments from database.")
    experiments = []
    for experiment_name in logbookclient.database_names():
        expdb = logbookclient[experiment_name]
        collnames = expdb.collection_names()
        if 'info' in collnames:
            expinfo = __load_single_experiment(experiment_name)
            __cached_experiments[experiment_name] = expinfo
        else:
            logger.debug("Skipping non-experiment database " + experiment_name)

    return experiments


def __establish_kafka_consumers():
    """
    Establish Kafka consumers that listen to new experiments and runs and updates the cache.
    """
    def subscribe_kafka():
        consumer = KafkaConsumer(bootstrap_servers=[os.environ.get("KAFKA_BOOTSTRAP_SERVER", "localhost:9092")])
        consumer.subscribe(["runs", "experiments"])

        for msg in consumer:
            logger.info("Message from Kafka %s", msg)
            info = json.loads(msg.value)
            logger.info("JSON from Kafka %s", info)
            message_type = msg.topic
            experiment_name = info['experiment_name']
            # No matter what the message type is, we reload the experiment info.
            global __cached_experiments
            expinfo = __load_single_experiment(experiment_name)
            __cached_experiments[experiment_name] = expinfo


    # Create thread for kafka consumer
    kafka_client_thread = threading.Thread(target=subscribe_kafka)
    kafka_client_thread.start()

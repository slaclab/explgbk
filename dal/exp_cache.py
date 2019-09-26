import os
import json
import time
import datetime
import pytz
import dateutil.relativedelta
import logging
import re

import requests
import threading
import sched

from pymongo import ASCENDING, DESCENDING
from bson import ObjectId

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from context import logbookclient, imagestoreurl, instrument_scientists_run_table_defintions, usergroups, kafka_producer

__author__ = 'mshankar@slac.stanford.edu'

logger = logging.getLogger(__name__)

all_experiment_names = set()
roles_with_post_privileges = []

def init_app(app):
    if 'experiments' not in list(logbookclient['explgbk_cache'].collection_names()):
        logbookclient['explgbk_cache']['experiments'].create_index( [("name", "text" ), ("description", "text" ), ("instrument", "text" ), ("contact_info", "text" )] )
    if 'operations' not in list(logbookclient['explgbk_cache'].collection_names()):
        logbookclient['explgbk_cache']['operations'].create_index( [("name", DESCENDING)], unique=True)
        logbookclient['explgbk_cache']['operations'].insert_one({"name": "explgbk_cache_rebuild", "initiated": datetime.datetime.utcfromtimestamp(0.0), "completed": datetime.datetime.utcfromtimestamp(0.0)})
    global roles_with_post_privileges
    roles_with_post_privileges = [x["name"] for x in logbookclient["site"]["roles"].find({"app": "LogBook", "privileges": { "$in": ["post"] }}, {"name": 1, "_id": 0})]
    __load_experiment_names()

    scheduler = sched.scheduler()
    __establish_kafka_consumers()

    def __periodic(scheduler, interval, action, actionargs=()):
        # This is the function that runs periodically
        scheduler.enter(interval, 1, __periodic, (scheduler, interval, action, actionargs))
        last_rebuild = logbookclient['explgbk_cache']['operations'].find_one({"name": "explgbk_cache_rebuild"})
        db_time_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
        if (db_time_utc - last_rebuild["initiated"]).total_seconds() > interval:
            action(*actionargs)
        else:
            logger.info("Skipping the periodic cache rebuild as we rebuilt the cache at %s within the specified interval %s", last_rebuild["initiated"], interval)

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

def get_cached_experiment_names():
    """
    Get the cached experiment names. Use for debugging.
    """
    global all_experiment_names
    return list(all_experiment_names)

def get_experiments_with_post_privileges(userid):
    """
    Get the list of experiments that the logged in user has post privileges for.
    If the logged in user (or one of her groups) is in the site database, we return all experiments.
    Else we query the experiment cache and return those.
    """
    groups = usergroups.get_user_posix_groups(userid)
    u_a_g = ["uid:" + userid] + groups
    logger.debug("Looking for experiments with post privileges for %s", u_a_g)
    site_roles = [ x for x in logbookclient["site"]["roles"].find({"app": "LogBook", "privileges": { "$in": ["post"]}, "players": { "$in": u_a_g }})]
    if site_roles:
        logger.debug("User %s has post privileges for all experiments")
        return get_experiments()
    return list(logbookclient['explgbk_cache']["experiments"].find({"post_players": {"$in": u_a_g}}))

def get_experiment_stats():
    """
    Get various computed/cached stats for the experiments
    """
    return list(logbookclient['explgbk_cache']['experiment_stats'].find({}))

def get_experiment_daily_data_breakdown():
    """
    Run an aggregate on the daily data breakdown.
    Data returned is in TB.
    """
    return list(logbookclient['explgbk_cache']['experiment_stats'].aggregate([
      { "$unwind": "$dataDailyBreakdown" },
      { "$replaceRoot": {"newRoot": "$dataDailyBreakdown" }},
      { "$group": { "_id": "$_id", "total_size": {"$sum": {"$divide": ["$total_size", 1024]}}}},
      { "$sort": { "_id": -1 }}
    ]))

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


def __load_experiment_names():
    """ We cache the list of experimemt names to speedup authz/other operations.
    This reloads the cached list of experiment names from the explgbk_cache
    """
    global all_experiment_names
    all_experiment_names.update([x["name"] for x in logbookclient['explgbk_cache']['experiments'].find({}, {"name": 1, "_id":0})])

def __update_experiments_info():
    """
    Since we are using an database per experiment, getting basic information that spans experiments can take some time.
    We cache this information in a 'explgbk_cache' database.
    We update this using Kafka; but we also periodically do a full reload of this information
    """
    logger.info("Updating the experiment info cached in 'explgbk_cache'.")
    database_names = list(logbookclient.database_names())
    db_time_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    logbookclient['explgbk_cache']['operations'].update_one({"name": "explgbk_cache_rebuild"}, {"$set": {"initiated": db_time_utc}})
    for experiment_name in database_names:
        __update_single_experiment_info(experiment_name)
        db_time_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
        logbookclient['explgbk_cache']['operations'].update_one({"name": "explgbk_cache_rebuild"}, {"$set": {"completed": db_time_utc}})
    kafka_producer.send("explgbk_cache", { "cache_rebuild": True } )


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
        info = expdb["info"].find_one({}, {"latest_setup": 0})
        if 'name' not in info or 'instrument' not in info:
            logger.debug("Database %s has a info collection but the info object does not have an instrument or name", experiment_name)
            return
        all_experiment_names.add(experiment_name)
        expinfo = { "_id": experiment_name }
        roles = [x for x in expdb["roles"].find()]
        all_players = set()
        list(map(lambda x : all_players.update(x.get('players', [])), roles))
        expinfo["players"] = list(all_players)
        post_players = set()
        list(map(lambda x : post_players.update(x.get('players', [])), expdb["roles"].find({"name": {"$in": roles_with_post_privileges}}, {"_id": 0, "players": 1})))
        expinfo["post_players"] = list(post_players)
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
        try:
            if 'file_catalog' in collnames:
                def asTime(val):
                    if not val:
                        return None
                    elif isinstance(val[0]["create_timestamp"], datetime.datetime):
                        return val[0]["create_timestamp"]
                    elif isinstance(val[0]["create_timestamp"], str):
                        return datetime.datetime.strptime(val[0]["create_timestamp"], '%Y-%m-%dT%H:%M:%SZ')
                    else:
                        return None
                f_file = asTime(list(expdb['file_catalog'].find({}).sort([("create_timestamp", -1)]).limit(1)))
                l_file = asTime(list(expdb['file_catalog'].find({}).sort([("create_timestamp", 1)]).limit(1)))
                if f_file and l_file:
                    attrs = ['years', 'months', 'days', 'hours', 'minutes']
                    human_readable_diff = lambda delta: ['%d %s' % (getattr(delta, attr), getattr(delta, attr) > 1 and attr or attr[:-1]) for attr in attrs if getattr(delta, attr)]
                    expinfo['file_timestamps']  = {
                        "first_file_ts": f_file,
                        "last_file_ts": l_file,
                        "duration": (l_file - f_file).total_seconds(),
                        "hr_duration": human_readable_diff(dateutil.relativedelta.relativedelta (f_file, l_file))
                    }

                dataSummary = [x for x in expdb['file_catalog'].aggregate([ { "$group" :
                    { "_id" : None,
                        "totalDataSize": { "$sum": { "$divide": ["$size", 1024*1024*1024*1.0 ] } },
                        "totalFiles": { "$sum": 1 }
                    }
                } ])]
                if dataSummary:
                    expinfo['totalDataSize'] = dataSummary[0]['totalDataSize']
                    expinfo['totalFiles'] = dataSummary[0]['totalFiles']
                dataDailyBreakdown = [x for x in expdb['file_catalog'].aggregate([
                        {"$group": { "_id": {"$dateToParts": { "date": {"$convert": { "input": "$create_timestamp", "to": "date" }}}}, "total_size": {"$sum": "$size"}}},
                        {"$project": { "_id.year": 1, "_id.month": 1, "_id.day": 1, "total_size": 1 }},
                        {"$group": { "_id": {"$dateFromParts": { "year": "$_id.year", "month": "$_id.month", "day": "$_id.day" } }, "total_size": {"$sum": {"$divide": [ "$total_size", 1024*1024*1024]}}}}
                    ])]
                if dataDailyBreakdown:
                    logbookclient['explgbk_cache']['experiment_stats'].update({"_id": experiment_name}, { "_id": experiment_name, "dataDailyBreakdown": dataDailyBreakdown }, upsert=True)
        except Exception as e:
            logger.exception("Exception computing the file parameters")

        expinfo.update(info)
        expinfo["_id"] = experiment_name
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
        consumer.subscribe(["runs", "experiments", "roles", "explgbk_cache"])

        for msg in consumer:
            try:
                logger.info("Message from Kafka %s", msg)
                info = json.loads(msg.value)
                logger.info("JSON from Kafka %s", info)
                message_type = msg.topic
                if message_type == "explgbk_cache":
                    __load_experiment_names()
                elif 'experiment_name' in info:
                    experiment_name = info['experiment_name']
                    crud = info.get("CRUD", "Update")
                    # No matter what the message type is, we reload the experiment info.
                    __update_single_experiment_info(experiment_name, crud=crud)
                else:
                    logger.error("Kafka message without an experiment name")
            except Exception as e:
                logger.exception("Exception processing Kafka message.")

    # Create thread for kafka consumer
    kafka_client_thread = threading.Thread(target=subscribe_kafka)
    kafka_client_thread.start()

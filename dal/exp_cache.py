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

from pymongo import ASCENDING, DESCENDING, ReadPreference
from bson import ObjectId

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from context import logbookclient, instrument_scientists_run_table_defintions, usergroups, kafka_producer, local_kafka_events, reload_named_caches
from dal.explgbk import get_experiments_for_instrument, get_poc_feedback_changes, get_poc_feedback_document

__author__ = 'mshankar@slac.stanford.edu'

logger = logging.getLogger(__name__)

all_experiment_names = set()
roles_with_post_privileges = []

class PeriodicUpdates():
    """
    Gather experiment names to be updated periodically in the future.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.experiment_names = set()
    def add(self, experiment_name):
        with self.lock:
            try:
                self.experiment_names.add(experiment_name)
            except Exception as e:
                logger.exception("Exception adding %s to periodic updater", experiment_name)
    def getAndReset(self):
        with self.lock:
            ret = self.experiment_names
            self.experiment_names = set()
            return ret

periodic_updates = PeriodicUpdates()

def init_app(app):
    if 'experiments' not in list(logbookclient['explgbk_cache'].list_collection_names()):
        logbookclient['explgbk_cache']['experiments'].create_index( [("name", "text" ), ("description", "text" ), ("instrument", "text" ), ("contact_info", "text" ), ("params.PNR", "text" )] )
    if 'operations' not in list(logbookclient['explgbk_cache'].list_collection_names()):
        logbookclient['explgbk_cache']['operations'].create_index( [("name", DESCENDING)], unique=True)
        logbookclient['explgbk_cache']['operations'].insert_one({"name": "explgbk_cache_rebuild", "initiated": datetime.datetime.utcfromtimestamp(0.0), "completed": datetime.datetime.utcfromtimestamp(0.0)})
    global roles_with_post_privileges
    roles_with_post_privileges = [x["name"] for x in logbookclient["site"]["roles"].find({"app": "LogBook", "privileges": { "$in": ["post"] }}, {"name": 1, "_id": 0})]
    __load_experiment_names()

    scheduler = sched.scheduler()
    __establish_kafka_consumers()
    __establish_local_kafka_consumers__()

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


    def _non_immediate_update():
        try:
            global periodic_updates
            exps = periodic_updates.getAndReset()
            logger.info("Processing the non immediate cache for %s experiments", len(exps))
            for exp in exps:
                try:
                    update_single_experiment_info(exp)
                except:
                    logger.exception("Exception in periodic updater updating %s", exp)
        except:
            logger.exception("Exception in periodic updater")
    def __non_immediate_periodic(scheduler, interval, action, actionargs=()):
        scheduler.enter(interval, 1, __non_immediate_periodic, (scheduler, interval, action, actionargs))
        action(*actionargs)

    nonimmediatesched = sched.scheduler()

    def __kickoff_non_immediate_thread():
        __non_immediate_periodic(nonimmediatesched, 5*60, _non_immediate_update)
        nonimmediatesched.run()

    __non_immediate_updater_thread = threading.Thread(target=__kickoff_non_immediate_thread)
    __non_immediate_updater_thread.start()




def reload_cache(experiment_name=None):
    """
    Reload the experiment cache from the database.
    Use only if you make changes directly in the database bypassing the app.
    If you are using to recover from invalid cache issues; please do generate a bug report.
    """
    if experiment_name:
        logger.debug("Refreshing the cache for experiment %s", experiment_name)
        if experiment_name in ["admin", "config", "local", "site"]:
            return
        update_single_experiment_info(experiment_name)
        return

    __update_experiments_info()

def get_experiments():
    """
    Get a list of experiments from the database.
    Returns basic information and also some info on the first and last runs.
    """
    return list(logbookclient['explgbk_cache']['experiments'].find({}))

def get_cached_experiment_info(experiment_id):
    """
    Returns basic information and also some info on the first and last runs.
    """
    return logbookclient['explgbk_cache']['experiments'].find_one({"_id": experiment_id})

def get_experiments_starting_in_time_frame(start_time, end_time):
    """
    Get a list of experiments whose start_time is in the given time range.
    """
    return list(logbookclient['explgbk_cache']['experiments'].find({"$and": [
        {"start_time": {"$gte": start_time}},
        {"start_time": {"$lte": end_time}}
        ]}, {"name": 1, "start_time": 1}))

def get_sorted_experiments_ids(sort_criteria):
    """
    Get only the experiment ids sorted according to the sort criteria.
    Sort criteria is a JSON array of [[sort_attr, sort_direction]]
    """
    return [ x["_id"] for x in logbookclient['explgbk_cache']['experiments'].find({}, { "_id": 1, "name": 1 }).sort(sort_criteria)]

def get_experiments_for_user(uid):
    """
    Get a list of experiments for which the user has read access.
    """
    sitedb = logbookclient["site"]
    cachedb = logbookclient['explgbk_cache']
    groups = usergroups.get_user_posix_groups(uid)
    groups.append("uid:" + uid)
    # See if the user has any global read privileges
    global_read_roles_for_user = [ x for x in sitedb["roles"].find({"players": {"$in": groups}, "privileges": "read"}) ]
    if global_read_roles_for_user:
        logger.debug("User %s has read privileges for all experiments from the site database", uid)
        return get_experiments()
    global_read_roles = set([(x["app"], x["name"]) for x in sitedb["roles"].find({"privileges": "read"}, {"_id": 0, "app": 1, "name": 1})])
    # Check for instrument level privileges
    instrument_roles_for_user = [x for x in sitedb["instruments"].aggregate([{"$match": {"roles.players": {"$in": groups}}}, {"$unwind": "$roles"}])]
    exp_for_uid = {}
    for irole in instrument_roles_for_user:
        if (irole["roles"]["app"], irole["roles"]["name"]) in global_read_roles:
            logger.debug("User %s has read permission for instrument %s because of role %s/%s", uid, irole["_id"], irole["roles"]["app"], irole["roles"]["name"] )
            for exp in get_experiments_for_instrument(irole["_id"]):
                exp_for_uid[exp["_id"]] = exp
    # Now for experiments for which the user is directly a collaborator
    for exp in list(logbookclient['explgbk_cache']["experiments"].find({"players": {"$in": groups}})):
        exp_for_uid[exp["_id"]] = exp
    return exp_for_uid.values()

def get_direct_experiments_for_user(uid):
    """
    Get a list of experiments for which the user is a direct collaborator.
    This information typically comes in from the URAWI BTR.
    """
    return list(logbookclient['explgbk_cache']["experiments"].find({"players": {"$in": ["uid:" + uid]}}, {"name": 1, "instrument": 1}))

def get_cached_experiment_names():
    """
    Get the cached experiment names. Use for debugging.
    """
    global all_experiment_names
    return list(all_experiment_names)

def get_experiments_with_post_privileges(userid, active_exps):
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
        postable_exps = get_experiments()
    else:
        postable_exps = list(logbookclient['explgbk_cache']["experiments"].find({"post_players": {"$in": u_a_g}}))
    # Sort
    ret_exps = [ { attr : x.get(attr, None) for attr in ["_id", "name", "instrument", "description", "start_time", "end_time", "posix_group", "params"] } for x in postable_exps ]
    active_exp_names = [ x["name"] for x in active_exps if "name" in x ]
    for exp in ret_exps:
        if exp["name"] in active_exp_names:
            exp["is_active"] = True
    return ret_exps

def get_experiment_stats():
    """
    Get various computed/cached stats for the experiments
    """
    return list(logbookclient['explgbk_cache']['experiment_stats'].find({}))

def get_experiment_daily_data_breakdown(report_type, instrument):
    """
    Run an aggregate on the daily data breakdown.
    Data returned is in TB.
    """
    if report_type == "file_sizes":
        if not instrument or instrument == "ALL":
            return list(logbookclient['explgbk_cache']['experiment_stats'].aggregate([
              { "$unwind": "$dataDailyBreakdown" },
              { "$replaceRoot": {"newRoot": "$dataDailyBreakdown" }},
              { "$group": { "_id": "$_id", "total_size": {"$sum": {"$divide": ["$total_size", 1024]}}}},
              { "$sort": { "_id": -1 }}
            ]))
        else:
            return list(logbookclient['explgbk_cache']['experiment_stats'].aggregate([
              { "$lookup": { "from": "experiments", "localField": "_id", "foreignField": "_id", "as": "exp"}},
              { "$unwind": "$exp" },
              { "$match": { "exp.instrument": instrument }},
              { "$unwind": "$dataDailyBreakdown" },
              { "$replaceRoot": {"newRoot": "$dataDailyBreakdown" }},
              { "$group": { "_id": "$_id", "total_size": {"$sum": {"$divide": ["$total_size", 1024]}}}},
              { "$sort": { "_id": -1 }}
            ]))
    elif report_type == "run_counts":
        if not instrument or instrument == "ALL":
            return list(logbookclient['explgbk_cache']['experiment_stats'].aggregate([
              { "$unwind": "$runDailyBreakdown" },
              { "$replaceRoot": {"newRoot": "$runDailyBreakdown" }},
              { "$group": { "_id": "$_id", "total_runs": {"$sum": "$run_count"}}},
              { "$sort": { "_id": -1 }}
            ]))
        else:
            return list(logbookclient['explgbk_cache']['experiment_stats'].aggregate([
              { "$lookup": { "from": "experiments", "localField": "_id", "foreignField": "_id", "as": "exp"}},
              { "$unwind": "$exp" },
              { "$match": { "exp.instrument": instrument }},
              { "$unwind": "$runDailyBreakdown" },
              { "$replaceRoot": {"newRoot": "$runDailyBreakdown" }},
              { "$group": { "_id": "$_id", "total_runs": {"$sum": "$run_count"}}},
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
    collnames = list(expdb.list_collection_names())
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

def search_experiments_for_common_fields(search_term, sort_criteria):
    """
    Search the experiment cache for experiments regex matching the search term in a subset of fields.
    The fields searched are _id, name, contact_info, description
    """
    patt = re.compile(search_term)
    matching_entries = list(logbookclient['explgbk_cache']['experiments'].find(
        { "$or": [
            { "_id": { "$regex": patt } },
            { "name": { "$regex": patt } },
            { "contact_info": { "$regex": patt } },
            { "description": { "$regex": patt } }
        ]}, {"_id": 1, "name": 1}).sort(sort_criteria))
    return matching_entries

def get_all_param_names_matching_regex(rgx):
    """
    Get all param names in all experiments matching the incoming regex.
    """
    patt = re.compile(rgx)
    apns = logbookclient['explgbk_cache']["experiments"].distinct("all_param_names")
    return [ x for x in apns if patt.match(x) ]

def get_experiments_proposal_mappings():
    """
    Get all the experiments with their PNR's if present.
    """
    return list(logbookclient['explgbk_cache']["experiments"].find({}, {"name": 1, "params.PNR": 1, "instrument": 1}))

def __load_experiment_names():
    """ We cache the list of experimemt names to speedup authz/other operations.
    This reloads the cached list of experiment names from the explgbk_cache
    """
    global all_experiment_names
    all_experiment_names = set([x["name"] for x in logbookclient['explgbk_cache']['experiments'].find({}, {"name": 1, "_id":0})])

def __update_experiments_info():
    """
    Since we are using an database per experiment, getting basic information that spans experiments can take some time.
    We cache this information in a 'explgbk_cache' database.
    We update this using Kafka; but we also periodically do a full reload of this information
    """
    logger.info("Updating the experiment info cached in 'explgbk_cache'.")
    database_names = sorted(list(logbookclient.database_names()), reverse=True)
    db_time_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    logbookclient['explgbk_cache']['operations'].update_one({"name": "explgbk_cache_rebuild"}, {"$set": {"initiated": db_time_utc}})
    for experiment_name in database_names:
        if experiment_name in ["admin", "config", "local", "site"]:
            continue
        update_single_experiment_info(experiment_name)
        db_time_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
        logbookclient['explgbk_cache']['operations'].update_one({"name": "explgbk_cache_rebuild"}, {"$set": {"completed": db_time_utc}})
    kafka_producer.send("explgbk_cache", { "cache_rebuild": True } )


def update_single_experiment_info(experiment_name, crud="Update"):
    """
    Load a single experiment's info and return the info as a dict
    """
    global all_experiment_names
    if crud == "Delete":
        all_experiment_names.remove(experiment_name)
        logbookclient['explgbk_cache']['experiments'].delete_one({"_id": experiment_name})
        logbookclient['explgbk_cache']['experiment_stats'].delete_one({"_id": experiment_name})
        return
    logger.debug("Gathering the experiment info cached in 'explgbk_cache' for experiment %s", experiment_name)
    expdb = logbookclient[experiment_name]
    collnames = list(expdb.list_collection_names())
    if 'info' in collnames:
        info = expdb["info"].find_one({}, {"latest_setup": 0})
        if 'name' not in info or 'instrument' not in info:
            logger.error("Database %s has a info collection but the info object does not have an instrument or name. Note this could also be a timing issue if you are using secondaries", experiment_name)
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
                runDailyBreakdown = list(expdb["runs"].aggregate([
                    {"$group": { "_id": {"$dateToParts": { "date": {"$convert": { "input": "$begin_time", "to": "date" }}}}, "run_count": {"$sum": 1}}},
                    {"$project": { "_id.year": 1, "_id.month": 1, "_id.day": 1, "run_count": 1 }},
                    {"$group": { "_id": {"$dateFromParts": { "year": "$_id.year", "month": "$_id.month", "day": "$_id.day" } }, "run_count": {"$sum": "$run_count"}}},
                    {"$sort": {"_id": 1}}
                ]))
                if runDailyBreakdown:
                    logbookclient['explgbk_cache']['experiment_stats'].update_one({"_id": experiment_name}, { "$set": { "runDailyBreakdown": runDailyBreakdown } }, upsert=True)

                expinfo["all_param_names"] = [x["_id"] for x in expdb["runs"].aggregate([
                    { "$project": { "params": { "$objectToArray": "$params" }}},
                    { "$unwind": "$params" },
                    { "$group": { "_id": "$params.k", "total": { "$sum": 1 }}},
                    { "$sort": { "_id": 1 }}
                ])]
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
                    ], allowDiskUse=True)]
                if dataDailyBreakdown:
                    logbookclient['explgbk_cache']['experiment_stats'].update_one({"_id": experiment_name}, { "$set": { "dataDailyBreakdown": dataDailyBreakdown } }, upsert=True)
        except Exception as e:
            logger.exception("Exception computing the file parameters")

        poc_feedback_changes = get_poc_feedback_changes(experiment_name)
        if poc_feedback_changes:
            poc_feedback_doc = get_poc_feedback_document(experiment_name)
            expinfo["poc_feedback"] = {
                "num_items": len(poc_feedback_changes),
                "num_items_4_5": len(list(filter(lambda kv: kv[0] not in ["basic-scheduled", "basic-actual"] and (kv[1] in [ "4", "5" ]), poc_feedback_doc.items()))),
                "last_modified_by": poc_feedback_changes[-1]["modified_by"],
                "last_modified_at": poc_feedback_changes[-1]["modified_at"]
                }

        expinfo.update(info)
        expinfo["_id"] = experiment_name
        logbookclient['explgbk_cache']['experiments'].update({"_id": experiment_name}, expinfo, upsert=True)

        logger.info("Updated the experiment info cached in 'explgbk_cache' for experiment %s", experiment_name)
    else:
        logger.error("Database %s does not have a info collection. Note this could also be a timing issue if you are using secondaries", experiment_name)


def __establish_local_kafka_consumers__():
    """
    This processes from the local queue
    """
    def processMessage(msg):
        try:
            logger.debug("Kafka/local Message %s", msg)
            info = json.loads(msg["value"])
            logger.debug("Kafka/local JSON %s", info)
            message_type = msg["topic"]
            if message_type == "explgbk_cache":
                if info.get("named_cache", None):
                    logger.info("Reloading named cache %s", info["named_cache"])
                    reload_named_caches(info["named_cache"])
                __load_experiment_names()
            elif message_type in ["experiments", "roles", "samples"]:
                if 'experiment_name' in info:
                    experiment_name = info['experiment_name']
                    logger.info("Got a Kafka/local message %s for experiment %s - building the cache entry", message_type, experiment_name)
                    crud = info.get("CRUD", "Update") if message_type == "experiments" else "Update"
                    update_single_experiment_info(experiment_name, crud=crud)
                else:
                    logger.error("Kafka/local message in immediate topics without an experiment name %s", message_type)
            else:
                logger.debug("Not re-building immediately for a non immediate topic %s", message_type)
                global periodic_updates
                if 'experiment_name' in info:
                    experiment_name = info['experiment_name']
                    periodic_updates.add(experiment_name)
                else:
                    logger.error("Kafka/local message in non-immediate topics without an experiment name %s", message_type)
        except Exception as e:
            logger.exception("Exception processing Kafka/local message.")
    def worker():
        while True:
            msg = local_kafka_events.get()
            processMessage(msg)
            local_kafka_events.task_done()
    local_msg_thread = threading.Thread(target=worker)
    local_msg_thread.start()

def __establish_kafka_consumers():
    """
    Establish Kafka consumers that listen to new experiments and runs and updates the cache.
    """
    def subscribe_kafka():
        consumer = KafkaConsumer(bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVER", "localhost:9092").split(","))
        consumer.subscribe(["experiments", "explgbk_cache"])

        for msg in consumer:
            try:
                logger.info("Message from Kafka in topic %s", msg.topic)
                message_type = msg.topic
                if message_type == "explgbk_cache":
                    info = json.loads(msg.value)
                    logger.debug("JSON from Kafka %s", info)
                    if info.get("named_cache", None):
                        logger.info("Reloading named cache %s", info["named_cache"])
                        reload_named_caches(info["named_cache"])

                __load_experiment_names()
            except Exception as e:
                logger.exception("Exception processing Kafka message.")

    # Create thread for kafka consumer
    kafka_client_thread = threading.Thread(target=subscribe_kafka)
    kafka_client_thread.start()

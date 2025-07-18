'''
The model level business logic goes here.
Most of the code here gets a connection to the database, executes a query and formats the results.
'''
import os
import json
import datetime
import logging
import re
import copy
from operator import itemgetter
import shutil
import math

import requests
import tempfile
import subprocess

from pymongo import ASCENDING, DESCENDING, ReadPreference
from bson import ObjectId

# This (g) should be the only import from Flask; we use this as a thread local context variable.
from flask import g

from context import logbookclient, instrument_scientists_run_table_defintions, security, usergroups, imagestoreurl, \
    MAX_ATTACHMENT_SIZE, URAWI_URL, LOGBOOK_SITE
from dal.run_control import get_current_run, start_run, end_run, is_run_closed
from dal.imagestores import parseImageStoreURL
from dal.utils import escape_chars_for_mongo, reverse_escape_chars_for_mongo

PROJECTS_DB="lgbkprjs"

__author__ = 'mshankar@slac.stanford.edu'

logger = logging.getLogger(__name__)

class LgbkException(Exception):
    """
    Exception whose message gets passed to the end user as an error message
    """
    pass

def get_instruments():
    """
    Get the list of instruments from the site database.
    """
    sitedb = logbookclient["site"]
    return [x for x in sitedb["instruments"].find().sort([("_id", 1)])]

def get_experiments_for_instrument(instrument):
    """
    Get a list of experiments from the database for a instrument.
    Returns basic information and also some info on the first and last runs.
    """
    return list(logbookclient['explgbk_cache']['experiments'].find({"instrument": instrument}))


def get_experiment_info(experiment_name):
    """
    Get the basic information for the experiment.
    :param experiment_name - for example - diadaq13
    :return: The info JSON document.
    """
    expdb = logbookclient.get_database(experiment_name, read_preference=ReadPreference.SECONDARY_PREFERRED)
    info = expdb['info'].find_one()
    if not info:
        logger.error("Cannot find info for %s. Was the experiment deleted/renamed?", experiment_name)
        return {"name": experiment_name}
    setup_oid = info.get("latest_setup", None)
    if setup_oid:
        setup_doc = expdb['setup'].find_one({"_id": setup_oid})
        if setup_doc:
            info["latest_setup"] = setup_doc
    return info


def save_new_experiment_setup(experiment_name, setup_document, userid):
    """
    Save a new setup document.
    :param experiment_name - for example - diadaq13
    :param setup_document - The new setup document
    :param userid - The user making the change.
    """
    expdb = logbookclient[experiment_name]
    setup_document["modified_by"] = userid
    setup_document["modified_at"] = datetime.datetime.utcnow()
    latest_setup_id = expdb['setup'].insert_one(setup_document).inserted_id
    expdb['info'].find_one_and_update({}, {'$set': {'latest_setup': latest_setup_id}})


def register_new_experiment(experiment_name, incoming_info, create_auto_roles=True, skip_initial_objects=False):
    """
    Registers a new experiment.
    In mongo, this mostly means creating the info object, the run number counter and various indices.
    """
    if experiment_name in list(logbookclient.list_database_names()):
        return (False, "Experiment %s has already been registered" % experiment_name)

    expdb = logbookclient[experiment_name]
    info = {}
    info.update(incoming_info)
    info["_id"]                = experiment_name.replace(" ", "_")
    info["name"]               = experiment_name
    info["start_time"]         = datetime.datetime.strptime(info["start_time"], '%Y-%m-%dT%H:%M:%S.%fZ')
    info["end_time"]           = datetime.datetime.strptime(info["end_time"],   '%Y-%m-%dT%H:%M:%S.%fZ')

    expdb['info'].insert_one(info)

    # Create the run number counter
    expdb["counters"].insert_one({'_id': "next_runnum", 'seq': 0})

    # Now create the various indices
    expdb["runs"].create_index( [("num", DESCENDING)], unique=True)
    expdb["elog"].create_index( [("root", ASCENDING)])
    expdb["elog"].create_index( [("parent", ASCENDING)])
    expdb["elog"].create_index( [("content", "text" ), ("title", "text" )])
    expdb["roles"].create_index( [("app", ASCENDING), ("name", ASCENDING)], unique=True)
    expdb["run_param_descriptions"].create_index( [("param_name", DESCENDING)], unique=True)
    expdb["setup"].create_index( [("modified_by", ASCENDING), ("modified_at", ASCENDING)], unique=True)
    expdb["shifts"].create_index( [("name", ASCENDING)], unique=True)
    expdb["shifts"].create_index( [("begin_time", ASCENDING)], unique=True)
    expdb["file_catalog"].create_index( [("path", ASCENDING), ("run_num", DESCENDING)], unique=True)
    expdb["file_catalog"].create_index( [("run_num", DESCENDING)])
    expdb["run_tables"].create_index( [("name", ASCENDING)], unique=True)
    expdb["workflow_definitions"].create_index( [("name", ASCENDING)], unique=True)

    if skip_initial_objects:
        logger.debug("Skipping creating initial objects")
        # We do this for internal calls clone/rename as they copy over the collections as they are.
        return (True, "")

    # Create a default shift
    expdb["shifts"].insert_one( { "name" : "Default",
        "begin_time" : datetime.datetime.utcnow(),
        "end_time" : None,
        "leader" : security.get_current_user_id(),
        "description" : "Default shift created automatically during experiment registration",
        "params" : {}
        } )

    if create_auto_roles:
        leaderacc_roles = [ {"app" : "LogBook", "name": "Editor", "players": [ "uid:" + info["leader_account"]] } ]
        if LOGBOOK_SITE in ["LCLS"]:
            logger.debug("LCLS does not want to give PI's the Manager role; so skipping for experiment %s", experiment_name)
        else:
            leaderacc_roles.append({"app" : "LogBook", "name": "Manager", "players": [ "uid:" + info["leader_account"]] })

        expdb["roles"].insert_many(leaderacc_roles)
        if "posix_group" in info and len(info["posix_group"]) > 1:
            expdb["roles"].insert_one({"app" : "LogBook", "name": "Writer", "players": [ info["posix_group"]] })
        if security.get_current_user_id() != info["leader_account"] and not security.check_privilege_for_experiment("ops_page", None, None):
            expdb["roles"].update_one({"app" : "LogBook", "name": "Editor"}, {"$addToSet": { "players": "uid:" + security.get_current_user_id() }})
            expdb["roles"].update_one({"app" : "LogBook", "name": "Manager"}, {"$addToSet": { "players": "uid:" + security.get_current_user_id() }})


    if "initial_sample" in incoming_info and incoming_info["initial_sample"]:
        try:
            create_sample(experiment_name, {
                "name": incoming_info["initial_sample"],
                "description": "The initial sample created as part of experiment creation."
                })
            make_sample_current(experiment_name, incoming_info["initial_sample"])
            start_run(experiment_name, "DATA")
        except:
            logger.exception("Exception creating an initial sample. Please create the sample manually.")
            return (True, "Exception creating an initial sample. Please create the sample manually.")

    try:
        clone_system_template_run_tables_into_experiment(experiment_name, info["instrument"])
    except:
        logger.exception("Exception creating copies of template system run tables")

    return (True, "")

def update_existing_experiment(experiment_name, incoming_info):
    """
    Update an existing experiment
    """
    if experiment_name not in logbookclient.list_database_names():
        return (False, "Experiment %s does not exist" % experiment_name)

    expdb = logbookclient[experiment_name]
    info = {}
    info.update(incoming_info)
    info_id                    = experiment_name.replace(" ", "_")
    info["name"]               = experiment_name
    info["start_time"]         = datetime.datetime.strptime(info["start_time"], '%Y-%m-%dT%H:%M:%S.%fZ')
    info["end_time"]           = datetime.datetime.strptime(info["end_time"],   '%Y-%m-%dT%H:%M:%S.%fZ')

    expdb['info'].update_one({}, { "$set": info })
    return (True, "")

def clone_experiment(experiment_name, source_experiment_name, incoming_info, copy_specs, skip_initial_objects=False):
    """
    Registers a new experiment based on an existing experiment.
    We use the "info" of the existing experiment as a template for the new experiment.
    In addition, optionally, we copy over these collections from the source experiment.
    -- setup
    -- samples
    -- run_param_descriptions
    -- roles
    This is specified in copy_specs which is a dict of collection names to booleans.
    """
    src_exp_db = logbookclient[source_experiment_name]

    if experiment_name in list(logbookclient.list_database_names()):
        return (False, "Experiment %s has already been registered" % experiment_name)

    expdb = logbookclient[experiment_name]
    info = {}
    info.update(src_exp_db["info"].find_one())
    info.update(incoming_info)
    info["_id"]                = experiment_name.replace(" ", "_")
    info["name"]               = experiment_name
    if "experiment_name" in info: # Bug from previous releases?
        del info["experiment_name"]

    status, msg = register_new_experiment(experiment_name, info, create_auto_roles=False, skip_initial_objects=skip_initial_objects)
    if not status:
        return (status, msg)

    def copy_collection_from_src_to_clone(collection_name):
        for doc in src_exp_db[collection_name].find({}):
            expdb[collection_name].insert_one(doc)

    for coll, cp_select in copy_specs.items():
        if cp_select:
            logger.info("Copying over collection %s from source experiment %s to dest experiment %s", coll, source_experiment_name, experiment_name)
            copy_collection_from_src_to_clone(coll)

    # Make sure the person doing the cloning has admin privileges in the expeirment.
    current_user = security.get_current_user_id()
    expdb["roles"].update_one({"app" : "LogBook", "name": "Manager"}, {"$addToSet": {"players": "uid:" + current_user}}, upsert=True)
    expdb["roles"].update_one({"app" : "LogBook", "name": "Editor"}, {"$addToSet": {"players": "uid:" + current_user}}, upsert=True)

    try:
        clone_system_template_run_tables_into_experiment(experiment_name, info["instrument"])
    except:
        logger.exception("Exception creating copies of template system run tables")

    return (True, "")


def rename_experiment(experiment_name, new_experiment_name):
    """
    Renames an experiment with a new name.
    """
    if new_experiment_name in list(logbookclient.list_database_names()):
        return (False, "Experiment %s has already been registered" % new_experiment_name)
    if experiment_name in [x["name"] for x in get_currently_active_experiments() if "name" in x]:
        return (False, "Experiment %s is currently active" % experiment_name)

    src_exp_db = logbookclient[experiment_name]
    info = src_exp_db["info"].find_one()
    mods = {}
    mods["start_time"] = info["start_time"].strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    mods["end_time"] = info["end_time"].strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    copy_specs = { x : True for x in src_exp_db.list_collection_names() }
    for cn in ["info", "counters"]:
        copy_specs[cn] = False
    status, msg = clone_experiment(new_experiment_name, experiment_name, mods, copy_specs, skip_initial_objects=True)
    if not status:
        return (status, msg)

    new_exp_db = logbookclient[new_experiment_name]

    # Before dropping the src database, we should copy over the run counter.
    run_counter = src_exp_db["counters"].find_one({'_id': "next_runnum"})
    new_exp_db["counters"].update_one({'_id': "next_runnum"}, {"$set": {'seq': run_counter['seq']}})

    logger.info("Dropping the experiment database for %s", experiment_name)
    logbookclient.drop_database(experiment_name)

    return (True, "")

def lock_unlock_experiment(experiment_name):
    """
    Toggle an experiment's locked status.
    """
    expdb = logbookclient[experiment_name]
    curr_is_locked = expdb["info"].find_one().get("is_locked", False)

    expdb['info'].update_one({}, { "$set": {"is_locked": False if curr_is_locked else True } })
    return (True, "")

def delete_experiment(experiment_name):
    """
    Delete the experiment; we cannot recover from this without a backup.
    Make sure the experiment is not active and is actually an experiment.
    We also check to make sure that none of the attacments use http for an image store.
    """
    active_experiments = [ x.get("name", "Standby") for x in get_currently_active_experiments() ]
    if experiment_name in active_experiments:
        return (False, "Experiment %s is currently active" % experiment_name)

    expdb = logbookclient[experiment_name]
    if not expdb["info"].find_one() or not "instrument" in expdb["info"].find_one():
        return (False, "Is %s an experiment?" % experiment_name)

    http_attachments = expdb["elog"].count_documents({"$or": [{"attachments.url": {"$regex": re.compile("^http://")}}, {"attachments.preview_url": {"$regex": re.compile("^http://")}}]})
    if http_attachments:
        return (False, "We have %s attachments in an external image store; please archive the experiment before deleting." % http_attachments)

    logbookclient.drop_database(experiment_name)
    return (True, "")

def add_update_experiment_params(experiment_name, params):
    """
    Add or update the experiment params. We expect a dict of key value pairs; we'll add params to all the keys.
    """
    expdb = logbookclient[experiment_name]
    updated_params = { "params." + k : v for k, v in params.items()}
    logger.debug(updated_params)
    expdb["info"].update_one({}, {"$set": updated_params})
    return True, ""

def migrate_attachments_to_local_store(experiment_name):
    """
    Move the attachments from an external image store to either GridFS or a tar.gz on the file system.
    This is a step in preparation for archiving/deleting the experiment.
    """
    mg_imgstore = parseImageStoreURL("mongo://")
    expdb = logbookclient[experiment_name]
    failures = 0
    elog_entries = expdb["elog"].find({"$or": [{"attachments.url": {"$regex": re.compile("^http://")}}, {"attachments.preview_url": {"$regex": re.compile("^http://")}}]})
    for elog_entry in elog_entries:
        def __migrate_to_mongo__(aurl, attachment):
            logger.debug("Migrating %s to mongo", aurl)
            try:
                bio = parseImageStoreURL(aurl).return_url_contents(experiment_name, aurl)
                if not bio:
                    logger.debug("Cannot get attachment contents for %s", aurl)
                    return None
                murl = mg_imgstore.store_file_and_return_url(experiment_name, attachment["name"], attachment["type"], bio)
                logger.debug("Migrated %s to mongo as %s", aurl, murl)
                return murl
            except:
                logger.exception("Exception migrating attachment %s", aurl)
                return None

        for attachment in elog_entry.get("attachments", []):
            if attachment.get("url", "").startswith("http://"):
                murl = __migrate_to_mongo__(attachment["url"], attachment)
                if murl:
                    expdb["elog"].update_one({"_id": elog_entry["_id"], "attachments._id": attachment["_id"]}, {"$set": {"attachments.$.url": murl}})
                else:
                    failures = failures + 1
            if attachment.get("preview_url", "").startswith("http://"):
                murl = __migrate_to_mongo__(attachment["preview_url"], attachment)
                if murl:
                    expdb["elog"].update_one({"_id": elog_entry["_id"], "attachments._id": attachment["_id"]}, {"$set": {"attachments.$.preview_url": murl}})
                else:
                    failures = failures + 1

    if failures:
        return (False, "%s attachments were not migrated. Please see the server logs for more details" % failures)
    return (True, "")


def create_update_instrument(instrument_name, createp, incoming_info):
    """
    Create or update an instrument.
    :param instrument_name: Name of the instrument.
    :createp: A boolean indicating if this is to be created.
    :incoming_info: The JSON document containing the description of the instrument to be created.
    """
    sitedb = logbookclient["site"]
    if createp and sitedb.instruments.find_one({"_id": instrument_name}):
        return (False, "Instrument %s already exists" % instrument_name)
    if not createp and not sitedb.instruments.find_one({"_id": instrument_name}):
        return (False, "Instrument %s does not exist" % instrument_name)

    if createp:
        sitedb.instruments.insert_one(incoming_info)
    else:
        sitedb.instruments.find_one_and_update({"_id": instrument_name}, { "$set": incoming_info })
    return (True, "Instrument %s processed" % instrument_name)

def get_instrument_station_list():
    """
    Get a list of instrumens and end stations as a list.
    This skips those instruments that have a num_stations of 0.
    """
    ins_st_list = []
    for instr in get_instruments():
        name = instr["_id"]
        params = instr.get("params", {})
        num_stations = int(params.get("num_stations", 0))
        if num_stations:
            # Skip those that have a num_stations of 0.
            for station in range(num_stations):
                ins_st_list.append({ "instrument": name, "station": station })
    return ins_st_list


def get_currently_active_experiments():
    """
    Get the currently active experiments at each instrment/station.
    """
    active_queries = get_instrument_station_list()

    sitedb = logbookclient["site"]
    ret = []
    for qry in active_queries:
        logger.debug("Looking for active experiment for %s", qry)
        for exp in sitedb["experiment_switch"].find(qry).sort([( "switch_time", -1 )]).limit(1):
            exp_info = get_experiment_info(exp["experiment_name"]) if not exp.get("is_standby", False) else { "instrument": qry["instrument"], "is_standby": True }
            exp_info["station"] = qry["station"]
            exp_info["switch_time"] = exp["switch_time"]
            exp_info["requestor_uid"] = exp["requestor_uid"]
            if 'name' in exp_info:
                curr_sample = get_current_sample_name(exp_info['name'])
                if curr_sample:
                    exp_info['current_sample'] = curr_sample
                curr_run = get_current_run(exp_info['name'])
                if curr_run:
                    exp_info['current_run'] = { x : curr_run[x] for x in ['num', 'begin_time', 'end_time'] if x in curr_run and curr_run[x] }
                cached_exp_info = logbookclient['explgbk_cache']['experiments'].find_one({"_id": exp_info['name']})
                if cached_exp_info:
                    if "last_run" in cached_exp_info:
                        exp_info["last_run"] = cached_exp_info["last_run"]
                    if "first_run" in cached_exp_info:
                        exp_info["first_run"] = cached_exp_info["first_run"]
            ret.append(exp_info)

    return ret

def get_active_experiment_name_for_instrument_station(instrument, station):
    sitedb = logbookclient["site"]
    origins = instrument
    caseinsinslkp = { x["_id"].upper() : x["_id"] for x in sitedb["instruments"].find({}, {"_id": 1})}
    instrument = caseinsinslkp.get(instrument.upper(), None)
    if not instrument:
        logger.error("Cannot find instrument %s", origins)
        return None

    for active_experiment in sitedb["experiment_switch"].find({ "instrument": instrument, "station": station }).sort([( "switch_time", -1 )]).limit(1):
        if 'instrument' in active_experiment and active_experiment['instrument'] == instrument and active_experiment['station'] == int(station) and not active_experiment.get('is_standby', False):
            return get_experiment_info(active_experiment['experiment_name'])
    return None

def switch_experiment(instrument, station, experiment_name, userid):
    """
    Switch the currently active experiment on the instrument.
    This mostly consists inserting an entry into the experiment_switch database.
    Also switch in/switch out the operator account for the instrument.
    """
    current_active_experiment = get_active_experiment_name_for_instrument_station(instrument, station)
    sitedb = logbookclient["site"]
    sitedb.experiment_switch.insert_one({
        "experiment_name" : experiment_name,
        "instrument" : instrument,
        "station" : int(station),
        "switch_time" : datetime.datetime.utcnow(),
        "requestor_uid" : userid
        })
    operator_uid = { x["_id"] : x for x in get_instruments()}[instrument].get("params", {}).get("operator_uid", None)

    if operator_uid:
        fq_role_name = "LogBook/Writer"
        if current_active_experiment:
            active_exp_name = current_active_experiment.get("name", None)
            logger.info("Removing post privileges for uid:" + operator_uid + " from " + active_exp_name)
            remove_collaborator_from_role(active_exp_name, "uid:" + operator_uid, fq_role_name)
        logger.debug("Adding post privileges for uid:" + operator_uid + " to " + experiment_name)
        add_collaborator_to_role(experiment_name, "uid:" + operator_uid, fq_role_name)
    else:
        logger.debug("No operator_uid defined for %s; skipping auto-add of operator accounts", instrument)

    return (True, "")

def instrument_standby(instrument, station, userid):
    """
    Put the instrument into standby mode.
    This mostly creates an experiment switch entry with the is_standby flag set.
    """
    sitedb = logbookclient["site"]
    sitedb.experiment_switch.insert_one({
        "experiment_name" : "Standby",
        "instrument" : instrument,
        "station" : int(station),
        "switch_time" : datetime.datetime.utcnow(),
        "requestor_uid" : userid,
        "is_standby": True
        })
    return (True, "")

def get_switch_history(instrument, station):
    """
    Return the experiment switch history for an instrument/station.
    """
    sitedb = logbookclient["site"]
    ins_exps = { x["name"] : x for x in get_experiments_for_instrument(instrument) }
    ret = []
    for x in sitedb.experiment_switch.find({"instrument": instrument, "station": station}).sort([("switch_time", -1)]):
        expname = x.get("experiment_name", "")
        if expname != "Standby" and expname in ins_exps:
            x["description"] = ins_exps[expname]["description"]
            x["PI"] = ins_exps[expname]["contact_info"]
        ret.append(x)
    return ret

def get_global_roles():
    sitedb = logbookclient["site"]
    return [x for x in sitedb["roles"].find({"app": "LogBook"})]

def add_player_to_global_role(player, role):
    sitedb = logbookclient["site"]
    sitedb["roles"].update_one({"app": "LogBook", "name": role}, {"$addToSet": {"players": player}})

def remove_player_from_global_role(player, role):
    sitedb = logbookclient["site"]
    sitedb["roles"].update_one({"app": "LogBook", "name": role}, {"$pull": {"players": player}})

def add_player_to_instrument_role(instrument, player, role):
    sitedb = logbookclient["site"]
    ins = sitedb["instruments"].find_one({ "_id": instrument })
    if not "roles" in ins:
        sitedb["instruments"].update_one({ "_id": instrument }, {"$set": {"roles": [{"app": "LogBook", "name": role, "players": [ player ]}]}})
        return sitedb["instruments"].find_one({ "_id": instrument })
    rl = [ x for x in ins.get("roles", []) if x["app"] == "LogBook" and x["name"] == role ]
    if rl:
        sitedb["instruments"].update_one({ "_id": instrument, "roles.app": "LogBook", "roles.name": role}, {"$addToSet": {"roles.$.players": player}})
        return sitedb["instruments"].find_one({ "_id": instrument })
    else:
        sitedb["instruments"].update_one({ "_id": instrument}, {"$push": {"roles": {"app": "LogBook", "name": role, "players": [ player ]}}})
        return sitedb["instruments"].find_one({ "_id": instrument })

def remove_player_from_instrument_role(instrument, player, role):
    sitedb = logbookclient["site"]
    ins = sitedb["instruments"].find_one({ "_id": instrument })
    if not "roles" in ins:
        return sitedb["instruments"].find_one({ "_id": instrument })

    rl = [ x for x in ins.get("roles", []) if x["app"] == "LogBook" and x["name"] == role ]
    if rl:
        sitedb["instruments"].update_one({ "_id": instrument, "roles.app": "LogBook", "roles.name": role}, {"$pull": {"roles.$.players": player}})
        sitedb["instruments"].update_one({ "_id": instrument, "roles.app": "LogBook", "roles.name": role, "roles.players": {"$exists": True, "$size": 0}}, {"$pull": {"roles": {"app": "LogBook", "name": role}}})

    return sitedb["instruments"].find_one({ "_id": instrument })

def get_elog_entries(experiment_name, sample_name=None):
    """
    Get the elog entries for the experiment as a flat list sorted by inserted time ascending.
    The sort order is important as the UI uses this to optimize tree-building.
    """
    expdb = logbookclient[experiment_name]
    if not sample_name or sample_name == "All Samples":
        return [entry for entry in expdb['elog'].find().sort([("insert_time", 1)])]
    else:
        # We start at samples for performance reasons;
        return [x for x in expdb.samples.aggregate([
            { "$match": { "name": sample_name }},
            { "$lookup": { "from": "runs", "localField": "_id", "foreignField": "sample", "as": "run"}},
            { "$unwind": "$run" }, # lookup generates an array field, we convert to a list of docs with a single field instead.
            { "$replaceRoot": { "newRoot": "$run" } },
            { "$lookup": { "from": "elog", "localField": "num", "foreignField": "run_num", "as": "elog"}},
            { "$unwind": "$elog" },
            { "$replaceRoot": { "newRoot": "$elog" } },
            { "$sort": { "insert_time": 1 }}
        ])]

def get_specific_elog_entry(experiment_name, id):
    """
    Get the specified elog entry for the experiment.
    For now, we have id based lookups.
    """
    expdb = logbookclient[experiment_name]
    return expdb['elog'].find_one({"_id": ObjectId(id)})

def __get_root_and_parent_entries(experiment_name, matching_entries):
    """
    Get the root and parent entries for all elog entries in matching entries.
    """
    logger.debug("Recursively expanding root and parent entries for %s", experiment_name)
    anyAdditions = False
    def __addEntryIfNotPresent(matching_entry, idname):
        nonlocal anyAdditions
        if idname in matching_entry and matching_entry[idname] not in matching_entries:
            matching_entries[matching_entry[idname]] = get_specific_elog_entry(experiment_name, matching_entry[idname])
            anyAdditions = True

    for matching_entry in matching_entries.copy().values():
        __addEntryIfNotPresent(matching_entry, "root")
        __addEntryIfNotPresent(matching_entry, "parent")
    return anyAdditions


def search_elog_for_text(experiment_name, search_text):
    """
    Search for elog entries that match text.
    Return the matching entries sorted by inserted time ascending.
    The sort order is important as the UI uses this to optimize tree-building.
    """
    expdb = logbookclient[experiment_name]
    matching_entries = {x["_id"] : x for x in expdb['elog'].find({ "$text": { "$search": search_text }})}
    if not matching_entries:
        matching_entries = {x["_id"] : x for x in expdb['elog'].find({ "content": { "$regex": re.compile(".*" + search_text + ".*", re.IGNORECASE)}})}
    # Recursively gather all root and parent entries
    while __get_root_and_parent_entries(experiment_name, matching_entries):
        pass

    return list(sorted(matching_entries.values(), key=lambda x : x["insert_time"]))

def get_elogs_for_run_num(experiment_name, run_num):
    """
    Get elog entries belonging to run number run_num
    """
    expdb = logbookclient[experiment_name]
    matching_entries = {x["_id"] : x for x in expdb['elog'].find({ "run_num": run_num})}
    # Recursively gather all root and parent entries
    while __get_root_and_parent_entries(experiment_name, matching_entries):
        pass

    return list(sorted(matching_entries.values(), key=lambda x : x["insert_time"]))


def get_elogs_for_run_num_range(experiment_name, start_run_num, end_run_num):
    """
    Get elog entries for the run number range - start_run_num to end_run_num (both inclusive)
    """
    expdb = logbookclient[experiment_name]
    matching_entries = {x["_id"] : x for x in expdb['elog'].find({ "run_num": {"$gte": start_run_num, "$lte": end_run_num}})}
    # Recursively gather all root and parent entries
    while __get_root_and_parent_entries(experiment_name, matching_entries):
        pass

    return list(sorted(matching_entries.values(), key=lambda x : x["insert_time"]))

def get_elog_entries_by_author(experiment_name, author):
    """
    Get elog entries by the specified author
    """
    expdb = logbookclient[experiment_name]
    matching_entries = {x["_id"] : x for x in expdb['elog'].find({ "author": author })}
    # Recursively gather all root and parent entries
    while __get_root_and_parent_entries(experiment_name, matching_entries):
        pass

    return list(sorted(matching_entries.values(), key=lambda x : x["insert_time"]))

def get_elog_entries_by_tag(experiment_name, tag):
    """
    Get elog entries with the specified tag
    """
    expdb = logbookclient[experiment_name]
    matching_entries = {x["_id"] : x for x in expdb['elog'].find({ "tags": tag })}
    # Recursively gather all root and parent entries
    while __get_root_and_parent_entries(experiment_name, matching_entries):
        pass

    return list(sorted(matching_entries.values(), key=lambda x : x["insert_time"]))

def get_run_numbers_with_tag(experiment_name, tag):
    """
    Get elog entries with the specified tag
    """
    expdb = logbookclient[experiment_name]
    run_nums = set([ x["run_num"] for x in expdb['elog'].find({ "tags": tag, "run_num": {"$exists": 1} }, {"run_num": 1} ) ])
    return sorted(list(run_nums))

def get_tag_to_run_numbers(experiment_name):
    """
    Get a dict of tag to the run number that have elog statements containing the tag
    """
    expdb = logbookclient[experiment_name]
    runs_with_tags = [ x for x in expdb['elog'].find({ "tags": {"$exists": 1}, "run_num": {"$exists": 1} }, {"run_num": 1, "tags": 1} ) ]
    ret = {}
    for run_with_tags in runs_with_tags:
        for tag in run_with_tags["tags"]:
            if tag not in ret:
                ret[tag] = []
            ret[tag].append(run_with_tags["run_num"])
    return ret

def get_tags_for_runs(experiment_name):
    """
    Get a dict of run number to array of tags.
    """
    expdb = logbookclient[experiment_name]
    runs_with_tags = [ x for x in expdb['elog'].find({ "tags": {"$exists": 1}, "run_num": {"$exists": 1} }, {"run_num": 1, "tags": 1} ) ]
    ret = {}
    for run_with_tags in runs_with_tags:
        for tag in run_with_tags["tags"]:
            run_num = run_with_tags["run_num"]
            if run_num not in ret:
                ret[run_num] = []
            ret[run_num].extend(run_with_tags["tags"])
    for k, v in ret.items():
        ret[k] = sorted(set(v))
    return ret

def get_elogs_for_specified_id(experiment_name, specified_id):
    """
    Get the elog entries related to the entry with the specified id.
    """
    specified_entry = get_specific_elog_entry(experiment_name, specified_id)
    if specified_entry:
        matching_entries = { specified_entry["_id"]: specified_entry }
        while __get_root_and_parent_entries(experiment_name, matching_entries):
            pass
        return list(sorted(matching_entries.values(), key=lambda x : x["insert_time"]))
    else:
        return []

def get_elog_tree_for_specified_id(experiment_name, specified_id):
    """
    Get all the children of the specified elog entry; the result includes the entry also.
    """
    expdb = logbookclient[experiment_name]
    specified_entry = get_specific_elog_entry(experiment_name, specified_id)
    ret = [ specified_entry ]
    if specified_entry:
        ret.extend([x for x in expdb["elog"].find({"root": specified_entry["_id"]})])
        return list(sorted(ret, key=lambda x : x["insert_time"]))
    else:
        return []

def get_complete_elog_tree_for_specified_id(experiment_name, specified_id):
    """
    Get all the parents and all the children of the specified elog entry; the result includes the entry also.
    """
    expdb = logbookclient[experiment_name]
    specified_entry = get_specific_elog_entry(experiment_name, ObjectId(specified_id))
    if specified_entry:
        if 'root' in specified_entry:
            ret = {x["_id"] : x for x in expdb['elog'].find({ "root": specified_entry["root"]})}
            ret[specified_entry["root"]] = get_specific_elog_entry(experiment_name, specified_entry["root"])
        else:
            ret = {x["_id"] : x for x in expdb['elog'].find({ "root": specified_entry["_id"]})}
            ret[specified_entry["_id"]] = specified_entry
        return list(sorted(ret.values(), key=lambda x : x["insert_time"]))
    return []

def get_elogs_for_date_range(experiment_name, start_date, end_date):
    """
    Get the elog entries between the specified date range; >= start_date and <= end_date
    """
    expdb = logbookclient[experiment_name]
    logger.debug("Looking for entries between %s and %s", start_date, end_date)
    matching_entries = {x["_id"] : x for x in expdb['elog'].find({ "relevance_time": { "$gte": start_date, "$lte": end_date } })}
    # Recursively gather all root and parent entries
    while __get_root_and_parent_entries(experiment_name, matching_entries):
        pass

    return list(sorted(matching_entries.values(), key=lambda x : x["insert_time"]))

def get_elog_entries_by_regex(experiment_name, regx):
    """
    Get the elog entries that match the regex
    """
    expdb = logbookclient[experiment_name]
    logger.debug("Looking for entries matching %s", regx)
    try:
        matching_entries = {x["_id"] : x for x in expdb['elog'].find({"content": {"$regex": regx, "$options": "m"}})}
        # Recursively gather all root and parent entries
        while __get_root_and_parent_entries(experiment_name, matching_entries):
            pass

        return list(sorted(matching_entries.values(), key=lambda x : x["insert_time"]))
    except:
        logger.exception("Exception matching regex %s for experiment %s", regx, experiment_name)
        return []

def __upload_attachments_to_imagestore_and_return_urls(experiment_name, files):
    """
    Given a list of file uploads, upload these to the imagestore, generate thumbnails and return a list of attachments objects.
    """
    attachments = []
    for file in files:
        filename = file[0]
        filestorage = file[1] # http://werkzeug.pocoo.org/docs/0.14/datastructures/#werkzeug.datastructures.FileStorage

        imgurl = parseImageStoreURL(imagestoreurl).store_file_and_return_url(experiment_name, filename, filestorage.mimetype, filestorage.stream)
        attachment = {"_id": ObjectId(), "name" : filename, "type": filestorage.mimetype, "url" : imgurl }

        # We get the data back from the image server; this is to make sure the content did make it there; also the stream is probably in an inconsistent state
        # Not the most efficient but the safest perhaps.
        with parseImageStoreURL(imgurl).return_url_contents(experiment_name, imgurl) as imgget, tempfile.NamedTemporaryFile("w+b") as fd:
            tfname, tf_thmbname = fd.name, fd.name+".png"
            shutil.copyfileobj(imgget, fd, 1024)
            fd.flush()
            attachment_size = os.fstat(fd.fileno()).st_size
            if attachment_size > MAX_ATTACHMENT_SIZE:
                raise LgbkException("We limit the size of attachments to %s M" % str(MAX_ATTACHMENT_SIZE/(1024*1024)))
            logger.info("Attachment size %s", attachment_size)
            cp = subprocess.run(["convert", "-thumbnail", "128", tfname, tf_thmbname], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=30)
            logger.info(cp)
            if cp.returncode == 0 and os.path.exists(tf_thmbname):
                with open(tf_thmbname, 'rb') as thmb_s:
                    thmb_imgurl = parseImageStoreURL(imagestoreurl).store_file_and_return_url(experiment_name, "preview_" + filename, "image/png", thmb_s)
                    attachment["preview_url"] = thmb_imgurl
            else:
                logger.warn("Skipping generating a thumbnail for %s for experiment %s", filename, experiment_name)

        attachments.append(attachment)
    return attachments


def post_new_log_entry(experiment_name, author, log_content, files, run_num=None, shift=None, root=None, parent=None, email_to=None, tags=None, title=None, post_to_elogs=None, jira_ticket=None):
    """
    Create a new log entry.
    """
    expdb = logbookclient[experiment_name]
    attachments = __upload_attachments_to_imagestore_and_return_urls(experiment_name, files)
    now_ts = datetime.datetime.utcnow()
    elog_doc = {
        "relevance_time": now_ts,
        "insert_time": now_ts,
        "author": author,
        "content": log_content,
        "content_type": "TEXT"
    }
    if attachments:
        elog_doc["attachments"] = attachments
    if run_num:
        elog_doc["run_num"] = run_num
    if shift:
        elog_doc["shift"] = shift
    if email_to:
        elog_doc["email_to"] = email_to
    if tags:
        elog_doc["tags"] = tags
    if root:
        elog_doc["root"] = root
    if parent:
        elog_doc["parent"] = parent
    if title:
        elog_doc["title"] = title
    if post_to_elogs:
        elog_doc["post_to_elogs"] = post_to_elogs
    if jira_ticket:
        elog_doc["jira_ticket"] = jira_ticket

    ins_id = expdb['elog'].insert_one(elog_doc).inserted_id
    entry = expdb['elog'].find_one({"_id": ins_id})
    return entry

def delete_elog_entry(experiment_name, entry_id, userid):
    """
    Mark the elog entry specified by the entry_id as being deleted
    This is a logical delete; so we add a deleted_by and deleted_time
    """
    expdb = logbookclient[experiment_name]
    result = expdb['elog'].update_one({"_id": ObjectId(entry_id)}, {"$set": { "deleted_by": userid, "deleted_time": datetime.datetime.utcnow()}})
    if result.modified_count <= 0:
        return False
    current_entry = expdb['elog'].find_one({"_id": ObjectId(entry_id)})
    if "post_to_elogs" in current_entry and current_entry["post_to_elogs"]:
        for post_to_elog in current_entry["post_to_elogs"]:
            logger.debug("Deleting instrument elog entry in %s", post_to_elog)
            logbookclient[post_to_elog]["elog"].update_one({"src_id": current_entry["_id"], "src_expname": experiment_name}, {"$set": { "deleted_by": userid, "deleted_time": datetime.datetime.utcnow()}})
    return True

def modify_elog_entry(experiment_name, entry_id, userid, new_content, email_to, tags, files, title=None, run_num=None):
    """
    Change the content for the specified elog entry.
    We have to retain the history of the change; so we clone the existing entry but make the clone a child of the existing entry.
    We also set the deleted_by/deleted_time for the clone; so it should show up as deleted.
    """
    expdb = logbookclient[experiment_name]
    attachments = __upload_attachments_to_imagestore_and_return_urls(experiment_name, files)
    current_entry = expdb['elog'].find_one({"_id": ObjectId(entry_id)})
    hist_entry = copy.deepcopy(current_entry)
    del hist_entry["_id"]
    hist_entry["parent"] = current_entry["_id"]
    hist_entry["root"] = current_entry["root"] if "root" in current_entry else current_entry["_id"]
    hist_entry["deleted_by"] = userid
    hist_entry["deleted_time"] = datetime.datetime.utcnow()
    hist_entry["relevance_time"] = hist_entry["deleted_time"]
    if "previous_version" in current_entry:
        hist_entry["previous_version"] = current_entry["previous_version"]
    hist_result = expdb['elog'].insert_one(hist_entry)
    if hist_result and hist_result.inserted_id:
        modification = {"$set": {
            "content": new_content,
            "author": userid,
            "tags": tags,
            "previous_version": hist_result.inserted_id
        }}
        if attachments:
            modification["$push"] = { "attachments": { "$each": attachments }}
        if email_to:
            modification.setdefault("$addToSet", {})["email_to"] = { "$each": email_to }
        if title:
            modification["$set"]["title"] = title
        if not hist_entry.get("run_num", None) == run_num:
            if run_num ==  None:
                modification["$unset"] = { "run_num" : 1 }
            else:
                modification["$set"]["run_num"] = run_num
        result = expdb['elog'].update_one({"_id": current_entry["_id"]}, modification)
        if result.modified_count <= 0:
            return False
        if "post_to_elogs" in current_entry and current_entry["post_to_elogs"]:
            del modification["$set"]["previous_version"]
            for post_to_elog in current_entry["post_to_elogs"]:
                logger.debug("Updating instrument elog entry in %s", post_to_elog)
                logbookclient[post_to_elog]["elog"].update_one({"src_id": current_entry["_id"], "src_expname": experiment_name}, modification)
        return True
    return False

def post_related_elog_entry(related_experiment, src_experiment, src_elog_entry_id):
    '''
    Copy an elog entry into a related elog; typically an instrument elog
    When we copy, we maintain the source experiment and source elog entry id to make it easier to tie children to the parent.
    '''
    expdb = logbookclient[related_experiment]
    src_expdb = logbookclient[src_experiment]
    src_elog_entry = get_specific_elog_entry(src_experiment, src_elog_entry_id)
    if "root" not in src_elog_entry and "parent" not in src_elog_entry and related_experiment not in src_elog_entry.get("post_to_elogs", []):
        expdb["elog"].update_one({"_id": src_elog_entry["_id"]}, {"$addToSet": {"post_to_elogs": related_experiment}})
    del src_elog_entry["_id"]
    if "post_to_elogs" in src_elog_entry:
        del src_elog_entry["post_to_elogs"]
    src_elog_entry["src_expname"] = src_experiment
    src_elog_entry["src_id"] = src_elog_entry_id
    def __check_and_link__(attr):
        if attr in src_elog_entry:
            rel_entry = expdb['elog'].find_one({"src_expname": src_experiment, "src_id": src_elog_entry[attr]})
            if not rel_entry:
                logger.error("Cannot find related entry %s with id %s in %s", attr, src_elog_entry[attr], related_experiment)
            else:
                src_elog_entry[attr] = rel_entry["_id"]
    __check_and_link__("root")
    __check_and_link__("parent")

    mg_imgstore = parseImageStoreURL("mongo://")
    def __copy_attachment__(attch, attr):
        if attr in attch and attch[attr].startswith("mongo://"):
            aurl = attch[attr]
            try:
                bio = parseImageStoreURL(aurl).return_url_contents(src_experiment, aurl)
                if not bio:
                    logger.debug("Cannot get attachment contents for %s", aurl)
                    return None
                murl = mg_imgstore.store_file_and_return_url(related_experiment, attch["name"], attch["type"], bio)
                logger.debug("Copied %s to mongo as %s", aurl, murl)
                attch[attr] = murl
                return murl
            except:
                logger.exception("Exception copying attachment %s", aurl)
                return None
    for attch in src_elog_entry.get("attachments", []):
        __copy_attachment__(attch, "url")
        __copy_attachment__(attch, "preview_url")

    ins_id = expdb['elog'].insert_one(src_elog_entry).inserted_id
    entry = expdb['elog'].find_one({"_id": ins_id})
    return entry

def get_related_instrument_elog_entries(experiment_name, entry_id):
    '''
    Get the related instrument elog entries for a given elog entry if they are present.
    Returns a dict of experiment/elog name with the related entry.
    '''
    current_entry = get_specific_elog_entry(experiment_name, entry_id)
    ret = {}
    if current_entry and "post_to_elogs" in current_entry and current_entry["post_to_elogs"]:
        for post_to_elog in current_entry["post_to_elogs"]:
            related_entry = logbookclient[post_to_elog]["elog"].find_one({"src_id": current_entry["_id"], "src_expname": experiment_name})
            if related_entry:
                ret[post_to_elog] = related_entry
    return ret

def get_elog_authors(experiment_name):
    '''
    Get the distinct authors for the elog entries.
    '''
    expdb = logbookclient[experiment_name]
    return expdb['elog'].distinct("author")

def get_elog_tags(experiment_name):
    '''
    Get the distinct tags for the elog entries.
    '''
    sitedb = logbookclient["site"]
    ins = sitedb["instruments"].find_one({ "_id": get_experiment_info(experiment_name)["instrument"] })
    ins_tags = ins.get("params", {}).get("tags", "").split(" ")
    expdb = logbookclient[experiment_name]
    return expdb['elog'].distinct("tags") + ins_tags

def get_elog_emails(experiment_name):
    '''
    Get all the email addresses that we sent elog messages to that are recorded in the db.
    '''
    expdb = logbookclient[experiment_name]
    emails = list({x for x in [y for x in [ x['email_to'] for x in filter(lambda x : x, list(expdb['elog'].find({}, { "email_to": 1, "_id": 0 }))) ]  for y in x]})
    # Add in site and instrument specific email mailing lists.
    if logbookclient['site']['siteinfo'].find_one({}, {"_id": 0, "params.elog_mailing_lists": 1}):
        emails.extend(logbookclient['site']['siteinfo'].find_one({}, {"_id": 0, "params.elog_mailing_lists": 1}).get('params', {}).get('elog_mailing_lists', []))
    ins = get_experiment_info(experiment_name)['instrument']
    if logbookclient['site']['instruments'].find_one({"_id": ins}, {"_id": 0, "params.elog_mailing_lists": 1}):
        emails.extend(logbookclient['site']['instruments'].find_one({"_id": ins}, {"_id": 0, "params.elog_mailing_lists": 1}).get('params', {}).get('elog_mailing_lists', []))
    return sorted(emails)

def get_elog_email_subscriptions(experiment_name):
    '''
    The logbook will send email messages when new elog messages are posted to the elog.
    Get all the subscribers who have subscribed to email messages for this experiment.
    '''
    expdb = logbookclient[experiment_name]
    return list(expdb.subscribers.find({}))

def get_elog_email_subscriptions_emails(experiment_name):
    '''
    Get an array of email addresses of folks who have subscried to emails for this experiment.
    '''
    expdb = logbookclient[experiment_name]
    return [x['email_address'] for x in list(expdb.subscribers.find({}, {"email_address": 1}))]

def elog_email_subscribe(experiment_name, userid):
    '''
    Add the specified user to the email subscriptions
    '''
    expdb = logbookclient[experiment_name]
    result = expdb.subscribers.insert_one({"_id": userid, "subscriber": userid, "email_address": userid + "@slac.stanford.edu", "subscribed_time": datetime.datetime.utcnow() })
    return result.acknowledged

def elog_email_unsubscribe(experiment_name, userid):
    '''
    Remove the specified user from the email subscriptions
    '''
    expdb = logbookclient[experiment_name]
    result = expdb.subscribers.delete_one({"_id": userid})
    return result.acknowledged

def get_site_naming_conventions():
    '''
    Get the naming conventions from the site config.
    Naming conventions are object/attribute documents; for example, experiment.name
    Each document has a placeholder, tooltip and validation_regex attribute.
    The placeholder is used as the HTML placeholder/example for the attribute.
    The validation regex will do some basic regex; however, it's probably very difficult to cover all cases with a regex.
    The tooltip should have enought detail to outlines the naming convention for operators.
    '''
    sitedb = logbookclient["site"]
    s_config = sitedb["site_config"].find_one({})
    if s_config:
        return s_config.get("naming_conventions", {})
    return {}

def get_site_file_types():
    """
    For the file manager, we classify the files in the file catalog into types.
    These are assumed to be equivalent and basically different versions of the same data.
    For example, in LCLS, the detector data is stored initially as XTC or XTC2 files.
    Some users convert these into HDF5 (h5) files and primarily use those for analysis.
    Typically, users use one of these types of files.
    To capture this, we define filemanager_file_types in the site_config.
	"filemanager_file_types" : {
		"XTC" : {
			"name" : "XTC",
			"label" : "XTC files",
			"tooltip" : "Large and smalldata xtc and xtc2 files",
			"patterns" : [
				"^.*/xtc/.*.xtc$",
				"^.*/xtc/.*.xtc2$"
			],
			"selected" : true
		},
    The filemanager supports restoration of one or all of these file types.
    """
    sitedb = logbookclient["site"]
    s_config = sitedb["site_config"].find_one({})
    if s_config:
        return s_config.get("filemanager_file_types", {})
    return {}

def get_instrument_elogs(experiment_name, include_instrument_elogs=True, include_site_spanning_elogs=True):
    '''
    Get the associated elogs for experiment.
    This consists of the elog(s) for the instrument (instrument param elog in the instrument object).
    And global experiment_spanning_elogs logs (like the LCLS sample delivery elog) in the site's info object.
    Also can be specified on a per experiment basis as the experiment parameter xpost_elogs ( comma separated list ).
    '''
    ret = []
    exp_info = get_experiment_info(experiment_name)
    exp_x_post_elogs = exp_info.get("params", {}).get("xpost_elogs", None)
    if exp_x_post_elogs:
        ret.extend([x.strip() for x in exp_x_post_elogs.split(",")])
    sitedb = logbookclient["site"]
    if include_instrument_elogs:
        instrument_elog = sitedb["instruments"].find_one({"_id": exp_info["instrument"]}).get("params", {}).get("elog", None)
        if instrument_elog:
            ret.append(instrument_elog)
    if include_site_spanning_elogs:
        siteinfo = sitedb["site_config"].find_one()
        if siteinfo and 'experiment_spanning_elogs' in siteinfo and siteinfo['experiment_spanning_elogs']:
            ret.extend(siteinfo['experiment_spanning_elogs'])
    return ret

def get_experiment_files(experiment_name, sample_name=None):
    '''
    Get the files for the given experiment
    '''
    expdb = logbookclient[experiment_name]
    if not sample_name or sample_name == "All Samples":
        return [file for file in expdb['file_catalog'].find().sort([("run_num", -1), ("create_timestamp", -1)])]
    else:
        return [x for x in expdb.samples.aggregate([
            { "$match": { "name": sample_name }},
            { "$lookup": { "from": "runs", "localField": "_id", "foreignField": "sample", "as": "run"}},
            { "$unwind": "$run" },
            { "$replaceRoot": { "newRoot": "$run" } },
            { "$lookup": { "from": "file_catalog", "localField": "num", "foreignField": "run_num", "as": "file_catalog"}},
            { "$unwind": "$file_catalog" },
            { "$replaceRoot": { "newRoot": "$file_catalog" } },
            { "$sort": { "run_num": -1 }}
        ])]

def get_experiment_files_for_run(experiment_name, run_num):
    '''
    Get the files for the given experiment for the specified run
    '''
    expdb = logbookclient[experiment_name]
    return [file for file in expdb['file_catalog'].find({"run_num": run_num}).sort([("run_num", -1), ("create_timestamp", -1)])]

def get_experiment_files_for_run_for_live_mode(experiment_name, run_num):
    '''
    Get a minimal set of information for psana live mode.
    Return only the path information for only the xtc/xtc2 files in the xtc folder ( and not it's children ).
    '''
    expdb = logbookclient.get_database(experiment_name, read_preference=ReadPreference.SECONDARY_PREFERRED)
    ret = [file["path"] for file in expdb['file_catalog'].find({"run_num": run_num, "path": { "$regex": re.compile(".*/xtc/[^/]*[.](xtc|xtc2)$") }}, {"_id": -0, "path": 1}).sort([("path", 1)])]
    return ret

def get_experiment_files_for_run_for_live_mode_at_location(experiment_name, run_num, location):
    '''
    Return some basic information on whether the run is complete and files are available at a location.
    '''
    expdb = logbookclient.get_database(experiment_name, read_preference=ReadPreference.SECONDARY_PREFERRED)
    run_doc = expdb.runs.find_one({"num": run_num})

    ret = {
        "begin_time": run_doc["begin_time"],
        "end_time": run_doc.get("end_time", None),
        "is_closed": is_run_closed(experiment_name, run_num),
        "files": []
    }

    files = expdb['file_catalog'].find({"run_num": run_num, "path": { "$regex": re.compile(".*/xtc/[^/]*[.](xtc|xtc2)$") }}, {"_id": -0, "path": 1, "locations": 1}).sort([("path", 1)])
    for file in files:
        ret["files"].append({"path": file["path"], "is_present": "asof" in file.get("locations", {}).get(location, {}).keys()})

    ret["all_present"] = ret["is_closed"] and all(map(lambda x : x["is_present"], ret["files"]))
    return ret

def get_experiment_files_for_live_mode_at_location(experiment_name, location):
    '''
    A experiment-wide version of get_experiment_files_for_run_for_live_mode_at_location
    '''
    expdb = logbookclient.get_database(experiment_name, read_preference=ReadPreference.SECONDARY_PREFERRED)
    aggr = expdb.runs.aggregate([
      { "$lookup": { "from": "file_catalog", "localField": "num", "foreignField": "run_num", "as": "files"}},
      { "$project": { "_id": 0, "num": 1, "begin_time" : 1, "end_time": 1, "files.path": 1, "files.locations." + location + ".asof": 1 } },
      { "$sort": {"num": -1} }
    ])
    ret = []
    for x in aggr:
        robj = { "run_num": x["num"], "begin_time": x["begin_time"], "end_time": x.get("end_time", None), "is_closed": "end_time" in x and x["end_time"] != None, "files": [] }
        for f in x["files"]:
            robj["files"].append({"path": f["path"], "is_present": "asof" in f.get("locations", {}).get(location, {}).keys()})
        robj["all_present"] = robj["is_closed"] and all(map(lambda x : x["is_present"], robj["files"]))
        ret.append(robj)

    return ret

def get_exp_file_counts_by_extension(experiment_name):
    """
    Return the file counts based on file type that we know about.
    """
    expdb = logbookclient[experiment_name]
    extensions =  [ x for x in expdb.file_catalog.aggregate([
        { "$project": { "extension": { "$first": { "$reverseArray": { "$split": [ "$path", "."] }}}}},
        { "$group": { "_id": "$extension", "count": { "$sum": 1 } }},
        { "$project": { "_id": 0, "extension": "$_id", "count": "$count" }}
    ])]
    return { x["extension"] : x["count"] for x in extensions }

def get_experiment_runs(experiment_name, include_run_params=False, sample_name=None):
    '''
    Get the runs for the given experiment.
    Does not include the run parameters by default
    '''
    expdb = logbookclient[experiment_name]
    run_params_projection = { "params": False } if not include_run_params else { "some_non_existent_field": False }
    if not sample_name or sample_name == "All Samples":
        run_docs = [run for run in expdb['runs'].find(projection=run_params_projection).sort([("num", -1)])]
    else:
        # We start at samples for performance reasons;
        run_docs =  [x for x in expdb.samples.aggregate([
            { "$match": { "name": sample_name }},
            { "$lookup": { "from": "runs", "localField": "_id", "foreignField": "sample", "as": "run"}},
            { "$unwind": "$run" }, # lookup generates an array field, we convert to a list of docs with a single field instead.
            { "$replaceRoot": { "newRoot": "$run" } },
            { "$project": run_params_projection },
            { "$sort": { "num": -1 }}
        ])]
    for run_doc in run_docs:
        if "sample" in run_doc:
            run_doc["sample"] = expdb['samples'].find_one({"_id": run_doc["sample"]})
    return run_docs

def get_experiment_run_document(experiment_name, rnum):
    '''
    Get the run document for the specified run.
    '''
    expdb = logbookclient[experiment_name]
    run_doc = expdb['runs'].find_one({"num": rnum})
    if "sample" in run_doc:
        run_doc["sample"] = expdb['samples'].find_one({"_id": run_doc["sample"]})        
    return run_doc

def get_all_run_tables(experiment_name, instrument):
    '''
    Get specifications for both the default and user defined run tables.
    The default run tables are based on these items.
    * Find all run_param_descriptions that are summaries. These have their param names separated by the "/" character into the category and param name. We create a run table definition dynamically based on category.
    * The run tables defined in the site database are added to all experiments. These are ahead of the experiment specific ones; so the default run tables are the system wide run tables.
    * Finally, the experiment specific run tables are added.
    '''
    expdb = logbookclient[experiment_name]
    sitedb = logbookclient["site"]
    allRunTables = []
    def mark_sys(x):
        x["is_system_run_table"] = True
        x["is_editable"] = False
        return x
    system_run_tables = [ mark_sys(r) for r in sitedb["run_tables"].find({"$or": [ {"instrument": instrument}, {"instrument": { "$exists": False}}]})]

    allRunTables.extend(system_run_tables)
    allRunTables.extend([x for x in expdb['run_tables'].find()])

    mimes = { "params." + x["param_name"] : x["type"] for x in sitedb['run_param_descriptions'].find({"type": { "$exists": True }})}
    mimes.update({ "params." + x["param_name"] : x["type"] for x in expdb['run_param_descriptions'].find({"type": { "$exists": True }})})

    # The run table categories change with time. This is where we patch for versions of the instrument scientist source list.
    for rt in allRunTables:
        for coldef in rt["coldefs"]:
            if coldef['type'].startswith('EPICS:'):
                coldef['type'] = coldef['type'].replace('EPICS:', 'EPICS/')
            coldef['mime_type'] = mimes.get(coldef['source'], "text")
        if "sort_index" not in rt:
            rt["sort_index"] = 100

    # Sort by run table sort_index and then by name.
    allRunTables = sorted(allRunTables, key=itemgetter('sort_index', 'name'))
    return allRunTables

def get_runtable_data(experiment_name, instrument, tableName, sampleName):
    '''
    Get the data from the run tables for the given table.
    In addition to the basic run data, we add the sources for the given run table.
    This is mostly a matter of constructing the appropriate mongo filters.
    If sampleName is specified, we restrict the returned data to runs associated with the sample. Otherwise, we return all runs.
    '''
    tableDef = next(x for x in get_all_run_tables(experiment_name, instrument) if x['name'] == tableName and not x.get("is_template", False))
    sources = { "num": 1, "begin_time": 1, "end_time": 1 }
    sources.update({ x['source'] : 1 for x in tableDef['coldefs']})
    if tableDef.get("table_type", None) == "generatedtable" or tableDef.get("table_type", None) == "generatedscatter":
        logger.debug("Getting run table data based on pattern matches '%s'", tableDef["patterns"])
        allsources = [ x["source"] for y in get_runtable_sources(experiment_name).values() for x in y ]
        ptrn = re.compile(tableDef["patterns"])
        sources.update({ x : 1 for x in allsources if ptrn.match(x.replace("params.", ""))})
    query = {}
    if sampleName:
        logger.debug("Getting run table data for sample %s", sampleName)
        sample_doc = get_sample_for_experiment_by_name(experiment_name, sampleName)
        query = { "sample": sample_doc["_id"] } if sample_doc else query
    rtdata = [x for x in logbookclient[experiment_name]['runs'].find(query, sources).sort([("num", -1)])] # Use sources as a filter to find
    for rtd in rtdata:
        if 'duration' in sources.keys() and 'end_time' in rtd and rtd['end_time'] and 'begin_time' in rtd:
            rtd['duration'] = (rtd['end_time'] - rtd['begin_time']).total_seconds()
        if 'begin_time' in rtd and rtd['begin_time']:
            rtd['begin_time_epoch'] = int(rtd['begin_time'].timestamp()*1000)
        if 'end_time' in rtd and rtd['end_time']:
            rtd['end_time_epoch'] = int(rtd['end_time'].timestamp()*1000)
    if 'sample' in sources.keys():
        samples = { x["_id"] : x for x in get_samples(experiment_name) }
        def __replace_with_sample_name(x):
            if 'sample' in x:
                x['sample'] = samples[x['sample']]['name']
            return x
        rtdata = map(__replace_with_sample_name, rtdata)
    return rtdata

def get_run_param_descriptions(experiment_name):
    '''
    Get the run param descriptions for this experiment.
    '''
    return [x for x in logbookclient[experiment_name]['run_param_descriptions'].find({}).sort([("name", 1)])]

def add_update_run_param_descriptions(experiment_name, param_descs):
    '''
    Add or update the run parameter descriptions for this experiment.
    '''
    for k, v in param_descs.items():
        logbookclient[experiment_name]['run_param_descriptions'].update_one({"param_name": k}, {"$set": {"description": v}}, upsert=True)
    return True

def get_runtable_sources(experiment_name):
    '''
    Get the sources for user defined run tables.
    This is a combination of these items; not all of these are mutually exclusive.
    --> The attributes of the run itself
    --> Any number of editable parameters defined by the user.
    --> The run_param_descriptions.
    --> The instrument leads maintain a per instrument list of EPICS variables in a JSON file external to the logbook.
    We combine all of these into a param name --> category+description
    '''
    expdb = logbookclient[experiment_name]
    sitedb = logbookclient["site"]
    instrument = expdb.info.find_one({})['instrument']
    rtbl_sources = {}
    rtbl_sources["Run Info"] = [{"label": "Begin Time", "description": "The start of the run", "source": "begin_time", "category": "Run Info"},
        {"label": "End time", "description": "The end of the run", "source": "end_time", "category": "Run Info"},
        {"label": "Number", "description": "The run number", "source": "num", "category": "Run Info"},
        {"label": "Type", "description": "The run type", "source": "type", "category": "Run Info"},
        {"label": "Sample", "description": "The sample associated with the run", "source": "sample", "category": "Run Info"},
        {"label": "Run Duration", "description": "The duration of the run", "source": "duration", "category": "Run Info"}]
    rtbl_sources["Editables"] = [ { "label": x["_id"], "description": x["_id"], "source": "editable_params."+x["_id"]+".value", "category": "Editables" } for x in expdb.runs.aggregate([
        { "$project": { "editables": { "$objectToArray": "$editable_params" } } },
        { "$unwind": "$editables" },
        { "$group": { "_id": "$editables.k", "total": { "$sum": 1 } } } ])]
    rtbl_sources["Calibrations"] = [{"label": "Calibrations/comment", "description": "Calibrations/comment", "source": "params.Calibrations/comment", "category": "Calibrations"},
        {"label": "Calibrations/dark", "description": "Calibrations/dark", "source": "params.Calibrations/dark", "category": "Calibrations"},
        {"label": "Calibrations/flat", "description": "Calibrations/flat", "source": "params.Calibrations/flat", "category": "Calibrations"},
        {"label": "Calibrations/geom", "description": "Calibrations/geom", "source": "params.Calibrations/geom", "category": "Calibrations"}]
    rtbl_sources["Misc"] = [{"label": "Separator", "description": "A column separator", "source": "Separator", "category": "Misc"}]
    # Mongo currently does not support finding the leaves of documents if they have embedded fields; so we have to loop thru all the runs and do this in python.
    def join_key(current_key, new_key):
        return current_key + "." + new_key if current_key else new_key
    def get_leaves_of_a_document(current_key, items, keyset):
        for k, v in items:
            if isinstance(v, dict):
                get_leaves_of_a_document(join_key(current_key, k), v.items(), keyset)
            else:
                keyset.add(join_key(current_key, k))
    param_names = set()
    for run in expdb.runs.find({}, {"params" : 1}):
        get_leaves_of_a_document(None, run["params"].items(), param_names)
    param_descs = { x["param_name"] : { "label" : x["param_name"], "description": x["description"] if x["description"] else x["param_name"], "category": x['param_name'].split('/')[0] if '/' in x['param_name'] else "EPICS:Additional parameters" } for x in  expdb.run_param_descriptions.find({})}
    site_param_descs = { x["param_name"] : { "label" : x["param_name"], "description": x["description"] if "description" in x else x["param_name"], "category": x['category'] if 'category' in x else "EPICS:Additional parameters" } for x in  sitedb.run_param_descriptions.find({})}
    # Update the category and description from the instrument_scientists_run_table_defintions if present
    param_names_with_categories = []
    for param_name in sorted(param_names):
        unescaped_param_name = reverse_escape_chars_for_mongo(param_name)
        if instrument in instrument_scientists_run_table_defintions and unescaped_param_name in instrument_scientists_run_table_defintions[instrument]:
            param_names_with_categories.append({
                "label" : unescaped_param_name,
                "category": "EPICS/" + instrument_scientists_run_table_defintions[instrument][unescaped_param_name]["title"],
                "description": instrument_scientists_run_table_defintions[instrument][unescaped_param_name].get("description", param_name),
                "source": "params." + param_name })
        elif 'HEADER' in instrument_scientists_run_table_defintions and unescaped_param_name in instrument_scientists_run_table_defintions['HEADER']:
            param_names_with_categories.append({
                "label" : unescaped_param_name,
                "category": "EPICS/" + instrument_scientists_run_table_defintions['HEADER'][unescaped_param_name]["title"],
                "description": instrument_scientists_run_table_defintions['HEADER'][unescaped_param_name].get("description", param_name),
                "source": "params." + param_name })
        elif unescaped_param_name in param_descs:
            param_names_with_categories.append({
                "label" : unescaped_param_name,
                "category": param_descs[unescaped_param_name]['category'],
                "description": param_descs[unescaped_param_name].get("description", param_name),
                "source": "params." + param_name })
        elif unescaped_param_name in site_param_descs:
            param_names_with_categories.append({
                "label" : unescaped_param_name,
                "category": site_param_descs[unescaped_param_name]['category'],
                "description": site_param_descs[unescaped_param_name].get("description", param_name),
                "source": "params." + param_name })
        elif re.match("DAQ (.*)/(.*)", unescaped_param_name):
            param_names_with_categories.append({
                "label" : unescaped_param_name,
                "category": "DAQ",
                "description": unescaped_param_name,
                "source": "params." + param_name })
        else:
            param_names_with_categories.append({
                "label" : param_name,
                "category": "EPICS:Additional parameters",
                "description": param_name,
                "source": "params." + param_name })

    # Got thru the param_names_with_categories and update the descriptions from the run_table param_descs
    for pnc in param_names_with_categories:
        param_name = reverse_escape_chars_for_mongo(pnc["source"]).replace("params.", "")
        if param_name in param_descs:
            pnc["description"] = param_descs[param_name].get("description", param_name)
        elif param_name in site_param_descs:
            pnc["description"] = param_descs[param_name].get("description", param_name)

    rtbl_sources.update({ x['category'] : [] for x in param_names_with_categories})
    [ rtbl_sources[x['category']].append(x) for x in param_names_with_categories ]
    return rtbl_sources


def create_update_user_run_table_def(experiment_name, instrument, table_definition):
    '''
    Create or update an existing user run table definition for an experiment
    We expect a fully formed table_definition here...
    '''
    expdb = logbookclient[experiment_name]
    createp = "_id" not in table_definition.keys()
    rtbl_name = table_definition["name"]
    rtbl_id = None if createp else ObjectId(table_definition["_id"])
    all_rtbls = {x["name"] : x for x in get_all_run_tables(experiment_name, instrument)}
    if createp and rtbl_name in all_rtbls.keys():
        return (False, f"We already have a run table definition with the same name {rtbl_name}", None)
    if not createp and not expdb["run_tables"].find_one({"_id": rtbl_id}):
        return (False, f"Cannot update a table definition that does not exist for name {rtbl_name}", None)
    if not createp:
        rtbl_with_id = expdb["run_tables"].find_one({"_id": rtbl_id})
        if rtbl_name in all_rtbls and all_rtbls[rtbl_name]["_id"] != rtbl_id:
            exn = rtbl_with_id["name"]
            return (False, f"Cannot rename table {exn} to table {rtbl_name} that already exists ", None)

    if createp:
        expdb["run_tables"].insert_one(table_definition)
    else:
        table_definition["_id"] = rtbl_id # Replace string with ObjectId
        expdb["run_tables"].replace_one({"_id": rtbl_id}, table_definition)

    return (True, "", expdb["run_tables"].find_one({"name": table_definition["name"]}))

def delete_run_table(experiment_name, table_name):
    '''
    Delete the specified run table for the experiment.
    '''
    expdb = logbookclient[experiment_name]
    expdb["run_tables"].delete_one({"name": table_name})
    return (True, "")

def delete_system_run_table(experiment_name, instrument, table_name):
    '''
    Delete the specified system run table.
    We can't really tell if a particular name is a instrument specific run table or a global one just by the name alone.
    So, we first check to see if there is a instrument specific one; if so, we delete that.
    If not, we delete the global one.
    '''
    sitedb = logbookclient["site"]
    ins_rt_del = sitedb["run_tables"].delete_one({"name": table_name, "instrument": instrument})
    if ins_rt_del.deleted_count <= 0:
        logger.debug("Could not find an instrument specific run table %s", table_name)
        sitedb["run_tables"].delete_one({"name": table_name})

    return (True, "")

def clone_run_table_definition(experiment_name, existing_run_table_name, new_run_table_name):
    """
    Clone an existing run table definition.
    """
    expdb = logbookclient[experiment_name]
    sitedb = logbookclient["site"]
    existing_run_table = expdb["run_tables"].find_one({"name": existing_run_table_name})
    if not existing_run_table:
        existing_run_table = sitedb["run_tables"].find_one({"name": existing_run_table_name})
    new_run_table = expdb["run_tables"].find_one({"name": new_run_table_name})
    system_run_table = sitedb["run_tables"].find_one({"name": new_run_table_name})
    if not existing_run_table:
        return (False, "Cannot find existing run table %s " % existing_run_table_name, None)
    if new_run_table or system_run_table:
        return (False, "Run table %s already exists" % existing_run_table_name, None)
    new_run_table = existing_run_table
    del new_run_table["_id"]
    new_run_table["name"] = new_run_table_name
    expdb["run_tables"].insert_one(new_run_table)
    return (True, "", expdb["run_tables"].find_one({"name": new_run_table_name}))

def replace_system_run_table_definition(experiment_name, existing_run_table_name, system_run_table_name, instrument=None, is_template=False):
    """
    Replace a system run table (defined in the site database) with a run table from this experiment.
    This is a means to edit system run tables using the info available from this experiment.
    """
    expdb = logbookclient[experiment_name]
    sitedb = logbookclient["site"]
    existing_run_table = expdb["run_tables"].find_one({"name": existing_run_table_name})
    if not existing_run_table:
        return (False, "Cannot find existing run table %s " % existing_run_table_name, None)
    new_run_table = existing_run_table
    del new_run_table["_id"]
    new_run_table["name"] = system_run_table_name
    if is_template:
        new_run_table["is_template"] = True
    if instrument:
        new_run_table["instrument"] = instrument
        sitedb["run_tables"].replace_one({"name": system_run_table_name, "instrument": instrument}, new_run_table, upsert=True)
    else:
        sitedb["run_tables"].replace_one({"name": system_run_table_name}, new_run_table, upsert=True)

    expdb["run_tables"].delete_one({"name": existing_run_table_name})
    return (True, "", sitedb["run_tables"].find_one({"name": system_run_table_name}))


def clone_system_template_run_tables_into_experiment(experiment_name, instrument):
    """
    Clone all system run tables that are marked as being a template into the specified experiment.
    Note, we do not replace any existing run table with the same name.
    """
    expdb = logbookclient[experiment_name]
    sitedb = logbookclient["site"]
    template_run_tables = [ r for r in sitedb["run_tables"].find({"$and": [ {"$or": [ {"instrument": instrument}, {"instrument": { "$exists": False}}]}, {"is_template": True} ]})]
    existing_run_tables = [ x["name"] for x in expdb["run_tables"].find() ]
    for tr in template_run_tables:
        if tr["name"] in existing_run_tables:
            logger.debug("Skipping existing run table %s", tr["name"])
            continue
        logger.debug("Cloning template run table %s", tr["name"])
        del tr["is_template"]
        del tr["_id"]
        if "instrument" in tr.keys():
            del tr["instrument"]
        expdb["run_tables"].insert_one(tr)
    return (True, "", list(sitedb["run_tables"].find()))

def update_editable_param_for_run(experiment_name, runnum, source, value, userid):
    '''
    Update the specified editable parameter for the specified run for the experiment.
    :param experiment_name:
    :param runnum:
    :param source: Typically editable_params.Run Title or something like that.
    :param value:
    :param userid:
    '''
    expdb = logbookclient[experiment_name]
    if not source.startswith('editable_params.') and not source.startswith('params.Calibrations/'):
        raise Exception("Cannot update anything else other than an editable param")
    if source.startswith('editable_params.'):
        return expdb["runs"].find_one_and_update(
            {"num": runnum},
            {"$set": { source: {
                        "value": value,
                        "modified_by": userid,
                        "modified_time": datetime.datetime.utcnow()
                        }}})
    if source.startswith('params.Calibrations/'):
        return expdb["runs"].find_one_and_update(
            {"num": runnum},
            {"$set": { source: value }})
    raise Exception("Update editable param called for unknown param type " + source)

def get_experiment_shifts(experiment_name):
    """
    Get the shifts for an experiment.
    """
    expdb = logbookclient[experiment_name]
    shifts = list(expdb.shifts.find({}).sort([("begin_time", -1)]))

    previous_end_time = datetime.datetime.now() + datetime.timedelta(days=10*365)
    for shift in shifts:
        if 'end_time' in shift and shift['end_time']:
            shift['logical_end_time'] = shift['end_time']
        else:
            shift['logical_end_time'] = previous_end_time
        previous_end_time = shift['begin_time']

    return shifts

def get_specific_shift(experiment_name, id):
    """
    Get the specified shift entry for the experiment.
    For now, we have id based lookups.
    """
    expdb = logbookclient[experiment_name]
    return expdb['shifts'].find_one({"_id": ObjectId(id)})

def get_shift_for_experiment_by_name(experiment_name, shift_name):
    """
    Get the specified shift specified by shift_name for the experiment.
    """
    expdb = logbookclient[experiment_name]
    return expdb['shifts'].find_one({"name": shift_name})

def get_latest_shift(experiment_name):
    """
    Get's the latest shift as detemined by the shift begin time.
    """
    expdb = logbookclient[experiment_name]
    shifts = list(expdb.shifts.find({ "begin_time" : { "$lte": datetime.datetime.utcnow() }, "end_time": None }).sort([("begin_time", -1)]).limit(1))
    if shifts:
        return shifts[0]
    return None


def close_shift_for_experiment(experiment_name, shift_name):
    """
    Close the shift specified by shift_name for the experiment.
    For now, this mostly means setting the end time to the current time.
    """
    expdb = logbookclient[experiment_name]
    shift_doc = expdb['shifts'].find_one({"name": shift_name})
    if not shift_doc:
        return (False, "Cannot find the shift specified by shift name " % shift_name)
    expdb['shifts'].find_one_and_update({"name": shift_name}, {"$set": { "end_time" : datetime.datetime.utcnow()}})
    return (True, "")

def create_update_shift(experiment_name, shift_name, createp, info):
    """
    Create or update the shift for the specified experiment.
    """
    expdb = logbookclient[experiment_name]
    shift_doc = expdb['shifts'].find_one({"name": shift_name})
    if shift_doc and createp:
        return (False, "Shift %s already exists" % shift_name)
    if not shift_doc and not createp:
        return (False, "Shift %s does not exist" % shift_name)
    info['begin_time'] = datetime.datetime.strptime(info["begin_time"], '%Y-%m-%dT%H:%M:%S.%fZ')

    if createp:
        expdb['shifts'].insert_one(info)
    else:
        expdb['shifts'].find_one_and_update({"name": shift_name}, {"$set": info})

    return (True, "")

def get_samples(experiment_name):
    """
    Get the defined samples for the experiment
    The current sample (if any) is stored in the current collection.
    """
    expdb = logbookclient[experiment_name]
    samples = list(expdb.samples.find({}).sort([("_id", -1)]))
    current_sample = expdb.current.find_one({"_id": "sample"})
    if current_sample:
        current_sample_id = current_sample["sample"]
        def set_current(x):
            if x["_id"] == current_sample_id:
                x["current"] = True
            return x
        samples = list(map(set_current, samples))
    return samples

def get_current_sample_name(experiment_name):
    """
    Get the current sample name for the specified experiment.
    This can return None.
    """
    expdb = logbookclient[experiment_name]
    current_sample = expdb.current.find_one({"_id": "sample"})
    return expdb.samples.find_one({"_id": current_sample['sample']})['name'] if current_sample and 'sample' in current_sample else None

def get_sample_for_experiment_by_name(experiment_name, sample_name):
    """
    Get sample for experiment by name
    """
    expdb = logbookclient[experiment_name]
    requested_sample = expdb.samples.find_one({"name": sample_name})
    current_sample = expdb.current.find_one({"_id": "sample"})
    if current_sample and requested_sample and current_sample["sample"] == requested_sample["_id"]:
        requested_sample["current"] = True
    return requested_sample

def create_sample(experiment_name, sampledetails, automatically_create_associated_run=False):
    """
    Create a new sample for an experiment.
    """
    expdb = logbookclient[experiment_name]
    if "name" not in sampledetails or "description" not in sampledetails:
        return (False, "Please specify a sample name and description")
    sample_name = sampledetails["name"]
    if expdb['samples'].find_one({"name": sample_name}):
        return (False, "Sample %s already exists" % sample_name)
    validation, erromsg = validate_with_modal_params("samples", sampledetails)
    if not validation:
        return validation, erromsg

    expdb['samples'].insert_one(sampledetails)
    if automatically_create_associated_run:
        current_run = get_current_run(experiment_name)
        if current_run and not is_run_closed(experiment_name, current_run["num"]):
            return False, ("Cannot switch to and create a run if the current run %s is still open %s" % (current_run["num"], experiment_name))
        make_sample_current(experiment_name, sample_name)
        start_run(experiment_name, "DATA")
        end_run(experiment_name)
    return (True, "")

def update_sample(experiment_name, sampleid, sampledetails):
    """
    Update an existing sample for an experiment.
    """
    expdb = logbookclient[experiment_name]
    sampledetails["_id"] = ObjectId(sampleid)
    existing_sample = expdb['samples'].find_one({"_id": sampledetails["_id"]})
    if not existing_sample:
        return (False, "Sample %s does not exist" % sampledetails["_id"])
    if "name" not in sampledetails or "description" not in sampledetails:
        return (False, "Please specify a sample name and description")    
    sample_with_name = expdb['samples'].find_one({"name": sampledetails["name"]})
    if sample_with_name and existing_sample["_id"] != sample_with_name["_id"]:
        return (False, "Cannot rename sample %s to one that already exists %s" % (existing_sample["_id"], sample_with_name["_id"]))

    validation, erromsg = validate_with_modal_params("samples", sampledetails)
    if not validation:
        return validation, erromsg

    expdb['samples'].replace_one({"_id": existing_sample["_id"]}, sampledetails)
    return (True, "")

def clone_sample(experiment_name, existing_sample_name, new_sample_name):
    """
    Clone an existing sample.
    """
    expdb = logbookclient[experiment_name]
    if not expdb['samples'].find_one({"name": existing_sample_name}):
        return (False, "Sample %s does not exist" % existing_sample_name)
    if expdb['samples'].find_one({"name": new_sample_name}):
        return (False, "Sample %s already exists" % new_sample_name)

    existing_sample_doc = expdb['samples'].find_one({"name": existing_sample_name})
    del existing_sample_doc["_id"]
    existing_sample_doc["name"] = new_sample_name
    expdb['samples'].insert_one(existing_sample_doc)

    return (True, "")

def make_sample_current(experiment_name, sample_name):
    """
    Make the sample specified by the sample_name as the current sample.
    """
    expdb = logbookclient[experiment_name]
    sample_doc = expdb['samples'].find_one({"name": sample_name})
    if not sample_doc:
        return (False, "Sample %s does not exist" % sample_name)
    validation, erromsg = validate_with_modal_params("samples", sample_doc)
    if not validation:
        return validation, erromsg

    expdb.current.find_one_and_update({"_id": "sample"}, {"$set": { "_id": "sample", "sample" : sample_doc["_id"] }} , upsert=True)
    return (True, "")

def stop_current_sample(experiment_name, sample_name):
    """
    Stop the sample specified by the sample_name if it is the current sample and set the current sample to null
    """
    expdb = logbookclient[experiment_name]
    sample_doc = expdb['samples'].find_one({"name": sample_name})
    if not sample_doc:
        return (False, "Sample %s does not exist" % sample_name)

    current_sample = get_current_sample_name(experiment_name)
    if current_sample and current_sample != sample_name:
        return (False, "Sample %s is not the current sample" % sample_name)

    expdb.current.delete_one({"_id": "sample"})
    return (True, "")

def delete_sample_for_experiment(experiment_name, sample_name):
    """ Delete the sample for an experiment. We only allow deletion of samples if there are no runs associated with the sample and it is not current"""
    expdb = logbookclient[experiment_name]
    requested_sample = expdb.samples.find_one({"name": sample_name})
    current_sample = expdb.current.find_one({"_id": "sample"})
    if not requested_sample:
        return False, "Cannot find sample %s" % sample_name, None
    if current_sample and requested_sample and current_sample["sample"] == requested_sample["_id"]:
        return False, "Cannot delete sample %s as it is the current sample in the experiment" % sample_name, None
    runs = get_experiment_runs(experiment_name, include_run_params=False, sample_name=sample_name)
    if runs and len(runs) > 0:
        return False, "Cannot delete sample %s as it has %d runs associated with it" % (sample_name, len(runs)), None
    logger.debug("Actually deleting sample")
    expdb["samples"].delete_one({"name": sample_name})
    return True, "", None

def get_modal_param_definitions(modal_type):
    """
    Get the site specific modal param definitions for the specified modal type.
    """
    sitedb = logbookclient["site"]
    modal_params_file = "static/json/{}/modals/{}.json".format(LOGBOOK_SITE, modal_type)
    logger.info("Looking for modal definition in %s", modal_params_file)
    param_defs = {}
    if os.path.exists(modal_params_file):
        with open(modal_params_file, "r") as f:
            param_defs = json.load(f)
        return param_defs

    common_modal_params_file = "static/json/common/modals/{}.json".format(modal_type)
    if os.path.exists(common_modal_params_file):
        with open(common_modal_params_file, "r") as f:
            param_defs = json.load(f)
        return param_defs

    return param_defs

def validate_with_modal_params(modal_type, business_obj):
    """
    Validate a business object against any modal param definitions for this site.
    Returns a boolean/errormsg tuple.
    """
    modal_defs = get_modal_param_definitions(modal_type)
    if not modal_defs:
        return True, ""
    def __get_nested_attr__(theobj, attrname):
        nameparts = attrname.split(".")
        for namepart in nameparts[:-1]:
            theobj = theobj.get(namepart, {})
        return theobj.get(nameparts[-1], None)

    for required_param in [ x["param_name"] for x in modal_defs["params"] if x.get("required", False) ]:
        if not __get_nested_attr__(business_obj, required_param):
            logger.error("Missing %s in %s", required_param, business_obj)
            return False, "One of the required parameters {} was not specified".format(required_param)
    for num_param in [ x["param_name"] for x in modal_defs["params"] if x.get("param_type", "string") in ["int", "float"] ]:
        thenumval = __get_nested_attr__(business_obj, num_param)
        if not isinstance(thenumval, int) and not isinstance(thenumval, float):
            logger.error("params.%s is not an int/float in %s", num_param, business_obj)
            return False, "The parameter {} is not an number".format(num_param)
    return True, ""

def change_sample_for_run(experiment_name, run_num, sample_name):
    """
    Change the sample for the specified run.
    The association between sample and run is expected to be lightweight and purely logical.
    So, changing the sample for a run is merely changing the attribute in the run document.
    """
    sample_doc = get_sample_for_experiment_by_name(experiment_name, sample_name)
    if not sample_doc:
        return False, "Cannot find sample with name " + sample_name
    expdb = logbookclient[experiment_name]
    expdb["runs"].update_one({"num": run_num}, {"$set": {"sample": sample_doc["_id"]}})
    return True, ""

def register_file_for_experiment(experiment_name, info):
    """
    Register a file for the experiment.
    """
    expdb = logbookclient[experiment_name]
    if expdb['file_catalog'].find_one({"path": info["path"], "run_num": info["run_num"]}):
        expdb['file_catalog'].replace_one({"path": info["path"], "run_num": info["run_num"]}, info)
    else:
        expdb['file_catalog'].insert_one(info)
    return (True, expdb['file_catalog'].find_one({"path": info["path"], "run_num": info["run_num"]}))

def file_available_at_location(experiment_name, run_num, file_path, location):
    """
    Mark a file as being available at the specified location.
    """
    expdb = logbookclient[experiment_name]
    expdb['file_catalog'].update_one({"run_num": run_num, "path": file_path}, {"$set": {"locations."+location+".asof": datetime.datetime.utcnow()}})
    return expdb['file_catalog'].find_one({"run_num": run_num, "path": file_path})

def file_not_available_at_location(experiment_name, run_num, file_path, location):
    expdb = logbookclient[experiment_name]
    expdb['file_catalog'].update_one({"run_num": run_num, "path": file_path}, {"$unset": {"locations."+location: 1}})
    return expdb['file_catalog'].find_one({"run_num": run_num, "path": file_path})

def get_collaborators(experiment_name):
    """
    Get the list of collaborators and their permissions for the experiment.
    This is basically the roles collection for this experiment reorganized to serve the UI.
    """
    expdb = logbookclient[experiment_name]
    roles = [x for x in expdb["roles"].find()]
    all_players = set() # First, generate a set of all the players in the experiment.
    list(map(lambda x : all_players.update(x.get('players', [])), roles))
    players2roles = { x : [] for x in all_players }
    for role in roles:
        for player in role.get('players', []):
            players2roles[player].append("{0}/{1}".format(role['app'], role['name']))
    ret = []
    for player in players2roles.keys():
        is_group = False if player.startswith("uid:") else True
        user_details = usergroups.get_userids_matching_pattern(player.replace("uid:", "")) if not is_group else None
        ret.append({
            "uid": player,
            "is_group": is_group,
            "full_name": user_details[0].get('gecos', "N/A") if user_details else "N/A",
            "uidNumber": user_details[0].get('uidNumber', "N/A") if user_details else "N/A",
            "roles": players2roles[player]
        })
    return sorted(ret, key=lambda x: x["uid"].replace("uid:", ""))

def get_role_object(experiment_name, role_fq_name):
    expdb = logbookclient[experiment_name]
    application_name, role_name = role_fq_name.split("/")
    roleobj = expdb["roles"].find_one({"app": application_name, "name": role_name})
    return roleobj

def add_collaborator_to_role(experiment_name, uid, role_fq_name):
    expdb = logbookclient[experiment_name]
    application_name, role_name = role_fq_name.split("/")
    roleobj = expdb["roles"].find_one({"app": application_name, "name": role_name})
    if not roleobj:
        expdb["roles"].insert_one({"app": application_name, "name": role_name, "players": [ uid ]})
        return True
    if "players" not in roleobj:
        result = expdb["roles"].update_one({"app": application_name, "name": role_name}, { "$set": { "players": [ uid ] }})
    elif uid not in roleobj["players"]:
        result = expdb["roles"].update_one({"app": application_name, "name": role_name}, {"$addToSet": { "players": uid }})
    else:
        return False
    return result.matched_count > 0

def remove_collaborator_from_role(experiment_name, uid, role_fq_name):
    expdb = logbookclient[experiment_name]
    application_name, role_name = role_fq_name.split("/")
    roleobj = expdb["roles"].find_one({"app": application_name, "name": role_name})
    if not roleobj or "players" not in roleobj or uid not in roleobj["players"]:
        return False
    result = expdb["roles"].update_one({"app": application_name, "name": role_name}, { "$pull": { "players": uid }})
    return result.matched_count > 0

def get_collaborators_list_for_experiment(experiment_name):
    """
    Get all the collaborators for an experiment.
    This computes the collaborators list from the roles.players from this experiment alone.
    roles.players inherited from the instrument/site database are NOT returned here.
    Only the roles.players that being with uid: are returned (actual users, not groups).
    """
    expdb = logbookclient[experiment_name]
    roleobjs = [ x for x in expdb["roles"].find({}) ]
    ret = set()
    for roleobj in roleobjs:
        ret.update([x for x in roleobj.get("players", []) if x.startswith("uid:")])
    # Remove the operator account if present
    instrument = get_experiment_info(experiment_name)["instrument"]
    operator_uid = { x["_id"] : x for x in get_instruments()}[instrument].get("params", {}).get("operator_uid", None)
    if operator_uid and operator_uid in ret:
        ret.remove(operator_uid)
    return ret

def get_poc_feedback_changes(experiment_name):
    """
    Gets a list of POC feedback items sorted by ascending modified date.
    To reconstruct the document, simply apply the changes to a dict in sequence.
    """
    expdb = logbookclient.get_database(experiment_name, read_preference=ReadPreference.SECONDARY_PREFERRED)
    return list(expdb["poc_feedback"].find({}).sort([("modified_at", 1)]))

def get_poc_feedback_document(experiment_name):
    """
    Reconstructs the current feedback document from a questionnaire like history of changes.
    """
    poc_feedback_changes = get_poc_feedback_changes(experiment_name)
    poc_feedback_doc = {}
    exp_info = get_experiment_info(experiment_name)
    poc_feedback_doc["basic-scheduled"] = math.ceil((exp_info["end_time"] - exp_info["start_time"]).total_seconds()/(8*3600))

    if poc_feedback_changes:
        poc_feedback_doc.update({ x['name'] : x['value'] for x in get_poc_feedback_changes(experiment_name) })
        poc_feedback_doc['last_modified_by'] = poc_feedback_changes[-1]['modified_by']
        poc_feedback_doc['last_modified_at'] = poc_feedback_changes[-1]['modified_at']
    return poc_feedback_doc

def add_poc_feedback_item(experiment_name, item_name, item_value, modified_by):
    expdb = logbookclient[experiment_name]
    expdb["poc_feedback"].insert_one({"name": item_name, "value": item_value, "modified_by": modified_by, "modified_at": datetime.datetime.utcnow()})

def get_poc_feedback_experiments():
    cachedb = logbookclient["explgbk_cache"]
    return list(cachedb["experiments"].find({"poc_feedback.num_items": {"$gte": 1}}, {"_id": 0, "name": 1, "poc_feedback": 1, "instrument": 1, "params.PNR": 1, "last_run": 1 }))


def get_workflow_definitions(experiment_name):
    expdb = logbookclient[experiment_name]
    return list(expdb["workflow_definitions"].find({}).sort([("name", 1)]))

def get_dm_locations(experiment_name):
    sitedb = logbookclient["site"]
    expdb = logbookclient[experiment_name]
    siteinfo = sitedb["site_config"].find_one()
    ret = {}
    if siteinfo and 'dm_locations' in siteinfo and siteinfo['dm_locations']:
        ret.update({x["name"]: x for x in siteinfo['dm_locations'] if x.get("all_experiments", False)})
        exp_specific_dm_locations = expdb["info"].find_one().get("params", {}).get("dm_locations", "").split()
        for exp_specific_dm_location in exp_specific_dm_locations:
            if exp_specific_dm_location in [x["name"] for x in siteinfo['dm_locations']]:
                ret[exp_specific_dm_location] = [x for x in siteinfo['dm_locations'] if x["name"] == exp_specific_dm_location][0]

    return list(ret.values())

def get_site_config():
    sitedb = logbookclient["site"]
    siteinfo = sitedb["site_config"].find_one()
    return siteinfo

def get_workflow_triggers(experiment_name):
    return [{"value": "MANUAL", "label": "Manually triggered"}, {"value": "START_OF_RUN", "label": "Start of a run"}, {"value": "END_OF_RUN", "label": "End of a run"}, {"value": "FIRST_FILE_TRANSFERRED", "label": "First file transfer"}, {"value": "ALL_FILES_TRANSFERRED", "label": "All files transferred"}, {"value": "ALL_NONREC_FILES_TRANSFERRED", "label": "All non-recorder files transferred"}, {"value": "RUN_PARAM_IS_VALUE", "label": "Run table param has value"}]

def create_update_wf_definition(experiment_name, wf_obj):
    expdb = logbookclient[experiment_name]
    if "_id" in wf_obj:
        logger.debug("Updating workflow definition %s", wf_obj["_id"])
        cur_wf_obj = expdb["workflow_definitions"].find_one({"_id": ObjectId(wf_obj["_id"])})
        if not cur_wf_obj:
            return False, "Cannot find workflow definition with id %s " % wf_obj["_id"], None
        wf_obj["_id"] = cur_wf_obj["_id"]
        expdb["workflow_definitions"].replace_one({"_id": ObjectId(wf_obj["_id"])}, wf_obj)
        return True, "", expdb["workflow_definitions"].find_one({"_id": ObjectId(wf_obj["_id"])})
    else:
        wf_id = expdb["workflow_definitions"].insert_one(wf_obj).inserted_id
        return True, "", expdb["workflow_definitions"].find_one({"_id": wf_id})

def delete_wf_definition(experiment_name, wf_obj_id):
    expdb = logbookclient[experiment_name]
    cur_wf_obj = expdb["workflow_definitions"].find_one({"_id": ObjectId(wf_obj_id)})
    if not cur_wf_obj:
        return False, "Cannot find workflow object with id %s " % wf_obj_id, None
    wfjobs = expdb["workflow_jobs"].count_documents({"def_id": cur_wf_obj["_id"]})
    if wfjobs > 0:
        return False, "Cannot delete workflow definition as we have %s jobs using this definition." % wfjobs, None
    expdb["workflow_definitions"].delete_one({"_id": cur_wf_obj["_id"]})
    return True, "", None

def get_workflow_jobs(experiment_name):
    expdb = logbookclient[experiment_name]
    return [x for x in expdb["workflow_jobs"].aggregate([
        { "$lookup": { "from": "workflow_definitions", "localField": "def_id", "foreignField": "_id", "as": "def"}},
        { "$unwind": "$def" },
        { "$addFields": { "experiment": experiment_name }},
        { "$sort": { "run_num": -1, "name": 1}}
    ])]

def get_workflow_job_doc(experiment_name, job_id):
    expdb = logbookclient[experiment_name]
    wf_doc = expdb["workflow_jobs"].find_one({"_id": ObjectId(job_id)})
    if wf_doc and 'def_id' in wf_doc:
        wf_doc["experiment"] = experiment_name
        wf_doc["def"] = expdb["workflow_definitions"].find_one({"_id": wf_doc["def_id"]})
    return wf_doc

def create_wf_job(experiment_name, wf_job_doc):
    expdb = logbookclient[experiment_name]
    wf_id = expdb["workflow_jobs"].insert_one(wf_job_doc).inserted_id
    return True, "", get_workflow_job_doc(experiment_name, wf_id)

def delete_wf_job(experiment_name, job_id):
    expdb = logbookclient[experiment_name]
    wf_doc = expdb["workflow_jobs"].find_one({"_id": ObjectId(job_id)})
    if not wf_doc:
        return False, "Cannot find workflow job", None
    expdb["workflow_jobs"].delete_one({"_id": ObjectId(job_id)})
    return True, "", wf_doc

def update_wf_job(experiment_name, job_id, wf_updates):
    expdb = logbookclient[experiment_name]
    wf_doc = expdb["workflow_jobs"].find_one({"_id": ObjectId(job_id)})
    if not wf_doc:
        return False, "Cannot find workflow job", None
    expdb["workflow_jobs"].update_one({"_id": ObjectId(job_id)}, {"$set": wf_updates })
    return True, "", get_workflow_job_doc(experiment_name, job_id)

def get_URAWI_details(experiment_name, proposal_id=None):
    """
    Get details for the experiment from URAWI.
    """
    if URAWI_URL and experiment_name:
        URAWI_proposal_id = proposal_id
        try:
            # Check to see if we have an info object with a PNR
            expdb = logbookclient[experiment_name]
            expinfo = expdb['info'].find_one()
            if expinfo:
                URAWI_proposal_id = expinfo.get("params", {}).get("PNR", None)
            if not URAWI_proposal_id:
                # For LCLS and TestFac, we compose the experiment name by prefixing the instrument and appending the run period.
                if LOGBOOK_SITE in ["LCLS", "TestFac"]:
                    URAWI_proposal_id = experiment_name[3:-2].upper()
                else:
                    URAWI_proposal_id = experiment_name
            logger.info("Getting URAWI data for proposal %s using %s", URAWI_proposal_id, URAWI_URL)
            params={ "proposalNo" : URAWI_proposal_id }
            additionalAuthToken = os.environ.get("PSDM_AUTHTOKEN", None)
            if additionalAuthToken:
                prts = additionalAuthToken.split("=")
                params[prts[0]] = prts[1]
            urawi_doc = requests.get(URAWI_URL, params, verify=False).json()
            if LOGBOOK_SITE in ["LCLS", "TestFac"]:
                if urawi_doc.get("instrument") == "CRIXS":
                    logger.debug("Mapping one off instrument for LCLS/UED for proposal %s", URAWI_proposal_id)
                    urawi_doc["instrument"] = "RIX"
            return urawi_doc
        except Exception as e:
            logger.exception("Exception fetching data from URAWI using URL %s for %s", URAWI_URL, URAWI_proposal_id)
            return None
    return None

def import_users_from_URAWI(experiment_name, role_fq_name="LogBook/Writer"):
    """
    Get users from URAWI and add them as collaborators into this experiment.
    """
    existing_collaborators = get_collaborators_list_for_experiment(experiment_name)
    logger.debug(existing_collaborators)
    urawi_doc = get_URAWI_details(experiment_name)
    if urawi_doc and urawi_doc.get("status", "error") == "success":
        for coll in urawi_doc.get("collaborators", []):
            for acc in coll.get("account", []):
                if "unixGroup" not in acc or acc.get("unixGroup", "") == "xs":
                    logger.debug("Skipping adding probable experiment related account %s", acc)
                    continue
                accuid = "uid:" + acc["unixName"]
                if accuid in existing_collaborators:
                    logger.debug("Collaborator %s is already in the system", accuid)
                    continue
                add_collaborator_to_role(experiment_name, accuid, role_fq_name)
                logger.debug("Done adding collaborator %s to experiment %s", accuid, experiment_name)

def get_projects(user):
    """
    Get the projects for a user.
    """
    return [ x for x in logbookclient[PROJECTS_DB]["projects"].find({"players": "uid:" + user}).sort([("name", 1)]) ]

def get_project_info(prjid):
    """
    Get the project info
    """
    return logbookclient[PROJECTS_DB]["projects"].find_one({"_id": ObjectId(prjid)})

def create_project(prjinfo):
    """
    Create a new project
    """
    if "_id" in prjinfo:
        raise Exception("_id present in project info. Did you mean to edit the project?")
    prjid = logbookclient[PROJECTS_DB]["projects"].insert_one(prjinfo).inserted_id
    return logbookclient[PROJECTS_DB]["projects"].find_one({"_id": ObjectId(prjid)})

def update_project(prjid, prjinfo):
    """
    Update an existing project
    """
    if "_id" in prjinfo:
        del prjinfo["_id"]
    curr = logbookclient[PROJECTS_DB]["projects"].find_one({"_id": ObjectId(prjid)})
    if not curr:
        raise Exception("Cannot find project with _id " + prjid)
    logbookclient[PROJECTS_DB]["projects"].update_one({"_id": ObjectId(prjid)}, {"$set": prjinfo})
    return logbookclient[PROJECTS_DB]["projects"].find_one({"_id": ObjectId(prjid)})

    get_project_samples, add_session_to_project, add_sample_to_project, update_project_sample, \

def get_project_grids(prjid):
    """
    Get the project grids
    """
    return list(logbookclient[PROJECTS_DB]["grids"].find({"prjid": ObjectId(prjid)}).sort([("box", 1), ("number", 1)]))

def get_project_grid(prjid, gridid):
    """
    Get the specified gridid in the project.
    """
    return logbookclient[PROJECTS_DB]["grids"].find_one({"_id": ObjectId(gridid), "prjid": ObjectId(prjid)})

def add_grid_to_project(prjid, griddetails):
    """
    Add a grid to the project
    """
    griddetails["prjid"] = ObjectId(prjid)
    if "_id" in griddetails:
        del griddetails["_id"]
    validation, erromsg = validate_with_modal_params("sampprepgrid", griddetails)
    if not validation:
        return validation, erromsg

    grid_with_number = logbookclient[PROJECTS_DB]["grids"].find_one({"prjid": ObjectId(prjid), "number": griddetails["number"]})
    if grid_with_number:
        return (False, "A grid with the same grid number %s already exists in the project" % (griddetails["number"]))

    remapped_grid = logbookclient[PROJECTS_DB]["grids"].find_one({"prjid": ObjectId(prjid), "box": griddetails["box"], "boxposition": griddetails["boxposition"]})
    if remapped_grid:
        return (False, "The grid box position %s in grid box %s is already mapped to grid number %s" % (griddetails["boxposition"], griddetails["box"], remapped_grid["number"]))

    logbookclient[PROJECTS_DB]["grids"].insert_one(griddetails)
    return True, ""

def update_project_grid(prjid, gridid, griddetails):
    """
    Update a grid in the project
    """
    griddetails["_id"] = ObjectId(gridid)
    griddetails["prjid"] = ObjectId(prjid)
    validation, erromsg = validate_with_modal_params("sampprepgrid", griddetails)
    if not validation:
        return validation, erromsg

    existing_grid = logbookclient[PROJECTS_DB]["grids"].find_one({"_id": ObjectId(gridid)})

    grid_with_number = logbookclient[PROJECTS_DB]["grids"].find_one({"prjid": ObjectId(prjid), "number": griddetails["number"]})
    if grid_with_number and existing_grid["_id"] != grid_with_number["_id"]:
        return (False, "Cannot rename grid %s to one that already exists %s" % (existing_grid["_id"], grid_with_number["_id"]))
    
    remapped_grid = logbookclient[PROJECTS_DB]["grids"].find_one({"prjid": ObjectId(prjid), "box": griddetails["box"], "boxposition": griddetails["boxposition"]})
    if remapped_grid and existing_grid["_id"] != remapped_grid["_id"]:
        return (False, "The grid box position %s in grid box %s is mapped to different grid number %s" % (griddetails["boxposition"], griddetails["box"], remapped_grid["number"]))
    
    logbookclient[PROJECTS_DB]["grids"].replace_one({"_id": griddetails["_id"]}, griddetails, upsert=True)
    return True, ""

def link_grid_to_experiment(prjid, gridid, experiment_name):
    """
    Link an existing experiment with a grid
    """
    currently_mapped = logbookclient[PROJECTS_DB]["grids"].find_one({"exp_name": experiment_name})
    if currently_mapped:
        return (False, "The experiment %s is already mapped to a grid in an existing project %s" % (experiment_name, currently_mapped["prjid"]))
    logbookclient[PROJECTS_DB]["grids"].update_one({"_id": ObjectId(gridid), "prjid": ObjectId(prjid)}, {"$set": {"exp_name": experiment_name}})
    return True, ""

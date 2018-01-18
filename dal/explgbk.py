'''
The model level business logic goes here.
Most of the code here gets a connection to the database, executes a query and formats the results.
'''

import json
import datetime
import logging

import requests

from pymongo import ASCENDING, DESCENDING
from bson import ObjectId

from context import logbookclient, imagestoreurl


__author__ = 'mshankar@slac.stanford.edu'

logger = logging.getLogger(__name__)

__cached_experiments_list = []
__cached_experiments_list_fetched_time = datetime.datetime.fromtimestamp(0)


def init_app(app):
    """
    Perform startup initialization
    This is a good opportunity to preload caches etc.
    """
    get_experiments() # Cache experiments from the database


def get_experiments():
    """
    Get a list of experiments from the database.
    Returns basic information and also some info on the first and last runs.
    """
    global __cached_experiments_list
    global __cached_experiments_list_fetched_time
    nw = datetime.datetime.now()
    if (nw - __cached_experiments_list_fetched_time).total_seconds() < 30*60:
        return __cached_experiments_list

    logger.info("Reloading experiments from database.")
    experiments = []
    for database in logbookclient.database_names():
        expdb = logbookclient[database]
        collnames = expdb.collection_names()
        if 'info' in collnames:
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
            experiments.append(expinfo)
        else:
            logger.debug("Skipping non-experiment database " + database)

    __cached_experiments_list = experiments
    __cached_experiments_list_fetched_time = nw

    return experiments

def get_instruments():
    """
    Get the list of instruments from the site database.
    """
    sitedb = logbookclient["site"]
    return [x for x in sitedb["instruments"].find()]


def get_experiment_info(experiment_name):
    """
    Get the basic information for the experiment.
    :param experiment_name - for example - diadaq13
    :return: The info JSON document.
    """
    expdb = logbookclient[experiment_name]
    info = expdb['info'].find_one()
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
    setup_document["modified_at"] = datetime.datetime.now()
    latest_setup_id = expdb['setup'].insert_one(setup_document).inserted_id
    expdb['info'].find_one_and_update({}, {'$set': {'latest_setup': latest_setup_id}})


def register_new_experiment(experiment_name, incoming_info):
    """
    Registers a new experiment.
    In mongo, this mostly means creating the info object, the run number counter and various indices.
    """
    if experiment_name in logbookclient.database_names():
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
    expdb["counters"].insert_one({'_id': "next_runnum", 'seq': 1})

    # Now create the various indices
    expdb["runs"].create_index( [("num", DESCENDING)], unique=True)
    expdb["elog"].create_index( [("root", ASCENDING)])
    expdb["elog"].create_index( [("parent", ASCENDING)])
    expdb["elog"].create_index( [("content", "text" )]);
    expdb["roles"].create_index( [("app", ASCENDING), ("name", ASCENDING)], unique=True)
    expdb["run_param_descriptions"].create_index( [("param_name", DESCENDING)], unique=True)
    expdb["setup"].create_index( [("modified_by", ASCENDING), ("modified_at", ASCENDING)], unique=True)
    expdb["shifts"].create_index( [("begin_time", ASCENDING)], unique=True)
    expdb["files"].create_index( [("file_path", ASCENDING), ("run_num", DESCENDING)], unique=True)


    global __cached_experiments_list_fetched_time
    __cached_experiments_list_fetched_time = datetime.datetime.fromtimestamp(0)

    return (True, "")


def get_currently_active_experiments():
    """
    Get the currently active experiments at each instrment/station.
    """
    active_queries = []
    for instr in get_instruments():
        name = instr["_id"]
        params = instr.get("params", {})
        num_stations = int(params.get("num_stations", 0))
        if num_stations:
            # Skip those that have a num_stations of 0.
            for station in range(num_stations):
                active_queries.append({ "instrument": name, "station": station })

    sitedb = logbookclient["site"]
    ret = []
    for qry in active_queries:
        logger.info("Looking for active experiment for %s", qry)
        for exp in sitedb["experiment_switch"].find(qry).sort([( "switch_time", -1 )]).limit(1):
            exp_info = get_experiment_info(exp["experiment_name"])
            exp_info["station"] = qry["station"]
            exp_info["switch_time"] = exp["switch_time"]
            exp_info["requestor_uid"] = exp["requestor_uid"]
            ret.append(exp_info)

    return ret

def switch_experiment(instrument, station, experiment_name, userid):
    """
    Switch the currently active experiment on the instrument.
    This mostly consists inserting an entry into the experiment_switch database
    """
    sitedb = logbookclient["site"]
    sitedb.experiment_switch.insert_one({
        "experiment_name" : experiment_name,
        "instrument" : instrument,
        "station" : int(station),
        "switch_time" : datetime.datetime.now(),
        "requestor_uid" : userid
        })
    return (True, "")

def get_elog_entries(experiment_name):
    """
    Get the elog entries for the experiment as a flat list sorted by inserted time ascending.
    """
    expdb = logbookclient[experiment_name]
    return [entry for entry in expdb['elog'].find().sort([("insert_time", 1)])]

def get_specific_elog_entry(experiment_name, id):
    """
    Get the specified elog entry for the experiment.
    For now, we have id based lookups.
    """
    expdb = logbookclient[experiment_name]
    return expdb['elog'].find_one({"_id": ObjectId(id)})

def get_specific_shift(experiment_name, id):
    """
    Get the specified shift entry for the experiment.
    For now, we have id based lookups.
    """
    expdb = logbookclient[experiment_name]
    return expdb['shifts'].find_one({"_id": ObjectId(id)})


def post_new_log_entry(experiment_name, author, log_content, files, run_num=None, shift=None, root=None, parent=None):
    """
    Create a new log entry.
    """
    expdb = logbookclient[experiment_name]
    attachments = []
    for file in files:
        filename = file[0]
        filestorage = file[1] # http://werkzeug.pocoo.org/docs/0.14/datastructures/#werkzeug.datastructures.FileStorage
        isloc = requests.post(imagestoreurl + "dir/assign").json()
        imgurl = isloc['publicUrl'] + isloc['fid']
        logger.info("Posting attachment %s to URL %s", filename, imgurl)
        files = {'file': (filename, filestorage.stream, filestorage.mimetype, {'Content-Disposition' : 'inline; filename=%s' % filename})}
        requests.put(imgurl, files=files)
        attachments.append({"_id": ObjectId(), "name" : filename, "type": filestorage.mimetype, "url" : imgurl })

    elog_doc = {
        "relevance_time": datetime.datetime.now(),
        "insert_time": datetime.datetime.now(),
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
    if root:
        elog_doc["root"] = root
    if parent:
        elog_doc["parent"] = parent

    ins_id = expdb['elog'].insert_one(elog_doc).inserted_id
    entry = expdb['elog'].find_one({"_id": ins_id})
    return entry

def get_experiment_files(experiment_name):
    '''
    Get the files for the given experiment
    '''
    expdb = logbookclient[experiment_name]
    return [file for file in expdb['files'].find().sort([("run_num", -1), ("create_timestamp", -1)])]


def get_experiment_runs(experiment_name, include_run_params=False):
    '''
    Get the runs for the given experiment.
    Does not include the run parameters by default
    '''
    expdb = logbookclient[experiment_name]
    return [run for run in expdb['runs'].find(projection={ "params": include_run_params }).sort([("num", -1)])]

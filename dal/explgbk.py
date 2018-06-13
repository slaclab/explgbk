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

import requests
import tempfile
import subprocess

from pymongo import ASCENDING, DESCENDING
from bson import ObjectId

from context import logbookclient, imagestoreurl, instrument_scientists_run_table_defintions, security, usergroups

__author__ = 'mshankar@slac.stanford.edu'

logger = logging.getLogger(__name__)

def get_instruments():
    """
    Get the list of instruments from the site database.
    """
    sitedb = logbookclient["site"]
    return [x for x in sitedb["instruments"].find().sort([("_id", 1)])]


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
    setup_document["modified_at"] = datetime.datetime.utcnow()
    latest_setup_id = expdb['setup'].insert_one(setup_document).inserted_id
    expdb['info'].find_one_and_update({}, {'$set': {'latest_setup': latest_setup_id}})


def register_new_experiment(experiment_name, incoming_info, create_auto_roles=True):
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
    expdb["run_tables"].create_index( [("name", ASCENDING)], unique=True)

    # Create a default shift
    expdb["shifts"].insert_one( { "name" : "Default",
        "begin_time" : datetime.datetime.utcnow(),
        "end_time" : None,
        "leader" : security.get_current_user_id(),
        "description" : "Default shift created automatically during experiment registration",
        "params" : {}
        } )

    if create_auto_roles:
        expdb["roles"].insert_many([
            {"app" : "LDAP", "name": "Admin", "players": [ "uid:" + info["leader_account"]] },
            {"app" : "LogBook", "name": "Editor", "players": [ "uid:" + info["leader_account"]] },
            {"app" : "LogBook", "name": "Writer", "players": [ info["posix_group"]] }
            ]
        )

    return (True, "")

def update_existing_experiment(experiment_name, incoming_info):
    """
    Update an existing experiment
    """
    if experiment_name not in logbookclient.database_names():
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

def clone_experiment(experiment_name, source_experiment_name, incoming_info, copy_specs):
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

    if experiment_name in logbookclient.database_names():
        return (False, "Experiment %s has already been registered" % experiment_name)

    expdb = logbookclient[experiment_name]
    info = {}
    info.update(src_exp_db["info"].find_one())
    info.update(incoming_info)
    info["_id"]                = experiment_name.replace(" ", "_")
    info["name"]               = experiment_name
    if "experiment_name" in info: # Bug from previous releases?
        del info["experiment_name"]

    status, msg = register_new_experiment(experiment_name, info, create_auto_roles=False)
    if not status:
        return (status, msg)

    def copy_collection_from_src_to_clone(collection_name):
        for doc in src_exp_db[collection_name].find({}):
            del doc["_id"]
            expdb[collection_name].insert_one(doc)

    for coll, cp_select in copy_specs.items():
        if cp_select:
            logger.info("Copying over collection %s from source experiment %s to dest experiment %s", coll, source_experiment_name, experiment_name)
            copy_collection_from_src_to_clone(coll)

    return (True, "")


def rename_experiment(experiment_name, new_experiment_name):
    """
    Renames an experiment with a new name.
    """
    if new_experiment_name in logbookclient.database_names():
        return (False, "Experiment %s has already been registered" % experiment_name)

    logbookclient.admin.command('copydb', check=True, fromdb=experiment_name, todb=new_experiment_name)

    expdb = logbookclient[new_experiment_name]
    info = {}
    info.update(expdb["info"].find_one())
    info["_id"]  = new_experiment_name
    info["name"] = new_experiment_name
    expdb["info"].delete_one({"_id": experiment_name})
    expdb["info"].insert_one(info)

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
        logger.info("Looking for active experiment for %s", qry)
        for exp in sitedb["experiment_switch"].find(qry).sort([( "switch_time", -1 )]).limit(1):
            exp_info = get_experiment_info(exp["experiment_name"]) if not exp.get("is_standby", False) else { "instrument": qry["instrument"], "is_standby": True }
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
        "switch_time" : datetime.datetime.utcnow(),
        "requestor_uid" : userid
        })
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

def get_elog_entries(experiment_name):
    """
    Get the elog entries for the experiment as a flat list sorted by inserted time ascending.
    The sort order is important as the UI uses this to optimize tree-building.
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


def __upload_attachments_to_imagestore_and_return_urls(experiment_name, files):
    """
    Given a list of file uploads, upload these to the imagestore, generate thumbnails and return a list of attachments objects.
    """
    attachments = []
    for file in files:
        filename = file[0]
        filestorage = file[1] # http://werkzeug.pocoo.org/docs/0.14/datastructures/#werkzeug.datastructures.FileStorage

        isloc = requests.post(imagestoreurl + "dir/assign").json()
        imgurl = isloc['publicUrl'] + isloc['fid']
        logger.info("Posting attachment %s to URL %s", filename, imgurl)
        files = {'file': (filename, filestorage.stream, filestorage.mimetype, {'Content-Disposition' : 'inline; filename=%s' % filename})}
        requests.put(imgurl, files=files)
        attachment = {"_id": ObjectId(), "name" : filename, "type": filestorage.mimetype, "url" : imgurl }

        # We get the data back from the image server; this is to make sure the content did make it there; also the stream is probably in an inconsistent state
        # Not the most efficient but the safest perhaps.
        with requests.get(imgurl, stream=True) as imgget, tempfile.NamedTemporaryFile("w+b") as fd:
            tfname, tf_thmbname = fd.name, fd.name+".png"
            for chunk in imgget.iter_content(chunk_size=128):
                fd.write(chunk)
            fd.flush()
            cp = subprocess.run(["convert", "-thumbnail", "128", tfname, tf_thmbname], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=30)
            logger.info(cp)
            if cp.returncode == 0 and os.path.exists(tf_thmbname):
                with open(tf_thmbname, 'rb') as thmb_s:
                    thmb_isloc = requests.post(imagestoreurl + "dir/assign").json()
                    thmb_imgurl = thmb_isloc['publicUrl'] + thmb_isloc['fid']
                    logger.info("Posting attachment thumbnail %s to URL %s", tf_thmbname, thmb_imgurl)
                    thmb_files = {'file': (filename, thmb_s, "image/png", {'Content-Disposition' : 'inline; filename=%s' % "preview_" + filename})}
                    requests.put(thmb_imgurl, files=thmb_files)
                    attachment["preview_url"] = thmb_imgurl
            else:
                logger.warn("Skipping generating a thumbnail for %s for experiment %s", filename, experiment_name)

        attachments.append(attachment)
    return attachments


def post_new_log_entry(experiment_name, author, log_content, files, run_num=None, shift=None, root=None, parent=None, email_to=None, tags=None, title=None):
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
    return result.modified_count > 0

def modify_elog_entry(experiment_name, entry_id, userid, new_content, email_to, tags, files, title=None):
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
        result = expdb['elog'].update_one({"_id": current_entry["_id"]}, modification)
        return result.modified_count > 0
    return False

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
    expdb = logbookclient[experiment_name]
    return expdb['elog'].distinct("tags")

def get_experiment_files(experiment_name):
    '''
    Get the files for the given experiment
    '''
    expdb = logbookclient[experiment_name]
    return [file for file in expdb['file_catalog'].find().sort([("run_num", -1), ("create_timestamp", -1)])]

def get_experiment_files_for_run(experiment_name, run_num):
    '''
    Get the files for the given experiment for the specified run
    '''
    expdb = logbookclient[experiment_name]
    return [file for file in expdb['file_catalog'].find({"run_num": run_num}).sort([("run_num", -1), ("create_timestamp", -1)])]


def get_experiment_runs(experiment_name, include_run_params=False):
    '''
    Get the runs for the given experiment.
    Does not include the run parameters by default
    '''
    expdb = logbookclient[experiment_name]
    if include_run_params:
        return [run for run in expdb['runs'].find().sort([("num", -1)])]
    else:
        return [run for run in expdb['runs'].find(projection={ "params": include_run_params }).sort([("num", -1)])]

def get_all_run_tables(experiment_name):
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
    allRunTables.extend([ r for r in sitedb["run_tables"].find()])
    summtables = {}
    pdescs = [ x for x in expdb['run_param_descriptions'].find( { "param_name": re.compile(r'.*\/.*') } ) ]
    mimes = { "params." + x["param_name"] : x["type"] for x in sitedb['run_param_descriptions'].find({"type": { "$exists": True }})}
    mimes.update({ "params." + x["param_name"] : x["type"] for x in expdb['run_param_descriptions'].find({"type": { "$exists": True }})})
    for pdesc in pdescs:
        categoryName, paramName = pdesc['param_name'].split("/")
        if categoryName not in summtables:
            summtables[categoryName] = {
                "name" : categoryName,
                "description" : pdesc["description"],
                "is_editable" : False,
                "coldefs" : []
                }
        summtables[categoryName]["coldefs"].append({
            "label" : paramName,
            "type" : categoryName,
            "source": "params." + categoryName + "/" + paramName,
            "pvName": paramName,
            "is_editable" : False,
            "position" : 0
            })
    allRunTables.extend([summtables[x] for x in sorted(summtables.keys())])
    allRunTables.extend([x for x in expdb['run_tables'].find()])
    # The run table categories change with time. This is where we patch for versions of the instrument scientist source list.
    for rt in allRunTables:
        for coldef in rt["coldefs"]:
            if coldef['type'].startswith('EPICS:'):
                coldef['type'] = coldef['type'].replace('EPICS:', 'EPICS/')
            coldef['mime_type'] = mimes.get(coldef['source'], "text")
    return allRunTables

def get_runtable_data(experiment_name, tableName, sampleName):
    '''
    Get the data from the run tables for the given table.
    In addition to the basic run data, we add the sources for the given run table.
    This is mostly a matter of constructing the appropriate mongo filters.
    If sampleName is specified, we restrict the returned data to runs associated with the sample. Otherwise, we return all runs.
    '''
    tableDef = next(x for x in get_all_run_tables(experiment_name) if x['name'] == tableName)
    sources = { "num": 1, "begin_time": 1, "end_time": 1 }
    sources.update({ x['source'] : 1 for x in tableDef['coldefs']})
    query = {}
    if sampleName:
        logger.debug("Getting run table data for sample %s", sampleName)
        sample_doc = get_sample_for_experiment_by_name(experiment_name, sampleName)
        query = { "sample": sample_doc["_id"] } if sample_doc else query
    return [x for x in logbookclient[experiment_name]['runs'].find(query, sources).sort([("num", -1)])] # Use sources as a filter to find


def get_run_param_descriptions(experiment_name):
    '''
    Get the run param descriptions for this experiment.
    '''
    return [x for x in logbookclient[experiment_name]['run_param_descriptions'].find({}).sort([("name", 1)])]

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
        {"label": "Sample", "description": "The sample associated with the run", "source": "sample", "category": "Run Info"},
        {"label": "Run Duration", "description": "The duration of the run", "source": "duration", "category": "Run Info"}]
    rtbl_sources["Editables"] = [ { "label": x["_id"], "description": x["_id"], "source": "editable_params."+x["_id"]+".value", "category": "Editables" } for x in expdb.runs.aggregate([
        { "$project": { "editables": { "$objectToArray": "$editable_params" } } },
        { "$unwind": "$editables" },
        { "$group": { "_id": "$editables.k", "total": { "$sum": 1 } } } ])]
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
        if instrument in instrument_scientists_run_table_defintions and param_name in instrument_scientists_run_table_defintions[instrument]:
            param_names_with_categories.append({
                "label" : param_name,
                "category": "EPICS/" + instrument_scientists_run_table_defintions[instrument][param_name]["title"],
                "description": instrument_scientists_run_table_defintions[instrument][param_name].get("description", param_name),
                "source": "params." + param_name })
        elif 'HEADER' in instrument_scientists_run_table_defintions and param_name in instrument_scientists_run_table_defintions['HEADER']:
            param_names_with_categories.append({
                "label" : param_name,
                "category": "EPICS/" + instrument_scientists_run_table_defintions['HEADER'][param_name]["title"],
                "description": instrument_scientists_run_table_defintions['HEADER'][param_name].get("description", param_name),
                "source": "params." + param_name })
        elif param_name in param_descs:
            param_names_with_categories.append({
                "label" : param_name,
                "category": param_descs[param_name]['category'],
                "description": param_descs[param_name].get("description", param_name),
                "source": "params." + param_name })
        elif param_name in site_param_descs:
            param_names_with_categories.append({
                "label" : param_name,
                "category": site_param_descs[param_name]['category'],
                "description": site_param_descs[param_name].get("description", param_name),
                "source": "params." + param_name })
        else:
            param_names_with_categories.append({
                "label" : param_name,
                "category": "EPICS:Additional parameters",
                "description": param_name,
                "source": "params." + param_name })
    rtbl_sources.update({ x['category'] : [] for x in param_names_with_categories})
    [ rtbl_sources[x['category']].append(x) for x in param_names_with_categories ]
    return rtbl_sources


def create_update_user_run_table_def(experiment_name, table_definition):
    '''
    Create or update an existing user run table definition for an experiment
    We expect a fully formed table_definition here...
    '''
    expdb = logbookclient[experiment_name]
    return expdb['run_tables'].update({'name': table_definition['name']}, table_definition, True)

def delete_run_table(experiment_name, table_name):
    '''
    Delete the specified run table for the experiment.
    '''
    expdb = logbookclient[experiment_name]
    expdb["run_tables"].delete_one({"name": table_name})
    return (True, "")


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
    if not source.startswith('editable_params.'):
        raise Exception("Cannot update anything else other than an editable param")
    return expdb["runs"].find_one_and_update(
        {"num": runnum},
        {"$set": { source: {
                    "value": value,
                    "modified_by": userid,
                    "modified_time": datetime.datetime.utcnow()
                    }}})

def get_experiment_shifts(experiment_name):
    """
    Get the shifts for an experiment.
    """
    expdb = logbookclient[experiment_name]
    return list(expdb.shifts.find({}).sort([("begin_time", -1)]))

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

def create_update_sample(experiment_name, sample_name, createp, info):
    """
    Create or update a sample for an experiment.
    """
    expdb = logbookclient[experiment_name]
    if createp and expdb['samples'].find_one({"name": sample_name}):
        return (False, "Sample %s already exists" % sample_name)
    if not createp and not expdb['samples'].find_one({"_id": ObjectId(info["_id"])}):
        return (False, "Sample %s does not exist" % sample_name)

    if createp:
        expdb['samples'].insert_one(info)
    else:
        sample_id = info["_id"]
        del info["_id"]
        expdb['samples'].find_one_and_update({"_id": ObjectId(sample_id)}, {"$set": info})

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

    expdb.current.find_one_and_update({"_id": "sample"}, {"$set": { "_id": "sample", "sample" : sample_doc["_id"] }} , upsert=True)
    return (True, "")

def get_modal_param_definitions(modal_type):
    """
    Get the site specific modal param definitions from the site database for the specified modal type.
    """
    sitedb = logbookclient["site"]
    return sitedb["modal_params"].find_one({"_id": modal_type})

def register_file_for_experiment(experiment_name, info):
    """
    Register a file for the experiment.
    """
    expdb = logbookclient[experiment_name]
    inserted_id = expdb['file_catalog'].insert_one(info).inserted_id
    return (True, expdb['file_catalog'].find_one({"_id": ObjectId(inserted_id) }))

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

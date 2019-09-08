'''
Run control business logic.
'''

import json
import datetime
import logging
import re

import requests

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from bson import ObjectId

from context import logbookclient
from dal.utils import escape_chars_for_mongo

__author__ = 'mshankar@slac.stanford.edu'

logger = logging.getLogger(__name__)


def start_run(experiment_name, run_type, user_specified_run_number=None, user_specified_start_time=None):
    '''
    Start a new run for the specified experiment
    If the user_specified_run_number is not specified; we use the next_runnum autoincrement counter.
    '''
    expdb = logbookclient[experiment_name]
    if not user_specified_run_number:
        next_run_num_doc = expdb['counters'].find_one_and_update({ "_id" : "next_runnum"}, {'$inc': {'seq': 1}}, return_document=ReturnDocument.AFTER)
        if not next_run_num_doc:
            raise Exception("Could not update run number counter for experiment %s" % experiment_name)
        next_run_num = next_run_num_doc["seq"]
        logger.info("Next run for experiment %s is %s", experiment_name, next_run_num)
    else:
        next_run_num = user_specified_run_number
        logger.info("Next run for experiment %s is from the user %s", experiment_name, next_run_num)

    begin_time = user_specified_start_time if user_specified_start_time else datetime.datetime.utcnow()

    run_doc = {
        "num" : next_run_num,
        "type" : run_type,
        "begin_time" : begin_time,
        "end_time" : None,
        "params" : {},
        "editable_params" : {}}
    current_sample = expdb.current.find_one({"_id": "sample"})
    if current_sample:
        run_doc["sample"] = ObjectId(current_sample["sample"])

    result = expdb['runs'].insert_one(run_doc)
    return expdb['runs'].find_one({"num": next_run_num})

def get_current_run(experiment_name):
    '''
    Get the run document for the run with the maximum run number.
    '''
    expdb = logbookclient[experiment_name]
    current_run_doc = expdb.runs.find().sort([("num", DESCENDING)]).limit(1)
    return list(current_run_doc)[0] if current_run_doc.count() else None

def get_run_doc_for_run_num(experiment_name, run_num):
    """
    Get the run document for the specified run number
    """
    expdb = logbookclient[experiment_name]
    run_doc = expdb.runs.find_one({"num": run_num})
    if run_doc:
        return run_doc
    return None

def get_specified_run_params_for_all_runs(experiment_name, run_params):
    """
    Get the specified run parameters for all runs in the experiment.
    For now, this only includes the non-editable parameters submitted by the DAQ.
    """
    expdb = logbookclient[experiment_name]
    projection_op = {"num": 1}
    for run_param in run_params:
        projection_op["params." + escape_chars_for_mongo(run_param)] = 1
    return [x for x in expdb.runs.find({}, projection_op)]

def get_sample_for_run(experiment_name, run_num):
    """
    Lookup the sample for the specified run
    """
    expdb = logbookclient[experiment_name]
    run_doc = expdb.runs.find_one({"num": run_num})
    if not run_doc:
        return None
    if 'sample' not in run_doc:
        return None
    return expdb.samples.find_one({"_id": run_doc["sample"]})


def end_run(experiment_name, user_specified_end_time=None):
    '''
    End the current run; this is mostly a matter of filling in the end time
    '''
    expdb = logbookclient[experiment_name]
    current_run_doc = get_current_run(experiment_name)
    end_time = user_specified_end_time if user_specified_end_time else datetime.datetime.utcnow()
    return expdb.runs.find_one_and_update({"num": current_run_doc["num"]}, {'$set': {'end_time': end_time}}, return_document=ReturnDocument.AFTER)

def is_run_closed(experiment_name, run_num):
    '''
    Check if the specified run is closed
    '''
    expdb = logbookclient[experiment_name]
    run_doc = expdb.runs.find_one({"num": run_num})
    if run_doc and run_doc.get('end_time', None):
        return True
    return False

def add_run_params(experiment_name, run_doc, run_params):
    '''
    Add run parameters to the specified run.
    '''
    expdb = logbookclient[experiment_name]
    return expdb.runs.find_one_and_update({"num": run_doc["num"]}, {'$set': run_params }, return_document=ReturnDocument.AFTER)

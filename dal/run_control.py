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

__author__ = 'mshankar@slac.stanford.edu'

logger = logging.getLogger(__name__)


def start_run(experiment_name, run_type, user_specified_run_number=None):
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

    run_doc = {
        "num" : next_run_num,
        "type" : run_type,
        "begin_time" : datetime.datetime.now(),
        "end_time" : None,
        "params" : {},
        "editable_params" : {}}
    current_sample = expdb.current.find_one({"_id": "sample"})
    if current_sample:
        run_doc["sample"] = current_sample["name"]

    result = expdb['runs'].insert_one(run_doc)
    return expdb['runs'].find_one({"num": next_run_num})

def get_current_run(experiment_name):
    '''
    Get the run document for the run with the maximum run number.
    '''
    expdb = logbookclient[experiment_name]
    current_run_doc = expdb.runs.find().sort([("num", DESCENDING)]).limit(1)
    return list(current_run_doc)[0]

def get_run_doc_for_run_num(experiment_name, run_num):
    """
    Get the run document for the specified run number
    """
    expdb = logbookclient[experiment_name]
    run_doc = expdb.runs.find({"num": run_num})
    return list(run_doc)[0]

def end_run(experiment_name):
    '''
    End the current run; this is mostly a matter of filling in the end time
    '''
    expdb = logbookclient[experiment_name]
    current_run_doc = get_current_run(experiment_name)
    return expdb.runs.find_one_and_update({"num": current_run_doc["num"]}, {'$set': {'end_time': datetime.datetime.now()}}, return_document=ReturnDocument.AFTER)


def add_run_params(experiment_name, run_params):
    '''
    Add run parameters to the current run.
    '''
    expdb = logbookclient[experiment_name]
    current_run_doc = get_current_run(experiment_name)
    return expdb.runs.find_one_and_update({"num": current_run_doc["num"]}, {'$set': run_params }, return_document=ReturnDocument.AFTER)

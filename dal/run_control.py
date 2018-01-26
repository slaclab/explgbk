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


def start_run(experiment_name, run_type):
    '''
    Start a new run for the specified experiment
    '''
    expdb = logbookclient[experiment_name]
    next_run_num_doc = expdb['counters'].find_one_and_update({ "_id" : "next_runnum"}, {'$inc': {'seq': 1}}, return_document=ReturnDocument.AFTER)
    if not next_run_num_doc:
        raise Exception("Could not update run number counter for experiment %s" % experiment_name)

    next_run_num = next_run_num_doc["seq"]
    logger.info("Next run for experiment %s is %s", experiment_name, next_run_num)
    result = expdb['runs'].insert_one({
        "num" : next_run_num,
        "type" : run_type,
        "begin_time" : datetime.datetime.now(),
        "end_time" : None,
        "params" : {},
        "editable_params" : {}})
    return expdb['runs'].find_one({"num": next_run_num})

def get_current_run(experiment_name):
    '''
    Get the run document for the run with the maximum run number.
    '''
    expdb = logbookclient[experiment_name]
    current_run_doc = expdb.runs.find().sort([("num", DESCENDING)]).limit(1)
    return list(current_run_doc)[0]


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

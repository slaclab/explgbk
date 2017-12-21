'''
The model level business logic goes here.
Most of the code here gets a connection to the database, executes a query and formats the results.
'''

import json

from context import logbook_db

from dal.sql_queries import QUERY_SELECT_EXPERIMENTS_FOR_INSTRUMENT, QUERY_SELECT_ELOG_ENTRIES_FOR_EXPERIMENT, \
        QUERY_INSERT_NEW_HEADER_WITH_RUN, QUERY_INSERT_NEW_HEADER_WITHOUT_RUN, QUERY_INSERT_NEW_ELOG_ENTRY, QUERY_SELECT_ELOG_ENTRY_FOR_EXPERIMENT

__author__ = 'mshankar@slac.stanford.edu'


def get_experiments_for_instrument(instrument_name):
    """
    Return the experiments for a given instrument
    :param instrument_name: The instrument for the experiments, for example, XPP
    :return: List of experiments for this instrument.
    """
    with logbook_db.connect() as cursor:
        cursor.execute(QUERY_SELECT_EXPERIMENTS_FOR_INSTRUMENT, {"instrument_name": instrument_name})
        return cursor.fetchall()


def get_elog_for_experiment(experiment_name):
    """
    Get the elog entries for an experiment. 
    :param experiment_name - for example - diadaq13
    :return: List of elog entries + run start/stop entries for the experiment sorted by descending time.
    """
    with logbook_db.connect() as cursor:
        cursor.execute(QUERY_SELECT_ELOG_ENTRIES_FOR_EXPERIMENT, {"experiment_name": experiment_name})
        return cursor.fetchall()


def post_new_elog_entry(experiment_name, content, content_type, run_num, author):
    """
    Post a new elog entry for the experiment. 
    :param experiment_name - for example - diadaq13
    :param content - The content of the elog entry
    :param content_type - TEXT or HTML
    :param run_num - Can be None..
    :param author - The person posting the elog.
    :return: The posted elog entry
    We first lookup the run_num if specified; then create a header and a entry; then fetch the "document" for the entry and return that.
    """
    if run_num:
        with logbook_db.connect() as cursor:
            cursor.execute(QUERY_INSERT_NEW_HEADER_WITH_RUN, {
                "experiment_name": experiment_name,
                "run_num" : run_num
                })
            header_id = cursor.lastrowid

    else:
        with logbook_db.connect() as cursor:
            cursor.execute(QUERY_INSERT_NEW_HEADER_WITHOUT_RUN, {
                "experiment_name": experiment_name
                })
            header_id = cursor.lastrowid

    try:                
        with logbook_db.connect() as cursor:
            cursor.execute(QUERY_INSERT_NEW_ELOG_ENTRY, {
                "header_id": header_id,
                "content" : content,
                "content_type": content_type,
                "author": author
                })
            entry_id = cursor.lastrowid
    except:
        print(cursor._last_executed)
        raise
    
    with logbook_db.connect() as cursor:
        cursor.execute(QUERY_SELECT_ELOG_ENTRY_FOR_EXPERIMENT, {
            "experiment_name": experiment_name,
            'entry_id': entry_id
            })
        return cursor.fetchone()
    
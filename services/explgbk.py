'''
Code for the business logic.
Here's where you do the actual business logic using functions from the dal's business object.
The public methods here are expected to be Flask blueprint endpoints.
We get the arguments for the business logic from Flask; make various calls to the dal's and then send JSON responses.
Events are published into Kafka and the Websocket layer here.
Use security's authentication_required and authorization_required decorators to enforce authz/authn.

'''

import os
import json
import logging
import copy
import io
import re
import abc

import requests
import context
from functools import wraps
from collections import OrderedDict
from datetime import datetime, timedelta
import types
import hashlib
import urllib
import base64
import pytz
import jwt

import smtplib
from email.message import EmailMessage

from flask import Blueprint, jsonify, request, url_for, Response, stream_with_context, send_file, \
    abort, redirect, make_response, g, current_app

from dal.explgbk import LgbkException, get_experiment_info, save_new_experiment_setup, register_new_experiment, \
    get_instruments, get_currently_active_experiments, switch_experiment, get_elog_entries, post_new_log_entry, get_specific_elog_entry, \
    get_specific_shift, get_experiment_files, get_experiment_runs, get_all_run_tables, get_runtable_data, get_runtable_sources, \
    create_update_user_run_table_def, update_editable_param_for_run, get_instrument_station_list, update_existing_experiment, \
    create_update_instrument, get_experiment_shifts, get_shift_for_experiment_by_name, close_shift_for_experiment, \
    create_update_shift, get_latest_shift, get_samples, create_sample, update_sample, get_sample_for_experiment_by_name, \
    make_sample_current, register_file_for_experiment, search_elog_for_text, delete_run_table, get_current_sample_name, \
    get_elogs_for_run_num, get_elogs_for_run_num_range, get_elogs_for_specified_id, get_collaborators, get_role_object, \
    add_collaborator_to_role, remove_collaborator_from_role, delete_elog_entry, modify_elog_entry, clone_experiment, rename_experiment, \
    instrument_standby, get_experiment_files_for_run, get_elog_authors, get_elog_entries_by_author, get_elog_tags, get_elog_entries_by_tag, \
    get_elogs_for_date_range, clone_sample, get_modal_param_definitions, lock_unlock_experiment, get_elog_emails, \
    get_elog_email_subscriptions, elog_email_subscribe, elog_email_unsubscribe, get_elog_email_subscriptions_emails, \
    get_poc_feedback_changes, add_poc_feedback_item, clone_run_table_definition, replace_system_run_table_definition, \
    delete_system_run_table, get_instrument_elogs, post_related_elog_entry, get_related_instrument_elog_entries, \
    get_elog_tree_for_specified_id, get_workflow_definitions, get_dm_locations, get_workflow_triggers, \
    create_update_wf_definition, get_workflow_jobs, get_workflow_job_doc, create_wf_job, delete_wf_job, update_wf_job, \
    file_available_at_location, get_collaborators_list_for_experiment, get_site_naming_conventions, delete_sample_for_experiment, \
    get_global_roles, add_player_to_global_role, remove_player_from_global_role, get_site_config, file_not_available_at_location, \
    get_experiment_run_document, get_experiment_files_for_run_for_live_mode, get_switch_history, delete_experiment, migrate_attachments_to_local_store, \
    get_complete_elog_tree_for_specified_id, get_site_file_types, add_player_to_instrument_role, remove_player_from_instrument_role, \
    delete_wf_definition, get_elog_entries_by_regex, get_run_param_descriptions, add_update_run_param_descriptions, change_sample_for_run, \
    add_update_experiment_params, get_URAWI_details, import_users_from_URAWI, get_poc_feedback_document, get_poc_feedback_experiments, \
    get_experiment_files_for_run_for_live_mode_at_location, get_active_experiment_name_for_instrument_station, \
    get_experiment_files_for_live_mode_at_location, get_run_numbers_with_tag, stop_current_sample, get_tag_to_run_numbers, \
    get_tags_for_runs, clone_system_template_run_tables_into_experiment, get_projects, get_project_info, create_project, update_project, \
    get_project_grids, get_project_grid, add_grid_to_project, update_project_grid, link_grid_to_experiment, get_exp_file_counts_by_extension


from dal.run_control import start_run, get_current_run, end_run, add_run_params, get_run_doc_for_run_num, get_sample_for_run, \
    get_specified_run_params_for_all_runs, is_run_closed, get_run_nums_matching_params, get_run_nums_matching_editable_regex, \
    map_param_editable_to_run_nums

from dal.utils import JSONEncoder, escape_chars_for_mongo, replaceInfNan

from dal.exp_cache import get_experiments, get_experiments_for_user, does_experiment_exist, reload_cache as reload_experiment_cache, \
    text_search_for_experiments, get_experiment_stats, get_experiment_daily_data_breakdown, \
    get_experiments_with_post_privileges, get_cached_experiment_names, get_all_param_names_matching_regex, get_experiments_proposal_mappings, \
    update_single_experiment_info, get_experiments_starting_in_time_frame, get_sorted_experiments_ids, get_cached_experiment_info, \
    search_experiments_for_common_fields, get_direct_experiments_for_user, get_potentially_active_users, get_recently_updated_experiments

from dal.imagestores import parseImageStoreURL

__author__ = 'mshankar@slac.stanford.edu'

explgbk_blueprint = Blueprint('experiment_logbook_api', __name__)

def addHeaders(resp):
    # We don't send html with this blueprint; so we use that as a default.
    if 'Content-Type' not in resp.headers or resp.headers['Content-Type'].startswith('text/html'):
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
    return resp

explgbk_blueprint.after_request(addHeaders)

logger = logging.getLogger(__name__)

def logAndAbort(error_msg, ret_status=500):
    logger.error(error_msg)
    return Response(error_msg, status=ret_status)

def experiment_exists(wrapped_function):
    """
    Decorator to make sure experiment_name in the argument to the ws call exists.
    """
    @wraps(wrapped_function)
    def function_interceptor(*args, **kwargs):
        experiment_name = kwargs.get('experiment_name', None)
        if experiment_name and does_experiment_exist(experiment_name):
            exp_info = get_experiment_info(experiment_name)
            g.experiment_name = experiment_name
            g.instrument = exp_info["instrument"]
            g.exp_info = exp_info
            return wrapped_function(*args, **kwargs)
        else:
            logger.error("Experiment %s does not exist in the experiment cache", experiment_name)
            abort(404)
            return None

    return function_interceptor

def experiment_exists_and_unlocked(wrapped_function):
    """
    Decorator to make sure experiment_name in the argument to the ws call exists.
    """
    @wraps(wrapped_function)
    def function_interceptor(*args, **kwargs):
        experiment_name = kwargs.get('experiment_name', None)
        if experiment_name and does_experiment_exist(experiment_name):
            exp_info = get_experiment_info(experiment_name)
            if exp_info.get("is_locked", False) and set(["POST", "PUT", "DELETE"]) & set(request.url_rule.methods):
                logger.error("Experiment %s is locked; methods that modify data are not allowed. To change data, please unlock the experiment.", experiment_name)
                abort(423) # Webdav locked.
                return None
            g.experiment_name = experiment_name
            g.instrument = exp_info["instrument"]
            g.exp_info = exp_info
            return wrapped_function(*args, **kwargs)
        else:
            logger.error("Experiment %s does not exist in the experiment cache", experiment_name)
            abort(404)
            return None

    return function_interceptor

def instrument_exists(wrapped_function):
    """
    Decorator to pull the instrument name from the request in the absence of an experiment.
    For example, when switching an experiment etc.
    """
    @wraps(wrapped_function)
    def function_interceptor(*args, **kwargs):
        info = request.json
        if info:
            instrument = info.get("instrument", None)
            if instrument:
                g.instrument = instrument
            return wrapped_function(*args, **kwargs)
        else:
            logger.error("No instrument specified in call")
            abort(404)
            return None
    return function_interceptor


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/info", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_getexpinfo(experiment_name):
    """
    <div>Gets the basic info for the specified experiment
    <pre class="json">{
  "success": true,
  "value": {
    "_id": "diadaq13",
    "name": "diadaq13",
    "description": "Testing the DAQ system software of the instrument",
    "instrument": "DIA",
    "registration_time": "2013-05-24T03:52:25+00:00",
    "start_time": "2013-05-24T03:50:49+00:00",
    "end_time": "2013-05-24T03:50:50+00:00",
    "leader_account": "gapon",
    "contact_info": "Igor Gaponenko (gapon@slac.stanford.edu)",
    "posix_group": "diadaq13",
    "params": {
      "DATA_PATH": "/reg/data/ana01/",
      "dm_locations": "NERSC"
    }
  }
}</pre>
    </div>
    """
    info = get_experiment_info(experiment_name)
    return JSONEncoder().encode({'success': True, 'value': info})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/internalinfo", methods=["GET"])
@experiment_exists
def svc_get_internal_info(experiment_name):
    """
    Returns non-secure internal info about the experiment. This is an open endpoint meant for scripts and services.
    Returns these items
    --> Instrument
    --> URAWI proposal mapping
    --> params
    --> start date and end date
    """
    info = get_experiment_info(experiment_name)
    ret = {
        "instrument": info["instrument"],
        "proposal_id": __map_experiment_to_URAWI_proposal__(experiment_name, info)["proposal_id"],
        "start_time": info.get("start_time"),
        "end_time": info.get("end_time"),
        "posix_group": info.get("posix_group"),
        "params": info.get("params", {}),
    }
    return JSONEncoder().encode({'success': True, 'value': ret})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/info/setup", methods=["POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_saveexpinfosetup(experiment_name):
    """
    Save the setup for the experiment
    :param experiment_name - The name of the experiment - diadaq13
    """
    setup_details = json.loads(request.data.decode("utf-8"))
    logger.info("Saving setup %s", setup_details)
    save_new_experiment_setup(experiment_name, setup_details, context.security.get_current_user_id())

    return jsonify({"success": True})

class LegacyCatSort(metaclass=abc.ABCMeta):
    def __init__(self):
        self.legacy_run_period = -1 # Run periods older than this run are categorized into a legacy bucket
    @abc.abstractmethod
    def set_legacy_cutoff(self, legacy_run_period):
        """ Set the run period before which all experiment are bucketed into a legacy bucket"""
        raise NotImplementedError
    def __estimate_run_period__(self, exp):
        """ Estimate the LCLS run period """
        erp = 0
        override = exp.get("params", {}).get("run_period", None)
        if override:
            erp = int(override[-2:])
        else:
            erp = int(exp["name"][-2:] if exp["name"][-2:].isdigit() else "0")
        if erp and erp <= self.legacy_run_period:
            return 1
        ins = exp["instrument"]
        ctx_lg_cutoff = context.instrument_definitions.get(ins, {}).get("params", {}).get("legacy_cutoff", None)
        if ctx_lg_cutoff and erp <= int(ctx_lg_cutoff):
            return 1
        return erp

class CategorizerWithLegacy(LegacyCatSort):
    def __bucket_run_period__(self, exp):
        rp = self.__estimate_run_period__(exp)
        if rp == 1:
            return "Previous"
        return "Run " + str(rp) if rp else "null"
    def __call__(self, exp):
        return self.__bucket_run_period__(exp)
    def set_legacy_cutoff(self, legacy_run_period):
        self.legacy_run_period = legacy_run_period

class SorterWithLegacy(LegacyCatSort):
    def __init__(self):
        self.legacy_run_period = -1 # Run periods older than this run are categorized into a legacy bucket
    def __call__(self, exp):
        return self.__estimate_run_period__(exp)
    def set_legacy_cutoff(self, legacy_run_period):
        self.legacy_run_period = legacy_run_period


categorizers = {
    "instrument": [(lambda exp : exp.get("instrument", None))],
    "instrument_lastrunyear": [(lambda exp : exp.get("instrument", None)), (lambda exp : exp["last_run"]["begin_time"].year if "last_run" in exp else None)],
    "instrument_runperiod": [(lambda exp : exp.get("instrument", None)), CategorizerWithLegacy() ],
    }

sorters = {
    "name": ((lambda exp: exp["name"]), False),
    "lastrunyear": ((lambda exp: exp["last_run"]["begin_time"] if "last_run" in exp else exp["start_time"]), True),
    "runperiod": ((lambda exp: exp["last_run"]["begin_time"] if "last_run" in exp else exp["start_time"]), True),
    }

def categorize(explist, categorizers, sorter):
    ret = {}
    if sorter:
        explist = sorted(explist, key=sorter[0], reverse=sorter[1])
    for exp in explist:
        cur_dict = ret
        for n, categorizer in enumerate(categorizers):
            key = categorizer(exp)
            if (n+1) == len(categorizers):
                if key not in cur_dict:
                        cur_dict[key] = []
                cur_dict[key].append(exp)
            else:
                if key not in cur_dict:
                        cur_dict[key] = {}
                cur_dict = cur_dict[key]

    return ret


@explgbk_blueprint.route("/lgbk/ws/empty", methods=["GET"])
def svc_get_empty():
    """
    It makes it much easier in JS to build create/edit functionality by having a URL server side that returns an empty object.
    """
    return JSONEncoder().encode({"success": True, "value": {}})


@explgbk_blueprint.route("/lgbk/ws/experiments", methods=["GET"])
@context.security.authentication_required
def svc_get_experiments():
    """
    Returns the list of experiments and some basic information about each experiment.
    Support some categorization/sorting options as well.
    Without these options specified, a array of dicts is returned...
    Specify a categorization option using the categorize query parameter.
    When categorized, a dict of dict of arrays etc is returned; the array can be sorted using the sortby query parameter.
    For example, lgbk/ws/experiments?categorize=instrument_lastrunyear&sortby=lastrunyear should return a dict of dict of arrays of experiments.
    """
    experiments = get_experiments_for_user(context.security.get_current_user_id())
    for exp in experiments:
        if "all_param_names" in exp:
            del exp["all_param_names"]
    categorizer = categorizers.get(request.args.get("categorize", None), None)
    sortby = sorters.get(request.args.get("sortby", None), None)
    legacy_run_period_str = request.args.get("legacy_cutoff", None)
    if legacy_run_period_str:
        legacy_run_period = int(legacy_run_period_str)
        for cat in categorizer:
            if isinstance(cat, LegacyCatSort):
                cat.set_legacy_cutoff(legacy_run_period)
        for srt in sortby:
            if isinstance(srt, LegacyCatSort):
                srt.set_legacy_cutoff(legacy_run_period)

    if categorizer and sortby:
        return JSONEncoder().encode({"success": True, "value": categorize(experiments, categorizer, sortby)})
    if sortby:
        return JSONEncoder().encode({"success": True, "value": sorted(experiments, key=sortby[0], reverse=sortby[1])})

    return JSONEncoder().encode({"success": True, "value": experiments})

@explgbk_blueprint.route("/lgbk/ws/sorted_experiment_ids", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("experiment_create")
def svc_get_sorted_experiments_ids():
    """
    Get just the experiment ids ( normalized names ) sorted by the specified criteria.
    This is used ( along with the getExperimentInfos ) to support paging.
    Pass in a sort criteria as a URL encoded JSON array or arrays.
    For example, to sort by last_run.begin_time (descending) and then by end_time (descending) and then by name(ascending),
    encode [["last_run.begin_time", -1], ["end_time", -1], ["name", 1]] and pass this as the value of the parameter sort.
    If no parameter is specified, we use a descending sort on experiment start time; that is, [["start_time",-1]]
    """
    sort_criteria = json.loads(request.args.get("sort", '[["start_time", -1]]'))
    logger.info("Sorting by " + json.dumps(sort_criteria))
    return JSONEncoder().encode({"success": True, "value": get_sorted_experiments_ids(sort_criteria)})

@explgbk_blueprint.route("/lgbk/ws/get_experiment_infos", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("experiment_create")
def svc_get_experiment_infos():
    """
    Pass in a JSON array of experiment ids to get the experiment infos for them as an array.
    """
    exp_ids = request.json
    ret = [ get_cached_experiment_info(exp_id) for exp_id in exp_ids ]
    ret = [ x for x in ret if x ]
    for exp in ret:
        if "all_param_names" in exp:
            del exp["all_param_names"]
    return JSONEncoder().encode({"success": True, "value": ret})

@explgbk_blueprint.route("/lgbk/ws/ops_search_exp_infos", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("experiment_create")
def svc_ops_search_experiment_infos():
    """
    A experiment info search targeted at operators.
    Pass is the substring ( regex ) as a search_text parameter.
    Also, pass in the current sort as a sort parameter. The sort parameter is similar to svc_get_sorted_experiments_ids
    """
    search_term = request.args["search_text"]
    sort_criteria = json.loads(request.args.get("sort", '[["start_time", -1]]'))
    matching_experiment_ids = [x["_id"] for x in search_experiments_for_common_fields(search_term, sort_criteria)]
    return JSONEncoder().encode({"success": True, "value": matching_experiment_ids})

def __map_experiment_to_URAWI_proposal__(expname, ep):
    einfo = {"name": expname, "instrument": ep.get("instrument", "N/A")}
    if ep.get("params", {}).get("PNR", None):
        einfo["proposal_id"] = ep["params"]["PNR"]
    elif len(expname) == 9:
        # Newer experiments where we include the full proposal ID.
        einfo["proposal_id"] = expname[3:7].upper()
    elif len(expname) == 8:
        # Older experiments where we used to drop the L
        einfo["proposal_id"] = 'L' + expname[3:6].upper()
    else:
        # Possibly internal commissioning experiments which do not have a proposal id
        einfo["proposal_id"] = expname
    return einfo


@explgbk_blueprint.route("/lgbk/ws/experiments_to_proposal", methods=["GET"])
def svc_get_experiments_to_proposal():
    """
    Return a best guess mapping of all experiment names to their URAWI proposal ID's.
    Because of the changing nature of this relationship over the lifetime of various facilities, this is a best guess only and can be badly off.
    To fix issues where this mapping is incorrect, add a PNR experiment parameter to the experiment which explicitly lists the proposal ID.
    While this mapping is usually 1-1, sometimes, because of migration of experiments, there can be an occasional many-to-one mapping.
    That is, more than one experiment can map to the same proposal. However, for an experiment, there is only one proposal id.
    In addition, other attributes of an experiment that could possibly be computed from the experiment name but occasionally can't are also returned.
    The intent is for various services to use this call instead of using substring operations etc.
    For now, we return the proposal as proposal_id, instrument as instrument.
    """
    experiment_proposals = get_experiments_proposal_mappings()
    ret = {}
    for ep in experiment_proposals:
        expname = ep["name"]
        ret[expname] = __map_experiment_to_URAWI_proposal__(expname, ep)

    return JSONEncoder().encode({"success": True, "value": ret})

@explgbk_blueprint.route("/lgbk/ws/experiments_with_user_as_collaborator", methods=["GET"])
def svc_get_experiments_with_user_as_collaborator():
    """
    Returns a list of experiment for which the user is listed as a collaborator in the roles
    This information originally comes from URAWI.
    Note this call expects a userid as a parameter and returns a minimal amount of information.
    It is used primarily for backend integration with other systems.
    For a more comprehensive list of experiments for a user, please use the /experiments calls.
    """
    uid = request.args.get("uid", None)
    if not uid:
        return logAndAbort("Please specify a uid")
    
    return JSONEncoder().encode({"success": True, "value": get_direct_experiments_for_user(uid)})

@explgbk_blueprint.route("/lgbk/ws/search_experiment_info", methods=["GET"])
@context.security.authentication_required
def svc_search_experiment_info():
    """
    Perform a text search against the cached experiment info.
    This only searches against basic information like the name, description, PI etc.
    """
    search_terms = request.args.get("search_text", "")
    experiments = get_experiments_for_user(context.security.get_current_user_id())
    matching_experiment_names = [x["name"] for x in text_search_for_experiments(search_terms)]
    user_matches = [x for x in experiments if x["name"] in matching_experiment_names]
    return jsonify({'success': True, 'value': user_matches})


@explgbk_blueprint.route("/lgbk/ws/postable_experiments", methods=["GET"])
@context.security.authentication_required
def svc_get_experiments_with_post_privileges():
    """
    Get the list of experiments that the logged in user has post privileges for.
    The list of players with post privileges is stored in the experiment cache.
    If the logged in user (or one of her groups) is in the site database, we return all experiments.
    Else we query the experiment cache and return those.
    """
    userid = context.security.get_current_user_id()
    return jsonify({'success': True, 'value': get_experiments_with_post_privileges(userid, get_currently_active_experiments())})

@explgbk_blueprint.route("/lgbk/ws/get_cached_experiment_names", methods=["GET"])
def svc_get_cached_experiment_names():
    """
    Get a list of the cached experiment names.
    Mainly meant for debugging.
    """
    return jsonify({'success': True, 'value': get_cached_experiment_names()})


@explgbk_blueprint.route("/lgbk/ws/experiment_names_updated_within", methods=["GET"])
def svc_get_recently_updated_experiments():
    """
    Get a list of the experiments which have had updates within the specified time
    What constitutes as updated is for now restricted to the experiment's run.begin_times.
    This may be enhanced in the future to include elog/workflow_jobs etc.
    :param: Specify the time offset as offset_seconds
    """
    offset_secs = int(request.args.get("offset_secs", str(8*60*60))) # Defaults to a shift
    return jsonify({'success': True, 'value': get_recently_updated_experiments(offset_secs)})

@explgbk_blueprint.route("/lgbk/ws/instruments", methods=["GET"])
@context.security.authentication_required
def svc_get_instruments():
    """
    Get the list of instruments
    """
    return jsonify({'success': True, 'value': get_instruments()})

@explgbk_blueprint.route("/lgbk/ws/experiment_stats", methods=["GET"])
@context.security.authentication_required
def svc_get_experiment_stats():
    """
    Get various experiment stats
    """
    return jsonify({'success': True, 'value': get_experiment_stats()})

@explgbk_blueprint.route("/lgbk/ws/experiment_daily_data_breakdown", methods=["GET"])
@context.security.authentication_required
def svc_get_experiment_daily_data_breakdown():
    """
    Get the daily data breakdown; that is, data moved by day
    """
    instrument = request.args.get("instrument", "ALL")
    report_type = request.args.get("report_type", "file_sizes")
    return JSONEncoder().encode({'success': True, 'value': get_experiment_daily_data_breakdown(report_type, instrument)})

@explgbk_blueprint.route("/lgbk/ws/instrument_station_list", methods=["GET"])
@context.security.authentication_required
def svc_instrument_station_list():
    """
    Get the list of possible instrument/station pairs as a list.
    """
    return JSONEncoder().encode({'success': True, 'value': get_instrument_station_list()})

@explgbk_blueprint.route("/lgbk/ws/activeexperiments", methods=["GET"])
@context.security.authentication_required
def svc_get_active_experiments():
    """
    Get the list of currently active experiments at each instrument/station.
    """
    return JSONEncoder().encode({'success': True, 'value': get_currently_active_experiments()})


@explgbk_blueprint.route("/lgbk/ws/potentiallyactiveusers", methods=["GET"])
@context.security.authentication_required
def svc_get_potentially_active_users():
    """
    Get the list of users in experiments whose end date is after the specified date.
    The date is specified as the number of days as the query parameter cutoff_days.
    We include experiments whose end time is greater than or equal to cutoff_days before today.
    If a date is not specified, we use 3 years before now as a cutoff
    Return a list of users ( without the uid: in the prefix )
    """
    cutoff_days_str = request.args.get("cutoff_days", None)
    if not cutoff_days_str:
        cutoff_date = datetime.utcnow() - timedelta(days=365*3)
    else:
        cutoff_date = datetime.utcnow() - timedelta(days=int(cutoff_days_str))
    logger.info("Getting users from experiments after %s", cutoff_date)

    return JSONEncoder().encode({'success': True, 'value': get_potentially_active_users(cutoff_date)})

@explgbk_blueprint.route("/lgbk/ws/activeexperiment_for_instrument_station", methods=["GET"])
def svc_get_active_experiment_for_instrument_station():
    """
    Get the currently active experiment for a particular instrument/station.
    :param: instrument_name - Name of the instrument, for example XPP
    :param: station - Station number; defaults to 0.
    """
    instrument_name = request.args.get("instrument_name", None)
    if not instrument_name:
        return logAndAbort("Please pass in the instrument name, for example, XPP")
    station_num = int(request.args.get("station", "0"))
    active_experiment = get_active_experiment_name_for_instrument_station(instrument_name, station_num)
    if active_experiment:
        return JSONEncoder().encode({'success': True, 'value': active_experiment})
    else:
        return logAndAbort("Cannot find a valid active experiment for %s/%s, found %s" % (instrument_name, station_num, active_experiment))


@explgbk_blueprint.route("/lgbk/ws/usergroups", methods=["GET"])
@context.security.authentication_required
def svc_getUserGroupsForAuthenticatedUser():
    """
    Get the user id and groups for the authenticated user
    """
    userid = context.security.get_current_user_id()
    groups = context.usergroups.get_user_posix_groups(userid)
    return jsonify({'success': True, 'value': { "userid": userid, "groups": groups }})


@explgbk_blueprint.route("/lgbk/ws/instruments/", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("instrument_create")
def svc_create_instrument():
    """
    Create a new instrument. Pass in the document..
    """
    info = request.json
    if not info:
        return logAndAbort("Creating instrument missing info document")

    necessary_keys = set(['_id', 'description'])
    missing_keys = necessary_keys - info.keys()
    if missing_keys:
        return logAndAbort("Creating instrument missing keys %s" % missing_keys)

    if info["_id"] in set([x["_id"] for x in get_instruments()]):
        return logAndAbort("Instrument %s already exists" % info["_id"])

    (status, errormsg) = create_update_instrument(info["_id"], True, info)
    if status:
        context.kafka_producer.send("instruments", {"instrument_name" : info["_id"], "CRUD": "Create", "value": info })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})


@explgbk_blueprint.route("/lgbk/ws/instruments/<insid>", methods=["PUT"])
@context.security.authentication_required
@context.security.authorization_required("instrument_create")
def svc_update_instrument(insid):
    """
    Update an existing instrument. Pass in the document.
    """
    info = request.json
    if not info:
        return logAndAbort("Creating instrument missing info document")

    necessary_keys = set(['_id', 'description'])
    missing_keys = necessary_keys - info.keys()
    if missing_keys:
        return logAndAbort("Creating instrument missing keys %s" % missing_keys)
    
    if info["_id"] != insid:
        return logAndAbort("Instrument names do not match")

    if info["_id"] not in set([x["_id"] for x in get_instruments()]):
        return logAndAbort("Instrument %s does not exist" % info["_id"])

    (status, errormsg) = create_update_instrument(info["_id"], False, info)
    if status:
        context.kafka_producer.send("instruments", {"instrument_name" : info["_id"], "CRUD": "Update", "value": info })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})


@explgbk_blueprint.route("/lgbk/ws/global_roles", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("manage_groups")
def svc_get_global_roles():
    return JSONEncoder().encode({"success": True, "value": get_global_roles()})

@explgbk_blueprint.route("/lgbk/ws/add_player_to_global_role", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("manage_groups")
def svc_add_player_to_global_role():
    info = request.json
    if not info:
        return logAndAbort("Please specify parameters as a JSON document")

    role = info.get("role", None)
    if not role:
        return logAndAbort("Please specify a role")
    player = info.get("player", None)
    if not player:
        return logAndAbort("Please specify a player")

    return JSONEncoder().encode({"success": True, "value": add_player_to_global_role(player, role)})

@explgbk_blueprint.route("/lgbk/ws/remove_player_from_global_role", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("manage_groups")
def svc_remove_player_from_global_role():
    info = request.json
    if not info:
        return logAndAbort("Please specify parameters as a JSON document")

    role = info.get("role", None)
    if not role:
        return logAndAbort("Please specify a role")
    player = info.get("player", None)
    if not player:
        return logAndAbort("Please specify a player")

    return JSONEncoder().encode({"success": True, "value": remove_player_from_global_role(player, role)})

@explgbk_blueprint.route("/lgbk/ws/add_player_to_instrument_role", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("manage_groups")
def svc_add_player_to_instrument_role():
    info = request.json
    if not info:
        return logAndAbort("Please specify parameters as a JSON document")

    instrument = info.get("instrument", None)
    if not instrument:
        return logAndAbort("Please specify a instrument")
    role = info.get("role", None)
    if not role:
        return logAndAbort("Please specify a role")
    player = info.get("player", None)
    if not player:
        return logAndAbort("Please specify a player")

    return JSONEncoder().encode({"success": True, "value": add_player_to_instrument_role(instrument, player, role)})

@explgbk_blueprint.route("/lgbk/ws/remove_player_from_instrument_role", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("manage_groups")
def svc_remove_player_from_instrument_role():
    info = request.json
    if not info:
        return logAndAbort("Please specify parameters as a JSON document")

    instrument = info.get("instrument", None)
    if not instrument:
        return logAndAbort("Please specify a instrument")
    role = info.get("role", None)
    if not role:
        return logAndAbort("Please specify a role")
    player = info.get("player", None)
    if not player:
        return logAndAbort("Please specify a player")

    return JSONEncoder().encode({"success": True, "value": remove_player_from_instrument_role(instrument, player, role)})

@explgbk_blueprint.route("/lgbk/ws/lookup_experiment_in_urawi", methods=["GET"])
@context.security.authentication_required
def svc_lookup_experiment_in_URAWI():
    """
    Lookup the specified experiment in URAWI and return the information from URAWI as the value.
    """
    experiment_name = request.args.get("experiment_name", None)
    proposal_id = request.args.get("PNR", None)
    urawi_doc = get_URAWI_details(experiment_name, proposal_id)
    if urawi_doc and urawi_doc.get("status", "error") == "success":
        return jsonify({'success': True, "value": urawi_doc})
    return jsonify({'success': False})

@explgbk_blueprint.route("/lgbk/ws/register_new_experiment", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("experiment_create")
def svc_register_new_experiment():
    """
    Register a new experiment.
    We expect the experiment_name as a query parameter and the registration information as a JSON document in the POST body.
    """
    experiment_name = request.args.get("experiment_name", None)
    if not experiment_name:
        return logAndAbort("Experiment registration missing experiment_name in query parameters")
    if does_experiment_exist(experiment_name):
        return logAndAbort("Experiment %s already exists" % experiment_name)

    info = request.json
    if not info:
        return logAndAbort("Experiment registration missing info document")

    necessary_keys = set(['instrument', 'start_time', 'end_time', 'leader_account', 'contact_info'])
    missing_keys = necessary_keys - info.keys()
    if missing_keys:
        return logAndAbort("Experiment registration missing keys %s" % missing_keys)
    if info["instrument"] not in set([x["_id"] for x in get_instruments()]):
        return logAndAbort("The instrument specified %s  is not a valid instrument" % info["instrument"])
    if 'posix_group' in info and len(info["posix_group"].strip()) < 1:
        del info['posix_group']

    (status, errormsg) = register_new_experiment(experiment_name, info)

    try:
        import_users_from_URAWI(experiment_name)
    except:
        logger.exception("Exception importing users from URAWI")

    if status:
        context.kafka_producer.send("experiments", {"experiment_name" : experiment_name, "CRUD": "Create", "value": info })
        context.kafka_producer.send("shifts", {"experiment_name" : experiment_name, "CRUD": "Create", "value": get_latest_shift(experiment_name) })
        role_obj = get_role_object(experiment_name, "LogBook/Editor")
        role_obj.update({'collaborators_added': [x for x in get_collaborators_list_for_experiment(experiment_name)], 'collaborators_removed': [], 'requestor': context.security.get_current_user_id()})
        context.kafka_producer.send("roles", {"experiment_name" : experiment_name, "instrument": get_experiment_info(experiment_name)["instrument"], "CRUD": "Update", "value": role_obj })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/ws/experiment_edit_info", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("experiment_edit")
def svc_experiment_edit_info():
    """
    Update the information for an existing experiment.
    We expect the experiment_name as a query parameter and the registration information as a JSON document in the POST body.
    """
    experiment_name = request.args.get("experiment_name", None)
    if not experiment_name:
        return logAndAbort("Experiment registration missing experiment_name in query parameters")

    info = request.json
    if not info:
        return logAndAbort("Experiment registration missing info document")

    necessary_keys = set(['instrument', 'start_time', 'end_time', 'leader_account', 'contact_info'])
    missing_keys = necessary_keys - info.keys()
    if missing_keys:
        return logAndAbort("Experiment registration missing keys %s" % missing_keys)

    (status, errormsg) = update_existing_experiment(experiment_name, info)
    if status:
        context.kafka_producer.send("experiments", {"experiment_name" : experiment_name, "CRUD": "Update", "value": info})
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/ws/clone_experiment", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("experiment_create")
def svc_clone_experiment():
    """
    Copy/clone an existing experiment as a new experiment.
    """
    experiment_name = request.args.get("experiment_name", None)
    if not experiment_name:
        return logAndAbort("Experiment clone missing experiment_name in query parameters")
    src_experiment_name = request.args.get("src_experiment_name", None)
    if not src_experiment_name:
        return logAndAbort("Experiment clone missing src_experiment_name in query parameters")

    info = request.json
    if not info:
        return logAndAbort("Experiment clone missing info document")

    copy_specs = {k.replace("copy_", "") : v for k,v in info.items() if k.startswith("copy_")}
    info = {k : v for k,v in info.items() if not k.startswith("copy_")}

    necessary_keys = set(['start_time', 'end_time'])
    missing_keys = necessary_keys - info.keys()
    if missing_keys:
        return logAndAbort("Experiment clone missing keys %s" % missing_keys)

    (status, errormsg) = clone_experiment(experiment_name, src_experiment_name, info, copy_specs)
    if status:
        context.kafka_producer.send("experiments", {"experiment_name" : experiment_name, "CRUD": "Create", "value": info })
        context.kafka_producer.send("shifts", {"experiment_name" : experiment_name, "CRUD": "Create", "value": get_latest_shift(experiment_name) })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/ws/rename_experiment", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("experiment_edit")
def svc_rename_experiment():
    """
    Rename an existing experiment to a new experiment.
    """
    experiment_name = request.args.get("experiment_name", None)
    if not experiment_name:
        return logAndAbort("Experiment rename missing experiment_name in query parameters")
    new_experiment_name = request.args.get("new_experiment_name", None)
    if not new_experiment_name:
        return logAndAbort("Experiment clone missing src_experiment_name in query parameters")

    old_info = copy.copy(get_experiment_info(experiment_name))

    (status, errormsg) = rename_experiment(experiment_name, new_experiment_name)
    if status:
        context.kafka_producer.send("experiments", {"experiment_name" : new_experiment_name, "CRUD": "Create", "value": get_experiment_info(new_experiment_name) })
        context.kafka_producer.send("experiments", {"experiment_name" : experiment_name, "CRUD": "Delete", "value": old_info })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/add_update_experiment_params", methods=["POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("manage_groups")
def svc_add_update_experiment_params(experiment_name):
    """
    Add or update an experiment's parameters.
    We expect a JSON object of simple name value pairs.
    """
    params = request.json
    if not params:
        return logAndAbort("Please send the experiment parameters as a simple name value pair JSON dictionary")
    status, errormsg = add_update_experiment_params(experiment_name, params)
    if status:
        info = get_experiment_info(experiment_name)
        context.kafka_producer.send("experiments", {"experiment_name" : experiment_name, "CRUD": "Update", "value": info })
    return jsonify({'success': status, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/<experiment_name>/", methods=["DELETE"])
@context.security.authentication_required
@context.security.authorization_required("experiment_delete")
def svc_delete_experiment(experiment_name):
    """
    Delete an experiment.
    This drops the database; so recovery is only possible from backups.
    """
    old_info = copy.copy(get_experiment_info(experiment_name))
    (status, errormsg) = delete_experiment(experiment_name)
    if status:
        context.kafka_producer.send("experiments", {"experiment_name" : experiment_name, "CRUD": "Delete", "value": old_info })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/<experiment_name>/migrate_attachments", methods=["GET", "POST"])
@context.security.authentication_required
@context.security.authorization_required("experiment_delete")
def svc_migrate_attachments(experiment_name):
    """
    Prepare the experiment for archival by migrating attachments to a local image store - most likely mongo.
    The sysadmin is then expected to use mongodump --archive to make a backup of the experiment which should then include the attachments as well.
    """
    (status, errormsg) = migrate_attachments_to_local_store(experiment_name)
    return jsonify({'success': status, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/ws/lock_unlock_experiment", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("experiment_edit")
def svc_lock_unlock_experiment():
    """
    Lock/unlock an experiment.
    """
    experiment_name = request.args.get("experiment_name", None)
    if not experiment_name:
        return logAndAbort("Experiment lock/unlock missing experiment_name in query parameters")

    (status, errormsg) = lock_unlock_experiment(experiment_name)
    if status:
        context.kafka_producer.send("experiments", {"experiment_name" : experiment_name, "CRUD": "Update", "value": get_experiment_info(experiment_name)})
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/ws/reload_experiment_cache", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("edit")
def svc_reload_experiment_cache():
    """
    Reload the cached experiment info. This is also done automatically; use if the caches have no caught up for some reason.
    """
    experiment_name = request.args.get("experiment_name", None)
    if experiment_name:
        reload_experiment_cache(experiment_name=experiment_name)
        return jsonify({'success': True})


    reload_experiment_cache()
    return jsonify({'success': True})

@explgbk_blueprint.route("/lgbk/ws/reload_named_cache", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("edit")
def svc_reload_named_cache():
    """
    Reload the specified named cache.
    """
    cache_name = request.args.get("cache_name", None)
    if cache_name:
        context.kafka_producer.send("explgbk_cache", { "named_cache": cache_name } )
        return jsonify({'success': True})
    return jsonify({'success': False})

@explgbk_blueprint.route("/lgbk/ws/rebuild_experiment_cache_for_experiment", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("edit")
def svc_rebuild_experiment_cache():
    """
    Rebuild the experiment cache for the specified experiment
    """
    experiment_name = request.args.get("experiment_name", None)
    if experiment_name:
        update_single_experiment_info(experiment_name, "Update")
        context.kafka_producer.send("experiments", {"experiment_name" : experiment_name, "CRUD": "Update", "value": get_experiment_info(experiment_name)})
    return jsonify({'success': True})


@explgbk_blueprint.route("/lgbk/ws/switch_experiment", methods=["POST"])
@context.security.authentication_required
@instrument_exists
@context.security.authorization_required("switch")
def svc_switch_experiment():
    """
    Switch the active experiment at an instrument station.
    """
    info = request.json
    if not info:
        return jsonify({'success': False, 'errormsg': "No data supplied.."})

    experiment_name = info.get("experiment_name", None)
    if not experiment_name:
        return jsonify({'success': False, 'errormsg': "No experiment name"})

    instrument = info.get("instrument", None)
    if not instrument:
        return jsonify({'success': False, 'errormsg': "No instrument given"})

    if 'station' not in info:
        return jsonify({'success': False, 'errormsg': "No station given."})

    station = int(info.get("station"))

    info_from_database = get_experiment_info(experiment_name)
    if not info_from_database:
        return jsonify({'success': False, 'errormsg': "Experiment does not exist in the database"})

    if info_from_database["instrument"] != instrument:
        return jsonify({'success': False, 'errormsg': "Trying to switch experiment on instrument %s for experiment on %s" % (instrument, info_from_database["instrument"])})

    if experiment_name in [ x.get('name', '') for x in get_currently_active_experiments() ]:
        return jsonify({'success': False, 'errormsg': "Trying to switch experiment %s onto instrument %s but it is already currently active" % (experiment_name, instrument)})

    if context.LOGBOOK_SITE in ["LCLS"] and os.path.exists("/reg/g/psdm/data/ExpNameDb/experiment-db.dat"):
        logger.info("Checking to see if the experiment exists in the old style file naming list of experiments - /reg/g/psdm/data/ExpNameDb/experiment-db.dat")
        with open("/reg/g/psdm/data/ExpNameDb/experiment-db.dat", 'r') as f:
            lines = f.readlines()
            if experiment_name in [ x.split()[2] for x in lines ]:
                return jsonify({'success': False, 'errormsg': "The experiment %s is using old style file names as it exists in /reg/g/psdm/data/ExpNameDb/experiment-db.dat. Mixing and matching file name conventions is not supported." % (experiment_name)})

    userid = context.security.get_current_user_id()

    previously_active_experiment = get_active_experiment_name_for_instrument_station(instrument, station)

    (status, errormsg) = switch_experiment(instrument, station, experiment_name, userid)
    if status:
        expswdoc = {
            "instrument": instrument,
            "station": station,
            "experiment_name": experiment_name,
            "userid": userid,
        }
        if previously_active_experiment:
            expswdoc["previous_experiment_name"] = previously_active_experiment["name"]
        context.kafka_producer.send("experiment_switch", {"experiment_name" : experiment_name, "value": expswdoc})

        # We may add/remove operator_uid's etc Rebuild the caches for affected instruments.
        context.kafka_producer.send("experiments", {"experiment_name" : experiment_name, "CRUD": "Update", "value": get_experiment_info(experiment_name) })
        if previously_active_experiment:
            context.kafka_producer.send("experiments", {"experiment_name" : previously_active_experiment["name"], "CRUD": "Update", "value": get_experiment_info(previously_active_experiment["name"]) })

        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})


@explgbk_blueprint.route("/lgbk/ws/instrument_standby", methods=["POST"])
@context.security.authentication_required
@instrument_exists
@context.security.authorization_required("switch")
def svc_instrument_standby():
    """
    Put the specified instrument/station into standby mode.
    """
    info = request.json
    if not info:
        return jsonify({'success': False, 'errormsg': "No data supplied.."})

    instrument = info.get("instrument", None)
    if not instrument:
        return jsonify({'success': False, 'errormsg': "No instrument given"})

    if not "station" in info:
        return jsonify({'success': False, 'errormsg': "No station given."})

    station = info.get("station", None)

    userid = context.security.get_current_user_id()
    previously_active_experiment = get_active_experiment_name_for_instrument_station(instrument, station)

    (status, errormsg) = instrument_standby(instrument, station, userid)
    if status:
        context.kafka_producer.send("instrument_standby", {"value": {
            "instrument": instrument,
            "station": station,
            "userid": userid
        }})

        if previously_active_experiment:
            context.kafka_producer.send("experiments", {"experiment_name" : previously_active_experiment["name"], "CRUD": "Update", "value": get_experiment_info(previously_active_experiment["name"]) })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/ws/instrument_switch_history", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def svc_instrument_switch_history():
    """
    Get the history of experiment switches for an instrument/station.
    """
    return JSONEncoder().encode({"success": True, "value":get_switch_history(request.args["instrument"], int(request.args["station"]))})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/has_role", methods=["GET"])
@context.security.authentication_required
@experiment_exists
def svc_has_role(experiment_name):
    """
    Check's if the logged in user has a role.
    """
    # Should this check for a privilege? For now, we stop at roles.
    role_fq_name = request.args.get("role_fq_name", None)
    if not role_fq_name:
        return logAndAbort("Please pass in a fully qualified role name like LogBook/Editor")
    application_name, role_name = role_fq_name.split("/")
    return JSONEncoder().encode({"success": True,
        "value": {
            "role_fq_name": role_fq_name, "application_name": application_name, "role_name": role_name,
            "hasRole": context.roleslookup.has_slac_user_role(context.security.get_current_user_id(), application_name, role_name, experiment_name, instrument=g.instrument)
        }})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/elog", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_elog_entries(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_elog_entries(experiment_name, sample_name=request.args.get("sampleName", None))})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/attachment", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_elog_attachment(experiment_name):
    entry_id = request.args.get("entry_id", None)
    attachment_id = request.args.get("attachment_id", None)
    prefer_preview = request.args.get("prefer_preview", "False").lower() == "true"
    logger.info("Fetching attachment %s for entry %s prefer_preview is %s",  attachment_id, entry_id, prefer_preview)
    entry = get_specific_elog_entry(experiment_name, entry_id)
    for attachment in entry.get("attachments", None):
        if str(attachment.get("_id", None)) == attachment_id:
            if prefer_preview:
                file_type = "image/png"
                if "preview_url" in attachment:
                    logger.debug("Returning preview")
                    remote_url = attachment.get("preview_url", None)
                else:
                    return send_file('static/attachment.png')
            else:
                logger.debug("Returning main document")
                remote_url = attachment.get("url", None)
                file_type = attachment['type']
            if remote_url:
                urlcontents = parseImageStoreURL(remote_url).return_url_contents(experiment_name, remote_url)
                resp = make_response(send_file(urlcontents, mimetype=file_type))
                if not (attachment["type"].startswith("image") or "preview_url" in attachment):
                    resp.headers["Content-Disposition"] = 'attachment; filename="' + attachment["name"] + '"'
                return resp

    return Response("Cannot find attachment " + attachment_id , status=404)

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/ext_preview/<path:path>", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_ext_preview(experiment_name, path):
    """
    Send a redirect to an external path, as defined by the PREVIEW_PREFIX environment variable.
    Used to serve large previews from a web server.
    Authorization is performed in this method and a HTTP redirect is sent to PREVIEW_PREFIX/path.
    See docs/external_previews for more details.
    """
    path = path.replace("<experiment_name>", experiment_name)
    m = hashlib.md5()
    m.update(experiment_name.encode('utf-8'))
    m.update(context.PREVIEW_PREFIX_SHARED_SECRET.encode('utf-8'))
    # path = path.replace("<hash>", urllib.parse.quote(base64.standard_b64encode(m.hexdigest().encode())))
    response = make_response(redirect(context.PREVIEW_PREFIX + "/" + path))
    response.set_cookie("LGBK_EXT_PREVIEW", urllib.parse.quote(base64.standard_b64encode(m.hexdigest().encode())))
    return response


def send_elog_as_email(experiment_name, elog_doc, email_to):
    """
    Send the elog document as an emails to the specified list.
    """
    try:
        full_email_addresses = [ x + "@slac.stanford.edu" if '@' not in x else x for x in email_to]
        logger.info("Sending elog " + elog_doc["content"] + " for experiment " + experiment_name + " as an email to " + ",".join(full_email_addresses));
        if(len(list(filter(lambda x: "@" in x , full_email_addresses)))) != len(full_email_addresses):
            logger.error("Not all addresss in the email To list have a @ character. Not sending mail %s", full_email_addresses)
            return False
        def generateEMailMsgFromELogDoc(elog_doc):
            msg = EmailMessage()
            tz = pytz.timezone('America/Los_Angeles')
            msg_by_at = (elog_doc.get("author", ""), elog_doc.get("relevance_time", datetime.utcnow()).astimezone(tz).strftime('%b/%d/%Y %H:%M:%S'))
            if 'title' in elog_doc:
                msg.make_mixed()
                htmlmsg = EmailMessage()
                htmlmsg.make_alternative()
                htmlmsg.add_alternative(
                    "<p><span>By:</span><span style='padding-left: 0.5em; font-weight: bold'>{0}</span> <span>at:</span><span style='padding-left: 0.5em; font-weight: bold'>{1}</span> </p>\n".format(*msg_by_at)
                    + elog_doc["content"], subtype='html')
                msg.attach(htmlmsg)
            else:
                msg.set_content("By: {0} at: {1}\n\n".format(*msg_by_at) + elog_doc["content"])
                msg.make_mixed()
            for attachment in elog_doc.get("attachments", []):
                if 'type' in attachment and '/' in attachment['type']:
                    maintype, subtype = attachment['type'].split('/', 1)
                else:
                    maintype, subtype = "application", "data"
                with parseImageStoreURL(attachment["url"]).return_url_contents(experiment_name, attachment["url"]) as imgget:
                    msg.add_attachment(imgget.read(), maintype=maintype, subtype=subtype, filename=attachment['name'])
            return msg

        msg = generateEMailMsgFromELogDoc(elog_doc)
        msg['Subject'] = '' + "Elog message for " + experiment_name + " " + ("run {0} ".format(elog_doc["run_num"]) if elog_doc.get("run_num", None) else "") + elog_doc.get("title", "")
        msg['From'] = 'exp_logbook_robot@slac.stanford.edu'
        msg['To'] = ", ".join(full_email_addresses)
        parent_msg = msg
        while elog_doc.get("parent", None):
            elog_doc = get_specific_elog_entry(experiment_name, elog_doc["parent"])
            child_message = generateEMailMsgFromELogDoc(elog_doc)
            parent_msg.attach(child_message)
            parent_msg = child_message

        with smtplib.SMTP(os.environ.get("EMAIL_SERVER_HOST", "smtp.slac.stanford.edu"), int(os.environ.get("EMAIL_SERVER_PORT", "25"))) as s:
            mailstatus = s.sendmail(msg['From'], full_email_addresses, msg.as_string())
            if mailstatus:
                logger.warn(mailstatus)
            s.quit()
    except Exception:
        logger.exception("Exception sending elog emails for experiment " + experiment_name)

    return True

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/elog/<entry_id>/complete_elog_tree", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_complete_elog_tree_for_specified_id(experiment_name, entry_id):
    complete_tree = get_complete_elog_tree_for_specified_id(experiment_name, entry_id)
    return JSONEncoder().encode({'success': True, 'value': complete_tree})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/new_elog_entry", methods=["POST"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("post")
def svc_post_new_elog_entry(experiment_name):
    """
    Create a new log entry.
    Process multi-part file upload
    """
    experiment_name = experiment_name.replace(" ", "_")
    log_content = request.form["log_text"]

    if not log_content or not log_content.strip():
        return logAndAbort("Cannot post empty message")

    author = context.security.get_current_user_id()
    if request.form.get("author", None):
        author = request.form["author"]
        logger.debug("Overriding the author with %s", author)
        if not author.endswith("opr") and (author == "" or not context.usergroups.get_userids_matching_pattern(author)):
            raise Exception(f"Cannot override author with non-existent user {author}")

    optional_args = {}
    parent = request.form.get("parent", None)
    if parent:
        logger.debug("We are creating a followup entry for " + parent + " for experiment " + experiment_name)
        parent_entry = get_specific_elog_entry(experiment_name, parent)
        if parent_entry:
            optional_args["parent"] = parent_entry["_id"] # This should give back the oid
            parent_root = parent_entry.get("root", None) # This should give back the oid
            optional_args["root"] = parent_root if parent_root else parent_entry["_id"] # both should be oids
        else:
            return logAndAbort("Cannot find parent entry for followup log message for experiment " + experiment_name + " for parent oid " + parent)

    run_num_str = request.form.get("run_num", None);
    if run_num_str:
        if run_num_str == "current":
            current_run_doc = get_current_run(experiment_name)
            if current_run_doc and "num" in current_run_doc:
                optional_args["run_num"] = current_run_doc["num"]
        else:
            try:
                run_num = int(run_num_str)
            except ValueError:
                run_num = run_num_str # Cryo uses strings for run numbers.
            run_doc = get_run_doc_for_run_num(experiment_name, run_num)
            if not run_doc:
                return JSONEncoder().encode({'success': False, 'errormsg': "Cannot find run with specified run number - " + str(run_num) + " for experiment " + experiment_name})
            optional_args["run_num"] = run_num

    log_title = request.form.get("log_title", None);
    if log_title:
        optional_args["title"] = log_title

    shift = request.form.get("shift", None);
    if shift:
        shift_obj = get_specific_shift(experiment_name, shift)
        if shift_obj:
            optional_args["shift"] = shift_obj["_id"] # We should get a oid here

    log_emails = request.form.get("log_emails", None)
    if log_emails:
        optional_args["email_to"] = log_emails.split()
        logger.debug("Sending emails to %s", ", ".join(optional_args["email_to"]))

    # The grubber users a followup entry when posting text from an executed command ( typically a bunch of EPICS vars )
    # We don't want to send an email in this case
    skip_email = False
    is_command_followup = request.form.get("command_followup", None)
    if is_command_followup:
        skip_email = True

    log_tags_str = request.form.get("log_tags", None)
    if log_tags_str:
        tags = log_tags_str.split()
        optional_args["tags"] = tags

    is_issue = request.form.get("elog_support_issue", None)
    if is_issue:
        logger.info("Issue detected in experiment %s", experiment_name)
        optional_args["tags"] = optional_args["tags"] + ["ISSUE"] if "tags" in optional_args else ["ISSUE"]
    jira_ticket = request.form.get("jira_ticket", None)
    if jira_ticket:
        logger.info("Associated with an existing JIRA ticket %s", jira_ticket)
        optional_args["jira_ticket"] = jira_ticket
    is_roadblock = request.form.get("elog_support_roadblock", None)
    if is_roadblock:
        logger.info("Roadblock detected in experiment %s", experiment_name)
        optional_args["tags"] = optional_args["tags"] + ["ROADBLOCK"] if "tags" in optional_args else ["ROADBLOCK"]

    post_to_elogs = [ k.replace('post_to_elog_', '') for k, v in request.form.items() if k.startswith('post_to_elog_') and v.lower() == "on" ]

    # Alternate knob for cross posting to the intrument elog (if it exists).
    xpost_instrument_elog = json.loads(request.form.get("xpost_instrument_elog", "false").lower())
    if xpost_instrument_elog:
        instrument_elogs = get_instrument_elogs(experiment_name, include_site_spanning_elogs=False)
        if instrument_elogs:
            post_to_elogs.extend(instrument_elogs)
            post_to_elogs = list(set(post_to_elogs))
    if post_to_elogs:
        optional_args["post_to_elogs"] = post_to_elogs

    logger.debug("Optional args %s ", optional_args)

    files = []
    for upload in request.files.getlist("files"):
        filename = upload.filename.rsplit("/")[0]
        if filename:
            logger.info(filename)
            files.append((filename, upload))
    try:
        inserted_doc = post_new_log_entry(experiment_name, author, log_content, files, **optional_args)
    except LgbkException as e:
        return JSONEncoder().encode({'success': False, 'errormsg': str(e), 'value': None})
    if 'run_num' in inserted_doc:
        sample_obj = get_sample_for_run(experiment_name, inserted_doc['run_num'])
        if sample_obj:
            inserted_doc['sample'] = sample_obj['name']
    context.kafka_producer.send("elog", {"experiment_name" : experiment_name, "CRUD": "Create", "value": inserted_doc})
    logger.debug("Published the new elog entry for %s", experiment_name)

    # Send an email out if a list of emails was specified.
    email_to = inserted_doc.get("email_to", [])
    if not email_to and "root" in inserted_doc:
        email_to = get_specific_elog_entry(experiment_name, inserted_doc["root"]).get("email_to", [])
    email_to.extend(get_elog_email_subscriptions_emails(experiment_name))
    if email_to and not skip_email:
        logger.debug("Sending emails for new elog entry in experiment %s to %s", experiment_name, ",".join(email_to))
        send_elog_as_email(experiment_name, inserted_doc, email_to)

    if "root" in inserted_doc:
        root_posted = get_specific_elog_entry(experiment_name, inserted_doc["root"]).get("post_to_elogs", [])
        if root_posted:
            post_to_elogs.extend(root_posted)

    for  post_to_elog in post_to_elogs:
        post_to_elog = post_to_elog.replace(" ", "_")
        logger.debug("Cross posting entry to %s", post_to_elog)
        rel_ins_doc = post_related_elog_entry(post_to_elog, experiment_name, inserted_doc["_id"])
        if rel_ins_doc:
            logger.debug("Publishing cross post entry to %s", post_to_elog)
            context.kafka_producer.send("elog", {"experiment_name" : post_to_elog, "CRUD": "Create", "value": rel_ins_doc})
            email_to = get_elog_email_subscriptions_emails(post_to_elog)
            if not author.endswith("opr") and author not in email_to:
                logger.info("Adding the author %s as an email recipient of xpost elog entries", author)
                email_to.append(author)
            if email_to and not skip_email:
                logger.debug("Sending emails for cross posted elog entry in experiment %s to %s", post_to_elog, ",".join(email_to))
                send_elog_as_email(post_to_elog, rel_ins_doc, email_to)

    return JSONEncoder().encode({'success': True, 'value': inserted_doc})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/modify_elog_entry", methods=["POST"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("edit")
def svc_modify_elog_entry(experiment_name):
    entry_id = request.args.get("_id", None)
    log_content = request.form["log_text"]
    log_emails = request.form.get("log_emails", None)
    email_to = log_emails.split() if log_emails else None
    log_tags_str = request.form.get("log_tags", None)
    tags = log_tags_str.split() if log_tags_str else []
    title = request.form.get("log_title", None)
    run_num_str = request.form.get("run_num", None)
    if run_num_str:
        try:
            run_num = int(run_num_str)
        except ValueError:
            run_num = run_num_str
        if not get_run_doc_for_run_num(experiment_name, run_num):
            return logAndAbort("Please pass in the a valid run number")
    else:
        run_num = None

    if not entry_id or not log_content:
        return logAndAbort("Please pass in the _id of the elog entry for " + experiment_name + " and the new content")

    files = []
    for upload in request.files.getlist("files"):
        filename = upload.filename.rsplit("/")[0]
        if filename:
            logger.info(filename)
            files.append((filename, upload))

    status = modify_elog_entry(experiment_name, entry_id, context.security.get_current_user_id(), log_content, email_to, tags, files, title, run_num=run_num)
    if status:
        modified_entry = get_specific_elog_entry(experiment_name, entry_id)
        context.kafka_producer.send("elog", {"experiment_name" : experiment_name, "CRUD": "Update", "value": modified_entry})
        previous_version = get_specific_elog_entry(experiment_name, modified_entry["previous_version"])
        context.kafka_producer.send("elog", {"experiment_name" : experiment_name, "CRUD": "Create", "value": previous_version})
        for instr_elog_name, instr_elog_entry in get_related_instrument_elog_entries(experiment_name, entry_id).items():
            context.kafka_producer.send("elog", {"experiment_name" : instr_elog_name, "CRUD": "Update", "value": instr_elog_entry})

        email_to = modified_entry.get("email_to", None)
        if not email_to and "root" in modified_entry:
            email_to = get_specific_elog_entry(experiment_name, modified_entry["root"]).get("email_to", None)
        if email_to:
            send_elog_as_email(experiment_name, modified_entry, email_to)

    return JSONEncoder().encode({"success": status})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/search_elog", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_search_elog(experiment_name):
    search_text   = request.args.get("search_text", "")
    run_num_str   = request.args.get("run_num", None)
    start_run_num_str = request.args.get("start_run_num", None)
    end_run_num_str   = request.args.get("end_run_num", None)
    start_date_str = request.args.get("start_date", None)
    end_date_str   = request.args.get("end_date", None)
    tag_filter = request.args.get("tag", None)
    id_str = request.args.get("_id", None)
    if run_num_str:
        return JSONEncoder().encode({"success": True, "value": get_elogs_for_run_num(experiment_name, int(run_num_str))})
    elif start_run_num_str and end_run_num_str:
        return JSONEncoder().encode({"success": True, "value": get_elogs_for_run_num_range(experiment_name, int(start_run_num_str), int(end_run_num_str))})
    elif id_str:
        return JSONEncoder().encode({"success": True, "value": get_elogs_for_specified_id(experiment_name, id_str)})
    elif start_date_str and end_date_str:
        return JSONEncoder().encode({"success": True, "value": get_elogs_for_date_range(experiment_name, datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M:%S.%fZ'), datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M:%S.%fZ'))})
    elif search_text.startswith("t:"):
        return JSONEncoder().encode({"success": True, "value": get_elog_entries_by_tag(experiment_name, search_text[2:])})
    elif search_text.startswith("x:"):
        return JSONEncoder().encode({"success": True, "value": get_elog_entries_by_regex(experiment_name, search_text[2:])})
    elif len(search_text) < 1 and tag_filter:
        return JSONEncoder().encode({"success": True, "value": get_elog_entries_by_tag(experiment_name, tag_filter)})
    else:
        combined_results = {}
        if search_text in get_elog_authors(experiment_name):
            combined_results.update({ x["_id"] : x for x in get_elog_entries_by_author(experiment_name, search_text) })
        if search_text in get_elog_tags(experiment_name):
            combined_results.update({ x["_id"] : x for x in get_elog_entries_by_tag(experiment_name, search_text) })

        combined_results.update({ x["_id"] : x for x in search_elog_for_text(experiment_name, search_text) })

        if tag_filter:
            tag_entries = get_elog_entries_by_tag(experiment_name, tag_filter)
            combined_results = { x : combined_results[x] for x in set([ y["_id"] for y in tag_entries ]) & combined_results.keys() }

        return JSONEncoder().encode({"success": True, "value": list(sorted(combined_results.values(), key=lambda x : x["insert_time"]))})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/delete_elog_entry", methods=["DELETE"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("delete")
def svc_delete_elog_entry(experiment_name):
    entry_id   = request.args.get("_id", None)
    if not entry_id:
        return logAndAbort("Please pass in the _id of the elog entry for " + experiment_name)
    status = delete_elog_entry(experiment_name, entry_id, context.security.get_current_user_id())
    if status:
        entry = get_specific_elog_entry(experiment_name, entry_id)
        context.kafka_producer.send("elog", {"experiment_name" : experiment_name, "CRUD": "Update", "value": entry})
        for instr_elog_name, instr_elog_entry in get_related_instrument_elog_entries(experiment_name, entry_id).items():
            context.kafka_producer.send("elog", {"experiment_name" : instr_elog_name, "CRUD": "Update", "value": instr_elog_entry})
    return JSONEncoder().encode({"success": status})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/cross_post_elogs", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("post")
def svc_cross_post_elog_entry(experiment_name):
    """
    Cross post an existing elog entry to a instrument elog.
    """
    entry_id = request.args.get("_id", None)
    if not entry_id:
        return logAndAbort("Please pass in the _id of the elog entry for " + experiment_name)
    existing_entry = get_specific_elog_entry(experiment_name, entry_id)
    if not existing_entry:
        return logAndAbort("Cannot find log entry in " + experiment_name)
    post_to_elogs_str = request.args.get("post_to_elogs", None)
    if not post_to_elogs_str:
        return logAndAbort("Please pass in the names of the instrument elogs as post_to_elogs")
    post_to_elogs = post_to_elogs_str.split(",")
    all_elogs_for_id = get_elog_tree_for_specified_id(experiment_name, existing_entry["_id"])
    for post_to_elog in post_to_elogs:
        post_to_elog = post_to_elog.replace(" ", "_")
        logger.debug("Cross posting entry to %s", post_to_elog)
        for elog_for_id in all_elogs_for_id:
            logger.debug("Cross posting entry to %s %s", post_to_elog, elog_for_id["_id"])
            rel_ins_doc = post_related_elog_entry(post_to_elog, experiment_name, elog_for_id["_id"])
            if rel_ins_doc:
                context.kafka_producer.send("elog", {"experiment_name" : post_to_elog, "CRUD": "Create", "value": rel_ins_doc})
    return JSONEncoder().encode({"success": True})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/elog_emails", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_elog_emails(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_elog_emails(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/elog_email_subscriptions", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_elog_email_subscriptions(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_elog_email_subscriptions(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/elog_email_subscribe", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_elog_email_subscribe(experiment_name):
    return JSONEncoder().encode({"success": True, "value": elog_email_subscribe(experiment_name, context.security.get_current_user_id())})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/elog_email_unsubscribe", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_elog_email_unsubscribe(experiment_name):
    return JSONEncoder().encode({"success": True, "value": elog_email_unsubscribe(experiment_name, context.security.get_current_user_id())})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/get_elog_tags", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_elog_tags(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_elog_tags(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/get_instrument_elogs", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_instrument_elogs(experiment_name):
    include_site_spanning_elogs = json.loads(request.args.get("include_site_spanning_elogs", "true"))
    include_instrument_elogs = json.loads(request.args.get("include_instrument_elogs", "true"))
    return JSONEncoder().encode({"success": True, "value": get_instrument_elogs(experiment_name, include_instrument_elogs=include_instrument_elogs, include_site_spanning_elogs=include_site_spanning_elogs)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/files", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_files(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_experiment_files(experiment_name, sample_name=request.args.get("sampleName", None))})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/file_counts_by_extension", methods=["GET"])
@experiment_exists
def svc_exp_file_counts_by_extension(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_exp_file_counts_by_extension(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/<run_num>/files", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_files_for_run(experiment_name, run_num):
    try:
        rnum = int(run_num)
    except ValueError:
        rnum = run_num_str # Cryo uses strings for run numbers.
    return JSONEncoder().encode({"success": True, "value": get_experiment_files_for_run(experiment_name, rnum)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/<run_num>/files_for_live_mode", methods=["GET"])
def svc_get_files_for_run_for_live_mode(experiment_name, run_num):
    """
    Get a minimal set of information for psana live mode.
    Return only the path information for only the xtc/xtc2 files in the xtc folder ( and not it's children ).
    """
    try:
        rnum = int(run_num)
    except ValueError:
        rnum = run_num_str # Cryo uses strings for run numbers.
    return JSONEncoder().encode({"success": True, "value": get_experiment_files_for_run_for_live_mode(experiment_name, rnum)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/<run_num>/files_for_live_mode_at_location", methods=["GET"])
def svc_get_files_for_run_for_live_mode_at_location(experiment_name, run_num):
    """
    Similar to files_for_live_mode.
    In addition to the list of files, we accept a location and add a boolean as to whether we think the file is located there.
    Also include some info on when the run closed etc.
    The relies on the integration with the data mover/file migration messages being processed correctly and updated external to the logbook
    """
    try:
        rnum = int(run_num)
    except ValueError:
        rnum = run_num_str # Cryo uses strings for run numbers.
    location = request.args.get("location", None)
    if not location:
        return logAndAbort("Please pass in a valid data management location name using the location parameter")

    run_doc = get_run_doc_for_run_num(experiment_name, rnum)
    if not run_doc:
        return logAndAbort("Cannot find run number %s for experiment %s" % (rnum, experiment_name))

    return JSONEncoder().encode({"success": True, "value": get_experiment_files_for_run_for_live_mode_at_location(experiment_name, rnum, location)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/files_for_live_mode_at_location", methods=["GET"])
def svc_get_files_for_live_mode_at_location(experiment_name):
    """
    Similar to files_for_live_mode_for_run except for all runs.
    In addition to the list of files, we accept a location and add a boolean as to whether we think the file is located there.
    Also include some info on when the run closed etc.
    The relies on the integration with the data mover/file migration messages being processed correctly and updated external to the logbook
    """
    location = request.args.get("location", None)
    if not location:
        return logAndAbort("Please pass in a valid data management location name using the location parameter")

    ret = get_experiment_files_for_live_mode_at_location(experiment_name, location)
    return JSONEncoder().encode({"success": True, "value": ret})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/runs", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_runs(experiment_name):
    include_run_params = json.loads(request.args.get("includeParams", "true"))
    return JSONEncoder().encode({"success": True, "value": get_experiment_runs(experiment_name, include_run_params, sample_name=request.args.get("sampleName", None))})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/runs/<run_num>", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_run_document(experiment_name, run_num):
    try:
        rnum = int(run_num)
    except ValueError:
        rnum = run_num # Cryo uses strings for run numbers.
    run_doc = get_experiment_run_document(experiment_name, rnum)
    if not run_doc:
        return logAndAbort("Cannot find run document for " + rnum)
    return JSONEncoder().encode({"success": True, "value": run_doc})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/runs_for_calib", methods=["GET"])
@experiment_exists
def svc_get_legacy_runs(experiment_name):
    """
    Accommodate the calibration service; and return run information similar to the old logbook.
    We return information in the form
    {
        "begin_time": 1407350370,
        "end_time": 1407350373,
        "run_num": 32,
        "run_type": "EPICS"
    }
    The times are im PDT.
    """
    run_infos_src = get_experiment_runs(experiment_name, False, sample_name=None)
    tz = pytz.timezone('America/Los_Angeles')
    run_infos = []
    for ri in run_infos_src:
        rinf = { "begin_time": int(ri["begin_time"].astimezone(tz).timestamp()),
            "run_num": ri["num"],
            "run_type": ri.get("type", "DATA")
            }
        if "end_time" in ri and ri["end_time"]:
            rinf["end_time"] = int(ri["end_time"].astimezone(tz).timestamp())
        run_infos.append(rinf)

    return JSONEncoder().encode({"success": True, "value": run_infos})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/shifts", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_shifts(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_experiment_shifts(experiment_name)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/run_tables", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_runtables(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_all_run_tables(experiment_name, g.instrument)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/run_table_data", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_runtable_data(experiment_name):
    tableName = request.args.get("tableName")
    sampleName = request.args.get("sampleName", None)
    return JSONEncoder().encode({"success": True, "value": list(map(replaceInfNan, get_runtable_data(experiment_name, g.instrument, tableName, sampleName=sampleName)))})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/run_table_sources", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_runtable_sources(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_runtable_sources(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/create_update_user_run_table_def", methods=["POST"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("post")
def svc_create_update_user_run_table_def(experiment_name):
    """
    Create or update an existing user definition table.
    """
    logger.error(json.dumps(request.json, indent=2))
    (status, errormsg, rtbl_obj) = create_update_user_run_table_def(experiment_name, g.instrument, request.json)
    if status:
        return JSONEncoder().encode({"success": True, "value": rtbl_obj})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/run_table_editable_update", methods=["POST"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("post")
def svc_run_table_editable_update(experiment_name):
    """
    Update the editable param for the specified run for the experiment.
    :runnum: Specify the run using the runnum parameter.
    :source: Specify the source using the source parameter.
    :value: The new value
    """
    runnum = int(request.form.get("runnum"))
    source = request.form.get("source")
    value = request.form.get("value")
    userid = context.security.get_current_user_id()

    # params.Calibrations is a legacy of old LCLS1 experiments.
    if not source.startswith('editable_params.') and not source.startswith('params.Calibrations/'):
        return logAndAbort("We can only change editable parameters.")
    if source.endswith('.value'):
        source = source.replace(".value", "")
    return JSONEncoder().encode({"success": True, "result": update_editable_param_for_run(experiment_name, runnum, source, value, userid)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/clone_run_table_def", methods=["POST"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("post")
def svc_clone_run_table_def(experiment_name):
    existing_run_table_name = request.args.get("existing_run_table_name", None)
    new_run_table_name = request.args.get("new_run_table_name", None)
    if not existing_run_table_name or not new_run_table_name:
        return logAndAbort("Please specify the a table to clone along with the new name")
    (status, errormsg, val) = clone_run_table_definition(experiment_name, existing_run_table_name, new_run_table_name)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": val})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/replace_system_run_table_def", methods=["POST"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("post")
def svc_replace_system_run_table_def(experiment_name):
    existing_run_table_name = request.form.get("existing_run_table_name", None)
    system_run_table_name = request.form.get("system_run_table_name", None)
    if not existing_run_table_name or not system_run_table_name:
        return logAndAbort("Please specify the a table to use as a replacement along with the system run table name")

    is_instrument = json.loads(request.form.get("is_instrument", "false").lower())
    logger.debug("Making %s a system run table called %s. Is instrument %s", existing_run_table_name, system_run_table_name, is_instrument)
    is_template = json.loads(request.form.get("is_template", "false").lower())

    (status, errormsg, val) = replace_system_run_table_definition(experiment_name, existing_run_table_name, system_run_table_name, instrument=g.instrument if is_instrument else None, is_template=is_template )
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": val})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/clone_system_template_run_tables", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("post")
def svc_clone_system_template_run_tables(experiment_name):
    """
    Some system run tables are marked as templates; these run tables are copied into an experiment on creation.
    To get the latest ( or to install a new template in an old experiment ), use this method to clone any template system run tables into this experiment.
    If there is a run table with the same name as the template, it is not replaced. To get the latest in this case, delete the local run table and rerun this method.
    """
    clone_system_template_run_tables_into_experiment(experiment_name, g.instrument)
    return JSONEncoder().encode({"success": True})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/delete_run_table", methods=["DELETE"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("post")
def svc_delete_run_table(experiment_name):
    table_name = request.values.get("table_name", None)
    if not table_name:
        return logAndAbort("Please specify the table name to delete.")
    is_system_run_table = json.loads(request.values.get("is_system_run_table", "False"))
    if is_system_run_table:
        logger.debug("Deleting system run table")
        if context.security.check_privilege_for_experiment("ops_page", None, None):
            status, errormsg = delete_system_run_table(experiment_name, g.instrument, table_name)
            return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": None})
        else:
            return {"success": False, "errormsg": "Not enough permissions to perform this operation", "value": None}
    else:
        status, errormsg = delete_run_table(experiment_name, table_name)
        return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": None})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/runtables/export_as_csv", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_runtable_export_as_csv(experiment_name):
    """
    Return a CSV of the run table data for the specified run table.
    :param: runtable is the run table name
    :sampleName: export data only for this sample.
    """
    tableName = request.args.get("runtable", None)
    if not tableName:
        return logAndAbort("Please specify the table name to export.")
    sampleName = request.args.get("sampleName", None)
    tbldefs = [x for x in filter(lambda x : x["name"] == tableName and not x.get("is_template", False), get_all_run_tables(experiment_name, g.instrument))]
    if len(tbldefs) != 1:
        return logAndAbort("Cannot find the definition for table " + tableName)
    coltups = [ ("Run Number", "num") ] # List of tuples of label and attr name
    for cdef in tbldefs[0].get("coldefs", []):
        coltups.append((cdef["label"], cdef["source"]))
    tz = pytz.timezone('America/Los_Angeles')
    si = io.StringIO()
    si.write(",".join([x[0] for x in coltups]) + "\n")
    def __tocsv__(obj):
        if isinstance(obj, datetime):
            return obj.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S')
        else:
            return str(obj)
    def __ldget__(obj, attrpath, deflt):
        prts = attrpath.split(".")
        for prt in prts:
            obj = obj.get(prt, {})
        if not obj:
            return deflt
        return __tocsv__(obj)
    for dt in list(map(replaceInfNan, get_runtable_data(experiment_name, g.instrument, tableName, sampleName=sampleName))):
        si.write(",".join([ __ldget__(dt, ct[1], "") for ct in coltups]) + "\n")
    resp = make_response(si.getvalue())
    resp.headers["Content-Disposition"] = "attachment; filename="+tableName+".csv"
    resp.headers["Content-type"] = "text/csv"
    return resp

@explgbk_blueprint.route("/run_control/<experiment_name>/ws/start_run", methods=["GET", "POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_start_run(experiment_name):
    """
    Start a new run for an experiment.
    Pass in the type of the run as a query parameter run_type. This defaults to DATA.
    You can pass in an optional run number; note you cannot use both options for an experiment.
    For example, CryoEM uses the file prefix as the run number as that fits in with their workflow.
    LCLS uses a auto-increment counter.
    One can also pass parameters as a JSON using a POST
    """
    run_type = request.args.get("run_type", "DATA")
    user_specified_run_number = request.args.get("run_num", None)
    if user_specified_run_number:
        try:
            # LCLS uses int run numbers; Cryo users strings.
            rn = int(user_specified_run_number)
            user_specified_run_number = rn
            logger.debug("Converting user specified run number as int %s", user_specified_run_number)
        except ValueError:
            logger.debug("Using run number as is %s", user_specified_run_number)
            pass
    user_specified_start_time_str = request.args.get("start_time", None)
    user_specified_start_time = datetime.strptime(user_specified_start_time_str, '%Y-%m-%dT%H:%M:%S.%fZ') if user_specified_start_time_str else None
    user_specified_sample = request.args.get("sample", None)

    # Here's where we can put validations on starting a new run.
    # Currently; there are none (after discussions with the DAQ team)
    # But we may want to make sure the previous run is closed, the specified experiment is the active one etc.

    run_doc = get_current_run(experiment_name)
    if run_doc and not run_doc.get("end_time", None):
        logger.warn("Previous run for experiment %s was not closed; closing it", experiment_name)
        try:
            run_doc = __end_run_and_publish_message__(experiment_name)
        except:
            logger.exception("Exception closing previous unclosed run for experiment %s", experiment_name)

    params = { escape_chars_for_mongo(k) : v for k, v in request.get_json().items() }  if request.is_json else None

    run_doc = start_run(experiment_name, run_type, user_specified_run_number, user_specified_start_time, user_specified_sample, params=params)

    sample_obj = get_sample_for_run(experiment_name, run_doc['num'])
    if sample_obj:
        run_doc['sample'] = sample_obj['name']

    context.kafka_producer.send("runs", {"experiment_name" : experiment_name, "CRUD": "Create", "value": run_doc})
    logger.debug("Published the new run for %s", experiment_name)

    return JSONEncoder().encode({"success": True, "value": run_doc})

def __end_run_and_publish_message__(experiment_name, user_specified_end_time=None):
    run_doc = end_run(experiment_name, user_specified_end_time)

    sample_obj = get_sample_for_run(experiment_name, run_doc['num'])
    if sample_obj:
        run_doc['sample'] = sample_obj['name']
    try:
        run_doc["duration"] = (run_doc["end_time"] - run_doc["begin_time"]).total_seconds()
    except:
        logger.exception("Exception computing duration for run %s for experiment %s", run_doc["num"], experiment_name)
    run_doc["file_catalog"] = get_experiment_files_for_run(experiment_name, run_doc['num'])
    context.kafka_producer.send("runs", {"experiment_name" : experiment_name, "CRUD": "Update", "value": run_doc})
    return run_doc


@explgbk_blueprint.route("/run_control/<experiment_name>/ws/end_run", methods=["GET", "POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_end_run(experiment_name):
    """
    End the current run; ending the current run is mostly setting the end time.
    """
    user_specified_end_time_str = request.args.get("end_time", None)
    user_specified_end_time = datetime.strptime(user_specified_end_time_str, '%Y-%m-%dT%H:%M:%S.%fZ') if user_specified_end_time_str else None

    run_doc = __end_run_and_publish_message__(experiment_name, user_specified_end_time)
    return JSONEncoder().encode({"success": True, "value": run_doc})


@explgbk_blueprint.route("/run_control/<experiment_name>/ws/current_run", methods=["GET"])
@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/current_run", methods=["GET"])
@experiment_exists
def svc_current_run(experiment_name):
    """
    Get the run document for the current run.
    """
    skipClosedRuns = json.loads(request.args.get("skipClosedRuns", "false"))
    run_doc = get_current_run(experiment_name)
    if not run_doc:
        logger.error("Current run for experiment %s does not exist", experiment_name)
        return JSONEncoder().encode({"success": False, "value": None})
    if skipClosedRuns and run_doc.get("end_time", None):
        logger.error("Current run %s for experiment %s is already closed", run_doc.get("num", ""), experiment_name)
        return JSONEncoder().encode({"success": False, "value": None})

    try:
        # LCLS uses int run numbers. Mongo insists on returning this as a float sometimes.
        run_num_int = int(run_doc["num"])
        run_doc["num"] = run_num_int
    except ValueError:
        pass

    return JSONEncoder().encode({"success": True, "value": run_doc})

@explgbk_blueprint.route("/run_control/<experiment_name>/ws/add_run_params", methods=["POST"])
@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/add_run_params", methods=["POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_add_run_params(experiment_name):
    """
    Takes a dictionary as the POST body and bulk adds these are run parameters to the current run.
    For example, send all the EPICS variables as a JSON dict.
    We make sure the current run is still open (end_time is None)
    """
    user_specified_run_number = request.args.get("run_num", None)
    if user_specified_run_number:
        try:
            rnum = int(user_specified_run_number)
        except ValueError:
            rnum = user_specified_run_number # Cryo uses strings for run numbers.
        current_run_doc = get_run_doc_for_run_num(experiment_name, rnum)
    else:
        current_run_doc = get_current_run(experiment_name)

    # if current_run_doc['end_time']:
    #     return logAndAbort("The current run %s is closed for experiment %s" % (current_run_doc['num'], experiment_name))

    params = request.json
    if len(params) <= 0:
        logger.warn("No run parameters were specified in add_run_params.") # This is not an error; merely something to help with debugging.
        return JSONEncoder().encode({"success": True})
    run_params = {"params." + escape_chars_for_mongo(k) : v for k, v in params.items() }
    run_doc_after = add_run_params(experiment_name, current_run_doc, run_params)
    sample_obj = get_sample_for_run(experiment_name, run_doc_after['num'])
    if sample_obj:
        run_doc_after['sample'] = sample_obj['name']

    context.kafka_producer.send("runs", {"experiment_name" : experiment_name, "CRUD": "Update", "value": run_doc_after})
    return JSONEncoder().encode({"success": True, "value": run_doc_after})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/close_shift", methods=["GET", "POST"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("post")
def svc_close_shift(experiment_name):
    """
    Close the shift specified by the shift name.
    """
    shift_name = request.args.get("shift_name", None)
    if not shift_name:
        return logAndAbort("Need to specify a shift name when closing a shift")

    (status, errormsg) = close_shift_for_experiment(experiment_name, shift_name)
    if status:
        shift_doc = get_shift_for_experiment_by_name(experiment_name, shift_name)
        context.kafka_producer.send("shifts", {"experiment_name" : experiment_name, "CRUD": "Update", "value": shift_doc})
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/create_update_shift", methods=["POST"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("post")
def svc_create_update_shift(experiment_name):
    """
    Create/update a shift.
    Need to pass in the shift_name and a create indicating if this is a create or an update
    """
    shift_name = request.args.get("shift_name", None)
    if not shift_name:
        return logAndAbort("We need a shift_name as a parameter")

    create_str = request.args.get("create", None)
    if not create_str:
        return logAndAbort("Creating shift must have a boolean create parameter indicating if the shift is created or updated.")
    createp = create_str.lower() in set(["yes", "true", "t", "1"])
    logger.debug("Create update shift is %s for %s", createp, create_str)

    info = request.json
    if not info:
        return logAndAbort("Creating shift missing info document")

    necessary_keys = set(['name', 'leader', 'begin_time'])
    missing_keys = necessary_keys - info.keys()
    if missing_keys:
        return logAndAbort("Creating shift missing keys %s" % missing_keys)

    (status, errormsg) = create_update_shift(experiment_name, shift_name, createp, info)
    if status:
        shift_doc = get_shift_for_experiment_by_name(experiment_name, shift_name)
        context.kafka_producer.send("shifts", {"experiment_name" : experiment_name, "CRUD": "Create" if createp else "Update", "value": shift_doc })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/get_latest_shift", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_latest_shift(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_latest_shift(experiment_name)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/samples", methods=["GET"])
@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/samples/", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_samples(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_samples(experiment_name)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/samples/", methods=["POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_create_sample(experiment_name):
    """
    Create a sample.
    """
    sampledetails = request.json
    if not sampledetails.get("name") or not sampledetails["description"]:
        return logAndAbort("A sample must have a name and a description")
    if "_id" in sampledetails:
        return logAndAbort("Cannot specify an id when creating a sample")

    if 'create_associated_run' in sampledetails and sampledetails['create_associated_run']:
        current_run = get_current_run(experiment_name)
        if current_run and not is_run_closed(experiment_name, current_run["num"]):
            return jsonify({'success': False, 'errormsg': ("Cannot switch to and create a run if the current run %s is still open %s" % (current_run["num"], experiment_name))})
        del sampledetails['create_associated_run']
        automatically_create_associated_run = True
    else:
        automatically_create_associated_run = False

    (status, errormsg) = create_sample(experiment_name, sampledetails, automatically_create_associated_run)
    if status:
        sample_doc = get_sample_for_experiment_by_name(experiment_name, sampledetails["name"])
        context.kafka_producer.send("samples", {"experiment_name" : experiment_name, "CRUD": "Create", "value": sample_doc })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/samples/<sampleid>", methods=["PUT"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_update_sample(experiment_name, sampleid):
    """
    Update the speficied sample.
    """
    sampledetails = request.json
    if not sampledetails.get("name") or not sampledetails["description"]:
        return logAndAbort("A sample must have a name and a description")

    (status, errormsg) = update_sample(experiment_name, sampleid, sampledetails)
    if status:
        sample_doc = get_sample_for_experiment_by_name(experiment_name, sampledetails["name"])
        context.kafka_producer.send("samples", {"experiment_name" : experiment_name, "CRUD": "Update", "value": sample_doc })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/samples/<sample_name>", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_sample_by_name(experiment_name, sample_name):
    return JSONEncoder().encode({"success": True, "value": get_sample_for_experiment_by_name(experiment_name, sample_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/samples/<sample_name>", methods=["DELETE"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("edit")
def svc_delete_sample(experiment_name, sample_name):
    status, errormsg, obj = delete_sample_for_experiment(experiment_name, sample_name)
    if status:
        sample_doc = get_sample_for_experiment_by_name(experiment_name, sample_name)
        context.kafka_producer.send("samples", {"experiment_name" : experiment_name, "CRUD": "Delete", "value": sample_doc })
        return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": obj})
    else:
        return jsonify({'success': status, 'errormsg': errormsg})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/current_sample_name", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_current_sample(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_current_sample_name(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/clone_sample", methods=["GET", "POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_clone_sample(experiment_name):
    """
    Clone an existing sample.
    Pass in the existing sample name and the new sample name.
    """
    existing_sample_name = request.args.get("existing_sample_name", None)
    if not existing_sample_name:
        return logAndAbort("Please pass in the existing_sample_name as a parameter")
    new_sample_name = request.args.get("new_sample_name", None)
    if not new_sample_name:
        return logAndAbort("Please pass in the new sample name as a parameter")

    (status, errormsg) = clone_sample(experiment_name, existing_sample_name, new_sample_name)
    if status:
        sample_doc = get_sample_for_experiment_by_name(experiment_name, new_sample_name)
        context.kafka_producer.send("samples", {"experiment_name" : experiment_name, "CRUD": "Create", "value": sample_doc })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/make_sample_current", methods=["GET", "POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_make_sample_current(experiment_name):
    sample_name = request.args.get("sample_name", None)
    if not sample_name:
        return logAndAbort("We need a sample_name as a parameter")

    (status, errormsg) = make_sample_current(experiment_name, sample_name)
    if status:
        sample_doc = get_sample_for_experiment_by_name(experiment_name, sample_name)
        context.kafka_producer.send("samples", {"experiment_name" : experiment_name, "CRUD": "Make_Current", "value": sample_doc })
        userid = context.security.get_current_user_id()
        post_new_log_entry(experiment_name, userid, "Sample {} was activated by {}".format(sample_name, userid), [])
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/stop_current_sample", methods=["GET", "POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_stop_current_sample(experiment_name):
    sample_name = request.args.get("sample_name", None)
    if not sample_name:
        return logAndAbort("We need a sample_name as a parameter")
    (status, errormsg) = stop_current_sample(experiment_name, sample_name)
    if status:
        # Check with Cryp before publishing this message; we do not publish stop when messages when we switch samples.
        # sample_doc = get_sample_for_experiment_by_name(experiment_name, sample_name)
        # context.kafka_producer.send("samples", {"experiment_name" : experiment_name, "CRUD": "Stop", "value": sample_doc })
        userid = context.security.get_current_user_id()
        post_new_log_entry(experiment_name, userid, "Sample {} was stopped by {}".format(sample_name, userid), [])
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/change_sample_for_run", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("edit")
def svc_change_sample_for_run(experiment_name):
    sample_name = request.args.get("sample_name", None)
    if not sample_name:
        return logAndAbort("We need a sample_name as a parameter")

    run_num_str = request.args.get("run_num", None);
    if not run_num_str:
        return logAndAbort("We need a run_num as a parameter")
    try:
        run_num = int(run_num_str)
    except ValueError:
        run_num = run_num_str # Cryo uses strings for run numbers.

    status, errormsg = change_sample_for_run(experiment_name, run_num, sample_name)
    run_doc = get_run_doc_for_run_num(experiment_name, run_num)
    context.kafka_producer.send("runs", {"experiment_name" : experiment_name, "CRUD": "Update", "value": run_doc})
    return jsonify({'success': status, 'errormsg': errormsg})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/register_file", methods=["POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_register_file(experiment_name):
    """
    Registers a new file with the logbook.
    Pass in the JSON document for the file; this has the path, run_num, checksum, create_timestamp, modify_timestamp and size.
    The path is a necessary key; the rest are optional.
    We convert timestamps to Python datetimes; we expect the date time in Javascript UTC format
    If the run_num is not present, we associate the file with the current run.
    """
    info = request.json
    if not info:
        return logAndAbort("Please pass in the file json to register a new file.")

    necessary_keys = set(['path'])

    def attach_current_run(flinfo):
        if 'run_num' not in flinfo.keys():
            current_run_num = get_current_run(experiment_name)['num']
            logger.info("Associating file %s with current run %s", flinfo['path'], current_run_num)
            flinfo['run_num'] = current_run_num

    def convert_timestamps(flinfo):
        for k in flinfo.keys():
            if k.endswith('_timestamp'):
                flinfo[k] = datetime.strptime(flinfo[k], '%Y-%m-%dT%H:%M:%SZ')
                flinfo[k] = flinfo[k] + timedelta(microseconds=1)
        if 'create_timestamp' not in flinfo:
            flinfo['create_timestamp'] = datetime.utcnow()
        if 'modify_timestamp' not in flinfo:
            flinfo['modify_timestamp'] = datetime.utcnow()

    if isinstance(info, list):
        ret_status = []
        for finfo in info:
            missing_keys = necessary_keys - finfo.keys()
            if missing_keys:
                ret_status.append({'success': False, 'errormsg': "File registration missing keys %s" % missing_keys})
                continue

            attach_current_run(finfo)
            convert_timestamps(finfo)

            (status, errormsg) = register_file_for_experiment(experiment_name, finfo)
            if status:
                context.kafka_producer.send("file_catalog", {"experiment_name" : experiment_name, "CRUD": "Create", "value": finfo })
                ret_status.append({'success': True})
            else:
                ret_status.append({'success': False, 'errormsg': errormsg})
        return jsonify(ret_status)
    else:
        missing_keys = necessary_keys - info.keys()
        if missing_keys:
            return logAndAbort("File registration missing keys %s" % missing_keys)

        attach_current_run(info)
        convert_timestamps(info)

        (status, errormsg) = register_file_for_experiment(experiment_name, info)
        if status:
            context.kafka_producer.send("file_catalog", {"experiment_name" : experiment_name, "CRUD": "Create", "value": info })
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/file_available_at_location", methods=["GET", "POST"])
@context.security.authentication_required
@experiment_exists
def svc_file_available_at_location(experiment_name):
    location = request.args.get("location", None)
    if not location:
        return logAndAbort("Please specify the location.")
    if not location in [x["name"] for x in get_dm_locations(experiment_name)]:
        return logAndAbort("Please specify a valid location")
    file_path = request.args.get("file_path", None)
    if not file_path:
        return logAndAbort("Please specify the file path.")
    run_num = request.args.get("run_num", None)
    if not run_num:
        return logAndAbort("Please specify the run number")
    try:
        run_num = int(run_num)
    except ValueError:
        pass
    file_info = file_available_at_location(experiment_name, run_num, file_path, location)
    context.kafka_producer.send("file_catalog", {"experiment_name" : experiment_name, "CRUD": "Update", "value": file_info })
    return jsonify({'success': True})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/check_and_move_run_files_to_location", methods=["GET", "POST"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("post")
def svc_check_and_move_run_files_to_location(experiment_name):
    location = request.args.get("location", None)
    if not location:
        return logAndAbort("Please specify the location.")
    if not location in [x["name"] for x in get_dm_locations(experiment_name)]:
        return logAndAbort("Please specify a valid location")
    run_num = request.args.get("run_num", None)
    if not run_num:
        return logAndAbort("Please specify the run number")
    try:
        run_num = int(run_num)
    except ValueError:
        pass
    restore_missing_files = json.loads(request.args.get("restore_missing_files", "false"))
    file_types_to_restore = request.args.get("file_types_to_restore", "").split(",")
    file_patterns = []
    if not file_types_to_restore:
        logger.debug("Restoring all files")
        file_patterns.append(".*")
    else:
        file_types = get_site_file_types()
        for ftype in file_types_to_restore:
            file_patterns.extend(file_types.get(ftype, {}).get("patterns", []))

    site_config = get_site_config()
    if site_config.get("dm_mover_prefix", None):
        files_for_run = {x["path"] : x for x in get_experiment_files_for_run(experiment_name, run_num)}
        def __any_pattern__(f):
            return any(map(lambda x : re.match(x, f["path"]), file_patterns))
        files_for_run = {x["path"] : x for x in filter(lambda f: __any_pattern__(f), files_for_run.values())}
        resp = requests.post(site_config["dm_mover_prefix"] + "ws/" + experiment_name + "/check_files_for_run", json={
            "location": location,
            "run_num": run_num,
            "experiment_name": experiment_name,
            "instrument": get_experiment_info(experiment_name)["instrument"],
            "restore_missing_files": restore_missing_files,
            "files": [x["path"] for x in files_for_run.values()]
            }).json()
        for mfile, status in resp.get("files", {}).items():
            file_info = files_for_run.get(mfile, None)
            if status == "present" and file_info and not location in file_info.get("locations", {}).keys():
                logger.debug("I think %s is not there but it is already there", mfile)
                file_available_at_location(experiment_name, run_num, mfile, location)
            elif status != "present" and file_info and location in file_info.get("locations", {}).keys():
                logger.debug("I think %s is there but it has been removed", mfile)
                file_not_available_at_location(experiment_name, run_num, mfile, location)

        return JSONEncoder().encode({'success': True, "value": {"run_files": get_experiment_files_for_run(experiment_name, run_num), "matching_files": [x["path"] for x in files_for_run.values()], "dmstatus": resp.get("files", {})} })
    else:
        return JSONEncoder().encode({'success': False, "errormsg": "This site has not been configured with a mover endpoint."})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/collaborators", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_collaborators(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_collaborators(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/exp_posix_group_members", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_posix_group_members(experiment_name):
    """
    Return the group membership in the posix group with the same name as the experiment name.
    We only return the group membership if the experiment's posix group is set and it is the same as the experiment name.
    Otherwise, return a empty list...
    """
    exp_info = get_experiment_info(experiment_name)
    if exp_info.get("posix_group", None) != experiment_name:
        return JSONEncoder().encode({"success": True, "value": []})
    try:
        return JSONEncoder().encode({"success": True, "value": context.usergroups.get_group_members(experiment_name)})
    except:
        logger.exception("Exception getting posix members for %s", experiment_name)
        return JSONEncoder().encode({"success": True, "value": []})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/toggle_role", methods=["GET", "POST"])
@experiment_exists
@context.security.authentication_required
@context.security.authorization_required("manage_groups")
def svc_toggle_role(experiment_name):
    uid = request.args.get("uid", None)
    role_fq_name = request.args.get("role_fq_name", None)
    if not uid or not role_fq_name:
        return logAndAbort("Please specify a uid and role_fq_name")

    role_obj = get_role_object(experiment_name, role_fq_name)
    collaborators_before = get_collaborators_list_for_experiment(experiment_name)
    if role_obj and 'players' in role_obj and uid in role_obj['players']:
        status = remove_collaborator_from_role(experiment_name, uid, role_fq_name)
        collaborators_after = get_collaborators_list_for_experiment(experiment_name)
        collaborators_removed = collaborators_before - collaborators_after
        collaborators_added = []
    else:
        status = add_collaborator_to_role(experiment_name, uid, role_fq_name)
        collaborators_after = get_collaborators_list_for_experiment(experiment_name)
        collaborators_added = collaborators_after - collaborators_before
        collaborators_removed = []

    if status:
        role_obj = get_role_object(experiment_name, role_fq_name)
        role_obj.update({'collaborators_added': [x for x in collaborators_added], 'collaborators_removed': [x for x in collaborators_removed], 'requestor': context.security.get_current_user_id() })
        context.kafka_producer.send("roles", {"experiment_name" : experiment_name, "instrument": get_experiment_info(experiment_name)["instrument"], "CRUD": "Update", "value": role_obj })

    return JSONEncoder().encode({"success": status, "message": "Did not match any entries" if not status else ""})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/add_collaborator", methods=["GET", "POST"])
@experiment_exists
@context.security.authentication_required
@context.security.authorization_required("manage_groups")
def svc_add_collaborator(experiment_name):
    uid = request.args.get("uid", None)
    if not uid:
        return logAndAbort("Please specify a uid")
    role_fq_name = request.args.get("role_fq_name", "LogBook/Reader")

    collaborators_before = get_collaborators_list_for_experiment(experiment_name)
    status = add_collaborator_to_role(experiment_name, uid, role_fq_name)
    collaborators_after = get_collaborators_list_for_experiment(experiment_name)
    collaborators_added = collaborators_after - collaborators_before
    collaborators_removed = []

    if status:
        role_obj = get_role_object(experiment_name, role_fq_name)
        role_obj.update({'collaborators_added': [x for x in collaborators_added], 'collaborators_removed': [x for x in collaborators_removed], 'requestor': context.security.get_current_user_id() })
        context.kafka_producer.send("roles", {"experiment_name" : experiment_name, "instrument": get_experiment_info(experiment_name)["instrument"], "CRUD": "Update", "value": role_obj })
    return JSONEncoder().encode({"success": status, "message": "Did not match any entries" if not status else ""})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/remove_collaborator", methods=["GET", "POST"])
@experiment_exists
@context.security.authentication_required
@context.security.authorization_required("manage_groups")
def svc_remove_collaborator(experiment_name):
    uid = request.args.get("uid", None)
    if not uid:
        return logAndAbort("Please specify a uid")

    collaborator_roles = next(filter(lambda x : x["uid"] == uid, get_collaborators(experiment_name)))
    for role in collaborator_roles['roles']:
        collaborators_before = get_collaborators_list_for_experiment(experiment_name)
        remove_collaborator_from_role(experiment_name, uid, role)
        collaborators_after = get_collaborators_list_for_experiment(experiment_name)
        collaborators_added = []
        collaborators_removed = collaborators_before - collaborators_after
        role_obj = get_role_object(experiment_name, role)
        role_obj.update({'collaborators_added': [x for x in collaborators_added], 'collaborators_removed': [x for x in collaborators_removed], 'requestor': context.security.get_current_user_id() })
        context.kafka_producer.send("roles", {"experiment_name" : experiment_name, "instrument": get_experiment_info(experiment_name)["instrument"], "CRUD": "Update", "value": role_obj })

    return JSONEncoder().encode({"success": True, "message": "Removed collaborator"})


@explgbk_blueprint.route("/lgbk/ws/get_matching_uids", methods=["GET"])
@context.security.authentication_required
def get_matching_uids():
    """
    Get user's who cn matches
    """
    uids = request.args.getlist("uid", None)
    if not uids:
        return logAndAbort("Please specify a uid")
    ret = []
    for uid in uids:
        ret = ret + context.usergroups.get_userids_matching_pattern(uid)
    return JSONEncoder().encode({"success": True, "value": ret})

@explgbk_blueprint.route("/lgbk/ws/get_matching_groups", methods=["GET"])
@context.security.authentication_required
def get_matching_groups():
    group_name = request.args.get("group_name", None)
    if not group_name:
        return logAndAbort("Please specify a group_name")
    return JSONEncoder().encode({"success": True, "value": context.usergroups.get_groups_matching_pattern(group_name)})

def sync_collaborators_with_user_portal(experiment_name):
    logger.info("Importing collaborators from URAWI for %s", experiment_name)
    collaborators_before = get_collaborators_list_for_experiment(experiment_name)
    import_users_from_URAWI(experiment_name)
    collaborators_after = get_collaborators_list_for_experiment(experiment_name)
    collaborators_added = collaborators_after - collaborators_before
    collaborators_removed = []

    if collaborators_added:
        role_obj = get_role_object(experiment_name, "LogBook/Writer")
        role_obj.update({'collaborators_added': [x for x in collaborators_added], 'collaborators_removed': [x for x in collaborators_removed], 'requestor': context.security.get_current_user_id() })
        context.kafka_producer.send("roles", {"experiment_name" : experiment_name, "instrument": get_experiment_info(experiment_name)["instrument"], "CRUD": "Update", "value": role_obj })

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/sync_collaborators_with_user_portal", methods=["GET"])
@experiment_exists
@context.security.authentication_required
@context.security.authorization_required("manage_groups")
def svc_sync_collaborators_with_user_portal(experiment_name):
    sync_collaborators_with_user_portal(experiment_name)
    return JSONEncoder().encode({"success": True})


@explgbk_blueprint.route("/lgbk/ws/sync_collaborators_with_user_portal_for_upcoming_experiments", methods=["GET"])
def svc_sync_collaborators_with_user_portal_for_upcoming_experiments():
    """
    This is used primarily from a cron job to sync with URAWI and get the latest set of collaborators.
    """
    upcoming_experiments = get_experiments_starting_in_time_frame(datetime.utcnow() - timedelta(days=2), datetime.utcnow() + timedelta(days=10))
    for upcoming_experiment in upcoming_experiments:
        if "name" in upcoming_experiment:
            sync_collaborators_with_user_portal(upcoming_experiment["name"])
    return JSONEncoder().encode({"success": True})


@explgbk_blueprint.route("/lgbk/get_modal_param_definitions", methods=["GET"])
@context.security.authentication_required
def svc_get_modal_param_definitions():
    modal_type = request.args.get("modal_type", None)
    if not modal_type:
        return logAndAbort("Please specify a modal_type")
    param_defs = get_modal_param_definitions(modal_type)
    return JSONEncoder().encode({"success": True, "value": param_defs if param_defs else { "_id": modal_type, "params": [] }})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/get_modal_param_definitions", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_modal_param_definitions_for_experiment(experiment_name):
    modal_type = request.args.get("modal_type", None)
    if not modal_type:
        return logAndAbort("Please specify a modal_type")
    param_defs = get_modal_param_definitions(modal_type)
    return JSONEncoder().encode({"success": True, "value": param_defs if param_defs else {}})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/get_feedback_document", methods=["GET"])
@experiment_exists
def get_feedback_document(experiment_name):
    """
    Reconstructs the current feedback document from a questionnaire like history of changes.
    """
    poc_feedback_doc = get_poc_feedback_document(experiment_name)
    return JSONEncoder().encode({"success": True, "value": poc_feedback_doc})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/add_feedback_item", methods=["POST"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("feedback_write")
def add_feedback_item(experiment_name):
    item_name  = request.form.get("item_name", None)
    item_value = request.form.get("item_value", "")
    if not item_name:
        return logAndAbort("Please specify the item name (item_name)")

    add_poc_feedback_item(experiment_name, item_name, item_value, context.security.get_current_user_id())
    # We treat the poc_feedback similar to experiment params and send a Kafka message. Mostly this is to rebuild the cache.
    info = get_experiment_info(experiment_name)
    context.kafka_producer.send("experiments", {"experiment_name" : experiment_name, "CRUD": "Update", "value": info })
    return JSONEncoder().encode({"success": True})

# Tableau integration items - we follow https://jira.slac.stanford.edu/browse/PSWA-61 as much as possible.
@explgbk_blueprint.route("/lgbk/ws/poc_feedback/schema", methods=["GET"])
def get_poc_feedback_schema():
    feedback_defs_file = "static/json/{}/feedback.json".format(context.LOGBOOK_SITE)
    if not os.path.exists(feedback_defs_file):
        return JSONEncoder().encode({"status": "error", "message": "No schema definition found for this site {}".format(context.LOGBOOK_SITE)})
    with open(feedback_defs_file, "r") as f:
        defs = json.load(f)
    # Process the definitions and change some attribute names/values. Use hint for title, value for default_value, data_type for type
    def __map_schema_attrs__(o):
        if isinstance(o, list):
            return [ __map_schema_attrs__(x) for x in o ]
        elif isinstance(o, dict):
            ret = { "title": o["hint"] }
            if "groups" in o and "toggler" not in o:
                ret["groups"] = __map_schema_attrs__(o["groups"])
            else:
                ret["id"] = o["id"]
                if "value" in o:
                    ret["default_value"] = o["value"]
                if "datatype" in o:
                    ret["type"] = o["datatype"]
                else:
                    ret["type"] = {"readonly_text": "Number", "input": "String", "checkbox": "Boolean", "selector": "Number"}.get(o["type"], "String")
                if o["type"] == "selector" or o["type"] == "checkbox" and o.get("notes", False):
                    ret["id_notes"] = o["id"] + "-notes"
                if "groups" in o:
                    ret["groups"] = __map_schema_attrs__(o["groups"])
            return ret
    defs = __map_schema_attrs__(defs)

    return JSONEncoder().encode({"status": "success", "defs": defs })

@explgbk_blueprint.route("/lgbk/ws/poc_feedback/experiments", methods=["GET"])
def svc_get_poc_feedback_experiments():
    """
    Return all the experiments that have non-trivial poc feedback.
    """
    exps = get_poc_feedback_experiments()
    tz = pytz.timezone('America/Los_Angeles')
    ret = []
    for exp in exps:
        x = { "exper_name": exp["name"], "instr_name": exp["instrument"] }
        if exp.get("params", {}).get("PNR", None) and exp.get("params", {}).get("PNR") == "N/A":
            logger.debug("Skipping internal experiment %s", exp["name"])
            continue
        if exp.get("params", {}).get("PNR", None):
            x["proposalNo"] = exp["params"]["PNR"]
        else:
            if len(exp["name"]) == 9:
                # Newer experiments where we include the full proposal ID.
                x["proposalNo"] = exp["name"][3:7].upper()
            elif len(exp["name"]) == 8:
                # Older experiments where we used to drop the L
                x["proposalNo"] = 'L' + exp["name"][3:6].upper()
            else:
                pass
        if "proposalNo" not in x:
            logger.debug("No point sending POC feedback if we cannot map to a URAWI proposal for  %s", exp["name"])
            continue

        if exp.get("poc_feedback", {}).get("last_modified_by", None): x["last_report_uid"] = exp["poc_feedback"]["last_modified_by"]
        if exp.get("poc_feedback", {}).get("last_modified_at", None): x["last_report_time"] = exp["poc_feedback"]["last_modified_at"].astimezone(tz).strftime('%Y-%m-%d %H:%M:%S')
        if exp.get("poc_feedback", {}).get("last_modified_at", None): x["last_modified_at_utc"] = exp["poc_feedback"]["last_modified_at"]
        if exp.get("poc_feedback", {}).get("num_items", None): x["num_items"] = exp["poc_feedback"]["num_items"]
        if exp.get("poc_feedback", {}).get("num_items_4_5", None): x["num_items_4_5"] = exp["poc_feedback"]["num_items_4_5"]
        if exp.get("last_run", {}).get("begin_time", None): x["last_run_begin"] = exp["last_run"]["begin_time"].astimezone(tz).strftime('%Y-%m-%d %H:%M:%S')
        ret.append(x)

    return JSONEncoder().encode({"status": "success", "experiments": ret})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/get_run_params_for_all_runs", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_specified_run_params_for_all_runs(experiment_name):
    """
    Get the specified run parameters for all runs in the experiment.
    For now, this only includes the non-editable parameters submitted by the DAQ.
    Specify the run parameters as a comma separated list in the parameter param_names
    For EPICS fields, watch out for character encoding issues.
    """
    param_names_str = request.args.get("param_names", None)
    if not param_names_str:
        return logAndAbort("Please specify the run parameters as a comma separated list in the parameter param_names)")
    param_names = param_names_str.split(",")
    param_values = get_specified_run_params_for_all_runs(experiment_name, param_names)
    return JSONEncoder().encode({"success": True, "value": param_values})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/get_runs_matching_params", methods=["POST"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_runs_matching_param_values(experiment_name):
    """
    Get an array of run numbers for all runs that have the specified values for the specified parameters.
    We expect a JSON document with name value pairs.
    For now, this only includes the non-editable parameters submitted by the DAQ.
    For EPICS fields, watch out for character encoding issues.
    """
    query_doc = request.json
    if not query_doc:
        return logAndAbort("Please specify the query as a JSON document)")
    run_numbers = get_run_nums_matching_params(experiment_name, query_doc)
    return JSONEncoder().encode({"success": True, "value": run_numbers})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/get_runs_matching_editable", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_run_nums_matching_editable_regex(experiment_name):
    """
    Get an array of run numbers for all runs that have an editable param matching the specified regex.
    We do a case insensitive match.
    This addresses the index/merge use case where we "tag" runs in the UI with a tag using a run table during the indexing step.
    Then during the merge step, we query for runs matching a set of tags.
    """
    param_name = request.args.get("param_name", None)
    if not param_name:
        return logAndAbort("Please specify the parameter name")
    incoming_regex = request.args.get("param_value", None)
    if not incoming_regex:
        return logAndAbort("Please specify the regex to match the value against")

    try:
        run_numbers = get_run_nums_matching_editable_regex(experiment_name, param_name, incoming_regex)
        return JSONEncoder().encode({"success": True, "value": run_numbers})
    except Exception as e:
        logger.exception(e)
        return logAndAbort("Exception fetching run numbers " + str(e))

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/get_runs_with_tag", methods=["GET"])
@experiment_exists
def svc_get_run_nums_matching_tag(experiment_name):
    """
    Runs can be tagged as DARK etc in the elog.
    This call returns a list of run numbers that have elog entries that have the requested tag.
    """
    tag = request.args.get("tag", None)
    if not tag:
        return logAndAbort("Please specify the tag")
    run_numbers = get_run_numbers_with_tag(experiment_name, tag)
    return JSONEncoder().encode({"success": True, "value": run_numbers})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/get_tags_to_runs", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_tag_to_run_numbers(experiment_name):
    """
    Get a dict of tag to the run number that have elog statements containing the tag
    """
    return JSONEncoder().encode({"success": True, "value": get_tag_to_run_numbers(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/get_runs_to_tags", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_tags_for_runs(experiment_name):
    """
    Get a dict of run number to the union of tags for all elog statments associated with that run
    """
    return JSONEncoder().encode({"success": True, "value": get_tags_for_runs(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/<run_num>/get_tags_for_run", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_tags_for_run(experiment_name, run_num):
    """
    Get the union of tags for all elog statments associated with the specified run
    """
    run_num_str = run_num
    try:
        run_num = int(run_num_str)
    except ValueError:
        run_num = run_num_str # Cryo uses strings for run numbers.

    tags_for_runs = get_tags_for_runs(experiment_name)
    return JSONEncoder().encode({"success": True, "value": tags_for_runs.get(run_num, [])})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/map_param_editable_to_run_nums", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_map_param_editable_to_run_nums(experiment_name):
    """
    Given a run param name or an editable name; returns a dict of param value to array of run numbers.
    The method looks at both run params (as uploaded by the DAQ) and editable params (as set by the user)
    Since this is a very user facing call, we let the editable win.
    That is, if there is an editable param with the same name as a run param, we use the editable param as the source of the pivot.
    """
    param_name = request.args.get("param_name", None)
    if not param_name:
        return logAndAbort("Please specify the parameter name")
    return JSONEncoder().encode({"success": True, "value": map_param_editable_to_run_nums(experiment_name, param_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/dm_locations", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_dm_locations(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_dm_locations(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/workflow_definitions", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_wf_definitions(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_workflow_definitions(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/workflow_triggers", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_wf_triggers(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_workflow_triggers(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/create_update_workflow_def", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_create_update_wf_definition(experiment_name):
    """
    Create/update a workflow definition.
    """
    info = request.json
    if not info:
        return logAndAbort("Please pass in the workflow definition as a JSON document.")

    necessary_keys = set(['name', 'executable', 'trigger', 'location', 'parameters'])
    missing_keys = necessary_keys - info.keys()
    if missing_keys:
        return JSONEncoder().encode({"success": False, "errormsg": "Create/update workflow missing keys %s" % missing_keys, "value": None})
    if info['trigger'] not in [x["value"] for x in get_workflow_triggers(experiment_name)]:
        return JSONEncoder().encode({"success": False, "errormsg": "Invalid trigger %s in create/update workflow" % info['trigger'], "value": None})
    if info['location'] not in [ x["name"] for x in get_dm_locations(experiment_name) if "jid_prefix" in x and x["jid_prefix"] ]:
        return JSONEncoder().encode({"success": False, "errormsg": "Invalid location %s in create/update workflow" % info['location'], "value": None})
    info["run_as_user"] = context.security.get_current_user_id()
    if info["run_as_user"] == "root" or (len(info["run_as_user"]) == 6 and info["run_as_user"].endswith("opr")):
        return JSONEncoder().encode({"success": False, "errormsg": "Cannot create a workflow definition for the user %s for security reasons" % info["run_as_user"], "value": None})
    current_wfdefs = { x["name"] : x for x in get_workflow_definitions(experiment_name) }
    if info["name"] in current_wfdefs.keys() and "_id" not in info:
        return JSONEncoder().encode({"success": False, "errormsg": "There already exists a workflow definition for %s" % info["name"], "value": None})


    (status, errormsg, val) = create_update_wf_definition(experiment_name, info)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": val})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/workflow_definitions/<defid>", methods=["DELETE"])
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_create_delete_wf_definition(experiment_name, defid):
    """
    Delete a workflow definition
    """
    (status, errormsg, val) = delete_wf_definition(experiment_name, defid)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": val})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/workflow_jobs", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_wf_jobs(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_workflow_jobs(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/workflow/<job_id>/<path:action>", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_wf_job_action(experiment_name, job_id, action):
    """
    Make a call to the workflow JID for a particular action and proxy the results...
    """
    wf_job = get_workflow_job_doc(experiment_name, job_id)
    if not wf_job:
        return logAndAbort("Cannot find workflow in experiment %s for id %s" % (experiment_name, job_id), 404)
    if action not in ["job_statuses", "job_details", "job_log_file"]:
        return logAndAbort("For security reasons, action %s is not proxied thru the logbook" % (action), 405)
    def __proxy_JID__(location):
        logger.debug("Calling the JID at %s", (location["jid_prefix"]+"jid/ws/"+action))
        client_cert_params = {}
        if "jid_client_key" in location and "jid_client_cert" in location:
            client_cert_params["cert"] = (location["jid_client_cert"], location["jid_client_key"])
        if "jid_ca_cert" in location:
            client_cert_params["verify"] = location["jid_ca_cert"]
        arp_token = context.generateArpToken(context.security.get_current_user_id(), experiment_name)
        # The ARP does an exact match on userid in wf_job; so for these mostly innocent calls, we change the useird on the job doc
        wf_job["user"] = context.security.get_current_user_id()
        req = requests.post(location["jid_prefix"]+"jid/ws/"+experiment_name+"/"+action, data=JSONEncoder().encode(wf_job), stream=True, headers={"Content-Type": "application/json", "Authorization": "Bearer " + arp_token}, **client_cert_params)
        resp = Response(stream_with_context(req.iter_content(chunk_size=1024)))
        return resp

    location = { x["name"] : x for x in get_dm_locations(experiment_name) }.get(wf_job['def']['location'], None)
    if not location:
        return logAndAbort("Cannot determine workflow location in experiment %s for id %s %s" % (experiment_name, job_id, wf_job), 500)

    return __proxy_JID__(location)

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/create_workflow_job", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_create_workflow_job(experiment_name):
    """
    Create/update a workflow job.
    """
    info = request.json
    if not info:
        return logAndAbort("Please pass in the workflow job as a JSON document.")

    necessary_keys = set(['job_name', 'run_num'])
    missing_keys = necessary_keys - info.keys()
    if missing_keys:
        return JSONEncoder().encode({"success": False, "errormsg": "Create/update workflow job missing keys %s" % missing_keys, "value": None})

    def_id = { x["name"]: x for x in get_workflow_definitions(experiment_name) }.get(info["job_name"], {}).get("_id", None)
    if not def_id:
        return JSONEncoder().encode({"success": False, "errormsg": "Cannot find job definition for %s " % info["job_name"], "value": None})
    wf_job_doc = { "run_num": int(info["run_num"]), "def_id": def_id, "user": context.security.get_current_user_id(), "status": "START" }

    (status, errormsg, val) = create_wf_job(experiment_name, wf_job_doc)
    if status:
        context.kafka_producer.send("workflow_jobs", {"experiment_name" : experiment_name, "CRUD": "Create", "value": val })

    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": val})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/delete_workflow_job", methods=["GET", "POST"])
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_delete_workflow_job(experiment_name):
    """
    Delete a workflow job entry given the job _id.
    """
    job_id = request.args.get("job_id", None)
    if not job_id:
        return logAndAbort("Please pass in the workflow job id.")

    (status, errormsg, val) = delete_wf_job(experiment_name, job_id)
    if status:
        context.kafka_producer.send("workflow_jobs", {"experiment_name" : experiment_name, "CRUD": "Delete", "value": val })

    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": val})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/update_workflow_job", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_update_workflow_job(experiment_name):
    """
    Update a workflow job entry; only certain fields can be updated.
    These are - status, counters, tool_id, log_file_path.
    status is an enumeration.
    counters is an array of label/value pairs, the labels and values are both HTML fragments.
    tool_id is a LSF ID/SLURM ID/HPC workload management infrastructure id.
    log_file_path is a path to the log file.
    """
    info = request.json
    if not info:
        return logAndAbort("Please pass in the workflow job as a JSON document.")
    wf_id = info.get("_id", None)
    if not wf_id:
        return logAndAbort("Please pass in the job _id in a JSON document.")

    allowed_keys = ['status', 'counters', 'tool_id', 'log_file_path']
    wf_updates = { k: info[k] for k in allowed_keys if k in info and info[k] }

    (status, errormsg, val) = update_wf_job(experiment_name, wf_id, wf_updates)
    if status:
        context.kafka_producer.send("workflow_jobs", {"experiment_name" : experiment_name, "CRUD": "Update", "value": val })

    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": val})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/kill_workflow_job", methods=["GET", "POST"])
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_kill_workflow_job(experiment_name):
    """
    Kill/terminate a running workflow job.
    """
    job_id = request.args.get("job_id", None)
    if not job_id:
        return logAndAbort("Please pass in the workflow job id.")
    wf_job = get_workflow_job_doc(experiment_name, job_id)
    location_config = { x["name"] : x for x in get_dm_locations(experiment_name)}
    location = location_config[wf_job["def"]["location"]]
    client_cert_params = {}
    if "jid_client_key" in location and "jid_client_cert" in location:
        client_cert_params["cert"] = (location["jid_client_cert"], location["jid_client_key"])
    if "jid_ca_cert" in location:
        client_cert_params["verify"] = location["jid_ca_cert"]
    user_for_token = context.security.get_current_user_id()
    if user_for_token != wf_job["user"]:
        user_for_token = wf_job["user"]
        logger.warning("Only for the kill job, we generate the token as the user %s running the job %s instead of the logged in user %s", user_for_token, wf_job["user"], context.security.get_current_user_id())
    arp_token = context.generateArpToken(user_for_token, experiment_name)
    resp = requests.post(location["jid_prefix"] + "jid/ws/"+experiment_name+"/"+"kill_job", data=JSONEncoder().encode(wf_job), headers={"Content-Type": "application/json", "Authorization": "Bearer " + arp_token}, **client_cert_params)
    respdoc = resp.json()["value"]
    (status, errormsg, val) = update_wf_job(experiment_name, job_id, {"status": respdoc.get("status", wf_job["status"])})
    if status:
        context.kafka_producer.send("workflow_jobs", {"experiment_name" : experiment_name, "CRUD": "Update", "value": val })

    return JSONEncoder().encode({"success": status, "errormsg": errormsg, "value": val})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/generate_arp_token", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_workflow_generate_arp_token(experiment_name):
    """
    Generate a ARP bearer token that is valid for the specified time.
    This is only available if this call ( the one to generate the token ) is made using a Kerberos endpoint.
    Do not allow for other endpoints.
    Please specify token lifetime using the token_lifetime parameter. This is in minutes.
    The max token lifetime is for a shift; so 8*60 minutes = 480 minutes.
    By default, we generate tokens that are valid for 1 minute
    """
    token_lifetime = int(request.args.get("token_lifetime", "1"))
    if token_lifetime > 480:
        return logAndAbort("Cannot generate tokens with lifetimes larger than 480 minutes")
    if request.headers.get("X-Forwarded-Auth-Type", None) != "Kerberos":
        return logAndAbort("Tokens are support only with the ws-kerb endpoint")
    arp_token = context.generateArpToken(context.security.get_current_user_id(), experiment_name, token_lifetime)
    return JSONEncoder().encode({"success": True, "value": arp_token})

@explgbk_blueprint.route("/lgbk/naming_conventions", methods=["GET"])
@context.security.authentication_required
def svc_get_site_naming_conventions():
    """
    Get the site config
    """
    return JSONEncoder().encode({"success": True, "value": get_site_naming_conventions()})

@explgbk_blueprint.route("/lgbk/filemanager_file_types", methods=["GET"])
@context.security.authentication_required
def svc_get_site_filemanager_file_types():
    """
    Get the file manager file types for this site
    """
    return JSONEncoder().encode({"success": True, "value": get_site_file_types()})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/run_param_descriptions", methods=["GET"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("read")
def svc_get_run_param_descriptions(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_run_param_descriptions(experiment_name)})


@explgbk_blueprint.route("/run_control/<experiment_name>/ws/add_update_run_param_descriptions", methods=["POST"])
@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/add_update_run_param_descriptions", methods=["POST"])
@context.security.authentication_required
@experiment_exists
@context.security.authorization_required("post")
def svc_add_update_run_param_descriptions(experiment_name):
    """
    Update the experiment specific run parameter descriptions for this experiment.
    Takes in a dict of attribute name/attribute descriptions.
    """
    param_descs = request.json
    if len(param_descs) <= 0:
        return JSONEncoder().encode({"success": True})
    add_update_run_param_descriptions(experiment_name, param_descs)
    return JSONEncoder().encode({"success": True})


@explgbk_blueprint.route("/lgbk/ws/get_params_matching_prefix", methods=["GET"])
def svc_get_params_matching_prefix():
    """
    Return parameter names across all experiments that match a prefix.
    """
    prefixes = request.args.getlist("prefix")
    if not prefixes:
        return logAndAbort("Please pass in prefixes using the prefix argument")
    pattern = "^(" + "|".join(prefixes) + ")"
    matches = get_all_param_names_matching_regex(pattern)
    return JSONEncoder().encode({"success": True, "value": matches})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/<run_num>/get_params_matching_prefix", methods=["GET"])
def svc_get_params_matching_prefix_for_run(experiment_name, run_num):
    """
    Return parameter names that match a prefix for an experiment/run
    """
    prefixes = request.args.getlist("prefix")
    if not prefixes:
        return logAndAbort("Please pass in prefixes using the prefix argument")
    rgx = "^(" + "|".join(prefixes) + ")"
    patt = re.compile(rgx)
    run_num_str = run_num
    try:
        run_num = int(run_num_str)
    except ValueError:
        run_num = run_num_str # Cryo uses strings for run numbers.

    run_doc = get_run_doc_for_run_num(experiment_name, run_num)
    if not run_doc:
        return JSONEncoder().encode({"success": True, "value": []})
    matches = [ x for x in run_doc.get("params", {}).keys() if patt.match(x) ]
    return JSONEncoder().encode({"success": True, "value": matches})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/<run_num>/daq_run_params", methods=["GET"])
def svc_get_get_daq_run_params(experiment_name, run_num):
    """
    Return special parameters for the specified experiment and run.
    If CalibMan can use auth, then we should eliminate this method and use runs/<run_num>
    Otherwise this returns params that have a standard prefix.
    This mostly applies to the LCLS DAQ.
    """
    std_prefixes = ["Calibrations/", "DAQ Detector Totals/", "DAQ_Detector_Totals/", "DAQ Detectors/", "DAQ_Detectors/"]
    run_num_str = run_num
    try:
        run_num = int(run_num_str)
    except ValueError:
        run_num = run_num_str # Cryo uses strings for run numbers.

    run_doc = get_run_doc_for_run_num(experiment_name, run_num)
    if not run_doc:
        return JSONEncoder().encode({"success": True, "value": []})

    matches = {}
    params = run_doc.get("params", {})
    for k, v in params.items():
        if any(k.startswith(x) for x in std_prefixes):
            matches[k] = v

    return JSONEncoder().encode({"success": True, "value": matches})

@explgbk_blueprint.route("/lgbk/ws/api_endpoints", methods=["GET"])
@context.security.authentication_required
def svc_get_api_endpoints():
    fnnames = []
    for k, v in globals().items():
        if type(v) is types.FunctionType:
            fnnames.append(v.__name__)
    api_endpoints_docs = {}
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint != 'static':
            if current_app.view_functions[rule.endpoint].__doc__:
                epname = current_app.view_functions[rule.endpoint].__name__
                if epname not in api_endpoints_docs:
                    api_endpoints_docs[epname] = []
                api_endpoints_docs[epname].append({ "endpoint": rule.rule, "methods": list(rule.methods - set(["HEAD", "OPTIONS"])),  "docstring": current_app.view_functions[rule.endpoint].__doc__})
    sorted_api_endpoints = []
    for fn in fnnames:
        if fn in api_endpoints_docs:
            sorted_api_endpoints.extend(api_endpoints_docs[fn])
    return JSONEncoder().encode(sorted_api_endpoints)

@explgbk_blueprint.route("/lgbk/ws/projects", methods=["GET"])
@context.security.authentication_required
def svc_get_projects():
    return JSONEncoder().encode({"success": True, "value": get_projects(context.security.get_current_user_id())})

def user_in_project(wrapped_function):
    """
    Check if user is in a project
    """
    @wraps(wrapped_function)
    def function_interceptor(*args, **kwargs):
        project_id = kwargs.get('prjid', None)
        if project_id:
            projectinfo =  get_project_info(project_id)
            if projectinfo:
                if "uid:" + context.security.get_current_user_id() in projectinfo["players"]:
                    g.projectinfo = projectinfo
                    return wrapped_function(*args, **kwargs)
        logger.error("User " + context.security.get_current_user_id() + " does not have permissions to view project " + project_id)
        abort(404)
        return None

    return function_interceptor

@explgbk_blueprint.route("/lgbk/ws/projects/<prjid>", methods=["GET"])
@user_in_project
def svc_get_project_info(prjid):
    projectinfo =  get_project_info(prjid)
    return JSONEncoder().encode({"success": True, "value": projectinfo})

@explgbk_blueprint.route("/lgbk/ws/projects/", methods=["POST"])
@context.security.authentication_required
def svc_create_project():
    prjinfo = request.json
    userid = context.security.get_current_user_id()
    prjinfo["players"] = [ "uid:" + userid ]
    prjinfo["owner"] = userid
    ret = create_project(prjinfo)
    return JSONEncoder().encode({"success": True, "value": ret})

@explgbk_blueprint.route("/lgbk/ws/projects/<prjid>", methods=["PUT"])
@user_in_project
def svc_update_project_info(prjid):
    prjinfo = request.json
    ret = update_project(prjid, prjinfo)
    return JSONEncoder().encode({"success": True, "value": ret})

@explgbk_blueprint.route("/lgbk/ws/projects/<prjid>/grids", methods=["GET"])
@user_in_project
def svc_get_project_grids(prjid):
    projectinfo =  get_project_info(prjid)
    grids = get_project_grids(prjid)
    return JSONEncoder().encode({"success": True, "value": grids})

@explgbk_blueprint.route("/lgbk/ws/projects/<prjid>/grids/<gridid>", methods=["GET"])
@user_in_project
def svc_get_project_grid(prjid, gridid):
    grid = get_project_grid(prjid, gridid)
    return JSONEncoder().encode({"success": True, "value": grid})

@explgbk_blueprint.route("/lgbk/ws/projects/<prjid>/grids/", methods=["POST"])
@user_in_project
def svc_add_grid_to_project(prjid):
    griddetails = request.json
    (status, errormsg) = add_grid_to_project(prjid, griddetails)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg})

@explgbk_blueprint.route("/lgbk/ws/projects/<prjid>/grids/<gridid>", methods=["PUT"])
@user_in_project
def svc_update_project_grid(prjid, gridid):
    griddetails = request.json
    (status, errormsg) = update_project_grid(prjid, gridid, griddetails)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg})

@explgbk_blueprint.route("/lgbk/ws/projects/<prjid>/grids/<gridid>/linksession", methods=["GET"])
@user_in_project
def svc_link_experiment_project_grid(prjid, gridid):
    experiment_name = request.args["experiment_name"]
    (status, errormsg) = link_grid_to_experiment(prjid, gridid, experiment_name)
    return JSONEncoder().encode({"success": status, "errormsg": errormsg})

@explgbk_blueprint.route("/lgbk/ws/projects/<prjid>/sessions", methods=["GET"])
@user_in_project
def svc_get_project_sessions(prjid):
    projectinfo =  get_project_info(prjid)
    sessions = projectinfo.get("sessions", {})
    experiments = { x["name"] : x for x in  get_experiments_for_user(context.security.get_current_user_id())}
    for sessionname, sessiondetails in sessions.items():
        if sessionname in experiments:
            sessiondetails["expinfo"] = experiments[sessionname]
    return JSONEncoder().encode({"success": True, "value": sessions})

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

import requests
import context


from flask import Blueprint, jsonify, request, url_for, Response, stream_with_context

from dal.explgbk import get_experiment_info, save_new_experiment_setup, get_experiments, register_new_experiment, \
    get_instruments, get_currently_active_experiments, switch_experiment, get_elog_entries, post_new_log_entry, get_specific_elog_entry, \
    get_specific_shift, get_experiment_files, get_experiment_runs, get_all_run_tables, get_runtable_data, get_runtable_sources, \
    create_update_user_run_table_def, update_editable_param_for_run, get_instrument_station_list, update_existing_experiment, \
    create_update_instrument

from dal.run_control import start_run, get_current_run, end_run, add_run_params

from dal.utils import JSONEncoder, escape_chars_for_mongo

__author__ = 'mshankar@slac.stanford.edu'

explgbk_blueprint = Blueprint('experiment_logbook_api', __name__)

logger = logging.getLogger(__name__)

def logAndAbort(error_msg):
    logger.error(error_msg)
    return Response(error_msg, status=500)


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/info", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def svc_getexpinfo(experiment_name):
    """
    Get the info for an experiment
    :param experiment_name - The name of the experiment - diadaq13
    :return: The info document for the experiment.
    """
    info = get_experiment_info(experiment_name)
    return JSONEncoder().encode({'success': True, 'value': info})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/info/setup", methods=["POST"])
@context.security.authentication_required
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

categorizers = {
    "instrument": [(lambda exp : exp.get("instrument", None))],
    "instrument_lastrunyear": [(lambda exp : exp.get("instrument", None)), (lambda exp : exp["last_run"]["begin_time"].year if "last_run" in exp else None)]
    }

sorters = {
    "name": ((lambda exp: exp["name"]), False),
    "lastrunyear": ((lambda exp: exp["last_run"]["begin_time"] if "last_run" in exp else exp["start_time"]), True)
    }

def categorize(list, categorizers, sorter):
    ret = {}
    if sorter:
        list = sorted(list, key=sorter[0], reverse=sorter[1])
    for exp in list:
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
    experiments = get_experiments()
    categorizer = categorizers.get(request.args.get("categorize", None), None)
    if not categorizer:
        return JSONEncoder().encode({"success": True, "value": experiments})

    sortby = sorters.get(request.args.get("sortby", None), None)
    return JSONEncoder().encode({"success": True, "value": categorize(experiments, categorizer, sortby)})

@explgbk_blueprint.route("/lgbk/ws/instruments", methods=["GET"])
@context.security.authentication_required
def svc_get_instruments():
    """
    Get the list of instruments
    """
    return jsonify({'success': True, 'value': get_instruments()})


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


@explgbk_blueprint.route("/lgbk/ws/usergroups", methods=["GET"])
@context.security.authentication_required
def svc_getUserGroupsForAuthenticatedUser():
    """
    Get the user id and groups for the authenticated user
    """
    userid = context.security.get_current_user_id()
    groups = context.usergroups.get_user_posix_groups(userid)
    return jsonify({'success': True, 'value': { "userid": userid, "groups": groups }})


@explgbk_blueprint.route("/lgbk/ws/create_update_instrument", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("edit")
def svc_create_update_instrument():
    """
    Create a new instrument. Pass in the document..
    """
    instrument_name = request.args.get("instrument_name", None)
    if not instrument_name:
        return logAndAbort("Creating instrument must pass instrument_name in query parameters")

    create_str = request.args.get("create", None)
    if not create_str:
        return logAndAbort("Creating instrument must have a boolean create parameter indicating if the instrument is created or updated.")
    createp = create_str.lower() in set(["yes", "true", "t", "1"])
    logger.debug("Create update instrument is %s for %s", createp, create_str)

    info = request.json
    if not info:
        return logAndAbort("Creating instrument missing info document")

    necessary_keys = set(['_id', 'description'])
    missing_keys = necessary_keys - info.keys()
    if missing_keys:
        return logAndAbort("Creating instrument missing keys %s" % missing_keys)

    (status, errormsg) = create_update_instrument(instrument_name, createp, info)
    if status:
        context.kafka_producer.send("instrument", {"instrument_name" : instrument_name, "CRUD": "Create" if createp else "Update", "value": info })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})



@explgbk_blueprint.route("/lgbk/ws/register_new_experiment", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("edit")
def svc_register_new_experiment():
    """
    Register a new experiment.
    We expect the experiment_name as a query parameter and the registration information as a JSON document in the POST body.
    """
    experiment_name = request.args.get("experiment_name", None)
    if not experiment_name:
        return logAndAbort("Experiment registration missing experiment_name in query parameters")

    info = request.json
    if not info:
        return logAndAbort("Experiment registration missing info document")

    necessary_keys = set(['instrument', 'start_time', 'end_time', 'leader_account', 'contact_info', 'posix_group'])
    missing_keys = necessary_keys - info.keys()
    if missing_keys:
        return logAndAbort("Experiment registration missing keys %s" % missing_keys)

    (status, errormsg) = register_new_experiment(experiment_name, info)
    if status:
        context.kafka_producer.send("experiment", {"experiment_name" : experiment_name, "CRUD": "Create", "value": info })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/ws/update_experiment_info", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("edit")
def svc_update_experiment_info():
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

    necessary_keys = set(['instrument', 'start_time', 'end_time', 'leader_account', 'contact_info', 'posix_group'])
    missing_keys = necessary_keys - info.keys()
    if missing_keys:
        return logAndAbort("Experiment registration missing keys %s" % missing_keys)

    (status, errormsg) = update_existing_experiment(experiment_name, info)
    if status:
        context.kafka_producer.send("experiment", {"experiment_name" : experiment_name, "CRUD": "Update", "value": info})
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})



@explgbk_blueprint.route("/lgbk/ws/switch_experiment", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("edit")
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

    station = info.get("station", None)
    if not station:
        return jsonify({'success': False, 'errormsg': "No station given."})

    info_from_database = get_experiment_info(experiment_name)
    if not info_from_database:
        return jsonify({'success': False, 'errormsg': "Experiment does not exist in the database"})

    if info_from_database["instrument"] != instrument:
        return jsonify({'success': False, 'errormsg': "Trying to switch experiment on instrument %s for experiment on %s" % (instrument, info_from_database["instrument"])})

    userid = context.security.get_current_user_id()

    (status, errormsg) = switch_experiment(instrument, station, experiment_name, userid)
    if status:
        context.kafka_producer.send("experiment_switch", {"experiment_name" : experiment_name, "value": {
            "instrument": instrument,
            "startion": station,
            "experiment_name": experiment_name,
            "userid": userid,
        }})
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/elog", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def svc_get_elog_entries(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_elog_entries(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/attachment", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def svc_get_elog_attachment(experiment_name):
    entry_id = request.args.get("entry_id", None)
    attachment_id = request.args.get("attachment_id", None)
    logger.info("Fetching attachment " + attachment_id + " for entry " + entry_id)
    entry = get_specific_elog_entry(experiment_name, entry_id)
    for attachment in entry.get("attachments", None):
        if str(attachment.get("_id", None)) == attachment_id:
            remote_url = attachment.get("url", None)
            if remote_url:
                req = requests.get(remote_url, stream = True)
                return Response(stream_with_context(req.iter_content(chunk_size=1024)), content_type = req.headers['content-type'])

    return Response("Cannot find attachment " + attachment_id , status=404)


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/new_elog_entry", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_post_new_elog_entry(experiment_name):
    """
    Create a new log entry.
    Process multi-part file upload
    """
    log_content = request.form["log_text"]

    if not log_content or not log_content.strip():
        return logAndAbort("Cannot post empty message")

    userid = context.security.get_current_user_id()

    optional_args = {}
    parent = request.form.get("parent", None);
    if parent:
        logger.debug("We are creating a followup entry for " + parent + " for experiment " + experiment_name)
        parent_entry = get_specific_elog_entry(experiment_name, parent)
        if parent_entry:
            optional_args["parent"] = parent_entry["_id"] # This should give back the oid
            parent_root = parent_entry.get("root", None) # This should give back the oid
            optional_args["root"] = parent_root if parent_root else parent_entry["_id"] # both should be oids
        else:
            return logAndAbort("Cannot find parent entry for followup log message for experiment " + experiment_name + " for parent oid " + parent)

    run_num = request.form.get("run_num", None);
    if(run_num):
        optional_args["run_num"] = run_num

    shift = request.form.get("shift", None);
    if(shift):
        shift_obj = get_specific_shift(experiment_name, shift)
        if shift_obj:
            optional_args["shift"] = shift_obj["_id"] # We should get a oid here

    logger.debug("Optional args %s ", optional_args)

    files = []
    for upload in request.files.getlist("files"):
        filename = upload.filename.rsplit("/")[0]
        if filename:
            logger.info(filename)
            files.append((filename, upload))
    inserted_doc = post_new_log_entry(experiment_name, userid, log_content, files, **optional_args)
    inserted_doc['experiment_name'] = experiment_name
    context.kafka_producer.send("elog", inserted_doc)
    logger.debug("Published the new elog entry for %s", experiment_name)
    return JSONEncoder().encode({'success': True, 'value': inserted_doc})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/files", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def svc_get_files(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_experiment_files(experiment_name)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/runs", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def svc_get_runs(experiment_name):
    include_run_params = bool(request.args.get("includeParams", "false"))
    return JSONEncoder().encode({"success": True, "value": get_experiment_runs(experiment_name, include_run_params)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/run_tables", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def svc_get_runtables(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_all_run_tables(experiment_name)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/run_table_data", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def svc_get_runtable_data(experiment_name):
    tableName = request.args.get("tableName")
    return JSONEncoder().encode({"success": True, "value": get_runtable_data(experiment_name, tableName)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/run_table_sources", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def svc_get_runtable_sources(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_runtable_sources(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/create_update_user_run_table_def", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_create_update_user_run_table_def(experiment_name):
    """
    Create or update an existing user definition table.
    """
    # logger.info(json.dumps(request.json, indent=2))
    return JSONEncoder().encode({"success": True, "status": create_update_user_run_table_def(experiment_name, request.json)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/run_table_editable_update")
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_run_table_editable_update(experiment_name):
    """
    Update the editable param for the specified run for the experiment.
    :runnum: Specify the run using the runnum parameter.
    :source: Specify the source using the source parameter.
    :value: The new value
    """
    runnum = int(request.args.get("runnum"))
    source = request.args.get("source")
    value = request.args.get("value")
    userid = context.security.get_current_user_id()

    if not source.startswith('editable_params.'):
        return logAndAbort("We can only change editable parameters.")
    if source.endswith('.value'):
        source = source.replace(".value", "")
    return JSONEncoder().encode({"success": True, "result": update_editable_param_for_run(experiment_name, runnum, source, value, userid)})


@explgbk_blueprint.route("/run_control/<experiment_name>/ws/start_run", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_start_run(experiment_name):
    """
    Start a new run for an experiment.
    Pass in the type of the run as a query parameter run_type. This defaults to DATA.
    """
    run_type = request.args.get("run_type", "DATA")

    # Here's where we can put validations on starting a new run.
    # Currently; there are none (after discussions with the DAQ team)
    # But we may want to make sure the previous run is closed etc.

    run_doc = start_run(experiment_name, run_type)

    run_doc['experiment_name'] = experiment_name
    context.kafka_producer.send("runs", run_doc)
    logger.debug("Published the new run for %s", experiment_name)

    return JSONEncoder().encode({"success": True, "value": run_doc})


@explgbk_blueprint.route("/run_control/<experiment_name>/ws/end_run", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_end_run(experiment_name):
    """
    End the current run; ending the current run is mostly setting the end time.
    """
    run_doc = end_run(experiment_name)
    run_doc['experiment_name'] = experiment_name
    context.kafka_producer.send("runs", run_doc)

    return JSONEncoder().encode({"success": True, "value": run_doc})


@explgbk_blueprint.route("/run_control/<experiment_name>/ws/current_run", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def svc_current_run(experiment_name):
    """
    Get the run document for the current run.
    """
    return JSONEncoder().encode({"success": True, "value": get_current_run(experiment_name)})



@explgbk_blueprint.route("/run_control/<experiment_name>/ws/add_run_params", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_add_run_params(experiment_name):
    """
    Takes a dictionary as the POST body and bulk adds these are run parameters to the current run.
    For example, send all the EPICS variables as a JSON dict.
    We make sure the current run is still open (end_time is None)
    """
    params = request.json
    run_params = {"params." + escape_chars_for_mongo(k) : v for k, v in params.items() }

    current_run_doc = get_current_run(experiment_name)
    if current_run_doc['end_time']:
        return logAndAbort("The current run %s is closed for experiment %s" % (current_run_doc['num'], experiment_name))

    return JSONEncoder().encode({"success": True, "value": add_run_params(experiment_name, run_params)})

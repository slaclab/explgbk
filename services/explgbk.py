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

import requests
import context
from functools import wraps
from datetime import datetime
import hashlib
import urllib
import base64

import smtplib
from email.message import EmailMessage

from flask import Blueprint, jsonify, request, url_for, Response, stream_with_context, send_file, \
    abort, redirect, make_response

from dal.explgbk import get_experiment_info, save_new_experiment_setup, register_new_experiment, \
    get_instruments, get_currently_active_experiments, switch_experiment, get_elog_entries, post_new_log_entry, get_specific_elog_entry, \
    get_specific_shift, get_experiment_files, get_experiment_runs, get_all_run_tables, get_runtable_data, get_runtable_sources, \
    create_update_user_run_table_def, update_editable_param_for_run, get_instrument_station_list, update_existing_experiment, \
    create_update_instrument, get_experiment_shifts, get_shift_for_experiment_by_name, close_shift_for_experiment, \
    create_update_shift, get_latest_shift, get_samples, create_update_sample, get_sample_for_experiment_by_name, \
    make_sample_current, register_file_for_experiment, search_elog_for_text, delete_run_table, get_current_sample_name, \
    get_elogs_for_run_num, get_elogs_for_run_num_range, get_elogs_for_specified_id, get_collaborators, get_role_object, \
    add_collaborator_to_role, remove_collaborator_from_role, delete_elog_entry, modify_elog_entry, clone_experiment, rename_experiment, \
    instrument_standby, get_experiment_files_for_run, get_elog_authors, get_elog_entries_by_author, get_elog_tags, get_elog_entries_by_tag, \
    get_elogs_for_date_range, clone_sample, get_modal_param_definitions, lock_unlock_experiment

from dal.run_control import start_run, get_current_run, end_run, add_run_params, get_run_doc_for_run_num

from dal.utils import JSONEncoder, escape_chars_for_mongo

from dal.exp_cache import get_experiments, does_experiment_exist, reload_cache as reload_experiment_cache, text_search_for_experiments

__author__ = 'mshankar@slac.stanford.edu'

explgbk_blueprint = Blueprint('experiment_logbook_api', __name__)

logger = logging.getLogger(__name__)

def logAndAbort(error_msg):
    logger.error(error_msg)
    return Response(error_msg, status=500)

def experiment_exists_and_unlocked(wrapped_function):
    """
    Decorator to make sure experiment_name in the argument to the ws call exists.
    """
    @wraps(wrapped_function)
    def function_interceptor(*args, **kwargs):
        experiment_name = kwargs.get('experiment_name', None)
        if experiment_name and does_experiment_exist(experiment_name):
            if get_experiment_info(experiment_name).get("is_locked", False) and set(["POST", "PUT", "DELETE"]) & set(request.url_rule.methods):
                logger.error("Experiment %s is locked; methods that modify data are not allowed. To change data, please unlock the experiment.", experiment_name)
                abort(423) # Webdav locked.
                return None
            return wrapped_function(*args, **kwargs)
        else:
            logger.error("Experiment %s does not exist in the experiment cache", experiment_name)
            abort(404)
            return None

    return function_interceptor

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/info", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
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

categorizers = {
    "instrument": [(lambda exp : exp.get("instrument", None))],
    "instrument_lastrunyear": [(lambda exp : exp.get("instrument", None)), (lambda exp : exp["last_run"]["begin_time"].year if "last_run" in exp else None)]
    }

sorters = {
    "name": ((lambda exp: exp["name"]), False),
    "lastrunyear": ((lambda exp: exp["last_run"]["begin_time"] if "last_run" in exp else exp["start_time"]), True)
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
    sortby = sorters.get(request.args.get("sortby", None), None)
    if categorizer and sortby:
        return JSONEncoder().encode({"success": True, "value": categorize(experiments, categorizer, sortby)})
    if sortby:
        return JSONEncoder().encode({"success": True, "value": sorted(experiments, key=sortby[0], reverse=sortby[1])})

    return JSONEncoder().encode({"success": True, "value": experiments})

@explgbk_blueprint.route("/lgbk/ws/search_experiment_info", methods=["GET"])
@context.security.authentication_required
def svc_search_experiment_info():
    """
    Perform a text search against the cached experiment info.
    This only searches against basic information like the name, description, PI etc.
    """
    search_terms = request.args.get("search_text", "")
    return jsonify({'success': True, 'value': text_search_for_experiments(search_terms)})

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

    if createp and info["_id"] in set([x["_id"] for x in get_instruments()]):
        return logAndAbort("Instrument %s already exists" % info["_id"])

    (status, errormsg) = create_update_instrument(instrument_name, createp, info)
    if status:
        context.kafka_producer.send("instruments", {"instrument_name" : instrument_name, "CRUD": "Create" if createp else "Update", "value": info })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})


@explgbk_blueprint.route("/lgbk/ws/lookup_experiment_in_urawi", methods=["GET"])
@context.security.authentication_required
def svc_lookup_experiment_in_URAWI():
    """
    Lookup the specified experiment in URAWI and return the information from URAWI as the value.
    """
    URAWI_URL = os.environ.get("URAWI_EXPERIMENT_LOOKUP_URL", None)
    experiment_name = request.args.get("experiment_name", None)
    if URAWI_URL and experiment_name:
        try:
            logger.info("Getting URAWI data for proposal %s using %s", experiment_name, URAWI_URL)
            urawi_doc = requests.get(URAWI_URL, params={ "proposalNo" : experiment_name }, verify=False).json()
            if urawi_doc.get("status", "error") == "success":
                return jsonify({'success': True, "value": urawi_doc})
            else:
                logger.warning("Did not get a successful response from URAWI for %s", experiment_name)
                return jsonify({'success': False})
        except Exception as e:
            logger.exception("Exception fetching data from URAWI using URL %s for %s", URAWI_URL, experiment_name)
            return jsonify({'success': False})

    return jsonify({'success': False})

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
    if does_experiment_exist(experiment_name):
        return logAndAbort("Experiment %s already exists" % experiment_name)

    info = request.json
    if not info:
        return logAndAbort("Experiment registration missing info document")

    necessary_keys = set(['instrument', 'start_time', 'end_time', 'leader_account', 'contact_info', 'posix_group'])
    missing_keys = necessary_keys - info.keys()
    if missing_keys:
        return logAndAbort("Experiment registration missing keys %s" % missing_keys)
    if info["instrument"] not in set([x["_id"] for x in get_instruments()]):
        return logAndAbort("The instrument specified %s  is not a valid instrument" % info["instrument"])

    (status, errormsg) = register_new_experiment(experiment_name, info)
    if status:
        context.kafka_producer.send("experiments", {"experiment_name" : experiment_name, "CRUD": "Create", "value": info })
        context.kafka_producer.send("shifts", {"experiment_name" : experiment_name, "CRUD": "Create", "value": get_latest_shift(experiment_name) })
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
        context.kafka_producer.send("experiments", {"experiment_name" : experiment_name, "CRUD": "Update", "value": info})
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

@explgbk_blueprint.route("/lgbk/ws/clone_experiment", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("edit")
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
@context.security.authorization_required("edit")
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

@explgbk_blueprint.route("/lgbk/ws/lock_unlock_experiment", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("edit")
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
    reload_experiment_cache()
    return jsonify({'success': True})


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

    if experiment_name in [ x.get('name', '') for x in get_currently_active_experiments() ]:
        return jsonify({'success': False, 'errormsg': "Trying to switch experiment %s onto instrument %s but it is already currently active" % (experiment_name, instrument)})

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


@explgbk_blueprint.route("/lgbk/ws/instrument_standby", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("edit")
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

    station = info.get("station", None)
    if not station:
        return jsonify({'success': False, 'errormsg': "No station given."})

    userid = context.security.get_current_user_id()

    (status, errormsg) = instrument_standby(instrument, station, userid)
    if status:
        context.kafka_producer.send("instrument_standby", {"value": {
            "instrument": instrument,
            "startion": station,
            "userid": userid
        }})
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/has_role", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
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
            "hasRole": context.roleslookup.has_slac_user_role(context.security.get_current_user_id(), application_name, role_name, experiment_name)
        }})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/elog", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_get_elog_entries(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_elog_entries(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/attachment", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
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
                if "preview_url" in attachment:
                    remote_url = attachment.get("preview_url", None)
                else:
                    return send_file('static/attachment.png')
            else:
                logger.debug("Cannot find preview, returning main document.")
                remote_url = attachment.get("url", None)
            if remote_url:
                req = requests.get(remote_url, stream = True)
                resp = Response(stream_with_context(req.iter_content(chunk_size=1024)), content_type = req.headers['content-type'])
                if not (attachment["type"].startswith("image") or "preview_url" in attachment):
                    resp.headers["Content-Disposition"] = 'attachment; filename="' + attachment["name"] + '"'
                return resp

    return Response("Cannot find attachment " + attachment_id , status=404)

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/ext_preview/<path:path>", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
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
            if 'title' in elog_doc:
                msg.make_mixed()
                htmlmsg = EmailMessage()
                htmlmsg.make_alternative()
                htmlmsg.add_alternative(elog_doc["content"], subtype='html')
                msg.attach(htmlmsg)
            else:
                msg.set_content(elog_doc["content"])
                msg.make_mixed()
            for attachment in elog_doc.get("attachments", []):
                if 'type' in attachment and '/' in attachment['type']:
                    maintype, subtype = attachment['type'].split('/', 1)
                else:
                    maintype, subtype = "application", "data"
                with requests.get(attachment["url"], stream=True) as imgget:
                    msg.add_attachment(imgget.raw.read(), maintype=maintype, subtype=subtype, filename=attachment['name'])
            return msg

        msg = generateEMailMsgFromELogDoc(elog_doc)
        msg['Subject'] = '' + "Elog message for " + experiment_name + " " + elog_doc.get("title", "")
        msg['From'] = 'exp_logbook_robot@slac.stanford.edu'
        msg['To'] = ", ".join(full_email_addresses)
        parent_msg = msg
        while elog_doc.get("parent", None):
            elog_doc = get_specific_elog_entry(experiment_name, elog_doc["parent"])
            child_message = generateEMailMsgFromELogDoc(elog_doc)
            parent_msg.attach(child_message)
            parent_msg = child_message

        s = smtplib.SMTP("smtp.slac.stanford.edu")
        s.sendmail(msg['From'], full_email_addresses, msg.as_string())
        s.quit()
    except Exception:
        logger.exception("Exception sending elog emails for experiment " + experiment_name)

    return True

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/new_elog_entry", methods=["POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
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

    run_num_str = request.form.get("run_num", None);
    if run_num_str:
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

    log_tags_str = request.form.get("log_tags", None)
    if log_tags_str:
        tags = log_tags_str.split()
        optional_args["tags"] = tags

    logger.debug("Optional args %s ", optional_args)

    files = []
    for upload in request.files.getlist("files"):
        filename = upload.filename.rsplit("/")[0]
        if filename:
            logger.info(filename)
            files.append((filename, upload))
    inserted_doc = post_new_log_entry(experiment_name, userid, log_content, files, **optional_args)
    context.kafka_producer.send("elog", {"experiment_name" : experiment_name, "CRUD": "Create", "value": inserted_doc})
    logger.debug("Published the new elog entry for %s", experiment_name)

    # Send an email out if a list of emails was specified.
    email_to = inserted_doc.get("email_to", None)
    if not email_to and "root" in inserted_doc:
        email_to = get_specific_elog_entry(experiment_name, inserted_doc["root"]).get("email_to", None)
    if email_to:
        send_elog_as_email(experiment_name, inserted_doc, email_to)

    return JSONEncoder().encode({'success': True, 'value': inserted_doc})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/modify_elog_entry", methods=["POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("edit")
def svc_modify_elog_entry(experiment_name):
    entry_id = request.args.get("_id", None)
    log_content = request.form["log_text"]
    log_emails = request.form.get("log_emails", None)
    email_to = log_emails.split() if log_emails else None
    log_tags_str = request.form.get("log_tags", None)
    tags = log_tags_str.split() if log_tags_str else []
    title = request.form.get("log_title", None)
    if not entry_id or not log_content:
        return logAndAbort("Please pass in the _id of the elog entry for " + experiment_name + " and the new content")

    files = []
    for upload in request.files.getlist("files"):
        filename = upload.filename.rsplit("/")[0]
        if filename:
            logger.info(filename)
            files.append((filename, upload))

    status = modify_elog_entry(experiment_name, entry_id, context.security.get_current_user_id(), log_content, email_to, tags, files, title)
    if status:
        modified_entry = get_specific_elog_entry(experiment_name, entry_id)
        context.kafka_producer.send("elog", {"experiment_name" : experiment_name, "CRUD": "Update", "value": modified_entry})
        previous_version = get_specific_elog_entry(experiment_name, modified_entry["previous_version"])
        context.kafka_producer.send("elog", {"experiment_name" : experiment_name, "CRUD": "Create", "value": previous_version})

        email_to = modified_entry.get("email_to", None)
        if not email_to and "root" in modified_entry:
            email_to = get_specific_elog_entry(experiment_name, modified_entry["root"]).get("email_to", None)
        if email_to:
            send_elog_as_email(experiment_name, modified_entry, email_to)

    return JSONEncoder().encode({"success": status})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/search_elog", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_search_elog(experiment_name):
    search_text   = request.args.get("search_text", "")
    run_num_str   = request.args.get("run_num", None)
    start_run_num_str = request.args.get("start_run_num", None)
    end_run_num_str   = request.args.get("end_run_num", None)
    start_date_str = request.args.get("start_date", None)
    end_date_str   = request.args.get("end_date", None)
    id_str = request.args.get("_id", None)
    if run_num_str:
        return JSONEncoder().encode({"success": True, "value": get_elogs_for_run_num(experiment_name, int(run_num_str))})
    elif start_run_num_str and end_run_num_str:
        return JSONEncoder().encode({"success": True, "value": get_elogs_for_run_num_range(experiment_name, int(start_run_num_str), int(end_run_num_str))})
    elif id_str:
        return JSONEncoder().encode({"success": True, "value": get_elogs_for_specified_id(experiment_name, id_str)})
    elif start_date_str and end_date_str:
        return JSONEncoder().encode({"success": True, "value": get_elogs_for_date_range(experiment_name, datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M:%S.%fZ'), datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M:%S.%fZ'))})
    else:
        combined_results = {}
        if search_text in get_elog_authors(experiment_name):
            combined_results.update({ x["_id"] : x for x in get_elog_entries_by_author(experiment_name, search_text) })
        if search_text in get_elog_tags(experiment_name):
            combined_results.update({ x["_id"] : x for x in get_elog_entries_by_tag(experiment_name, search_text) })

        combined_results.update({ x["_id"] : x for x in search_elog_for_text(experiment_name, search_text) })
        return JSONEncoder().encode({"success": True, "value": list(sorted(combined_results.values(), key=lambda x : x["insert_time"]))})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/delete_elog_entry", methods=["DELETE"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("delete")
def svc_delete_elog_entry(experiment_name):
    entry_id   = request.args.get("_id", None)
    if not entry_id:
        return logAndAbort("Please pass in the _id of the elog entry for " + experiment_name)
    status = delete_elog_entry(experiment_name, entry_id, context.security.get_current_user_id())
    if status:
        entry = get_specific_elog_entry(experiment_name, entry_id)
        context.kafka_producer.send("elog", {"experiment_name" : experiment_name, "CRUD": "Update", "value": entry})
    return JSONEncoder().encode({"success": status})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/files", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_get_files(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_experiment_files(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/<run_num>/files", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_get_files_for_run(experiment_name, run_num):
    try:
        rnum = int(run_num)
    except ValueError:
        rnum = run_num_str # Cryo uses strings for run numbers.
    return JSONEncoder().encode({"success": True, "value": get_experiment_files_for_run(experiment_name, rnum)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/runs", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_get_runs(experiment_name):
    include_run_params = bool(request.args.get("includeParams", "false"))
    return JSONEncoder().encode({"success": True, "value": get_experiment_runs(experiment_name, include_run_params)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/shifts", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_get_shifts(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_experiment_shifts(experiment_name)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/run_tables", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_get_runtables(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_all_run_tables(experiment_name)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/run_table_data", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_get_runtable_data(experiment_name):
    tableName = request.args.get("tableName")
    sampleName = request.args.get("sampleName", None)
    return JSONEncoder().encode({"success": True, "value": get_runtable_data(experiment_name, tableName, sampleName=sampleName)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/run_table_sources", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_get_runtable_sources(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_runtable_sources(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/create_update_user_run_table_def", methods=["POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_create_update_user_run_table_def(experiment_name):
    """
    Create or update an existing user definition table.
    """
    # logger.info(json.dumps(request.json, indent=2))
    return JSONEncoder().encode({"success": True, "status": create_update_user_run_table_def(experiment_name, request.json)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/run_table_editable_update", methods=["POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
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

    if not source.startswith('editable_params.'):
        return logAndAbort("We can only change editable parameters.")
    if source.endswith('.value'):
        source = source.replace(".value", "")
    return JSONEncoder().encode({"success": True, "result": update_editable_param_for_run(experiment_name, runnum, source, value, userid)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/delete_run_table", methods=["DELETE"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_delete_run_table(experiment_name):
    table_name = request.args.get("table_name", None)
    if not table_name:
        return logAndAbort("Please specify the table name to delete.")
    return JSONEncoder().encode({"success": True, "value": delete_run_table(experiment_name, table_name)})




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
    """
    run_type = request.args.get("run_type", "DATA")
    user_specified_run_number = request.args.get("run_num", None)

    # Here's where we can put validations on starting a new run.
    # Currently; there are none (after discussions with the DAQ team)
    # But we may want to make sure the previous run is closed, the specified experiment is the active one etc.

    run_doc = start_run(experiment_name, run_type, user_specified_run_number)

    context.kafka_producer.send("runs", {"experiment_name" : experiment_name, "CRUD": "Insert", "value": run_doc})
    logger.debug("Published the new run for %s", experiment_name)

    return JSONEncoder().encode({"success": True, "value": run_doc})


@explgbk_blueprint.route("/run_control/<experiment_name>/ws/end_run", methods=["GET", "POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_end_run(experiment_name):
    """
    End the current run; ending the current run is mostly setting the end time.
    """
    run_doc = end_run(experiment_name)
    context.kafka_producer.send("runs", {"experiment_name" : experiment_name, "CRUD": "Update", "value": run_doc})

    return JSONEncoder().encode({"success": True, "value": run_doc})


@explgbk_blueprint.route("/run_control/<experiment_name>/ws/current_run", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_current_run(experiment_name):
    """
    Get the run document for the current run.
    """
    return JSONEncoder().encode({"success": True, "value": get_current_run(experiment_name)})

@explgbk_blueprint.route("/run_control/<experiment_name>/ws/add_run_params", methods=["POST"])
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
        current_run_doc = get_run_doc_for_run_num(experiment_name, user_specified_run_number)
    else:
        current_run_doc = get_current_run(experiment_name)

    if current_run_doc['end_time']:
        return logAndAbort("The current run %s is closed for experiment %s" % (current_run_doc['num'], experiment_name))

    params = request.json
    run_params = {"params." + escape_chars_for_mongo(k) : v for k, v in params.items() }
    run_doc_after = add_run_params(experiment_name, current_run_doc, run_params)
    context.kafka_producer.send("runs", {"experiment_name" : experiment_name, "CRUD": "Update", "value": run_doc_after})
    return JSONEncoder().encode({"success": True, "value": run_doc_after})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/close_shift", methods=["GET", "POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
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
@experiment_exists_and_unlocked
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
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_get_latest_shift(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_latest_shift(experiment_name)})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/samples", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_get_samples(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_samples(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/current_sample_name", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_get_current_sample(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_current_sample_name(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/create_update_sample", methods=["POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_create_update_sample(experiment_name):
    """
    Create/update a sample.
    If you pass in a _id, then this is an update.
    """
    sample_name = request.args.get("sample_name", None)
    if not sample_name:
        return logAndAbort("We need a sample_name as a parameter")
    info = request.json
    if not info:
        return logAndAbort("Creating sample missing info document")

    createp = "_id" not in info
    necessary_keys = set(['name', 'description'])
    missing_keys = necessary_keys - info.keys()
    if missing_keys:
        return logAndAbort("Create/update sample missing fields %s" % missing_keys)

    (status, errormsg) = create_update_sample(experiment_name, sample_name, createp, info)
    if status:
        sample_doc = get_sample_for_experiment_by_name(experiment_name, sample_name)
        context.kafka_producer.send("samples", {"experiment_name" : experiment_name, "CRUD": "Create" if createp else "Update", "value": sample_doc })
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})

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
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'errormsg': errormsg})



@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/register_file", methods=["POST"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("post")
def svc_register_file(experiment_name):
    """
    Registers a new file with the data management service.
    Pass in the JSON document for the file; this has the path, run_num, checksum, create_timestamp, modify_timestamp and size.
    If the run_num is not present, we associate the file with the current run.
    """
    info = request.json
    if not info:
        return logAndAbort("Please pass in the file json to register a new file.")

    necessary_keys = set(['path', 'run_num', 'checksum', 'create_timestamp', 'modify_timestamp', 'size'])

    def attach_current_run(flinfo):
        if 'run_num' not in flinfo.keys():
            current_run_num = get_current_run(experiment_name)['num']
            logger.info("Associating file %s with current run %s", flinfo['path'], current_run_num)
            flinfo['run_num'] = current_run_num


    if isinstance(info, list):
        ret_status = []
        for finfo in info:
            missing_keys = necessary_keys - finfo.keys()
            if missing_keys:
                ret_status.append({'success': False, 'errormsg': "File registration missing keys %s" % missing_keys})
                continue

            attach_current_run(finfo)

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

        (status, errormsg) = register_file_for_experiment(experiment_name, info)
        if status:
            context.kafka_producer.send("file_catalog", {"experiment_name" : experiment_name, "CRUD": "Create", "value": info })
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'errormsg': errormsg})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/collaborators", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
@context.security.authorization_required("read")
def svc_get_collaborators(experiment_name):
    return JSONEncoder().encode({"success": True, "value": get_collaborators(experiment_name)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/toggle_role", methods=["GET", "POST"])
@experiment_exists_and_unlocked
@context.ldapadminsecurity.authentication_required
@context.ldapadminsecurity.authorization_required("manage_groups")
def svc_toggle_role(experiment_name):
    uid = request.args.get("uid", None)
    role_fq_name = request.args.get("role_fq_name", None)
    if not uid or not role_fq_name:
        return logAndAbort("Please specify a uid and role_fq_name")

    role_obj = get_role_object(experiment_name, role_fq_name)
    if role_obj and 'players' in role_obj and uid in role_obj['players']:
        status = remove_collaborator_from_role(experiment_name, uid, role_fq_name)
    else:
        status = add_collaborator_to_role(experiment_name, uid, role_fq_name)

    if status:
        role_obj = get_role_object(experiment_name, role_fq_name)
        context.kafka_producer.send("roles", {"experiment_name" : experiment_name, "CRUD": "Update", "value": role_obj })

    return JSONEncoder().encode({"success": status, "message": "Did not match any entries" if not status else ""})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/add_collaborator", methods=["GET", "POST"])
@experiment_exists_and_unlocked
@context.ldapadminsecurity.authentication_required
@context.ldapadminsecurity.authorization_required("manage_groups")
def svc_add_collaborator(experiment_name):
    uid = request.args.get("uid", None)
    if not uid:
        return logAndAbort("Please specify a uid")
    role_fq_name = request.args.get("role_fq_name", "LogBook/Reader")

    status = add_collaborator_to_role(experiment_name, uid, role_fq_name)

    if status:
        role_obj = get_role_object(experiment_name, role_fq_name)
        context.kafka_producer.send("roles", {"experiment_name" : experiment_name, "CRUD": "Update", "value": role_obj })
    return JSONEncoder().encode({"success": status, "message": "Did not match any entries" if not status else ""})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/remove_collaborator", methods=["GET", "POST"])
@experiment_exists_and_unlocked
@context.ldapadminsecurity.authentication_required
@context.ldapadminsecurity.authorization_required("manage_groups")
def svc_remove_collaborator(experiment_name):
    uid = request.args.get("uid", None)
    if not uid:
        return logAndAbort("Please specify a uid")

    collaborator_roles = next(filter(lambda x : x["uid"] == uid, get_collaborators(experiment_name)))
    for role in collaborator_roles['roles']:
        remove_collaborator_from_role(experiment_name, uid, role)
        role_obj = get_role_object(experiment_name, role)
        context.kafka_producer.send("roles", {"experiment_name" : experiment_name, "CRUD": "Update", "value": role_obj })

    return JSONEncoder().encode({"success": True, "message": "Removed collaborator"})


@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/get_matching_uids", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
def get_matching_uids(experiment_name):
    uid = request.args.get("uid", None)
    if not uid:
        return logAndAbort("Please specify a uid")
    return JSONEncoder().encode({"success": True, "value": context.usergroups.get_userids_matching_pattern(uid)})

@explgbk_blueprint.route("/lgbk/<experiment_name>/ws/get_matching_groups", methods=["GET"])
@context.security.authentication_required
@experiment_exists_and_unlocked
def get_matching_groups(experiment_name):
    group_name = request.args.get("group_name", None)
    if not group_name:
        return logAndAbort("Please specify a group_name")
    return JSONEncoder().encode({"success": True, "value": context.usergroups.get_groups_matching_pattern(group_name)})

@explgbk_blueprint.route("/lgbk/get_modal_param_definitions", methods=["GET"])
@context.security.authentication_required
def svc_get_modal_param_definitions():
    modal_type = request.args.get("modal_type", None)
    if not modal_type:
        return logAndAbort("Please specify a modal_type")
    param_defs = get_modal_param_definitions(modal_type)
    return JSONEncoder().encode({"success": True, "value": param_defs if param_defs else {}})

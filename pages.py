import os
import json
import logging
import pkg_resources
import datetime

import context

from flask import request, Blueprint, render_template, send_file, abort, make_response, jsonify, session

from dal.explgbk import get_current_sample_name, get_experiment_info
from services.explgbk import experiment_exists

pages_blueprint = Blueprint('pages_api', __name__)

logger = logging.getLogger(__name__)

@pages_blueprint.route("/")
def index():
    return render_template("choose_experiment.html")

@pages_blueprint.route("/status")
def status():
    return jsonify({"success": True, "mongo_version": context.logbookclient.server_info()['version']})


@pages_blueprint.route('/js/<path:path>')
def send_js(path):
    pathparts = os.path.normpath(path).split(os.sep)
    if pathparts[0] == 'python':
        # This is code for gettting the JS file from the package data of the python module.
        filepath = pkg_resources.resource_filename(pathparts[1], os.sep.join(pathparts[2:]))
        if os.path.exists(filepath):
            return send_file(filepath)


    # $CONDA_PREFIX/lib/node_modules/jquery/dist/
    filepath = os.path.join(os.getenv("CONDA_PREFIX"), "lib", "node_modules", path)
    if not os.path.exists(filepath):
        filepath = os.path.join(os.getenv("CONDA_PREFIX"), "lib", "node_modules", pathparts[0], "dist", *pathparts[1:])
    if os.path.exists(filepath):
        return send_file(filepath)
    else:
        logger.error("Cannot find static file %s in %s", path, filepath)
        abort(404)
        return None

@pages_blueprint.route("/lgbk/<experiment_name>/templates/<path:path>", methods=["GET"])
@experiment_exists
def templates(experiment_name, path):
    return render_template(path, experiment_name=experiment_name)

@pages_blueprint.route("/lgbk/ops", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("ops_page")
def operator_dashboard():
    logged_in_user=context.security.get_current_user_id()
    privileges = { x : context.security.check_privilege_for_experiment(x, None, None) for x in [ "ops_page", "switch", "experiment_create", "experiment_edit", "experiment_delete", "instrument_create", "manage_groups"]}
    return render_template("ops.html",
        logbook_site=context.LOGBOOK_SITE,
        logged_in_user=logged_in_user,
        privileges=json.dumps(privileges))


@pages_blueprint.route("/lgbk/experiments", methods=["GET"])
@context.security.authentication_required
def choose_experiments():
    logged_in_user=context.security.get_current_user_id()
    privileges = { x : context.security.check_privilege_for_experiment(x, None, None) for x in [ "read", "ops_page", "switch", "experiment_create", "experiment_edit"]}
    return render_template("experiments.html",
        logbook_site=context.LOGBOOK_SITE,
        logged_in_user=logged_in_user,
        logged_in_user_details=json.dumps(context.usergroups.get_userids_matching_pattern(logged_in_user)),
        privileges=json.dumps(privileges))

@pages_blueprint.route("/lgbk/register_new_experiment", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("experiment_create")
def register_new_experiment():
    return render_template("register_new_experiment.html")

@pages_blueprint.route("/lgbk/experiment_switch", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("switch")
def experiment_switch():
    return render_template("experiment_switch.html")

@pages_blueprint.route("/lgbk/logout", methods=["GET"])
@context.security.authentication_required
def logout():
    resp = make_response(render_template("logout.html"))
    session.clear()
    resp.set_cookie('webauth_at', ' ', expires=datetime.datetime.fromtimestamp(0))
    return resp

@pages_blueprint.route("/lgbk/docs/<path:path>", methods=["GET"])
@context.security.authentication_required
def docs(path):
    doc_path = os.path.join(os.path.dirname(__file__), "static", "html", "docs", path)
    logger.debug("Looking for path %s", doc_path)
    if os.path.exists(doc_path):
        return send_file(doc_path)
    abort(404)

@pages_blueprint.route("/lgbk/help", methods=["GET"])
@context.security.authentication_required
def lgbkhelp():
    logged_in_user=context.security.get_current_user_id()
    privileges = { x : context.security.check_privilege_for_experiment(x, None, None) for x in [ "read", "ops_page", "switch", "experiment_create", "experiment_edit", "experiment_edit"]}
    return render_template("help.html",
        logbook_site=context.LOGBOOK_SITE,
        logged_in_user=logged_in_user,
        logged_in_user_details=json.dumps(context.usergroups.get_userids_matching_pattern(logged_in_user)),
        privileges=json.dumps(privileges))


def __parse_expiration_header__(request):
    expiration = request.headers.get("Webauth-Token-Expiration", "0")
    return int(expiration.replace("t=", ""))//1000000 if expiration.startswith("t=") else int(expiration)

@pages_blueprint.route("/lgbk/<experiment_name>/", methods=["GET"])
@experiment_exists
@context.security.authentication_required
@context.security.authorization_required("read")
def exp_elog(experiment_name):
    logged_in_user=context.security.get_current_user_id()
    exp_info = get_experiment_info(experiment_name)
    instrument_name = exp_info.get("instrument", None) if exp_info else None
    privileges = { x : context.security.check_privilege_for_experiment(x, experiment_name, instrument_name) for x in [ "manage_groups", "delete", "edit", "post", "read", "experiment_create", "experiment_edit", "feedback_read", "feedback_write", "instrument_create", "ops_page", "switch" ]}
    return render_template("lgbk.html",
        experiment_name=experiment_name,
        instrument_name=instrument_name,
        is_locked=json.dumps(exp_info.get("is_locked", False)),
        logged_in_user=logged_in_user,
        privileges=json.dumps(privileges),
        current_sample_name=get_current_sample_name(experiment_name),
        auth_expiration_time=__parse_expiration_header__(request),
        logbook_site=context.LOGBOOK_SITE,
        show_feedback=json.dumps(os.path.exists(os.path.join("static", "json", "feedback_" + context.LOGBOOK_SITE + ".json")))
        )

@pages_blueprint.route("/lgbk/<experiment_name>/elogs/<entry_id>", methods=["GET"])
@experiment_exists
@context.security.authentication_required
@context.security.authorization_required("read")
def exp_elog_entry_only(experiment_name, entry_id):
    logged_in_user=context.security.get_current_user_id()
    exp_info = get_experiment_info(experiment_name)
    instrument_name = exp_info.get("instrument", None) if exp_info else None
    return render_template("elog_entry.html",
        experiment_name=experiment_name,
        instrument_name=instrument_name,
        entry_id=entry_id,
        logged_in_user=logged_in_user,
        logbook_site=context.LOGBOOK_SITE
    )

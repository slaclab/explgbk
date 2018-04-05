import os
import json
import logging
import pkg_resources

import context

from flask import Blueprint, render_template, send_file, abort

from dal.explgbk import get_current_sample_name

pages_blueprint = Blueprint('pages_api', __name__)

logger = logging.getLogger(__name__)

@pages_blueprint.route("/")
def index():
    return render_template("choose_experiment.html")

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
        abort(403)
        return None

@pages_blueprint.route("/lgbk/<experiment_name>/templates/<path:path>", methods=["GET"])
def templates(experiment_name, path):
    return render_template(path, experiment_name=experiment_name)

@pages_blueprint.route("/lgbk/ops", methods=["GET"])
@context.security.authentication_required
def operator_dashboard():
    return render_template("ops.html", logbook_site=context.LOGBOOK_SITE)


@pages_blueprint.route("/lgbk/experiments", methods=["GET"])
@context.security.authentication_required
def choose_experiments():
    return render_template("experiments.html")

@pages_blueprint.route("/lgbk/register_new_experiment", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("edit")
def register_new_experiment():
    return render_template("register_new_experiment.html")

@pages_blueprint.route("/lgbk/experiment_switch", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("edit")
def experiment_switch():
    return render_template("experiment_switch.html")


@pages_blueprint.route("/lgbk/<experiment_name>/", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def exp_elog(experiment_name):
    return render_template("lgbk.html",
        experiment_name=experiment_name,
        logged_in_user=context.security.get_current_user_id(),
        current_sample_name=get_current_sample_name(experiment_name),
        logbook_site=context.LOGBOOK_SITE
        )

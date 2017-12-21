import os
import json
import logging
import pkg_resources

import context

from flask import Blueprint, render_template, send_file, abort

pages_blueprint = Blueprint('pages_api', __name__)

logger = logging.getLogger(__name__)

@pages_blueprint.route("/")
def index():
    return render_template("index.html")

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



@pages_blueprint.route("/experiments/<instrument_id>", methods=["GET"])
def exp_ins(instrument_id):
    return render_template("experiments.html", instrument_id=instrument_id)

@pages_blueprint.route("/<experiment_name>/elog", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def exp_elog(experiment_name):
    return render_template("elog.html", experiment_name=experiment_name)

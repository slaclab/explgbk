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

from flask import Blueprint, jsonify, request, url_for, Response
    
from dal.business_object import get_experiments_for_instrument, get_elog_for_experiment, post_new_elog_entry

__author__ = 'mshankar@slac.stanford.edu'

business_service_blueprint = Blueprint('business_service_api', __name__)

logger = logging.getLogger(__name__)


@business_service_blueprint.route("/<instrument_name>/experiments", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def svc_get_experiments_for_instrument(instrument_name):
    """
    Get the experiments for an instrument
    :param instrument_id: Id of the instrument.
    :return: JSON of the experiment infos for the experiment
    """
    experiments = get_experiments_for_instrument(instrument_name)

    return jsonify({'success': True, 'value': experiments})

@business_service_blueprint.route("/<experiment_name>/elog", methods=["GET"])
@context.security.authentication_required
@context.security.authorization_required("read")
def svc_get_elog_for_experiment(experiment_name):
    """
    Get the elog for an experiment
    :param experiment_name - The name of the experiment - diadaq13
    :return: JSON of the elog entries for an experiment
    """
    elogs = get_elog_for_experiment(experiment_name)

    return jsonify({'success': True, 'value': elogs})

@business_service_blueprint.route("/<experiment_name>/elog", methods=["POST"])
@context.security.authentication_required
@context.security.authorization_required("post")
def svc_add_elog_for_experiment(experiment_name):
    """
    Add an elog entry for the experiment
    The JSON for the elog entry is send as the POST body with these parameters
    content_type - TEXT or HTML
    content - The content of the log message
    run_num - The run number to associate with the log entry
    :param experiment_name - The name of the experiment - diadaq13
    :return: JSON of the elog entries for an experiment
    """
    log_data = request.json
    posted_log_entry = post_new_elog_entry(experiment_name, log_data['content'], log_data['content_type'], log_data.get('run_num', None), context.security.get_current_user_id())
    if posted_log_entry and context.kafka_producer:
        kmsg = {'CRUD': 'INSERT', 'exper_name': experiment_name, 'value': posted_log_entry}
        logger.info("Publishing onto topic elog -  %s", kmsg)
        context.kafka_producer.send("elog", kmsg)

    return jsonify({'success': True, 'value': posted_log_entry})


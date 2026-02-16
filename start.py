import json
import logging
import os
import sys

import dal.exp_cache
from context import security
from flask import Flask
from flask_socket_util import socket_service
from pages import pages_blueprint
from services.explgbk import explgbk_blueprint


root = logging.getLogger()
root.setLevel(logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO")))
logging.getLogger("kafka").setLevel(logging.INFO)
logging.getLogger("engineio").setLevel(logging.WARN)
logging.getLogger("flask_authnz").setLevel(logging.WARN)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
root.addHandler(ch)

logger = logging.getLogger(__name__)

__author__ = "mshankar@slac.stanford.edu"


# Initialize application.
app = Flask("explgbk")
# Set the expiration for static files
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 60 * 60
app.secret_key = "This is a secret key that is somewhat temporary."
app.debug = False


@app.template_filter("json")
def jinga2_jsonfilter(value):
    return json.dumps(value)


# Register routes.
app.register_blueprint(pages_blueprint)
app.register_blueprint(explgbk_blueprint)

socket_service.init_app(
    app,
    security,
    kafkatopics=[
        "experiments",
        "elog",
        "runs",
        "shifts",
        "samples",
        "file_catalog",
        "workflow_jobs",
    ],
)

dal.exp_cache.init_app(app)

logger.info("Server initialization complete")

if __name__ == "__main__":
    print("Please use gunicorn for development as well.")
    sys.exit(-1)

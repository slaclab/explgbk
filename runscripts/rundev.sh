#!/bin/bash

# We pick up installation-specific config from a file outside of this repo.
PRNT_DIR=`dirname $PWD`
G_PRNT_DIR=`dirname $PRNT_DIR`;
GG_PRNT_DIR=`dirname $G_PRNT_DIR`;
GGG_PRNT_DIR=`dirname $GG_PRNT_DIR`;
EXTERNAL_CONFIG_FILE="${GGG_PRNT_DIR}/appdata/explgbk_config/explgbk_config.sh"

if [[ -f "${EXTERNAL_CONFIG_FILE}" ]]
then
   echo "Sourcing deployment specific configuration from ${EXTERNAL_CONFIG_FILE}"
   source "${EXTERNAL_CONFIG_FILE}"
else
   echo "Did not find external deployment specific configuration - ${EXTERNAL_CONFIG_FILE}"
fi

export ACCESS_LOG_FORMAT='%(h)s %(l)s %({REMOTE_USER}i)s %(t)s "%(r)s" "%(q)s" %(s)s %(b)s %(D)s'

# Of course, please change this port to the appropriate port in the 8000-1000 range.
# Also change start:app to your_service:app (this should make it easier to identify your service amongst the pile of gunicorns)
# Add a proxy in the web servce to proxy this port onto the location for this service.
export SERVER_IP_PORT=${SERVER_IP_PORT:-"0.0.0.0:5000"}

# Assume that the current directory for the process is this directory.
export PYTHONPATH="modules/flask_authnz:modules/flask_socket_util:${PYTHONPATH}"

export LOG_LEVEL=${LOG_LEVEL:-"INFO"}
export RELOAD=${RELOAD:-""}
export WORKER_CONFIG=${WORKER_CONFIG:-""}

# The exec assumes you are calling this from supervisord. If you call this from the command line; your bash shell is proabably gone and you need to log in.
exec gunicorn start:app -b ${SERVER_IP_PORT} --worker-class eventlet ${WORKER_CONFIG} ${RELOAD} \
       --log-level=${LOG_LEVEL} --capture-output --enable-stdio-inheritance \
       --timeout 300 --graceful-timeout 1 \
       --access-logfile - --access-logformat "${ACCESS_LOG_FORMAT}"

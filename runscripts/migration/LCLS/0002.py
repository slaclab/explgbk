#!/usr/bin/python
"""
This migration script copies over the group membership from LDAP into the database.
This is how the newer experiments will look like.
We add the user into the database and publish a Kafka message.
The rolemgr then adds it to LDAP triggered by the Kafka message.
So, both database and LDAP have the group membership explicitly listed.
"""
import os
import logging
import argparse

from pymongo import MongoClient
from flask_authnz import UserGroups

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

MONGODB_HOST=os.environ.get('MONGODB_HOST', "localhost")
MONGODB_PORT=int(os.environ.get('MONGODB_PORT', 27017))
MONGODB_USERNAME=os.environ['MONGODB_USERNAME']
MONGODB_PASSWORD=os.environ['MONGODB_PASSWORD']

usergroups = UserGroups()
logbookclient = MongoClient(host=MONGODB_HOST, username=MONGODB_USERNAME, password=MONGODB_PASSWORD, tz_aware=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate group memberships from LDAP to the database')
    parser.add_argument('--dryrun', action="store_true")
    parser.add_argument('experiment', help='Specify experiment name; to run this for all experiments, use "all"')
    args = parser.parse_args()

    experiments = []
    def __check_and_add__(experiment_name):
        if experiment_name in ["admin", "config", "local", "site"]:
            return
        expdb = logbookclient[experiment_name]
        collnames = list(expdb.list_collection_names())
        if 'info' in collnames and 'roles' in collnames:
            info = expdb["info"].find_one({}, {"latest_setup": 0})
            if 'name' not in info or 'instrument' not in info:
                logger.debug("Database %s has a info collection but the info object does not have an instrument or name", experiment_name)
                return
            if expdb["roles"].count_documents({"players": experiment_name}) <= 0:
                logger.debug("Experiment %s has does not have an experiment specific role", experiment_name)
                return
            experiments.append(experiment_name)
    if args.experiment != "all":
        __check_and_add__(args.experiment)
    else:
        database_names = list(logbookclient.database_names())
        for experiment_name in database_names:
            __check_and_add__(experiment_name)

    for experiment in experiments:
        logger.debug("Migrating LDAP memberships for %s", experiment)
        expdb = logbookclient[experiment]
        for role in expdb["roles"].find({"players": experiment}):
            logger.info("Found role %s for experiment %s", role["name"], experiment)
            for uid in usergroups.get_group_members(experiment):
                logger.info("Adding user %s to role %s for experiment %s", "uid:"+uid, role["name"], experiment)
                if args.dryrun:
                    continue
                expdb["roles"].update_one({"app": role["app"], "name": role["name"]}, {"$addToSet": {"players": "uid:"+uid}})

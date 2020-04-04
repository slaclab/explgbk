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
import re

from pymongo import MongoClient
from flask_authnz import UserGroups


MONGODB_HOST=os.environ.get('MONGODB_HOST', "localhost")
MONGODB_PORT=int(os.environ.get('MONGODB_PORT', 27017))
MONGODB_USERNAME=os.environ['MONGODB_USERNAME']
MONGODB_PASSWORD=os.environ['MONGODB_PASSWORD']

usergroups = UserGroups()
logbookclient = MongoClient(host=MONGODB_HOST, port=MONGODB_PORT, username=MONGODB_USERNAME, password=MONGODB_PASSWORD, tz_aware=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate group memberships from LDAP to the database')
    parser.add_argument('--verbose', action="store_true")
    parser.add_argument('--dryrun', action="store_true")
    parser.add_argument('experiment', help='Specify experiment name; to run this for all experiments, use "all"')
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

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
            logger.debug("Found role %s for experiment %s", role["name"], experiment)
            try:
                grps = usergroups.get_group_members(experiment)
            except KeyError as ke:
                if ke.args[0] == "memberUid":
                    logger.debug("Empty group membership for %s ", experiment)
                    continue
                else:
                    raise ke
            except Exception as ex:
                raise ex
            if isinstance(grps, list):
                for uid in usergroups.get_group_members(experiment):
                    if len(uid) < 3:
                        logger.error("The experiment group %s probably has only one member; too small a userid %s", experiment, uid)
                        continue
                    logger.info("Adding user %s to role %s for experiment %s", "uid:"+uid, role["name"], experiment)
                    if args.dryrun:
                        continue
                    expdb["roles"].update_one({"app": role["app"], "name": role["name"]}, {"$addToSet": {"players": "uid:"+uid}})
            elif isinstance(grps, str):
                    uid = grps
                    if len(uid) < 3:
                        logger.error("The experiment group %s probably has only one member; too small a userid %s", experiment, uid)
                        continue
                    logger.info("Adding user %s to role %s for experiment %s", "uid:"+uid, role["name"], experiment)
                    if args.dryrun:
                        continue
                    expdb["roles"].update_one({"app": role["app"], "name": role["name"]}, {"$addToSet": {"players": "uid:"+uid}})
            else:
                raise Exception("Unexpected type for roles %s", type(grps))

        for role in expdb["roles"].find({"players": {"$regex": re.compile("^ps-.*")}}):
            instr_players = [x for x in role["players"] if x.startswith("ps-")]
            if not instr_players:
                raise Exception("Mongo and python disagree.")
                continue
            logger.info("Removing instrument roles %s for role %s for experiment %s", ",".join(instr_players), role["name"], experiment)
            if args.dryrun:
                continue
            expdb["roles"].update_one({"app": role["app"], "name": role["name"]}, {"$pull": {"players": {"$in": instr_players }}})

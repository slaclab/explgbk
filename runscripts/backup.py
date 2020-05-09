#!/usr/bin/env python
'''
Script for backing up the logbook.
Meant to run as a cron job (perhaps daily) on the machines that have read access to the shard/replica sets storage.
One can potentially run this on all machines with access to a shared's replica set.
Run these at staggered times; the timestamp comparision will ensure that we do not backup a database multiple times in a time period.
The staggering will ensure that one's replica set's backups will not mess up the other replica set's backups.

This script relies on these settings in the mongod.conf for the shards
storage:
  engine: wiredTiger
  directoryPerDB: true
The directoryPerDB setting creates a folder for each database(or experiment) with the files for the various collections restricted to that folder.
We determine the most recent timestamp for all the files in a database folder and use that as a proxy for the database modified timestamp.
We initiate a backup if the database's most recent timestamp is more recent than the latest backup timestamp.

Note regarding the imagestores: We're deprecating support for external image stores; so only the mongo image stores are backed up.
The file based image stores are expected to be backed up to tape as part of the experimental data backup.

Backups are stored in a experiment per folder format with the filename of the backup based on the time the backup was initiated.
'''

import os
import sys
import logging
import glob
import argparse
import subprocess
import datetime
import shutil
import pathlib

from pymongo import MongoClient, ASCENDING, DESCENDING

DATETIME_FILE_NAME_FORMAT = "%Y_%m_%d_%H_%M_%S"

# Given a set of backup folders, we'll need to unambigously determine
# 1) The date the backup was made
# 2) If the backup was completed successfully.

logger = logging.getLogger(__name__)

def configureLogging(verbose):
    loglevel = logging.INFO

    if verbose:
        loglevel = logging.DEBUG

    root = logging.getLogger()
    root.setLevel(loglevel)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(loglevel)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root.addHandler(ch)

def test_executable_exists(commands):
    """
    Check to see if we can run the speficied command.
    """
    try:
        subprocess.run(commands, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return True
    except:
        logger.exception("Exception when checking to see if command exists %s", commands)
        sys.exit(-1)

def find_latest_timestamp_in_folder(folder):
    list_of_files = glob.glob(os.path.join(folder, "*"))
    if list_of_files:
        latest_file = max(list_of_files, key=os.path.getmtime)
        return datetime.datetime.fromtimestamp(os.path.getmtime(latest_file))
    return None

def backup_experiment(args, database_name):
    logger.debug("Looking to backup for %s", database_name)
    db_backup_folder = os.path.join(args.backup_folder, database_name)
    pathlib.Path(db_backup_folder).mkdir(parents=True, exist_ok=True)
    archive_file_name = os.path.join(db_backup_folder, datetime.datetime.now().strftime(DATETIME_FILE_NAME_FORMAT) + ".gz")

    latest_backup_ts = find_latest_timestamp_in_folder(db_backup_folder)
    if latest_backup_ts and args.dbpath is not None:
        logger.debug("We have a backup and a dbpath. Checking the dbpath to see if we need to do a backup")
        latest_mongo_file_ts = find_latest_timestamp_in_folder(os.path.join(args.dbpath, database_name.replace("-", ".45")))
        if not latest_mongo_file_ts:
            logger.error("Cannot seem to find any files in the dbpath folder %s for database %s", os.path.join(args.dbpath, database_name), database_name)
            sys.exit(-1)
        if latest_backup_ts > latest_mongo_file_ts:
            logger.info("%s - we already have a backup %s more recent than the database %s", database_name, latest_backup_ts, latest_mongo_file_ts)
            return

    # We need to make a backup. Check to see if we need to delete an older backup
    if args.keep_backups > 1:
        logger.debug("Keeping at most %s backups", args.keep_backups)
        list_of_files = glob.glob(os.path.join(db_backup_folder, "*.gz"))
        if len(list_of_files) > args.keep_backups:
            earliest_file = min(list_of_files, key=os.path.getmtime)
            if earliest_file:
                logger.info("%s - Removing earliest file %s for database", database_name, earliest_file)
                os.remove(earliest_file)

    logger.info("%s - New archive %s", database_name, archive_file_name)
    try:
        mdargs = [ args.mongodump_path,
            "-vv",
            "--host", args.mongo_host,
            "--port", str(args.mongo_port),
            "--username", args.mongo_user,
            "--password", args.mongo_password,
            "--authenticationDatabase", args.mongo_auth_db,
            "--db", database_name,
            "--gzip",
            "--archive=" + archive_file_name
            ]
        mdp = subprocess.run(mdargs, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
        logger.debug(mdp.stdout)
        logger.debug(mdp.stderr)
        if mdp.returncode != 0:
            logger.error(mdp.stdout)
            logger.error("mongodump command - %s - returned non-zero error code %s", " ".join(mdargs), mdp.returncode)
            sys.exit(-1)
    except:
        logger.exception("Exception dumping database to %s", archive_file_name)
        sys.exit(-1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose",     action='store_true', help="Turn on verbose logging")
    parser.add_argument("--mongo_host",        help="The hostname of the mongodb server. In sharded instances, this should point to the mongos router.", required=True)
    parser.add_argument("--mongo_port",        help="The port to the mongodb/mongos server.", default=27017, type=int)
    parser.add_argument("--mongo_user",        help="The username used for connecting to the Mongo server; what works is giving this user the backup role in the admin database.", required=True)
    parser.add_argument("--mongo_password",    help="The password for the user.", required=True)
    parser.add_argument("--mongo_auth_db",     help="The authentication database for the user. Since this user is one that spans databases; we probably need the user to come from the admin database", default="admin")
    parser.add_argument("--mongodump_path",    help="Full path to the mongodump command. If not specified, we use mongodump from the PATH.", default="mongodump")
    parser.add_argument("--keep_backups",      help="Keep at least this many complete backups; older backups are deleted.", default=0, type=int)
    parser.add_argument("--dbpath",            help="The db path to the shard/replica set we are trying to backup. Note, we assume that directoryPerDB is set and we have a folder per database.")
    parser.add_argument("backup_folder",       help="The folder containing the backups.")

    args = parser.parse_args()
    configureLogging(args.verbose)
    test_executable_exists([args.mongodump_path, "--help"])

    logbookclient = MongoClient(
        host=args.mongo_host,
        port=args.mongo_port,
        username=args.mongo_user,
        password=args.mongo_password,
        authSource=args.mongo_auth_db,
        tz_aware=True)

    backup_experiment(args, "site")

    logger.info("Gathering the list of experiments")
    database_names = sorted(list(logbookclient.list_database_names()))
    for experiment_name in database_names:
        if experiment_name in ["admin", "config", "local"]:
            logger.info("Not backing up %s", experiment_name)
            continue
        backup_experiment(args, experiment_name)

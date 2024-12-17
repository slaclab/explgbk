#!/usr/bin/env python
'''
Script for backing up the logbook/mongo.

Note regarding the imagestores: We're deprecating support for external image stores; so only the mongo image stores are backed up.
The file based image stores are expected to be backed up to tape as part of the experimental data backup.

Backups are stored in a database per folder format with the filename of the backup based on the time the backup was initiated.
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

def backup_database(args, database_name):
    logger.debug("Looking to backup for %s", database_name)
    db_backup_folder = os.path.join(args.backup_folder, database_name)
    pathlib.Path(db_backup_folder).mkdir(parents=True, exist_ok=True)
    archive_file_name = os.path.join(db_backup_folder, datetime.datetime.now().strftime(DATETIME_FILE_NAME_FORMAT) + ".gz")

    # We need to make a backup. Check to see if we need to delete an older backup
    if args.keep_backups != -1:
        logger.debug("Keeping at most %s backups", args.keep_backups)
        list_of_files = glob.glob(os.path.join(db_backup_folder, "*.gz"))
        if len(list_of_files) > args.keep_backups:
            for rmi in range(len(list_of_files) - args.keep_backups):
                list_of_files = glob.glob(os.path.join(db_backup_folder, "*.gz"))
                earliest_file = min(list_of_files, key=os.path.getmtime)
                if earliest_file:
                    logger.info("%s - Removing earliest file %s for database", database_name, earliest_file)
                    os.remove(earliest_file)

    uriwithdb = args.mongo_uri.split("?")[0] + database_name + "?" + args.mongo_uri.split("?")[1]

    logger.info("%s - New archive %s", database_name, archive_file_name)
    try:
        mdargs = [ args.mongodump_path,
            "-vv",
            "--uri", uriwithdb,
            "--gzip",
            "--archive=" + archive_file_name
            ]
        mdp = subprocess.run(mdargs, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
        if mdp.returncode != 0:
            logger.error("mongodump command - %s - returned non-zero error code %s", " ".join(mdargs), mdp.returncode)
            logger.error(mdp.stdout)
            logger.error(mdp.stderr)
        else:
            logger.debug(mdp.stdout)
            logger.debug(mdp.stderr)

    except:
        logger.exception("Exception dumping database to %s", archive_file_name)
        sys.exit(-1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose",     action='store_true', help="Turn on verbose logging")
    parser.add_argument("--mongo_uri",         help="The MongoURI to use; this seems the best way to specify some useful options including readPreference=secondary. This needs to be passed in a certain way for mongodump to work; that is, the path part should end with a / followed immediately by a ? with the options. For example, mongodb://backupuser:backuppassword@localhost:27017/?authSource=admin&readPreference=secondary", required=True)
    parser.add_argument("--mongodump_path",    help="Full path to the mongodump command. If not specified, we use mongodump from the PATH.", default="mongodump")
    parser.add_argument("--keep_backups",      help="Keep at least this many complete backups; older backups are deleted.", default=-1, type=int)
    parser.add_argument("backup_folder",       help="The folder containing the backups.")

    args = parser.parse_args()
    configureLogging(args.verbose)
    test_executable_exists([args.mongodump_path, "--help"])

    if not os.path.exists(args.backup_folder) or not os.path.isdir(args.backup_folder):
        logger.error("The root folder for database backups %s does not seem to exist", args.backup_folder)
        sys.exit(-1)

    logbookclient = MongoClient(args.mongo_uri, tz_aware=True)

    logger.info("Gathering the list of databases")
    database_names = sorted(list(logbookclient.list_database_names()))
    for database_name in database_names:
        if database_name in [ "config", "local" ]:
            logger.info("Not backing up system database %s", database_name)
            continue
        backup_database(args, database_name)

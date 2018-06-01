#!/usr/bin/env python
'''
Script for backing up the database and the attachments image store.
Meant to run as a cron job (perhaps daily).
We create a full backup of the database and the image store.

1) We create a folder for the backup.
2) Move the latest softlink to point to this folder.
3) Use mongodump to dump the entire database.
4) Use weed backup to dump the entire image store.
5) Create a backup_done file to indicate that the backup was successfully completed.
6) Remove older folders if applicable.
'''

import os
import sys
import logging
import argparse
import subprocess
import datetime
import shutil

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose",     action='store_true', help="Turn on verbose logging")
    parser.add_argument("--mongo_host",        help="The hostname of the mongodb server. In sharded instances, this should point to the mongos router.", required=True)
    parser.add_argument("--mongo_port",        help="The port to the mongodb/mongos server.", default="27017")
    parser.add_argument("--mongo_user",        help="The username used for connecting to the Mongo server; what works is giving this user the backup role in the admin database.", required=True)
    parser.add_argument("--mongo_password",    help="The password for the user.", required=True)
    parser.add_argument("--mongo_auth_db",     help="The authentication database for the user. Since this user is one that spans databases; we probably need the user to come from the admin database", default="admin")
    parser.add_argument("--mongodump_path",    help="Full path to the mongodump command. If not specified, we use mongodump from the PATH.", default="mongodump")
    parser.add_argument("--seaweed_master",    help="The hostname of the seaweed master server", required=True)
    parser.add_argument("--seaweed_port",      help="The port to the seaweed master server.", required=True)
    parser.add_argument("--seaweed_path",      help="Full path to the weed command. If not specified, we use weed from the PATH.", default="weed")
    parser.add_argument("--keep_backups",      help="Keep at least this many complete backups; older backups are deleted.", default=0, type=int)
    parser.add_argument("backup_folder",       help="The folder containing the backups.")

    backup_started_at = datetime.datetime.now()
    args = parser.parse_args()
    configureLogging(args.verbose)
    test_executable_exists([args.mongodump_path, "--help"])
    test_executable_exists([args.seaweed_path, "--help"])

    todays_folder = os.path.join(args.backup_folder, "explgbk_{0}".format(datetime.date.today().strftime("%Y-%m-%d")))
    logger.debug("Folder for backup is %s", todays_folder)
    if os.path.exists(todays_folder):
        print("Folder %s already exists. Please rename this to another folder and try again" % todays_folder)
        sys.exit(-1)
    logger.info("Creating the backup folder - %s", todays_folder)
    os.mkdir(todays_folder)

    try:
        mongo_backup_folder = os.path.join(todays_folder, "mongodump")
        os.mkdir(mongo_backup_folder)
        mdargs = [ args.mongodump_path,
            "-vv",
            "--host", args.mongo_host,
            "--port", args.mongo_port,
            "--username", args.mongo_user,
            "--password", args.mongo_password,
            "--authenticationDatabase", args.mongo_auth_db,
            "--gzip",
            "--out", mongo_backup_folder
            ]
        mdp = subprocess.run(mdargs, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
        logger.debug(mdp.stdout)
        with open(os.path.join(todays_folder, "backup.log"), "a") as f:
            f.write(mdp.stdout)
        if mdp.returncode != 0:
            logger.error(mdp.stdout)
            logger.error("mongodump command - %s - returned non-zero error code %s", " ".join(mdargs), mdp.returncode)
            sys.exit(-1)
    except:
        logger.exception("Exception dumping database to folder %s", todays_folder)
        sys.exit(-1)

    try:
        seaweed_backup_folder = os.path.join(todays_folder, "attachments")
        os.mkdir(seaweed_backup_folder)
        wb_main_args = [ args.seaweed_path,
            "backup",
            "-server={0}:{1}".format(args.seaweed_master, args.seaweed_port),
            "-dir={0}".format(seaweed_backup_folder)
            ]
        for volume in range(100):
            wbargs = list(wb_main_args)
            wbargs.append("-volumeId={0}".format(volume))
            wbp = subprocess.run(wbargs, check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
            logger.debug(wbp.stdout)
            with open(os.path.join(todays_folder, "backup.log"), "a") as f:
                f.write(wbp.stdout)
            if wbp.returncode != 0:
                logger.error(wbp.stdout)
                logger.error("weed backup command - %s - returned non-zero error code %s", " ".join(wbargs), wbp.returncode)
                sys.exit(-1)
    except:
        logger.exception("Exception dumping attachments to folder %s", todays_folder)
        sys.exit(-1)

    with open(os.path.join(todays_folder, "backup_done"), 'w') as f:
        f.write("Backup started at {0} completed at {1}".format(backup_started_at.isoformat(), datetime.datetime.now().isoformat()))

    if args.keep_backups > 1:
        logger.debug("Keeping at most %s backups", args.keep_backups)
        folders_with_backups = []
        for p in os.listdir(args.backup_folder):
            if p.startswith("explgbk_") and os.path.exists(os.path.join(args.backup_folder, p, 'backup_done')) and todays_folder != os.path.join(args.backup_folder, p):
                folders_with_backups.append(os.path.join(args.backup_folder, p))
        folders_with_backups = sorted(folders_with_backups)
        logger.debug("Folders with backups \n  %s", "\n  ".join(folders_with_backups))
        if len(folders_with_backups) > args.keep_backups:
            folders_to_delete = folders_with_backups[:-args.keep_backups]
            logger.debug("Folders to delete \n  %s", "\n  ".join(folders_to_delete))
            for dp in folders_to_delete:
                with open(os.path.join(todays_folder, "backup.log"), 'a') as f:
                    f.write("Deleting older backup folder {0}".format(dp))
                shutil.rmtree(dp)

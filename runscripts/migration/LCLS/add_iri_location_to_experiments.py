#!/usr/bin/env python3
"""
Add the "iri" location to specific experiments' info.params.dm_locations.

The dm_locations field is a space-separated string, e.g. "SRCF_FFB NERSC iri".
Experiments not listed in EXPERIMENTS below must have "iri" added manually,
via the experiment edit UI, or by setting all_experiments=True on the site_config
entry for "iri".

Edit the EXPERIMENTS list before running.

Run with:
    python add_iri_location_to_experiments.py [--execute] [--verbose]

Dry-run is the default. Pass --execute to actually write to the database.
"""

import os
import argparse
import logging

from pymongo import MongoClient

MONGODB_URL = os.environ.get("MONGODB_URL")
MONGODB_HOST = os.environ.get("MONGODB_HOST", "localhost")
MONGODB_PORT = int(os.environ.get("MONGODB_PORT", 27017))
MONGODB_USERNAME = os.environ["MONGODB_USERNAME"]
MONGODB_PASSWORD = os.environ["MONGODB_PASSWORD"]
EXPERIMENTS = ["diadaq13"]
IRI_LOCATIONS = ["s3df-iri", "nersc-iri"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Add the 'iri' DM location string to per-experiment info.params.dm_locations"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually write to the database (default is dry-run)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    if not EXPERIMENTS:
        logger.error(
            "No experiments listed — edit the EXPERIMENTS list in this script and re-run."
        )
        raise SystemExit(1)

    client = MongoClient(
        host=MONGODB_URL or MONGODB_HOST,
        port=None if MONGODB_URL else MONGODB_PORT,
        username=MONGODB_USERNAME,
        password=MONGODB_PASSWORD,
        tz_aware=True,
    )

    for expname in EXPERIMENTS:
        info = client[expname]["info"].find_one({})
        if not info:
            logger.warning("SKIP %s: no info document found.", expname)
            continue

        current = (info.get("params", {}).get("dm_locations") or "").strip()
        locs = current.split() if current else []
        logger.info("%s: current dm_locations = %r", expname, current)

        to_add = [loc for loc in IRI_LOCATIONS if loc not in locs]
        if not to_add:
            logger.info(
                "SKIP %s: all IRI locations already present (dm_locations=%r).",
                expname,
                current,
            )
            continue

        # add missing IRI locations
        locs.extend(to_add)

        updated = " ".join(locs)
        logger.info("UPDATED %s: dm_locations will be set to %r", expname, updated)

        if args.execute:
            client[expname]["info"].update_one(
                {}, {"$set": {"params.dm_locations": updated}}
            )
        else:
            logger.info("(dry-run — no write performed; pass --execute to apply)")

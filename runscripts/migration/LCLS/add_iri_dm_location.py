#!/usr/bin/env python3
"""
Add the "iri" site location to site.site_config.dm_locations.
The "iri" location uses the IRI/NERSC JID backend deployed at arpirijid.

Run with:
    python add_iri_dm_location.py [--execute]

Dry-run is the default. Pass --execute to actually write to the database.
"""

import os
import argparse

from pymongo import MongoClient

MONGODB_URL = os.environ.get("MONGODB_URL")
MONGODB_HOST = os.environ.get("MONGODB_HOST", "localhost")
MONGODB_PORT = int(os.environ.get("MONGODB_PORT", 27017))
MONGODB_USERNAME = os.environ["MONGODB_USERNAME"]
MONGODB_PASSWORD = os.environ["MONGODB_PASSWORD"]

IRI_LOCATIONS = [
    {
        "name": "s3df-iri",
        "all_experiments": False,
        "jid_prefix": "https://psdm.slac.stanford.edu/arpirijid/",
        "jid_ca_cert": "/reg/g/psdm/web/ws/prod/appdata/wflow_trig/rootCA.crt",
        "jid_client_cert": "/reg/g/psdm/web/ws/prod/appdata/wflow_trig/wflow_trig.crt",
        "jid_client_key": "/reg/g/psdm/web/ws/prod/appdata/wflow_trig/wflow_trig.key",
    },
    {
        "name": "nersc-iri",
        "all_experiments": False,
        "jid_prefix": "https://psdm.slac.stanford.edu/arpirijid/",
        "jid_ca_cert": "/reg/g/psdm/web/ws/prod/appdata/wflow_trig/rootCA.crt",
        "jid_client_cert": "/reg/g/psdm/web/ws/prod/appdata/wflow_trig/wflow_trig.crt",
        "jid_client_key": "/reg/g/psdm/web/ws/prod/appdata/wflow_trig/wflow_trig.key",
    },
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Add the 'iri' DM location to site_config"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually write to the database (default is dry-run)",
    )
    args = parser.parse_args()

    client = MongoClient(
        host=MONGODB_URL or MONGODB_HOST,
        port=None if MONGODB_URL else MONGODB_PORT,
        username=MONGODB_USERNAME,
        password=MONGODB_PASSWORD,
        tz_aware=True,
    )

    site_config = client["site"]["site_config"]
    for location in IRI_LOCATIONS:
        if site_config.find_one({"dm_locations.name": location["name"]}):
            print(
                f"Location '{location['name']}' already present in site_config.dm_locations — skipping."
            )
        else:
            print(
                f"Would add '{location['name']}' to site_config.dm_locations: {location}"
            )
            if args.execute:
                site_config.update_one({}, {"$push": {"dm_locations": location}})
                print("Done.")
            else:
                print("(dry-run — no write performed; pass --execute to apply)")

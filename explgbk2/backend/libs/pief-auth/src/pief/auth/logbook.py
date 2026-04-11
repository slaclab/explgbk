"""Logbook domain permission helpers.

Types: experiment, site.
Relations are placeholders — the logbook FGA model is not yet finalized.
"""

import openfga_sdk
from openfga_sdk.client.models import ClientCheckRequest


async def check_experiment_permission(
    client: openfga_sdk.OpenFgaClient,
    user_id: str,
    relation: str,
    experiment_id: str,
) -> bool:
    """Return True if user_id has `relation` on experiment:experiment_id."""
    response = await client.check(
        ClientCheckRequest(
            user=f"user:{user_id}",
            relation=relation,
            object=f"experiment:{experiment_id}",
        )
    )
    return bool(response.allowed)


async def check_site_permission(
    client: openfga_sdk.OpenFgaClient,
    user_id: str,
    relation: str,
    site_id: str,
) -> bool:
    """Return True if user_id has `relation` on site:site_id."""
    response = await client.check(
        ClientCheckRequest(
            user=f"user:{user_id}",
            relation=relation,
            object=f"site:{site_id}",
        )
    )
    return bool(response.allowed)

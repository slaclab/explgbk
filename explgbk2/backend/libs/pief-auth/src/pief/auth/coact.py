"""CoAct domain permission helpers.

Types: system, facility, repo.
See schema.fga.yaml for the full coact-authorization-model relations.
"""

import openfga_sdk
from openfga_sdk.client.models import ClientCheckRequest


async def check_facility_permission(
    client: openfga_sdk.OpenFgaClient,
    user_id: str,
    relation: str,
    facility_id: str,
) -> bool:
    """Return True if user_id has `relation` on facility:facility_id.

    Common relations: admin, czar, member, serviceaccount, can_manage, can_view.
    """
    response = await client.check(
        ClientCheckRequest(
            user=f"user:{user_id}",
            relation=relation,
            object=f"facility:{facility_id}",
        )
    )
    return bool(response.allowed)


async def check_repo_permission(
    client: openfga_sdk.OpenFgaClient,
    user_id: str,
    relation: str,
    repo_id: str,
) -> bool:
    """Return True if user_id has `relation` on repo:repo_id.

    Common relations: principal, leader, member, can_manage, can_view.
    """
    response = await client.check(
        ClientCheckRequest(
            user=f"user:{user_id}",
            relation=relation,
            object=f"repo:{repo_id}",
        )
    )
    return bool(response.allowed)

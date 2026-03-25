from app.core.db import get_mongo_client
from app.models.cache import Experiment
from tests.utils.utils import random_lower_string


async def create_random_experiment(players: list[str] | None = None) -> Experiment:
    name = random_lower_string()[:16]
    description = random_lower_string()
    players = players or []

    # Insert into explgbk_cache.experiments via Beanie (for GET / and /names)
    experiment = Experiment(
        id=name,
        name=name,
        description=description,
        instrument="TST",
        players=players,
        post_players=players,
    )
    await experiment.insert()

    # Create the per-experiment database (for GET /{id})
    client = get_mongo_client()
    await client[name]["info"].insert_one(
        {"_id": name, "name": name, "description": description, "instrument": "TST"}
    )
    if players:
        await client[name]["roles"].insert_one(
            {"app": "LogBook", "name": "Writer", "players": players}
        )

    return experiment

from httpx import AsyncClient

from app.core.config import settings
from tests.utils.experiment import create_random_experiment


async def test_read_experiments_superuser(
    client: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    await create_random_experiment()
    await create_random_experiment()
    response = await client.get(
        f"{settings.API_V1_STR}/experiments/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert "count" in content
    assert len(content["data"]) >= 2


async def test_read_experiments_normal_user_only_sees_own(
    client: AsyncClient, normal_user_token_headers: dict[str, str]
) -> None:
    from app.core.config import settings as s

    # Create an experiment the normal user is a player in
    user_key = f"uid:{s.EMAIL_TEST_USER}"
    owned = await create_random_experiment(players=[user_key])
    # Create one they're not a player in
    await create_random_experiment()

    response = await client.get(
        f"{settings.API_V1_STR}/experiments/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    names = [exp["name"] for exp in content["data"]]
    assert owned.name in names


async def test_read_experiment_names_superuser(
    client: AsyncClient, superuser_token_headers: dict[str, str]
) -> None:
    experiment = await create_random_experiment()
    response = await client.get(
        f"{settings.API_V1_STR}/experiments/names",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert isinstance(content, list)
    assert experiment.name in content


async def test_read_experiment_names_normal_user(
    client: AsyncClient, normal_user_token_headers: dict[str, str]
) -> None:
    from app.core.config import settings as s

    user_key = f"uid:{s.EMAIL_TEST_USER}"
    owned = await create_random_experiment(players=[user_key])
    not_owned = await create_random_experiment(players=[])

    response = await client.get(
        f"{settings.API_V1_STR}/experiments/names",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert owned.name in content
    assert not_owned.name not in content

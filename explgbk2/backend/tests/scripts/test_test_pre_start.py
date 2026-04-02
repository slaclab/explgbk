from unittest.mock import AsyncMock, MagicMock, patch

from app.tests_pre_start import init, logger


async def test_init_successful_connection() -> None:
    admin_mock = MagicMock()

    with (
        patch("app.tests_pre_start.AsyncMongoClient") as client_cls,
        patch.object(logger, "info"),
        patch.object(logger, "error"),
        patch.object(logger, "warn"),
    ):
        client = MagicMock()
        client.admin = admin_mock
        admin_mock.command = AsyncMock(return_value={"ok": 1})
        client_cls.return_value = client

        try:
            await init()
            connection_successful = True
        except Exception:
            connection_successful = False

        assert connection_successful, (
            "The database connection should be successful and not raise an exception."
        )

        admin_mock.command.assert_called_once_with("ping")

from pief.auth.client import AuthSettings


def test_auth_settings_defaults():
    settings = AuthSettings(
        OPENFGA_API_HOST="localhost:8080",
        OPENFGA_STORE_ID="test-store",
        OPENFGA_MODEL_ID="test-model",
    )
    assert settings.OPENFGA_API_SCHEME == "http"
    assert settings.OPENFGA_API_HOST == "localhost:8080"
    assert settings.OPENFGA_STORE_ID == "test-store"
    assert settings.OPENFGA_MODEL_ID == "test-model"


def test_auth_settings_https_scheme():
    settings = AuthSettings(
        OPENFGA_API_SCHEME="https",
        OPENFGA_API_HOST="fga.example.com",
        OPENFGA_STORE_ID="s1",
        OPENFGA_MODEL_ID="m1",
    )
    assert settings.OPENFGA_API_SCHEME == "https"


def test_fga_client_dep_import():
    from pief.auth.deps import FGAClientDep  # noqa: F401


def test_logbook_imports():
    from pief.auth.logbook import check_experiment_permission, check_site_permission  # noqa: F401


def test_coact_imports():
    from pief.auth.coact import check_facility_permission, check_repo_permission  # noqa: F401

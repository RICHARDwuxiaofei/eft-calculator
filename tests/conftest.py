"""Never write the real user's Qt settings during a test run."""
import pytest


@pytest.fixture(autouse=True)
def isolated_ui_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("EFT_TEST_SETTINGS_DIRECTORY", str(tmp_path / "settings"))

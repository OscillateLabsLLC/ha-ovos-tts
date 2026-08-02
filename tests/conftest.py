"""Fixtures for OVOS TTS Server tests."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ovos_tts.const import (
    CONF_BASE_URL,
    CONF_LANG,
    CONF_VOICE,
    DOMAIN,
)

TEST_HOST = "192.168.1.100"
TEST_PORT = 9666
TEST_BASE_URL = f"http://{TEST_HOST}:{TEST_PORT}"
STATUS_PAYLOAD = {"plugin": "piper", "default_lang": "en", "langs": ["en", "it"]}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in all tests."""
    return


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry matching a successful config flow."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="OVOS TTS (piper)",
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_VOICE: None,
            CONF_LANG: "en",
            "verify_ssl": True,
            CONF_BASE_URL: TEST_BASE_URL,
        },
    )


def mock_status(aioclient_mock: AiohttpClientMocker, **overrides) -> None:
    """Mock the server /status endpoint."""
    aioclient_mock.get(f"{TEST_BASE_URL}/status", json={**STATUS_PAYLOAD, **overrides})

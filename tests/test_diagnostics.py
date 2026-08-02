"""Tests for OVOS TTS Server diagnostics."""

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ovos_tts.diagnostics import async_get_config_entry_diagnostics

from .conftest import mock_status


async def test_diagnostics_redacts_host(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Diagnostics include server status and redact the host/URL."""
    mock_status(aioclient_mock)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diagnostics["entry_data"]["host"] == REDACTED
    assert diagnostics["entry_data"]["base_url"] == REDACTED
    assert diagnostics["server_status"] == {
        "plugin": "piper",
        "default_lang": "en",
        "supported_langs": ["en", "it"],
    }

"""Tests for the OVOS TTS Server config flow."""

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ovos_tts.config_flow import _build_base_url
from custom_components.ovos_tts.const import DOMAIN

from .conftest import TEST_BASE_URL, TEST_HOST, TEST_PORT, mock_status

USER_INPUT = {"host": TEST_HOST, "port": TEST_PORT, "verify_ssl": True}


async def test_user_flow_success(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A valid server creates an entry with discovered languages."""
    mock_status(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OVOS TTS (piper)"
    assert result["data"] == {
        "host": TEST_HOST,
        "port": TEST_PORT,
        "voice": None,
        "language": "en",
        "verify_ssl": True,
        "base_url": TEST_BASE_URL,
    }


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (aiohttp.ClientError(), "cannot_connect"),
        (TimeoutError(), "cannot_connect"),
        (ValueError("boom"), "unknown"),
    ],
)
async def test_user_flow_errors_and_recovery(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    exc: Exception,
    error: str,
) -> None:
    """Connection failures show an error, and the flow recovers."""
    aioclient_mock.get(f"{TEST_BASE_URL}/status", exc=exc)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    aioclient_mock.clear_requests()
    mock_status(aioclient_mock)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_invalid_lang(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An unsupported language override shows an error, then recovers."""
    mock_status(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={**USER_INPUT, "language": "de"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_lang"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={**USER_INPUT, "language": "it"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["language"] == "it"


async def test_user_flow_duplicate_aborts(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Configuring the same host/port twice aborts."""
    mock_config_entry.add_to_hass(hass)
    mock_status(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow_success(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reconfiguring updates entry data and reloads."""
    mock_config_entry.add_to_hass(hass)
    new_base = "http://10.0.0.5:9666"
    aioclient_mock.get(
        f"{new_base}/status",
        json={"plugin": "mimic", "default_lang": "en", "langs": ["en"]},
    )

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"host": "10.0.0.5", "port": 9666, "verify_ssl": True},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data["base_url"] == new_base
    assert mock_config_entry.title == "OVOS TTS (mimic)"


async def test_reconfigure_flow_error_and_recovery(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failed reconfigure shows an error and recovers on retry."""
    mock_config_entry.add_to_hass(hass)
    aioclient_mock.get(f"{TEST_BASE_URL}/status", exc=aiohttp.ClientError())

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    aioclient_mock.clear_requests()
    mock_status(aioclient_mock)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    ("host", "port", "expected"),
    [
        ("192.168.1.5", 9666, "http://192.168.1.5:9666"),
        ("192.168.1.5/", 9666, "http://192.168.1.5:9666"),
        ("https://tts.example.com", 443, "https://tts.example.com"),
        ("https://tts.example.com", 9666, "https://tts.example.com:9666"),
        ("http://host.local:8080", 9666, "http://host.local:8080"),
    ],
)
def test_build_base_url(host: str, port: int, expected: str) -> None:
    """Base URL handles bare hosts, schemes, and embedded ports."""
    assert _build_base_url(host, port) == expected

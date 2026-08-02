"""Tests for the OVOS TTS entity."""

import aiohttp
import pytest
from homeassistant.components.tts import DOMAIN as TTS_DOMAIN
from homeassistant.components.tts import TextToSpeechEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import DATA_INSTANCES
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ovos_tts.tts import _extension_from_content_type

from .conftest import TEST_BASE_URL, mock_status

ENTITY_ID = "tts.ovos_tts_piper_text_to_speech"
V2_URL = f"{TEST_BASE_URL}/v2/synthesize"
WAV_AUDIO = b"RIFF....WAVEfake-audio"


async def setup_entity(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entry: MockConfigEntry,
) -> TextToSpeechEntity:
    """Set up the integration and return the TTS entity."""
    mock_status(aioclient_mock)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity = hass.data[DATA_INSTANCES][TTS_DOMAIN].get_entity(ENTITY_ID)
    assert entity is not None
    return entity


async def test_entity_properties(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Entity exposes languages from the server and supports the voice option."""
    entity = await setup_entity(hass, aioclient_mock, mock_config_entry)

    # A None name breaks HA's speech manager ("TTS engine name is not set")
    assert entity.name == "Text-to-Speech"
    assert entity.default_language == "en"
    assert entity.supported_languages == ["en", "it"]
    assert entity.supported_options == ["voice"]
    assert entity.device_info is not None
    assert entity.device_info["manufacturer"] == "OpenVoiceOS"
    assert entity.device_info["model"] == "piper"


async def test_default_language_missing_from_langs(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A server default_lang absent from langs is still a supported language.

    Regression: kokoro reports default_lang "en-US" while langs only has "en";
    HA rejects tts.speak if the default language is not in the supported list.
    """
    entry = MockConfigEntry(
        domain=mock_config_entry.domain,
        title=mock_config_entry.title,
        data={**mock_config_entry.data, "language": None},
    )
    mock_status(aioclient_mock, default_lang="en-US")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity = hass.data[DATA_INSTANCES][TTS_DOMAIN].get_entity(ENTITY_ID)
    assert entity is not None
    assert entity.default_language == "en-US"
    assert entity.supported_languages == ["en", "it", "en-US"]


async def test_synthesize_v2(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The v2 endpoint is used when available."""
    entity = await setup_entity(hass, aioclient_mock, mock_config_entry)
    aioclient_mock.get(V2_URL, content=WAV_AUDIO, headers={"Content-Type": "audio/wav"})

    extension, audio = await entity.async_get_tts_audio("hello world", "en", {})

    assert extension == "wav"
    assert audio == WAV_AUDIO
    query = aioclient_mock.mock_calls[-1][1].query
    assert query["utterance"] == "hello world"
    assert query["lang"] == "en"
    assert "voice" not in query


async def test_synthesize_v1_fallback_is_cached(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A 404 from v2 falls back to v1, and later calls skip v2 entirely."""
    entity = await setup_entity(hass, aioclient_mock, mock_config_entry)
    aioclient_mock.get(V2_URL, status=404)
    aioclient_mock.get(
        f"{TEST_BASE_URL}/synthesize/hello%20world",
        content=WAV_AUDIO,
        headers={"Content-Type": "audio/x-wav"},
    )

    extension, audio = await entity.async_get_tts_audio("hello world", "en", {})
    assert extension == "wav"
    assert audio == WAV_AUDIO

    def v2_call_count() -> int:
        return sum(1 for call in aioclient_mock.mock_calls if "v2" in str(call[1]))

    calls_before = v2_call_count()
    await entity.async_get_tts_audio("hello world", "en", {})
    assert v2_call_count() == calls_before


async def test_synthesize_voice_option_overrides_default(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A per-call voice option overrides the configured default voice."""
    entry = MockConfigEntry(
        domain=mock_config_entry.domain,
        title=mock_config_entry.title,
        data={**mock_config_entry.data, "voice": "alan"},
    )
    entity = await setup_entity(hass, aioclient_mock, entry)
    aioclient_mock.get(V2_URL, content=WAV_AUDIO, headers={"Content-Type": "audio/wav"})

    await entity.async_get_tts_audio("hi", "en", {})
    assert aioclient_mock.mock_calls[-1][1].query["voice"] == "alan"

    await entity.async_get_tts_audio("hi", "en", {"voice": "amy"})
    assert aioclient_mock.mock_calls[-1][1].query["voice"] == "amy"


@pytest.mark.parametrize("exc", [aiohttp.ClientError(), TimeoutError()])
async def test_synthesize_failure_raises(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    exc: Exception,
) -> None:
    """Network failures raise HomeAssistantError instead of returning empty audio."""
    entity = await setup_entity(hass, aioclient_mock, mock_config_entry)
    aioclient_mock.get(V2_URL, exc=exc)

    with pytest.raises(HomeAssistantError):
        await entity.async_get_tts_audio("hello", "en", {})


async def test_synthesize_http_error_raises(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A 5xx from the server raises HomeAssistantError."""
    entity = await setup_entity(hass, aioclient_mock, mock_config_entry)
    aioclient_mock.get(V2_URL, status=500)

    with pytest.raises(HomeAssistantError):
        await entity.async_get_tts_audio("hello", "en", {})


@pytest.mark.parametrize(
    ("content_type", "expected"),
    [
        ("audio/wav", "wav"),
        ("audio/x-wav", "wav"),
        ("audio/wave", "wav"),
        ("audio/mpeg", "mp3"),
        ("audio/mp3", "mp3"),
        ("audio/ogg", "ogg"),
        ("audio/flac", "flac"),
        ("audio/mpeg; charset=utf-8", "mp3"),
        ("application/octet-stream", "wav"),
        ("", "wav"),
    ],
)
def test_extension_from_content_type(content_type: str, expected: str) -> None:
    """Content types map to audio extensions with a wav fallback."""
    assert _extension_from_content_type(content_type) == expected


def test_unknown_content_type_warns(caplog: pytest.LogCaptureFixture) -> None:
    """Non-audio content types warn; opaque/absent types fall back silently."""
    assert _extension_from_content_type("text/html") == "wav"
    assert "Unexpected Content-Type 'text/html'" in caplog.text

    caplog.clear()
    assert _extension_from_content_type("application/octet-stream") == "wav"
    assert _extension_from_content_type("") == "wav"
    assert "Unexpected Content-Type" not in caplog.text

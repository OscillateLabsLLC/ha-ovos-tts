"""TTS entity for OVOS TTS Server."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.components.tts import ATTR_VOICE, TextToSpeechEntity, TtsAudioType
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OvosTtsConfigEntry
from .const import CONF_LANG, CONF_VOICE, DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_CONTENT_TYPE_MAP = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/ogg": "ogg",
    "audio/flac": "flac",
}
_DEFAULT_EXTENSION = "wav"
# Common for servers that send raw audio without declaring a type; no warning.
_OPAQUE_CONTENT_TYPES = {"", "application/octet-stream"}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OvosTtsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OVOS TTS entity from a config entry."""
    async_add_entities([OVOSTTSEntity(config_entry)])


class OVOSTTSEntity(TextToSpeechEntity):
    """OVOS TTS Server entity."""

    # NOTE: TTS entities must have a non-None name (the speech manager uses it
    # as the cache key), so device-name inheritance via _attr_name = None does
    # not work here; use a translated entity name instead.
    _attr_has_entity_name = True
    _attr_translation_key = "ovos_tts"

    def __init__(self, config_entry: OvosTtsConfigEntry) -> None:
        """Initialize the OVOS TTS entity."""
        runtime = config_entry.runtime_data
        self._attr_supported_options = [ATTR_VOICE]
        self._client = runtime.client
        self._default_voice: str | None = config_entry.data.get(CONF_VOICE)

        self._attr_unique_id = config_entry.entry_id
        self._attr_default_language = (
            config_entry.data.get(CONF_LANG) or runtime.status.default_lang
        )
        # HA requires default_language to be in supported_languages, but some
        # servers report a default ("en-US") missing from langs (["en", ...]).
        langs = runtime.status.supported_langs
        self._attr_supported_languages = (
            langs
            if self._attr_default_language in langs
            else [*langs, self._attr_default_language]
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=config_entry.title,
            manufacturer="OpenVoiceOS",
            model=runtime.status.plugin,
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=runtime.client.base_url,
        )

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Synthesize speech via the OVOS TTS server."""
        voice = options.get(ATTR_VOICE, self._default_voice)

        try:
            content_type, audio = await self._client.async_synthesize(
                message, language, voice
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Speech synthesis request failed", exc_info=True)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="synthesize_failed",
            ) from err

        return (_extension_from_content_type(content_type), audio)


def _extension_from_content_type(content_type: str) -> str:
    """Map a Content-Type header to an audio file extension."""
    mime = content_type.split(";", maxsplit=1)[0].strip().lower()
    if mime in _CONTENT_TYPE_MAP:
        return _CONTENT_TYPE_MAP[mime]
    if mime not in _OPAQUE_CONTENT_TYPES:
        _LOGGER.warning(
            "Unexpected Content-Type %r from OVOS TTS server; assuming WAV audio",
            content_type,
        )
    return _DEFAULT_EXTENSION

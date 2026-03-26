"""TTS entity for OVOS TTS Server."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import aiohttp

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_BASE_URL, CONF_LANG, CONF_SUPPORTED_LANGS, CONF_VOICE

_LOGGER = logging.getLogger(__name__)

_CONTENT_TYPE_MAP = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/ogg": "ogg",
    "audio/flac": "flac",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OVOS TTS entity from a config entry."""
    async_add_entities([OVOSTTSEntity(config_entry)])


class OVOSTTSEntity(TextToSpeechEntity):
    """OVOS TTS Server entity."""

    _attr_has_entity_name = True

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the OVOS TTS entity."""
        self._attr_name = config_entry.title
        self._attr_unique_id = config_entry.entry_id
        self._attr_default_language = config_entry.data.get(CONF_LANG, "en")
        self._attr_supported_languages = config_entry.data.get(
            CONF_SUPPORTED_LANGS, ["en"]
        )

        self._base_url: str = config_entry.data[CONF_BASE_URL]
        self._verify_ssl: bool = config_entry.data.get(CONF_VERIFY_SSL, True)
        self._default_voice: str | None = config_entry.data.get(CONF_VOICE)

        # Cached after first request: None = untested, 2 = v2 works, 1 = v1 only
        self._api_version: int | None = None

    @property
    def supported_options(self) -> list[str]:
        """Return supported options like voice."""
        return [CONF_VOICE]

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Synthesize speech via the OVOS TTS server."""
        session = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        voice = options.get(CONF_VOICE, self._default_voice)

        params: dict[str, str] = {"lang": language}
        if voice:
            params["voice"] = voice

        try:
            return await self._synthesize(session, message, params)
        except Exception:
            _LOGGER.exception("Error synthesizing speech via OVOS TTS server")
            return (None, None)

    async def _synthesize(
        self,
        session: aiohttp.ClientSession,
        message: str,
        params: dict[str, str],
    ) -> TtsAudioType:
        """Try v2 endpoint, fall back to v1 if the server returns 404."""
        timeout = aiohttp.ClientTimeout(total=30)

        if self._api_version != 1:
            v2_params = {**params, "utterance": message}
            async with session.get(
                f"{self._base_url}/v2/synthesize",
                params=v2_params,
                timeout=timeout,
            ) as resp:
                if resp.status == 404:
                    _LOGGER.info(
                        "OVOS TTS server does not support v2 API, falling back to v1"
                    )
                    self._api_version = 1
                else:
                    resp.raise_for_status()
                    self._api_version = 2
                    return _parse_audio(resp, await resp.read())

        encoded_utterance = quote(message, safe="")
        async with session.get(
            f"{self._base_url}/synthesize/{encoded_utterance}",
            params=params,
            timeout=timeout,
        ) as resp:
            resp.raise_for_status()
            self._api_version = 1
            return _parse_audio(resp, await resp.read())


def _parse_audio(
    response: aiohttp.ClientResponse, audio_data: bytes
) -> TtsAudioType:
    """Determine audio format from Content-Type header."""
    content_type = response.content_type or ""
    mime = content_type.split(";")[0].strip().lower()
    extension = _CONTENT_TYPE_MAP.get(mime, "wav")
    return (extension, audio_data)

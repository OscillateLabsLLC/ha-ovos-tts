"""TTS entity for OVOS TTS Server."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import aiohttp

from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_LANG, CONF_VOICE, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONTENT_TYPE_MAP = {
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
    async_add_entities([OVOSTTSEntity(hass, config_entry)])


class OVOSTTSEntity(TextToSpeechEntity):
    """OVOS TTS Server entity."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the OVOS TTS entity."""
        self.hass = hass
        self._config_entry = config_entry
        self._attr_name = config_entry.title
        self._attr_unique_id = config_entry.entry_id

        data = config_entry.data
        self._base_url = data.get("base_url", f"{data[CONF_HOST]}:{data[CONF_PORT]}")
        self._verify_ssl = data.get(CONF_VERIFY_SSL, True)
        self._default_voice = data.get(CONF_VOICE)
        self._attr_default_language = data.get(CONF_LANG, "en")
        self._attr_supported_languages = data.get("supported_langs", ["en"])

        # Cached API version: None = untested, 2 = v2 works, 1 = v1 only
        self._api_version: int | None = None

    @property
    def supported_options(self) -> list[str]:
        """Return supported options."""
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
        """Try v2, fall back to v1 if needed."""
        timeout = aiohttp.ClientTimeout(total=30)

        if self._api_version != 1:
            # Try v2
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
                    return self._parse_audio(resp, await resp.read())

        # v1 fallback
        encoded_utterance = quote(message, safe="")
        async with session.get(
            f"{self._base_url}/synthesize/{encoded_utterance}",
            params=params,
            timeout=timeout,
        ) as resp:
            resp.raise_for_status()
            self._api_version = 1
            return self._parse_audio(resp, await resp.read())

    def _parse_audio(
        self, response: aiohttp.ClientResponse, audio_data: bytes
    ) -> TtsAudioType:
        """Determine audio format from response and return TtsAudioType."""
        content_type = response.content_type or ""
        # Strip parameters like charset
        mime = content_type.split(";")[0].strip().lower()
        extension = CONTENT_TYPE_MAP.get(mime, "wav")
        return (extension, audio_data)

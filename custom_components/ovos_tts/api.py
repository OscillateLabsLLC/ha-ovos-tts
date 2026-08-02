"""Async client for the OVOS TTS Server HTTP API."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from http import HTTPStatus
from urllib.parse import quote

import aiohttp

_LOGGER = logging.getLogger(__name__)

STATUS_TIMEOUT = aiohttp.ClientTimeout(total=10)
SYNTHESIZE_TIMEOUT = aiohttp.ClientTimeout(total=30)

_API_V1 = 1
_API_V2 = 2


@dataclass(slots=True)
class ServerStatus:
    """Status reported by the OVOS TTS server's /status endpoint."""

    plugin: str = "unknown"
    default_lang: str = "en"
    supported_langs: list[str] = field(default_factory=list)


class OvosTtsClient:
    """Client for a single OVOS TTS Server instance."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        """Initialize the client."""
        self._session = session
        self._base_url = base_url
        # None = untested, then locked to whichever API version the server speaks
        self._api_version: int | None = None

    @property
    def base_url(self) -> str:
        """Return the server base URL."""
        return self._base_url

    async def async_get_status(self) -> ServerStatus:
        """Fetch server status and supported languages."""
        async with self._session.get(
            f"{self._base_url}/status", timeout=STATUS_TIMEOUT
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        return ServerStatus(
            plugin=data.get("plugin", "unknown"),
            default_lang=data.get("default_lang", "en"),
            supported_langs=data.get("langs", []),
        )

    async def async_synthesize(
        self, message: str, language: str, voice: str | None
    ) -> tuple[str, bytes]:
        """Synthesize speech and return (content type, audio bytes).

        Tries the v2 endpoint first and permanently falls back to v1 if the
        server answers 404.
        """
        params: dict[str, str] = {"lang": language}
        if voice:
            params["voice"] = voice

        if self._api_version != _API_V1:
            async with self._session.get(
                f"{self._base_url}/v2/synthesize",
                params={**params, "utterance": message},
                timeout=SYNTHESIZE_TIMEOUT,
            ) as resp:
                if resp.status != HTTPStatus.NOT_FOUND:
                    resp.raise_for_status()
                    self._api_version = _API_V2
                    return (resp.content_type or "", await resp.read())
            _LOGGER.info(
                "OVOS TTS server does not support the v2 API, falling back to v1"
            )
            self._api_version = _API_V1

        async with self._session.get(
            f"{self._base_url}/synthesize/{quote(message, safe='')}",
            params=params,
            timeout=SYNTHESIZE_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            return (resp.content_type or "", await resp.read())

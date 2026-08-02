"""Config flow for OVOS TTS Server."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OvosTtsClient
from .const import (
    CONF_BASE_URL,
    CONF_LANG,
    CONF_VOICE,
    DEFAULT_PORT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_VOICE): str,
        vol.Optional(CONF_LANG): str,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)

_HTTPS_DEFAULT_PORT = 443


def _build_base_url(host: str, port: int) -> str:
    """Build a base URL from host and port.

    Handles bare hostnames, full URLs, and HTTPS on standard ports.
    """
    host = host.strip().rstrip("/")
    parsed = urlparse(host)
    if not parsed.scheme:
        host = f"http://{host}"
        parsed = urlparse(host)
    host = host.rstrip("/")
    if parsed.port or (parsed.scheme == "https" and port == _HTTPS_DEFAULT_PORT):
        return host
    return f"{host}:{port}"


class OVOSTTSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OVOS TTS Server."""

    VERSION = 1

    async def _async_validate(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, Any], str]:
        """Validate the connection and build entry data.

        Returns (errors, entry data, title); entry data and title are only
        meaningful when errors is empty.
        """
        errors: dict[str, str] = {}
        host = user_input[CONF_HOST].strip().rstrip("/")
        port = user_input[CONF_PORT]
        verify_ssl = user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)

        self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})

        base_url = _build_base_url(host, port)
        session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)
        client = OvosTtsClient(session, base_url)

        try:
            status = await client.async_get_status()
        except (aiohttp.ClientError, TimeoutError):
            _LOGGER.debug(
                "Cannot connect to OVOS TTS server at %s", base_url, exc_info=True
            )
            errors["base"] = "cannot_connect"
            return (errors, {}, "")
        except Exception:
            _LOGGER.exception("Unexpected error connecting to OVOS TTS server")
            errors["base"] = "unknown"
            return (errors, {}, "")

        user_lang = user_input.get(CONF_LANG)
        if (
            user_lang
            and status.supported_langs
            and user_lang not in status.supported_langs
        ):
            errors["base"] = "invalid_lang"
            return (errors, {}, "")

        data = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_VOICE: user_input.get(CONF_VOICE),
            CONF_LANG: user_lang or status.default_lang,
            CONF_VERIFY_SSL: verify_ssl,
            CONF_BASE_URL: base_url,
        }
        return (errors, data, f"OVOS TTS ({status.plugin})")

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, data, title = await self._async_validate(user_input)
            if not errors:
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            errors, data, title = await self._async_validate(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=data,
                    title=title,
                )

        suggested_values: dict[str, Any] = {
            **reconfigure_entry.data,
            **(user_input or {}),
        }

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested_values
            ),
            errors=errors,
        )

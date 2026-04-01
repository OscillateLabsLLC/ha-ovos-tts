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

from .const import (
    CONF_BASE_URL,
    CONF_LANG,
    CONF_SUPPORTED_LANGS,
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
    if parsed.port or (parsed.scheme == "https" and port == 443):
        return host
    return f"{host}:{port}"


class OVOSTTSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OVOS TTS Server."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip().rstrip("/")
            port = user_input[CONF_PORT]
            verify_ssl = user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)

            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})

            base_url = _build_base_url(host, port)
            session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)

            try:
                async with session.get(
                    f"{base_url}/status",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error connecting to OVOS TTS server")
                errors["base"] = "unknown"
            else:
                supported_langs: list[str] = data.get("langs", [])
                default_lang: str = data.get("default_lang", "en")
                plugin_name: str = data.get("plugin", "unknown")

                user_lang = user_input.get(CONF_LANG)
                if user_lang and supported_langs and user_lang not in supported_langs:
                    errors["base"] = "invalid_lang"
                else:
                    return self.async_create_entry(
                        title=f"OVOS TTS ({plugin_name})",
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_VOICE: user_input.get(CONF_VOICE),
                            CONF_LANG: user_lang or default_lang,
                            CONF_VERIFY_SSL: verify_ssl,
                            CONF_SUPPORTED_LANGS: supported_langs
                            or [user_lang or default_lang],
                            CONF_BASE_URL: base_url,
                        },
                    )

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
            host = user_input[CONF_HOST].strip().rstrip("/")
            port = user_input[CONF_PORT]
            verify_ssl = user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)

            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})

            base_url = _build_base_url(host, port)
            session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)

            try:
                async with session.get(
                    f"{base_url}/status",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error connecting to OVOS TTS server")
                errors["base"] = "unknown"
            else:
                supported_langs: list[str] = data.get("langs", [])
                default_lang: str = data.get("default_lang", "en")
                plugin_name: str = data.get("plugin", "unknown")

                user_lang = user_input.get(CONF_LANG)
                if user_lang and supported_langs and user_lang not in supported_langs:
                    errors["base"] = "invalid_lang"
                else:
                    return self.async_update_reload_and_abort(
                        reconfigure_entry,
                        data_updates={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_VOICE: user_input.get(CONF_VOICE),
                            CONF_LANG: user_lang or default_lang,
                            CONF_VERIFY_SSL: verify_ssl,
                            CONF_SUPPORTED_LANGS: supported_langs
                            or [user_lang or default_lang],
                            CONF_BASE_URL: base_url,
                        },
                        title=f"OVOS TTS ({plugin_name})",
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

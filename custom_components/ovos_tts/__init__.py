"""The OVOS TTS Server integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OvosTtsClient, ServerStatus
from .const import CONF_BASE_URL, DEFAULT_VERIFY_SSL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.TTS]


@dataclass(slots=True)
class OvosTtsRuntimeData:
    """Runtime data for an OVOS TTS config entry."""

    client: OvosTtsClient
    status: ServerStatus


type OvosTtsConfigEntry = ConfigEntry[OvosTtsRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: OvosTtsConfigEntry) -> bool:
    """Set up OVOS TTS Server from a config entry."""
    session = async_get_clientsession(
        hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
    )
    client = OvosTtsClient(session, entry.data[CONF_BASE_URL])

    try:
        status = await client.async_get_status()
    except (aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.debug(
            "Cannot connect to OVOS TTS server at %s during setup",
            entry.data[CONF_BASE_URL],
            exc_info=True,
        )
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"base_url": entry.data[CONF_BASE_URL]},
        ) from err

    entry.runtime_data = OvosTtsRuntimeData(client=client, status=status)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OvosTtsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

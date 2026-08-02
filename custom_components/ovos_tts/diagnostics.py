"""Diagnostics support for OVOS TTS Server."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import OvosTtsConfigEntry
from .const import CONF_BASE_URL

TO_REDACT = {CONF_HOST, CONF_BASE_URL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OvosTtsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "server_status": asdict(entry.runtime_data.status),
    }

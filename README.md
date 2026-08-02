# OVOS TTS Server for Home Assistant

[![Status: Active](https://img.shields.io/badge/status-active-brightgreen)](https://github.com/OscillateLabsLLC/.github/blob/main/SUPPORT_STATUS.md)
[![HACS: Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Custom Home Assistant integration that uses an [OVOS TTS Server](https://github.com/OpenVoiceOS/ovos-tts-server/) as a text-to-speech backend. Use any OpenVoiceOS TTS plugin (Piper, Mimic, Coqui, etc.) as a Home Assistant TTS engine.

Built to the [Home Assistant integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/) Platinum standard; see [`quality_scale.yaml`](custom_components/ovos_tts/quality_scale.yaml) for the rule-by-rule accounting. (The official scale badge only applies to core integrations.)

## Features

- Automatic v2/v1 API detection with caching
- Language discovery from the server's `/status` endpoint
- Optional voice selection passed through to the TTS plugin
- SSL verification toggle for self-signed certificates
- Config flow with connection validation, reconfiguration support, and diagnostics

## Supported servers

Any [OVOS TTS Server](https://github.com/OpenVoiceOS/ovos-tts-server/) (or [ovos-tts-server-plugin](https://github.com/OpenVoiceOS/ovos-tts-server) compatible endpoint), regardless of which TTS plugin it wraps. Both the modern `/v2/synthesize` API and the legacy `/synthesize/<utterance>` API are supported; the integration probes v2 once and remembers the result.

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots in the top right corner and select **Custom repositories**
3. Add `https://github.com/OscillateLabsLLC/ha-ovos-tts` as an **Integration**
4. Search for "OVOS TTS Server" and install it
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/ovos_tts` directory into your Home Assistant `config/custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **OVOS TTS Server**
3. Enter your server details (validated before the entry is created):

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| Host | Yes | — | Hostname, IP, or full URL of the server (e.g. `192.168.1.100` or `https://tts.example.com`) |
| Port | Yes | `9666` | Ignored when the host is an HTTPS URL on port 443 or already contains a port |
| Voice | No | server default | Default voice passed to the TTS plugin |
| Language | No | server default | Override the default language; must be one the server supports |
| Verify SSL certificate | No | on | Disable to allow self-signed certificates |

To change settings later, use the entry's **Reconfigure** option (⋮ menu on the integration card). Multiple servers can be added as separate entries.

### Data updates

There is no polling. Supported languages and the active plugin name are read from the server's `/status` endpoint when the entry is set up (and again on reload/reconfigure); audio is fetched on demand for each TTS request. If the server is unreachable at startup, setup retries automatically until it comes back.

## Usage

Once configured, the OVOS TTS entity appears as a TTS service. Use it in:

- **Automations** — select the OVOS TTS entity in any TTS action
- **Developer Tools** — call `tts.speak` with the entity
- **Voice pipelines** — set it as your TTS engine in Assist

### Example: speak on a media player

```yaml
action: tts.speak
target:
  entity_id: tts.ovos_tts_piper
data:
  media_player_entity_id: media_player.living_room
  message: "The garage door has been open for ten minutes."
  options:
    voice: en_US-lessac-medium
```

The `voice` option is optional and overrides the configured default for that call.

## Troubleshooting

- **"Unable to connect" during setup** — verify the server is reachable from the Home Assistant host: `curl http://<host>:9666/status` should return JSON. Check firewalls and that the port matches your server config.
- **Setup succeeds but speech fails** — download diagnostics from the integration page (Settings > Devices & Services > OVOS TTS Server > ⋮ > Download diagnostics) and check the Home Assistant log for `custom_components.ovos_tts` entries. A failing synthesis raises a visible error in the calling automation/action.
- **Self-signed certificates** — disable **Verify SSL certificate** in the config/reconfigure flow.
- **Wrong or missing voices** — voices are defined by the TTS plugin running on the server, not by this integration. Confirm the voice name against your server plugin's documentation.

### Known limitations

- The OVOS TTS Server API is unauthenticated; put it behind a reverse proxy if you need access control.
- Available voices are not enumerable through the server API, so the voice field is free text rather than a dropdown.
- Language list is refreshed only at setup/reload, not continuously.

## Removal

1. Go to **Settings > Devices & Services > OVOS TTS Server**
2. Open the ⋮ menu on the entry and select **Delete**
3. If installed via HACS, remove the repository from HACS to delete the code, then restart Home Assistant

Removal leaves nothing behind on the OVOS TTS server (the integration is a pure client).

## Development

```bash
uv sync            # install dev dependencies
uv run pytest      # unit tests (100% coverage enforced at >=95%)
uv run ruff check .
uv run mypy        # strict typing
python test_integration.py --tts-host http://<server>   # optional end-to-end test in a Docker HA instance
```

## Requirements

- A running [OVOS TTS Server](https://github.com/OpenVoiceOS/ovos-tts-server/) accessible from your Home Assistant instance
- Home Assistant 2024.11.0 or newer

## License

[Apache-2.0](LICENSE)

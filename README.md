# OVOS TTS Server for Home Assistant

[![Status: Active](https://img.shields.io/badge/status-active-brightgreen)](https://github.com/OscillateLabsLLC/.github/blob/main/SUPPORT_STATUS.md)
[![HACS: Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Custom Home Assistant integration that uses an [OVOS TTS Server](https://github.com/OpenVoiceOS/ovos-tts-server/) as a text-to-speech backend. Use any OpenVoiceOS TTS plugin (Piper, Mimic, Coqui, etc.) as a Home Assistant TTS engine.

## Features

- Automatic v2/v1 API detection with caching
- Language discovery from the server's `/status` endpoint
- Optional voice selection passed through to the TTS plugin
- SSL verification toggle for self-signed certificates
- Config flow with connection validation

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
3. Enter your server host and port (default: `9666`)
4. Optionally set a default voice or language override
5. The integration validates the connection and discovers supported languages automatically

## Usage

Once configured, the OVOS TTS entity appears as a TTS service. Use it in:

- **Automations** — select the OVOS TTS entity in any TTS action
- **Developer Tools** — call `tts.speak` with the entity
- **Voice pipelines** — set it as your TTS engine in Assist

## Requirements

- A running [OVOS TTS Server](https://github.com/OpenVoiceOS/ovos-tts-server/) accessible from your Home Assistant instance
- Home Assistant 2024.1.0 or newer

## License

[Apache-2.0](LICENSE)

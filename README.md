# OVOS TTS Server for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Custom Home Assistant integration that uses an [OVOS TTS Server](https://github.com/OpenVoiceOS/ovos-tts-server/) as a text-to-speech backend. Use any OpenVoiceOS TTS plugin (Piper, Mimic, Coqui, etc.) as a Home Assistant TTS engine.

## Features

- Automatic v2/v1 API detection with caching
- Language discovery from server `/status` endpoint
- Optional voice selection
- SSL verification toggle for self-signed certificates

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots in the top right corner and select **Custom repositories**
3. Add `https://github.com/OscillateLabs/ha-ovos-tts` as an **Integration**
4. Search for "OVOS TTS Server" and install it
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/ovos_tts` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for "OVOS TTS Server"
3. Enter your OVOS TTS server host and port (default: 9666)
4. Optionally set a default voice or language override
5. The integration will validate the connection and discover supported languages

## Usage

Once configured, the OVOS TTS entity will appear as a TTS service. Use it via:

- **Automations**: Select the OVOS TTS entity in any TTS action
- **Developer Tools**: Call `tts.speak` with the OVOS TTS entity

## Requirements

- A running [OVOS TTS Server](https://github.com/OpenVoiceOS/ovos-tts-server/) accessible from your Home Assistant instance
- Home Assistant 2024.1.0 or newer

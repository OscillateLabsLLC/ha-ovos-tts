#!/usr/bin/env python3
"""Automated integration test for OVOS TTS in Home Assistant.

Spins up a fresh HA container, installs the custom component,
drives the config flow via the REST API, and verifies TTS works.

Usage:
    python test_integration.py --tts-host https://tts.example.com       # specify server
    python test_integration.py --tts-host http://10.0.0.5 --tts-port 9666
    python test_integration.py --keep                                   # keep container after
    python test_integration.py --ha-port 28123                          # custom HA port

Environment variables:
    OVOS_TTS_TEST_HOST  TTS server URL (default: http://localhost)
    OVOS_TTS_TEST_PORT  TTS server port (default: 9666)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import requests

# Defaults
DEFAULT_CONTAINER_NAME = "ha-ovos-tts-test"
DEFAULT_HA_PORT = 18123
DEFAULT_TTS_HOST = os.environ.get("OVOS_TTS_TEST_HOST", "http://localhost")
DEFAULT_TTS_PORT = int(os.environ.get("OVOS_TTS_TEST_PORT", "9666"))
DEFAULT_HA_USER = "test"
DEFAULT_HA_PASSWORD = "testtest1"

BOOT_TIMEOUT = 120
POLL_INTERVAL = 3


def run(cmd: str) -> subprocess.CompletedProcess:
    """Run a shell command."""
    print(f"  $ {cmd}")
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


class HATestHarness:
    """Manages an ephemeral Home Assistant container for integration testing."""

    def __init__(
        self,
        container_name: str,
        ha_port: int,
        tts_host: str,
        tts_port: int,
        keep: bool = False,
    ):
        self.container_name = container_name
        self.ha_port = ha_port
        self.ha_base = f"http://localhost:{ha_port}"
        self.tts_host = tts_host
        self.tts_port = tts_port
        self.keep = keep
        self.token: str | None = None
        self._tmpdir: tempfile.TemporaryDirectory | None = None
        self._results: list[tuple[str, bool, str]] = []

    # --- lifecycle ---

    def setup(self) -> str:
        """Create config dir with custom component and return its path."""
        self._tmpdir = tempfile.TemporaryDirectory()
        config_dir = os.path.join(self._tmpdir.name, "config")
        cc_dest = os.path.join(config_dir, "custom_components", "ovos_tts")
        os.makedirs(cc_dest)

        src = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "custom_components",
            "ovos_tts",
        )
        for f in os.listdir(src):
            filepath = os.path.join(src, f)
            if os.path.isfile(filepath):
                shutil.copy2(filepath, cc_dest)

        with open(os.path.join(config_dir, "configuration.yaml"), "w") as f:
            f.write("default_config:\n")

        return config_dir

    def start(self, config_dir: str):
        """Start a fresh HA container."""
        self._record("cleanup", True, "removing any previous container")
        run(f"docker rm -f {self.container_name}")

        print("\n--- Starting Home Assistant container ---")
        result = run(
            f"docker run -d --name {self.container_name} "
            f"-p {self.ha_port}:8123 "
            f"-v {config_dir}:/config "
            f"ghcr.io/home-assistant/home-assistant:stable"
        )
        if result.returncode != 0:
            self._record("start_container", False, result.stderr.strip())
            self._fail("Failed to start container")
        print(f"  Container started: {result.stdout.strip()[:12]}")
        self._record("start_container", True, "container running")

    def teardown(self):
        """Clean up container and temp dir."""
        if self.keep:
            print(f"\n--- Keeping container '{self.container_name}' ---")
            print(f"  URL: {self.ha_base}")
            print(f"  Username: {DEFAULT_HA_USER}")
            print(f"  Password: {DEFAULT_HA_PASSWORD}")
        else:
            print("\n--- Cleanup ---")
            run(f"docker rm -f {self.container_name}")

        if self._tmpdir:
            self._tmpdir.cleanup()

    # --- HA interaction ---

    def wait_for_ready(self):
        """Wait for HA API to respond."""
        print("\n--- Waiting for Home Assistant to boot ---")
        deadline = time.time() + BOOT_TIMEOUT
        while time.time() < deadline:
            try:
                resp = requests.get(f"{self.ha_base}/api/", timeout=5)
                if resp.status_code in (200, 401):
                    print("  HA API is responding!")
                    self._record("ha_boot", True, "API responding")
                    return
            except requests.ConnectionError:
                pass
            time.sleep(POLL_INTERVAL)

        run(f"docker logs --tail 30 {self.container_name}")
        self._record("ha_boot", False, "timed out")
        self._fail("Home Assistant did not start in time")

    def onboard(self):
        """Complete HA onboarding and store access token."""
        print("\n--- Onboarding Home Assistant ---")

        resp = requests.post(
            f"{self.ha_base}/api/onboarding/users",
            json={
                "client_id": f"{self.ha_base}/",
                "name": "Test",
                "username": DEFAULT_HA_USER,
                "password": DEFAULT_HA_PASSWORD,
                "language": "en",
            },
        )
        if resp.status_code != 200:
            print(f"  Onboarding failed ({resp.status_code}), trying login...")
            self.token = self._login()
        else:
            auth_code = resp.json()["auth_code"]
            print("  Owner account created")
            self.token = self._exchange_code(auth_code)

        print(f"  Got access token: {self.token[:20]}...")

        # Complete remaining onboarding steps (some may 400 — that's fine)
        headers = self._headers()
        for step in ["core_config", "analytics", "integration"]:
            requests.post(
                f"{self.ha_base}/api/onboarding/{step}",
                headers=headers,
                json={},
            )

        self._record("onboarding", True, "authenticated")

    def create_config_entry(self) -> dict:
        """Drive the config flow and return the created entry."""
        print("\n--- Creating OVOS TTS config entry ---")
        headers = self._headers()

        # Init flow
        resp = requests.post(
            f"{self.ha_base}/api/config/config_entries/flow",
            headers=headers,
            json={"handler": "ovos_tts"},
        )
        if resp.status_code != 200:
            self._record("config_flow_init", False, f"HTTP {resp.status_code}")
            self._fail(f"Failed to start config flow: {resp.text}")

        flow = resp.json()
        flow_id = flow["flow_id"]
        print(f"  Flow started (step={flow.get('step_id')})")

        # Submit form
        resp = requests.post(
            f"{self.ha_base}/api/config/config_entries/flow/{flow_id}",
            headers=headers,
            json={
                "host": self.tts_host,
                "port": self.tts_port,
                "verify_ssl": self.tts_host.startswith("https"),
            },
        )
        if resp.status_code != 200:
            self._dump_logs()
            self._record("config_flow_submit", False, f"HTTP {resp.status_code}")
            self._fail(f"Config flow submission failed: {resp.text}")

        result = resp.json()
        flow_type = result.get("type")

        if flow_type == "create_entry":
            title = result.get("title", "?")
            print(f"  Config entry created: {title}")
            self._record("config_flow", True, title)
            return result

        if flow_type == "form":
            errors = result.get("errors", {})
            self._record("config_flow", False, f"form errors: {errors}")
            self._fail(f"Config flow returned errors: {errors}")

        self._record("config_flow", False, f"unexpected type: {flow_type}")
        self._fail(f"Unexpected flow result: {json.dumps(result, indent=2)}")

    def find_tts_entity(self) -> str:
        """Find and return the OVOS TTS entity_id."""
        print("\n--- Verifying TTS entity ---")
        time.sleep(3)  # Let HA set up the entity

        resp = requests.get(f"{self.ha_base}/api/states", headers=self._headers())
        states = resp.json()

        tts_entities = [s for s in states if s["entity_id"].startswith("tts.")]
        print(f"  All TTS entities: {[e['entity_id'] for e in tts_entities]}")

        for entity in tts_entities:
            if "ovos" in entity["entity_id"]:
                eid = entity["entity_id"]
                attrs = entity.get("attributes", {})
                print(f"  Found: {eid}")
                print(f"  Supported languages: {attrs.get('supported_languages', '?')}")
                self._record("entity_exists", True, eid)
                return eid

        self._record("entity_exists", False, "no ovos entity found")
        self._fail("No OVOS TTS entity found")

    def test_tts(self, entity_id: str):
        """Synthesize speech and verify audio is returned."""
        print("\n--- Testing TTS synthesis ---")
        headers = self._headers()

        resp = requests.post(
            f"{self.ha_base}/api/tts_get_url",
            headers=headers,
            json={
                "engine_id": entity_id,
                "message": "Hello from the OVOS TTS integration test!",
                "language": "en",
            },
        )
        if resp.status_code != 200:
            self._record("tts_get_url", False, f"HTTP {resp.status_code}: {resp.text}")
            self._fail(f"tts_get_url failed: {resp.text}")

        result = resp.json()
        tts_path = result.get("path") or result.get("url", "")

        if not tts_path:
            self._record("tts_get_url", False, "no URL in response")
            self._fail(f"No URL returned: {result}")

        print(f"  TTS path: {tts_path}")
        self._record("tts_get_url", True, tts_path)

        # Fetch audio via the path (using localhost, not container IP)
        audio_url = f"{self.ha_base}{tts_path}" if tts_path.startswith("/") else tts_path
        # Replace any container-internal IPs with localhost
        audio_url = re.sub(
            r"http://[\d.]+:8123",
            self.ha_base,
            audio_url,
        )

        print(f"  Fetching audio from: {audio_url}")
        audio_resp = requests.get(audio_url, headers=headers, timeout=30)

        if audio_resp.status_code != 200:
            self._record("tts_audio", False, f"HTTP {audio_resp.status_code}")
            self._fail(f"Failed to download audio: {audio_resp.status_code}")

        audio_size = len(audio_resp.content)
        content_type = audio_resp.headers.get("Content-Type", "unknown")
        print(f"  Audio: {audio_size} bytes, Content-Type: {content_type}")

        if audio_size < 100:
            self._record("tts_audio", False, f"too small: {audio_size} bytes")
            self._fail("Audio file suspiciously small")

        out_path = "/tmp/ha_ovos_tts_test.wav"
        with open(out_path, "wb") as f:
            f.write(audio_resp.content)
        print(f"  Saved to {out_path}")
        self._record("tts_audio", True, f"{audio_size} bytes, {content_type}")

    # --- helpers ---

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _login(self) -> str:
        resp = requests.post(
            f"{self.ha_base}/auth/login_flow",
            json={
                "client_id": f"{self.ha_base}/",
                "handler": ["homeassistant", None],
                "redirect_uri": f"{self.ha_base}/",
            },
        )
        flow_id = resp.json()["flow_id"]
        resp = requests.post(
            f"{self.ha_base}/auth/login_flow/{flow_id}",
            json={
                "username": DEFAULT_HA_USER,
                "password": DEFAULT_HA_PASSWORD,
                "client_id": f"{self.ha_base}/",
            },
        )
        return self._exchange_code(resp.json()["result"])

    def _exchange_code(self, code: str) -> str:
        resp = requests.post(
            f"{self.ha_base}/auth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": f"{self.ha_base}/",
            },
        )
        if resp.status_code != 200:
            self._fail(f"Token exchange failed: {resp.text}")
        return resp.json()["access_token"]

    def _dump_logs(self):
        print("\n--- Container logs (last 30 lines) ---")
        result = run(f"docker logs --tail 30 {self.container_name}")
        print(result.stdout or result.stderr)

    def _record(self, name: str, passed: bool, detail: str):
        self._results.append((name, passed, detail))

    def _fail(self, message: str):
        print(f"  FATAL: {message}")
        self._print_results()
        sys.exit(1)

    def _print_results(self):
        print("\n========================================")
        print("  TEST RESULTS")
        print("========================================")
        for name, passed, detail in self._results:
            icon = "PASS" if passed else "FAIL"
            print(f"  [{icon}] {name}: {detail}")
        all_passed = all(p for _, p, _ in self._results)
        print("========================================")
        if all_passed:
            print("  ALL TESTS PASSED")
        else:
            print("  SOME TESTS FAILED")
        print("========================================\n")

    def print_results(self):
        self._print_results()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Integration test for OVOS TTS HA custom component"
    )
    parser.add_argument(
        "--tts-host",
        default=DEFAULT_TTS_HOST,
        help=f"OVOS TTS server URL (default: {DEFAULT_TTS_HOST})",
    )
    parser.add_argument(
        "--tts-port",
        type=int,
        default=DEFAULT_TTS_PORT,
        help=f"OVOS TTS server port (default: {DEFAULT_TTS_PORT})",
    )
    parser.add_argument(
        "--ha-port",
        type=int,
        default=DEFAULT_HA_PORT,
        help=f"Local port for HA container (default: {DEFAULT_HA_PORT})",
    )
    parser.add_argument(
        "--container-name",
        default=DEFAULT_CONTAINER_NAME,
        help=f"Docker container name (default: {DEFAULT_CONTAINER_NAME})",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the container running after tests (for manual inspection)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    harness = HATestHarness(
        container_name=args.container_name,
        ha_port=args.ha_port,
        tts_host=args.tts_host,
        tts_port=args.tts_port,
        keep=args.keep,
    )

    config_dir = harness.setup()
    harness.start(config_dir)

    try:
        harness.wait_for_ready()
        harness.onboard()
        harness.create_config_entry()
        entity_id = harness.find_tts_entity()
        harness.test_tts(entity_id)
        harness.print_results()
    except SystemExit:
        harness._dump_logs()
        raise
    finally:
        harness.teardown()


if __name__ == "__main__":
    main()

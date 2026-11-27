# SPDX-License-Identifier: MPL-2.0
"""Back end for the setup wizard (assets/setup.html): Arduino Cloud checks.

- Whether the board is connected to Arduino Cloud, and which Thing it's on, from
  the board's arduino-cloud-connector daemon (the same socket the Cloud brick uses).
- The Arduino Cloud API key, saved in data/cloud-credentials.json so the app's
  container can read it. It's only needed to create the Thing's variables and
  dashboards from the wizard, and for receiving another BirdBox's birdsong.
- Creating the variables and dashboards with tools/setup_cloud.py.
"""

from __future__ import annotations

import http.client
import json
import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import arduino_cloud  # noqa: E402
import setup_cloud  # noqa: E402

CONNECTOR_SOCKET = os.environ.get("ARDUINO_CLOUD_CONNECTOR_SOCKET", "/run/arduino-cloud-connector/daemon.sock")


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float = 3.0) -> None:
        super().__init__("localhost", timeout=timeout)
        self._path = path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._path)


def board_status() -> dict:
    """The board's own Cloud connection: provisioned, connected, and its Thing."""
    try:
        conn = _UnixHTTPConnection(CONNECTOR_SOCKET)
        conn.request("GET", "/v1/status")
        data = json.loads(conn.getresponse().read())
        conn.close()
    except (OSError, ValueError) as err:
        return {"reachable": False, "error": str(err)}
    cloud = data.get("cloud") or {}
    return {
        "reachable": True,
        "provisioned": data.get("provisioning") == "provisioned",
        "state": cloud.get("state"),
        "connected": cloud.get("state") == "Steady",
        "thing_id": cloud.get("thing_id"),
    }


def has_credentials() -> bool:
    try:
        arduino_cloud._credentials()
    except RuntimeError:
        return False
    return True


def save_credentials(client_id: str, client_secret: str, org_id: str = "") -> None:
    """Save an API key for the app, after checking Arduino Cloud accepts it."""
    client_id, client_secret, org_id = client_id.strip(), client_secret.strip(), org_id.strip()
    if not client_id or not client_secret:
        raise ValueError("Client ID and Client Secret are both needed")
    path = arduino_cloud.APP_CREDENTIALS
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_bytes() if path.exists() else None
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump({"client_id": client_id, "client_secret": client_secret, "org_id": org_id}, handle)
    arduino_cloud._token.clear()
    try:
        arduino_cloud.token()
    except RuntimeError:
        # Put back what was there, so a typo doesn't lose a working key.
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(previous)
        arduino_cloud._token.clear()
        raise


def things() -> list[dict]:
    return [{"id": t["id"], "name": t["name"], "device_id": t.get("device_id")}
            for t in arduino_cloud.api("GET", "/iot/v2/things?show_properties=false")]


def cloud_plan(thing_id: str, free: bool) -> list[dict]:
    """What creating the variables would change on this Thing."""
    return [{"action": a, "name": n, "detail": d} for a, n, d in setup_cloud.plan({"id": thing_id}, free)]


def cloud_apply(thing_id: str, free: bool, dashboards: bool) -> list[dict]:
    """Create the missing variables and (optionally) the dashboards. Returns what changed."""
    thing = {"id": thing_id}
    steps = cloud_plan(thing_id, free)
    try:
        setup_cloud.apply_thing(thing, free, delete_legacy=False)
        if dashboards:
            for action, name in setup_cloud.apply_dashboards(thing, ["free"] if free else ["free", "pro"]):
                steps.append({"action": action, "name": name, "detail": "dashboard"})
    except SystemExit as err:            # setup_cloud exits on a missing variable
        raise RuntimeError(str(err)) from None
    return steps

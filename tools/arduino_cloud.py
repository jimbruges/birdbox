# SPDX-License-Identifier: MPL-2.0
"""Small Arduino Cloud API helper for setting up the BirdBox Thing and dashboards.

Credentials are read from ~/.config/arduino-cloud/credentials.json (or the file
named by ARDUINO_CLOUD_CREDENTIALS), which holds an API key created at
https://app.arduino.cc/api-keys:

    {"client_id": "...", "client_secret": "...", "org_id": ""}

org_id is only needed when the Thing lives in a shared space. The secret is
never printed.

Usage:
    python3 tools/arduino_cloud.py things
    python3 tools/arduino_cloud.py props <thing_id>
    python3 tools/arduino_cloud.py dashboards
    python3 tools/arduino_cloud.py get <api path>          e.g. /iot/v2/dashboards/<id>
    python3 tools/arduino_cloud.py send <METHOD> <api path> [json file]
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HOST = "https://api2.arduino.cc"
TOKEN_URL = f"{HOST}/iot/v1/clients/token"
AUDIENCE = f"{HOST}/iot"
CREDENTIALS = Path(os.environ.get("ARDUINO_CLOUD_CREDENTIALS", Path.home() / ".config/arduino-cloud/credentials.json"))

_token: dict = {}


def _credentials() -> dict:
    try:
        creds = json.loads(CREDENTIALS.read_text())
    except FileNotFoundError:
        sys.exit(f"No credentials at {CREDENTIALS}. See the docstring at the top of this file.")
    if not creds.get("client_id") or not creds.get("client_secret"):
        sys.exit(f"{CREDENTIALS} needs client_id and client_secret")
    return creds


def _org_header(creds: dict) -> dict:
    return {"X-Organization": creds["org_id"]} if creds.get("org_id") else {}


def token() -> str:
    """A cached access token, refreshed a minute before it expires."""
    if _token and _token["expires_at"] > time.time() + 60:
        return _token["access_token"]
    creds = _credentials()
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "audience": AUDIENCE,
    }).encode()
    request = urllib.request.Request(TOKEN_URL, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded", **_org_header(creds)})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as err:
        sys.exit(f"Token request failed: HTTP {err.code} {err.read().decode(errors='replace')[:300]}")
    _token.update(access_token=data["access_token"], expires_at=time.time() + int(data.get("expires_in", 300)))
    return _token["access_token"]


def api(method: str, path: str, payload: object = None) -> object:
    """Call the API and return the decoded JSON (or None for an empty body)."""
    creds = _credentials()
    headers = {"Authorization": f"Bearer {token()}", "Accept": "application/json", **_org_header(creds)}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{HOST}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as err:
        raise RuntimeError(f"{method} {path}: HTTP {err.code} {err.read().decode(errors='replace')[:500]}") from None
    return json.loads(raw) if raw.strip() else None


def main(argv: list[str]) -> None:
    if not argv:
        sys.exit(__doc__)
    command, *rest = argv
    if command == "things":
        for thing in api("GET", "/iot/v2/things?show_properties=false"):
            device = thing.get("device_id") or "-"
            print(f"{thing['id']}  {thing['name']!r}  device={device}  properties={thing.get('properties_count')}")
    elif command == "props":
        for prop in sorted(api("GET", f"/iot/v2/things/{rest[0]}/properties"), key=lambda p: p["name"]):
            print(f"{prop['id']}  {prop['name']:<22} {prop['type']:<12} {prop['permission']:<11} "
                  f"{prop.get('update_strategy', ''):<10} persist={prop.get('persist')}  value={prop.get('last_value')!r}")
    elif command == "dashboards":
        for dash in api("GET", "/iot/v2/dashboards"):
            print(f"{dash['id']}  {dash['name']!r}  widgets={len(dash.get('widgets') or [])}")
    elif command == "get":
        print(json.dumps(api("GET", rest[0]), indent=2))
    elif command == "send":
        method, path, *file = rest
        payload = json.loads(Path(file[0]).read_text()) if file else None
        print(json.dumps(api(method.upper(), path, payload), indent=2))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])

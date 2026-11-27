# SPDX-License-Identifier: MPL-2.0
"""Small Arduino Cloud API helper for setting up the BirdBox Thing and dashboards.

Credentials are read from the file named by ARDUINO_CLOUD_CREDENTIALS, or else
~/.config/arduino-cloud/credentials.json, or else data/cloud-credentials.json in
the app (where the setup wizard saves it: the app's container can't see your home
folder). The file holds an API key created at https://app.arduino.cc/api-keys:

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
HOME_CREDENTIALS = Path.home() / ".config/arduino-cloud/credentials.json"
APP_CREDENTIALS = Path(__file__).resolve().parent.parent / "data" / "cloud-credentials.json"


def credentials_path() -> Path:
    """The first credentials file that exists, in order of preference."""
    if os.environ.get("ARDUINO_CLOUD_CREDENTIALS"):
        return Path(os.environ["ARDUINO_CLOUD_CREDENTIALS"])
    return HOME_CREDENTIALS if HOME_CREDENTIALS.exists() or not APP_CREDENTIALS.exists() else APP_CREDENTIALS

_token: dict = {}


def _credentials() -> dict:
    """The saved API key. Raises RuntimeError (not exit) so the app can report it."""
    path = credentials_path()
    try:
        creds = json.loads(path.read_text())
    except FileNotFoundError:
        raise RuntimeError("No Arduino Cloud API key saved on the board. Add one in the setup wizard.") from None
    except ValueError:
        raise RuntimeError(f"{path} isn't valid JSON") from None
    if not creds.get("client_id") or not creds.get("client_secret"):
        raise RuntimeError(f"{path} needs client_id and client_secret")
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
        raise RuntimeError(f"Token request failed: HTTP {err.code} {err.read().decode(errors='replace')[:300]}") from None
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
    try:
        _run_command(argv)
    except RuntimeError as err:
        sys.exit(str(err))


def _run_command(argv: list[str]) -> None:
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

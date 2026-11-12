# SPDX-License-Identifier: MPL-2.0
"""Create the BirdBox Thing variables and dashboards through the Arduino Cloud API.

Needs an API key saved as described in tools/arduino_cloud.py.

    python3 tools/setup_cloud.py plan        --thing <name or id>
    python3 tools/setup_cloud.py thing       --thing <name or id> [--free] [--delete-legacy]
    python3 tools/setup_cloud.py dashboards  --thing <name or id> [--free | --pro]

`plan` only reads. `thing` adds any missing variables (only the Free set with
--free, which fits the Free plan's 5-variable limit) and fixes permissions;
--delete-legacy also removes variables from older versions of the app.
`dashboards` creates "BirdBox Free" and/or "BirdBox Pro", or replaces their
widgets if they already exist.
"""

import argparse
import sys
import uuid

from arduino_cloud import api

# name: (type, permission). STATUS is Arduino Cloud's Boolean.
VARIABLES = {
    # Settings, Cloud -> board
    "min_confidence": ("FLOAT", "READ_WRITE"),
    "sensitivity": ("FLOAT", "READ_WRITE"),
    "cooldown_seconds": ("INT", "READ_WRITE"),
    "range_filter": ("STATUS", "READ_WRITE"),
    "latitude": ("FLOAT", "READ_WRITE"),
    "longitude": ("FLOAT", "READ_WRITE"),
    "servo_enabled": ("STATUS", "READ_WRITE"),
    "birdsong_enabled": ("STATUS", "READ_WRITE"),
    "hold_for_song": ("STATUS", "READ_WRITE"),
    "travel_ms": ("INT", "READ_WRITE"),
    "servo_speed": ("INT", "READ_WRITE"),
    "home_overrun": ("INT", "READ_WRITE"),
    "hold_ms": ("INT", "READ_WRITE"),
    "servo_command": ("CHARSTRING", "READ_WRITE"),
    "debug_ui": ("STATUS", "READ_WRITE"),
    # Printer (v2)
    "printer_enabled": ("STATUS", "READ_WRITE"),
    "print_each_detection": ("STATUS", "READ_WRITE"),
    "card_picture": ("STATUS", "READ_WRITE"),
    "card_song": ("STATUS", "READ_WRITE"),
    "card_description": ("STATUS", "READ_WRITE"),
    "card_llm": ("STATUS", "READ_WRITE"),
    "summary_hour": ("INT", "READ_WRITE"),
    # Results, board -> Cloud
    "last_species": ("CHARSTRING", "READ_ONLY"),
    "last_scientific_name": ("CHARSTRING", "READ_ONLY"),
    "last_confidence": ("FLOAT", "READ_ONLY"),
    "last_detection_at": ("CHARSTRING", "READ_ONLY"),
    "detections_today": ("INT", "READ_ONLY"),
    "species_today": ("INT", "READ_ONLY"),
    "listening": ("STATUS", "READ_ONLY"),
    "servo_state": ("CHARSTRING", "READ_ONLY"),
    "detection_log": ("CHARSTRING", "READ_ONLY"),
}

# The five variables the Free dashboard uses (the Free plan allows 5 per Thing).
FREE_VARIABLES = ("last_species", "detections_today", "servo_enabled", "birdsong_enabled", "debug_ui")

# Variables from older versions of the app.
LEGACY = ("sweep_enabled", "out_position", "servo_position", "servo_angle", "sweep_degrees", "sweep_ms")

# Widgets as (type, title, variable, x, y, width, height, options) on the
# 24-column desktop grid. The mobile layout is derived from the same order.
FREE_DASHBOARD = [
    ("Value", "Last bird", "last_species", 0, 0, 8, 4, {}),
    ("Value", "Detections today", "detections_today", 8, 0, 4, 4, {}),
    ("Switch", "Bird moves", "servo_enabled", 12, 0, 4, 4, {"showLabels": True}),
    ("Switch", "Birdsong", "birdsong_enabled", 16, 0, 4, 4, {"showLabels": True}),
    ("Switch", "Debug UI", "debug_ui", 20, 0, 4, 4, {"showLabels": True}),
    ("Messenger", "Birds heard", "last_species", 0, 4, 12, 12, {}),
    ("Chart", "Detections today", "detections_today", 12, 4, 12, 12, {}),
]

PRO_DASHBOARD = [
    # Now
    ("Status", "Listening", "listening", 0, 0, 4, 4, {"mode": "On / Off"}),
    ("Value", "Last bird", "last_species", 4, 0, 8, 4, {}),
    ("Value", "Scientific name", "last_scientific_name", 12, 0, 6, 4, {}),
    ("Value", "Heard at", "last_detection_at", 18, 0, 6, 4, {}),
    # Today
    ("Gauge", "Confidence", "last_confidence", 0, 4, 6, 8, {"min": 0, "max": 1}),
    ("Messenger", "Detection log", "detection_log", 6, 4, 9, 12, {}),
    ("Chart", "Detections today", "detections_today", 15, 4, 9, 6, {}),
    ("Chart", "Confidence", "last_confidence", 15, 10, 9, 6, {}),
    ("Value", "Detections today", "detections_today", 0, 12, 3, 4, {}),
    ("Value", "Species today", "species_today", 3, 12, 3, 4, {}),
    # Bird box
    ("Switch", "Bird moves", "servo_enabled", 0, 16, 4, 4, {"showLabels": True}),
    ("Switch", "Birdsong", "birdsong_enabled", 4, 16, 4, 4, {"showLabels": True}),
    ("Switch", "Stay out for song", "hold_for_song", 8, 16, 4, 4, {"showLabels": True}),
    ("Value", "Rail", "servo_state", 12, 16, 4, 4, {}),
    ("Messenger", "Commands: test, out, in, stop, song, card, summary, line", "servo_command", 16, 16, 8, 12, {}),
    # Detection
    ("Value", "Confidence threshold", "min_confidence", 0, 20, 4, 4, {"decimals": 2}),
    ("Value", "Sensitivity", "sensitivity", 4, 20, 4, 4, {"decimals": 2}),
    ("Slider", "Cooldown per species (s)", "cooldown_seconds", 8, 20, 8, 5, {"min": 0, "max": 600}),
    ("Switch", "Range filter", "range_filter", 0, 25, 4, 4, {"showLabels": True}),
    ("Value", "Latitude", "latitude", 4, 25, 6, 4, {"decimals": 4}),
    ("Value", "Longitude", "longitude", 10, 25, 6, 4, {"decimals": 4}),
    # Calibration
    ("Slider", "Servo speed (%)", "servo_speed", 0, 29, 6, 5, {"min": 10, "max": 100}),
    ("Slider", "Travel at 100% (ms)", "travel_ms", 6, 29, 6, 5, {"min": 50, "max": 1500}),
    ("Stepper", "Overrun (ms)", "home_overrun", 12, 29, 4, 5, {"min": 0, "max": 200, "step": 10}),
    ("Slider", "Hold out (ms)", "hold_ms", 16, 29, 8, 5, {"min": 0, "max": 10000}),
    ("Switch", "Debug UI", "debug_ui", 0, 34, 4, 4, {"showLabels": True}),
    # Printer
    ("Switch", "Printing", "printer_enabled", 4, 34, 4, 4, {"showLabels": True}),
    ("Switch", "Print every detection", "print_each_detection", 8, 34, 4, 4, {"showLabels": True}),
    ("Slider", "Daily summary at (hour, -1 = off)", "summary_hour", 12, 34, 12, 5, {"min": -1, "max": 23}),
    ("Switch", "Card: picture", "card_picture", 0, 39, 6, 4, {"showLabels": True}),
    ("Switch", "Card: song", "card_song", 6, 39, 6, 4, {"showLabels": True}),
    ("Switch", "Card: description", "card_description", 12, 39, 6, 4, {"showLabels": True}),
    ("Switch", "Description by local LLM", "card_llm", 18, 39, 6, 4, {"showLabels": True}),
]

DASHBOARDS = {"free": ("BirdBox Free", FREE_DASHBOARD), "pro": ("BirdBox Pro", PRO_DASHBOARD)}


def find_thing(name_or_id: str) -> dict:
    things = api("GET", "/iot/v2/things")
    matches = [t for t in things if name_or_id in (t["id"], t["name"])]
    if len(matches) != 1:
        names = ", ".join(repr(t["name"]) for t in things)
        sys.exit(f"Thing {name_or_id!r} not found (or not unique). Things: {names}")
    return matches[0]


def properties(thing: dict) -> dict:
    return {p["variable_name"]: p for p in api("GET", f"/iot/v2/things/{thing['id']}/properties")}


def wanted(free: bool) -> dict:
    return {name: VARIABLES[name] for name in FREE_VARIABLES} if free else VARIABLES


def plan(thing: dict, free: bool) -> list[tuple]:
    """What `thing` would change: (action, name, detail)."""
    existing = properties(thing)
    steps = []
    for name, (kind, permission) in wanted(free).items():
        prop = existing.get(name)
        if prop is None:
            steps.append(("add", name, f"{kind} {permission}"))
        elif prop["type"] != kind:
            steps.append(("WRONG TYPE", name, f"is {prop['type']}, needs {kind}: delete it and run again"))
        elif prop["permission"] != permission:
            steps.append(("fix", name, f"permission {prop['permission']} -> {permission}"))
    for name in LEGACY:
        if name in existing:
            steps.append(("legacy", name, "unused, removed with --delete-legacy"))
    return steps


def apply_thing(thing: dict, free: bool, delete_legacy: bool) -> None:
    existing = properties(thing)
    base = f"/iot/v2/things/{thing['id']}/properties"
    for action, name, detail in plan(thing, free):
        if action == "add":
            kind, permission = VARIABLES[name]
            api("PUT", base, {"name": name, "variable_name": name, "type": kind, "permission": permission,
                               "update_strategy": "ON_CHANGE", "persist": True})
        elif action == "fix":
            prop = existing[name]
            api("POST", f"{base}/{prop['id']}", {"name": name, "variable_name": name, "type": prop["type"],
                                                "permission": VARIABLES[name][1], "update_strategy": "ON_CHANGE",
                                                "persist": True})
        elif action == "legacy" and delete_legacy:
            api("DELETE", f"{base}/{existing[name]['id']}")
        elif action == "legacy":
            continue
        print(f"{action:<10} {name:<22} {detail}")


def widgets(layout: list, ids: dict) -> list[dict]:
    """API widgets, with a mobile layout that keeps the order: small widgets two to a row."""
    result, mx, my, row_height = [], 0, 0, 0
    for kind, title, variable, x, y, width, height, options in layout:
        if variable not in ids:
            sys.exit(f"The Thing has no {variable!r} variable. Run the `thing` command first.")
        mw = 4 if width <= 4 else 8
        if mx + mw > 8:
            mx, my, row_height = 0, my + row_height, 0
        result.append({
            "id": str(uuid.uuid4()), "type": kind, "name": title,
            "x": x, "y": y, "width": width, "height": height,
            "x_mobile": mx, "y_mobile": my, "width_mobile": mw, "height_mobile": height,
            "options": {"name": title, **options}, "variables": [ids[variable]],
        })
        mx, row_height = mx + mw, max(row_height, height)
    return result


def apply_dashboards(thing: dict, which: list[str]) -> None:
    ids = {name: prop["id"] for name, prop in properties(thing).items()}
    current = {d["name"]: d for d in api("GET", "/iot/v2/dashboards")}
    for key in which:
        name, layout = DASHBOARDS[key]
        body = {"name": name, "widgets": widgets(layout, ids)}
        if name in current:
            api("PUT", f"/iot/v2/dashboards/{current[name]['id']}", body)
            print(f"updated   {name}")
        else:
            created = api("POST", "/iot/v2/dashboards", body)
            print(f"created   {name}  {created['id']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("plan", "thing", "dashboards"))
    parser.add_argument("--thing", required=True, help="the Thing's name or id")
    parser.add_argument("--free", action="store_true", help="only the Free plan's 5 variables / dashboard")
    parser.add_argument("--pro", action="store_true", help="only the Pro dashboard")
    parser.add_argument("--delete-legacy", action="store_true", help="remove variables from older versions")
    args = parser.parse_args()

    thing = find_thing(args.thing)
    if args.command == "plan":
        steps = plan(thing, args.free)
        for action, name, detail in steps:
            print(f"{action:<10} {name:<22} {detail}")
        print("Nothing to change." if not steps else f"{len(steps)} change(s).")
    elif args.command == "thing":
        apply_thing(thing, args.free, args.delete_legacy)
    else:
        apply_dashboards(thing, ["free"] if args.free else ["pro"] if args.pro else ["free", "pro"])


if __name__ == "__main__":
    main()

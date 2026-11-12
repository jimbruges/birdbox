# SPDX-License-Identifier: MPL-2.0

"""BirdBox.

Listens on a microphone, identifies birds on-device with BirdNET V2.4, mirrors
every detection into Arduino Cloud, asks the sketch to push the bird out on its
FS90R-driven rail, and plays a simulated song for the species on a Modulino
Buzzer.

Every setting can be changed from an Arduino Cloud dashboard or from the debug
web UI on port 7000, and is saved on the board. The Thing only needs the
variables you want on your dashboard - see docs/arduino-cloud.md.

The debug UI shows the microphone, the model's best candidates, every setting
and the servo controls. It is switched on and off with the `debug_ui` Cloud
variable.
"""

import io
import json
import math
import threading
import time
import wave
from datetime import date, datetime
from pathlib import Path

import numpy as np
from fastapi import HTTPException, Response

from arduino.app_bricks.arduino_cloud import ArduinoCloud, DEVICE_WINS
from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App, Bridge, Logger

from birdnet import SAMPLE_RATE, BirdNET, Detection

import birdinfo
import history
import receipts
import songs
from printer import Printer

logger = Logger("BirdBox")

birds = BirdNET()
cloud = ArduinoCloud()
web_ui = WebUI()
printer = Printer(lambda name, *args: _bridge(name, *args))

# Every Cloud variable registered below, so the debug UI can list them all.
variable_names: list[str] = []

# Serialises Bridge calls made from the web UI, Cloud writes and the heartbeat.
_bridge_lock = threading.RLock()


def _bridge(name: str, *args):
    with _bridge_lock:
        return Bridge.call(name, *args)

# Counters, reset at local midnight.
_today = date.today()
_detections_today = 0
_species_today: set[str] = set()

servo_enabled = True
birdsong_enabled = True
debug_enabled = False

# The sketch reports the rail as one of these.
RAIL_STATES = {0: "unknown", 1: "in", 2: "out", 3: "moving"}


def register_variable(name: str, **options) -> None:
    """Register a Cloud variable and remember its name for the debug UI."""
    variable_names.append(name)
    cloud.register(name, **options)


def _roll_over_day() -> None:
    """Zero the daily counters when the date changes."""
    global _today, _detections_today
    if date.today() != _today:
        _today = date.today()
        _detections_today = 0
        _species_today.clear()
        logger.info("New day, counters reset")


def on_bird(detection: Detection) -> None:
    """Publish a detection to the Cloud, push the bird out and play its song."""
    global _detections_today

    _roll_over_day()
    _detections_today += 1
    _species_today.add(detection.common_name)

    cloud.last_species = detection.common_name
    cloud.last_scientific_name = detection.scientific_name
    cloud.last_confidence = round(detection.confidence, 3)
    cloud.last_detection_at = detection.timestamp.isoformat(timespec="seconds")
    cloud.detections_today = _detections_today
    cloud.species_today = len(_species_today)
    # One line per detection, for a Messenger widget to show as a running log.
    cloud.detection_log = (
        f"{detection.timestamp:%H:%M} {detection.common_name} {round(detection.confidence * 100)}%"
    )

    if servo_enabled:
        # Fire-and-forget: the sketch runs the out/hold/retract cycle on its own
        # clock, we must not block the analysis thread waiting for it.
        Bridge.notify("servo_present")

    if birdsong_enabled:
        # With the servo on, the song waits until the bird is fully out.
        play_song(detection.scientific_name, wait_for_bird=servo_enabled)

    history.record(detection.timestamp, detection.scientific_name, detection.common_name, detection.confidence)
    # Fetch the picture and description now, so a card prints without waiting.
    birdinfo.prefetch(detection.scientific_name, detection.common_name,
                      use_llm=settings["card_description"] and settings["card_llm"])
    if settings["printer_enabled"] and settings["print_each_detection"]:
        line = receipts.scroll_line(common=detection.common_name, when=detection.timestamp,
                                    confidence=detection.confidence)
        printer.submit(line, f"scroll line for {detection.common_name}", tear=False)


_buzzer_missing_logged = False

# Extra quiet time after a song, for echoes and the buzzer ringing down.
BIRDSONG_MUTE_TAIL_S = 0.5


def _send_song(scientific_name: str, wait_for_bird: bool) -> None:
    global _buzzer_missing_logged

    song, how = songs.song_for(scientific_name)
    sent_at = time.monotonic()
    try:
        with _bridge_lock:
            Bridge.call("buzzer_clear")
            for chunk in songs.encode_chunks(song):
                if Bridge.call("buzzer_add", chunk) < 0:
                    if not _buzzer_missing_logged:
                        logger.warning("No Modulino Buzzer found by the sketch, birdsong is silent")
                        _buzzer_missing_logged = True
                    return
            # buzzer_arm holds the song until the bird reaches the outer stop.
            Bridge.call("buzzer_arm" if wait_for_bird else "buzzer_start")
    except Exception as err:
        logger.warning(f"Could not play birdsong: {err}")
        return

    # Stop the mic hearing the buzzer and reporting it as a bird. The sketch's
    # timing is deterministic: the song starts after the out move (if it waits
    # for the bird) and lasts exactly as long as its segments.
    song_s = sum(ms for _, _, ms in song) / 1000
    wait_s = _out_move_seconds() if wait_for_bird else 0.0
    birds.mute(sent_at, sent_at + wait_s + song_s + BIRDSONG_MUTE_TAIL_S)

    when = "once the bird is out" if wait_for_bird else "now"
    logger.info(
        f"Playing birdsong for {scientific_name} {when} ({how}, {song_s:.1f} s); "
        f"detections muted for {wait_s + song_s + BIRDSONG_MUTE_TAIL_S:.1f} s"
    )


def _out_move_seconds() -> float:
    """How long the sketch's out move takes, from the same formula it uses."""
    return (settings["travel_ms"] * 100 / settings["servo_speed"] + settings["home_overrun"]) / 1000


def play_song(scientific_name: str, wait_for_bird: bool = False) -> None:
    """Send the species' song to the buzzer without blocking the caller."""
    threading.Thread(
        target=_send_song, args=(scientific_name, wait_for_bird), name="birdsong", daemon=True
    ).start()


birds.on_detection(on_bird)


# --- Settings ---------------------------------------------------------------
# Every setting lives in one table. A setting can be changed from Arduino Cloud
# (when the Thing has a variable of the same name) or from the debug UI, and is
# saved to data/settings.json so it survives a restart either way. That lets a
# Free-plan Thing with only a few variables be set up entirely from the debug UI.
#
# On start-up the saved value is the starting point. For a variable the Thing
# does define, the Cloud's stored value then wins (CLOUD_WINS) and is saved.

SETTINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "settings.json"
_settings_lock = threading.Lock()


def _load_saved() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as err:
        logger.warning(f"Ignoring unreadable {SETTINGS_FILE.name}: {err}")
        return {}


def _save() -> None:
    with _settings_lock:
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            partial = SETTINGS_FILE.with_suffix(".tmp")
            partial.write_text(json.dumps(settings, indent=2, sort_keys=True))
            partial.replace(SETTINGS_FILE)
        except OSError as err:
            logger.warning(f"Could not save settings: {err}")


def apply_min_confidence(value: float) -> None:
    birds.min_confidence = value
    logger.info(f"Confidence threshold set to {value:.2f}")


def apply_sensitivity(value: float) -> None:
    birds.sensitivity = value
    logger.info(f"Sensitivity set to {value:.2f}")


def apply_cooldown(value: int) -> None:
    birds.cooldown_seconds = value
    logger.info(f"Per-species cooldown set to {value}s")


def apply_location(_value: object = None) -> None:
    """Enable the range filter only when it is switched on and has coordinates."""
    if settings["range_filter"]:
        birds.set_location(settings["latitude"], settings["longitude"])
    else:
        birds.set_location(None, None)


def apply_boost(value: float) -> None:
    birds.gain_db = value
    logger.info(f"Digital mic boost set to {value:.1f} dB")


def apply_servo_enabled(value: bool) -> None:
    global servo_enabled
    servo_enabled = value
    logger.info(f"Servo {'enabled' if value else 'disabled'}")


def apply_birdsong_enabled(value: bool) -> None:
    global birdsong_enabled
    birdsong_enabled = value
    logger.info(f"Birdsong {'enabled' if value else 'disabled'}")
    if not value:
        Bridge.notify("buzzer_stop")


def apply_debug_ui(value: bool) -> None:
    global debug_enabled
    debug_enabled = value
    logger.info(f"Debug UI {'on' if value else 'off'}")


# --- Servo calibration -----------------------------------------------------
# The rail has a hard stop at each end, about 140 degrees of servo rotation
# apart. Every move drives for the full travel time (scaled by speed) plus an
# overrun into the stop, so the only thing to calibrate is travel_ms: the
# stop-to-stop time at full speed. Too short and the bird stops short of the
# end; too long and the servo pushes against the stop for longer than needed.


def apply_travel_ms(value: int) -> None:
    Bridge.call("servo_set_travel", value)
    logger.info(f"Stop-to-stop travel set to {value} ms at full speed")


def apply_hold_ms(value: int) -> None:
    Bridge.call("servo_set_hold", value)
    logger.info(f"Bird stays out for {value} ms")


def apply_servo_speed(value: int) -> None:
    Bridge.call("servo_set_speed", value)
    logger.info(f"Servo speed set to {value}%")


def apply_home_overrun(value: int) -> None:
    Bridge.call("servo_set_overrun", value)
    logger.info(f"Overrun into each stop set to {value} ms")


def apply_hold_for_song(value: bool) -> None:
    Bridge.call("servo_set_hold_for_song", 1 if value else 0)
    logger.info(f"Bird {'stays out for the song' if value else 'stays out for hold_ms only'}")


# --- Printer -----------------------------------------------------------------
# Optional. With no printer attached every print is skipped with a log line,
# and the debug page still previews each receipt.


def apply_printer_port(value: str) -> None:
    printer.port = value
    printer.begin()
    logger.info(f"Printer connection: {printer.device or 'no USB printer found'}")


def apply_printer_baud(value: int) -> None:
    printer.baud = value
    printer.begin()
    logger.info(f"Printer serial speed set to {value} baud")


def apply_printer_raster(value: str) -> None:
    printer.raster_mode = value
    logger.info(f"Printer image command: {value}")


def apply_printer_reverse(value: bool) -> None:
    printer.reverse = value
    logger.info(f"Printer direction: {'Reverse (lines pre-rotated)' if value else 'Normal'}")


def apply_printer_busy_pin(value: int) -> None:
    Bridge.call("printer_set_busy_pin", value)
    logger.info(f"Printer busy line on {'D' + str(value) if value >= 0 else 'no pin'}")


def apply_printer_spacing(value: int) -> None:
    printer.line_spacing = value
    logger.info(f"Printer ESC * line spacing set to {value}")


def apply_printer_device(value: str) -> None:
    printer.device_setting = value
    if printer.port == "usb":
        logger.info(f"USB printer: {printer.device or 'none found'} (setting {value!r})")


def apply_button_pin(index: int):
    def apply(value: int) -> None:
        Bridge.call("button_set_pin", index, value)
        logger.info(f"Button {index} on {'D' + str(value) if value >= 0 else 'no pin'}")
    return apply


def apply_logged(name: str):
    def apply(value: object) -> None:
        logger.info(f"{name} set to {value}")
    return apply


# name: (type, default, min, max, step, handler, group, label, unit, synced to Cloud)
# The ones that drive the sketch are re-sent whenever the sketch (re)connects.
SETTINGS = {
    "min_confidence": (float, birds.min_confidence, 0.01, 0.99, 0.01, apply_min_confidence, "Detection", "Confidence threshold", "", True),
    "sensitivity": (float, birds.sensitivity, 0.5, 1.5, 0.05, apply_sensitivity, "Detection", "Sensitivity", "", True),
    "cooldown_seconds": (int, int(birds.cooldown_seconds), 0, 3600, 5, apply_cooldown, "Detection", "Per-species cooldown", "s", True),
    "boost_db": (float, birds.gain_db, 0.0, 30.0, 0.5, apply_boost, "Detection", "Digital mic boost", "dB", False),
    "range_filter": (bool, False, None, None, None, apply_location, "Location", "Range filter", "", True),
    "latitude": (float, 0.0, -90.0, 90.0, None, apply_location, "Location", "Latitude (north +)", "°", True),
    "longitude": (float, 0.0, -180.0, 180.0, None, apply_location, "Location", "Longitude (east +)", "°", True),
    "servo_enabled": (bool, True, None, None, None, apply_servo_enabled, "Bird box", "Bird moves", "", True),
    "birdsong_enabled": (bool, True, None, None, None, apply_birdsong_enabled, "Bird box", "Birdsong", "", True),
    "hold_for_song": (bool, True, None, None, None, apply_hold_for_song, "Bird box", "Stay out until the song ends (+0.3 s)", "", True),
    "servo_speed": (int, 40, 10, 100, 1, apply_servo_speed, "Servo", "Speed", "%", True),
    "travel_ms": (int, 320, 50, 3000, 10, apply_travel_ms, "Servo", "Travel (at 100%)", "ms", True),
    "home_overrun": (int, 30, 0, 1000, 5, apply_home_overrun, "Servo", "Overrun into stop", "ms", True),
    "hold_ms": (int, 500, 0, 30000, 100, apply_hold_ms, "Servo", "Hold out", "ms", True),
    "printer_enabled": (bool, True, None, None, None, apply_logged("Printing"), "Printer", "Printing on", "", True),
    "print_each_detection": (bool, False, None, None, None, apply_logged("Detection scroll"), "Printer", "Print a line for every detection", "", True),
    "card_picture": (bool, True, None, None, None, apply_logged("Card picture"), "Printer", "Card: silhouette", "", True),
    "card_song": (bool, True, None, None, None, apply_logged("Card song"), "Printer", "Card: song contour", "", True),
    "card_description": (bool, True, None, None, None, apply_logged("Card description"), "Printer", "Card: description", "", True),
    "card_llm": (bool, True, None, None, None, apply_logged("LLM descriptions"), "Printer", "Description written by the local LLM", "", True),
    "card_credits": (bool, True, None, None, None, apply_logged("Card credits"), "Printer", "Card: picture and text credits", "", True),
    "summary_hour": (int, -1, -1, 23, 1, apply_logged("Daily summary hour"), "Printer", "Daily summary at (−1 = off)", "h", True),
    "printer_port": (str, "serial", None, None, None, apply_printer_port, "Printer", "Connected to", "", False),
    "printer_baud": (int, 9600, 9600, 115200, None, apply_printer_baud, "Printer", "Serial speed", "baud", False),
    "printer_raster": (str, "esc_k", None, None, None, apply_printer_raster, "Printer", "Image command", "", False),
    "printer_busy_pin": (int, -1, -1, 21, None, apply_printer_busy_pin, "Printer", "Busy (CTS) pin", "", False),
    "printer_reverse": (bool, True, None, None, None, apply_printer_reverse, "Printer", "Printer set to Reverse direction (ESC K)", "", False),
    "printer_spacing": (int, 24, 1, 120, 1, apply_printer_spacing, "Printer", "ESC * band spacing (see spacing test)", "", False),
    "printer_device": (str, "auto", None, None, None, apply_printer_device, "Printer", "USB device", "", False),
    "button1_pin": (int, 2, -1, 21, None, apply_button_pin(1), "Buttons", "Button 1 pin (D, −1 = none)", "", False),
    "button1_action": (str, "card", None, None, None, apply_logged("Button 1 action"), "Buttons", "Button 1 does", "", False),
    "button2_pin": (int, 3, -1, 21, None, apply_button_pin(2), "Buttons", "Button 2 pin (D, −1 = none)", "", False),
    "button2_action": (str, "summary", None, None, None, apply_logged("Button 2 action"), "Buttons", "Button 2 does", "", False),
    "debug_ui": (bool, False, None, None, None, apply_debug_ui, "Debug", "Debug UI", "", True),
}
SKETCH_SETTINGS = ("servo_speed", "travel_ms", "home_overrun", "hold_ms", "hold_for_song",
                   "button1_pin", "button2_pin", "printer_baud", "printer_busy_pin")

BUTTON_ACTIONS = ("card", "summary", "line", "test", "song", "none")
# Settings shown as a drop-down: the allowed values, with labels for the debug page.
CHOICES = {
    "printer_port": {"serial": "MCU serial pins D0/D1", "usb": "USB on the hub"},
    "printer_baud": {str(b): f"{b} baud" for b in (9600, 19200, 38400, 57600, 115200)},
    "printer_raster": {"esc_k": "ESC K (SPRT / RS PRO panel printers)", "gs_v0": "GS v 0 (ESC/POS raster)",
                       "esc_star": "ESC * (bit image)", "dc2_star": "DC2 * (CSN-A2 / Adafruit)"},
    "printer_busy_pin": {"-1": "Not used", **{str(d): f"D{d}" for d in (2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13)}},
    **{f"button{n}_action": {"card": "Print the bird card", "summary": "Print the daily summary",
                             "line": "Print a scroll line", "test": "Test the bird (out, song, in)",
                             "song": "Play the last bird's song", "none": "Nothing"} for n in (1, 2)},
    **{f"button{n}_pin": {"-1": "Not used", **{str(d): f"D{d}" for d in (2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13)}}
       for n in (1, 2)},
}


def _coerce(name: str, value: object) -> object:
    """Cast to the setting's type and clamp to its range."""
    kind, default, low, high = SETTINGS[name][:4]
    try:
        if kind is bool:
            value = value.strip().lower() in ("1", "true", "on", "yes") if isinstance(value, str) else bool(value)
        elif kind is str:
            value = str(value).strip() or default
        else:
            value = kind(float(value))
    except (TypeError, ValueError):
        return default
    if name in CHOICES and str(value) not in CHOICES[name]:
        return default
    if low is not None:
        value = max(low, min(high, value))
    return value


def _run_handler(name: str) -> None:
    try:
        with _bridge_lock:
            SETTINGS[name][5](settings[name])
    except Exception as err:
        # The sketch may not be up yet; it gets every setting when it connects.
        logger.warning(f"Could not apply {name}: {err}")


def change_setting(name: str, value: object, publish: bool) -> object:
    """Apply a setting, save it, and (from the debug UI) publish it to the Cloud."""
    settings[name] = _coerce(name, value)
    _run_handler(name)
    _save()
    if publish and SETTINGS[name][9]:
        setattr(cloud, name, settings[name])
    return settings[name]


def push_sketch_settings() -> None:
    for name in SKETCH_SETTINGS:
        _run_handler(name)


_saved = _load_saved()
settings = {name: _coerce(name, _saved.get(name, spec[1])) for name, spec in SETTINGS.items()}
if _saved:
    logger.info(f"Loaded saved settings from {SETTINGS_FILE.name}")


# The test action always sings this species, matching the felt robin on the prototype.
TEST_SPECIES = "Erithacus rubecula"


# --- Receipts ------------------------------------------------------------------


def _last_bird() -> dict | None:
    """The last detection: from the log, or the Cloud's last values before v2 kept a log."""
    last = history.last()
    if last:
        return last
    sci = cloud.get("last_scientific_name", "")
    if not sci:
        return None
    try:
        when = datetime.fromisoformat(cloud.get("last_detection_at", ""))
    except ValueError:
        when = datetime.now()
    return {"when": when, "scientific": sci, "common": cloud.get("last_species", sci),
            "confidence": float(cloud.get("last_confidence", 0) or 0)}


def build_card() -> tuple[object, dict | None]:
    """(image, the bird it describes) for the last species heard."""
    bird = _last_bird()
    if bird is None:
        return receipts.scroll_line(common="No birds heard yet", when=datetime.now(), confidence=0), None
    today, total = history.counts(bird["scientific"])
    picture = birdinfo.silhouette(bird["scientific"]) if settings["card_picture"] else None
    text = (birdinfo.description(bird["scientific"], use_llm=settings["card_llm"])
            if settings["card_description"] else None)
    song = songs.song_for(bird["scientific"])[0] if settings["card_song"] else None
    image = receipts.bird_card(common=bird["common"], scientific=bird["scientific"], when=bird["when"],
                               confidence=bird["confidence"], today=max(today, 1), total=max(total, 1),
                               song=song, picture=picture, description=text and text[0],
                               description_source=text[1] if text else "wikipedia",
                               credits=settings["card_credits"])
    return image, bird


def build_summary():
    return receipts.daily_summary(summary=history.day_summary(), hourly=history.hourly_last_24h(),
                                  when=datetime.now())


def build_line():
    bird = _last_bird()
    if bird is None:
        return receipts.scroll_line(common="No birds heard yet", when=datetime.now(), confidence=0)
    return receipts.scroll_line(common=bird["common"], when=bird["when"], confidence=bird["confidence"])


RECEIPTS = ("card", "summary", "line")


def build_receipt(kind: str):
    if kind == "card":
        return build_card()[0]
    return build_summary() if kind == "summary" else build_line()


def print_receipt(kind: str) -> bool:
    """Render and queue one receipt. Runs the rendering off the caller's thread."""
    if not settings["printer_enabled"]:
        logger.info(f"Printing is off, not printing the {kind}")
        return False
    if printer.device is None:
        logger.info(f"No printer found, not printing the {kind}")
        return False

    def run() -> None:
        try:
            if kind == "card":
                image, bird = build_card()
                if printer.submit(image, "bird card") and bird:
                    # Next card for this species gets a freshly written entry.
                    birdinfo.printed(bird["scientific"], bird["common"],
                                     use_llm=settings["card_description"] and settings["card_llm"])
            elif kind == "summary":
                printer.submit(build_summary(), "daily summary")
            else:
                printer.submit(build_line(), "scroll line", tear=False)
        except Exception as err:  # noqa: BLE001 - a rendering bug must not take the app down
            logger.warning(f"Could not build the {kind}: {err}")

    threading.Thread(target=run, name=f"print-{kind}", daemon=True).start()
    return True


def run_command(client: object, value: str) -> None:
    """Calibration commands, sent from a Messenger widget on the dashboard."""
    global _clear_command

    command = str(value).strip().lower()
    if not command:
        return

    # Cloud only fires on a change, so the variable is reset to "" once this
    # handler has returned (see heartbeat). Otherwise repeats do nothing.
    _clear_command = True

    if command == "out":
        Bridge.call("servo_out")
    elif command in ("in", "home"):
        Bridge.call("servo_in")
    elif command == "stop":
        Bridge.call("servo_stop")
    elif command == "test":
        # The whole detection action, so hold_for_song can be tried too.
        Bridge.call("servo_present")
        if birdsong_enabled:
            play_song(TEST_SPECIES, wait_for_bird=True)
    elif command == "song":
        play_song(cloud.get("last_scientific_name", "") or TEST_SPECIES)
    elif command in RECEIPTS:
        print_receipt(command)
    else:
        logger.warning(f"Unknown command {command!r}. Use: in, out, stop, test, song, card, summary, line")
        return

    logger.info(f"Servo command: {command}")


def _from_cloud(name: str):
    return lambda client, value: change_setting(name, value, publish=False)


# CLOUD_WINS (the default): for a variable the Thing defines, the Cloud's stored
# value is pushed down on connect. A variable with no Cloud value, or one the
# Thing doesn't define at all, keeps the saved value.
for _name, _spec in SETTINGS.items():
    if _spec[9]:
        register_variable(_name, value=settings[_name], on_write=_from_cloud(_name))
register_variable("servo_command", value="", on_write=run_command)

# --- Results published up to the Cloud -------------------------------------
# The last detection keeps the Cloud's value across a restart (CLOUD_WINS), so
# the dashboard still shows the last bird and Messenger widgets don't get a
# blank entry each time the app starts.
register_variable("last_species", value="")
register_variable("last_scientific_name", value="")
register_variable("last_confidence", value=0.0)
register_variable("last_detection_at", value="")
register_variable("detection_log", value="")

# DEVICE_WINS: on reconnect the board's reading is the truth, not a stale
# value the Cloud is still holding from the last session.
register_variable("detections_today", value=0, sync=DEVICE_WINS)
register_variable("species_today", value=0, sync=DEVICE_WINS)
register_variable("listening", value=False, sync=DEVICE_WINS)
register_variable("servo_state", value="unknown", sync=DEVICE_WINS)

# Have the last bird's card extras ready straight after a restart.
_startup_bird = _last_bird()
if _startup_bird:
    birdinfo.prefetch(_startup_bird["scientific"], _startup_bird["common"],
                      use_llm=settings["card_description"] and settings["card_llm"])

# Apply everything that runs on this side; the sketch's settings follow once it
# answers (see heartbeat).
for _name in SETTINGS:
    if _name not in SKETCH_SETTINGS:
        _run_handler(_name)


# --- Debug web UI -----------------------------------------------------------
# The server is started by the App with the bricks; the debug_ui switch gates
# every route, so when it is off the page and API answer 503 and touch nothing.

SERVO_COMMANDS = ("out", "in", "stop", "test")


def _require_debug() -> None:
    if not debug_enabled:
        raise HTTPException(status_code=503, detail="Debug UI is off. Set debug_ui to true in Arduino Cloud.")


def _settings_schema() -> list[dict]:
    """Every setting with its current value, for the debug UI to build controls from."""
    return [
        {
            "name": name,
            "type": kind.__name__,
            "value": settings[name],
            "min": low,
            "max": high,
            "step": step,
            "group": group,
            "label": label,
            "unit": unit,
            "cloud": synced,
            "choices": CHOICES.get(name),
        }
        for name, (kind, _, low, high, step, _, group, label, unit, synced) in SETTINGS.items()
    ]


def _jsonable(value: object) -> object:
    return value if value is None or isinstance(value, (bool, int, float, str)) else str(value)


def api_status() -> dict:
    _require_debug()
    stats = birds.stats
    return {
        "listening": stats["listening"],
        "mic": {
            "device": stats["device"],
            "volume": stats["mic_volume"],
            "level": stats["level"],
            "history": stats["level_history"],
        },
        "birdnet": {
            "windows_analysed": stats["windows_analysed"],
            "last_inference_ms": stats["last_inference_ms"],
            "species_in_range": stats["species_in_range"],
            "min_confidence": stats["min_confidence"],
            "top": stats["top"],
            "top_at": stats["top_at"],
            "watch": stats["watch"],
            "windows_muted": stats["windows_muted"],
            "last_window_muted": stats["last_window_muted"],
        },
        "servo": {
            "enabled": servo_enabled,
            "state": cloud.get("servo_state", "unknown"),
        },
        "birdsong": {
            "enabled": birdsong_enabled,
            "buzzer_found": _buzzer_found,
        },
        "printer": {
            "enabled": settings["printer_enabled"],
            "device": printer.device,
            "status": printer.describe_status(),
            "printed": printer.printed,
            "last_error": printer.last_error,
            "llm": birdinfo.last_exchange(),
        },
        "settings": _settings_schema(),
        "variables": {name: _jsonable(cloud.get(name)) for name in variable_names},
    }


def api_servo(body: dict) -> dict:
    _require_debug()
    command = str(body.get("command", "")).strip().lower()
    if command not in SERVO_COMMANDS:
        raise HTTPException(status_code=400, detail=f"Unknown servo command {command!r}")
    with _bridge_lock:
        run_command(None, command)
    return {"ok": True, "command": command}


def api_songs() -> dict:
    """The predefined songs, for the debug UI's species picker."""
    _require_debug()
    curated = [{"scientific": sci, "name": common} for sci, (common, _) in songs.CURATED.items()]
    return {"curated": sorted(curated, key=lambda s: s["name"])}


def api_birdsong(body: dict) -> dict:
    """Play a species' song now. Works even while birdsong_enabled is off, for testing."""
    _require_debug()
    scientific = str(body.get("scientific", "")).strip()
    if not scientific:
        raise HTTPException(status_code=400, detail="scientific name required")
    song, how = songs.song_for(scientific)
    play_song(scientific)
    return {"ok": True, "scientific": scientific, "match": how, "segments": len(song)}


def api_setting(body: dict) -> dict:
    """Change any setting from the debug UI. It is saved, and sent to the Cloud too."""
    _require_debug()
    name = body.get("name")
    if name not in SETTINGS or name == "debug_ui":
        raise HTTPException(status_code=400, detail=f"Unknown setting {name!r}")
    value = change_setting(name, body.get("value"), publish=True)
    return {"ok": True, "name": name, "value": value}


def api_mic(body: dict) -> dict:
    _require_debug()
    try:
        birds.set_mic_volume(int(body.get("volume", 0)))
    except RuntimeError as err:
        raise HTTPException(status_code=409, detail=str(err))
    return {"ok": True, "volume": birds.mic_volume}


def _wav_bytes(samples: np.ndarray) -> bytes:
    """Mono 16-bit PCM WAV at the capture rate."""
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


def _dbfs(amplitude: float) -> str:
    return f"{20.0 * math.log10(max(amplitude, 1e-6)):.1f}"


def api_sample(seconds: float = 3.0, boosted: bool = False) -> Response:
    """The newest audio the mic captured, as a WAV the browser can play or save."""
    _require_debug()
    seconds = max(0.5, min(10.0, float(seconds)))
    samples = birds.recent_audio(seconds)
    if samples.size == 0:
        raise HTTPException(status_code=409, detail="No audio captured yet")
    if boosted and birds.gain_db > 0:
        samples = np.clip(samples * (10.0 ** (birds.gain_db / 20.0)), -1.0, 1.0)

    headers = {
        "X-Peak-dBFS": _dbfs(float(np.max(np.abs(samples)))),
        "X-RMS-dBFS": _dbfs(float(np.sqrt(np.mean(np.square(samples))))),
        "X-Samples": str(samples.size),
        "Cache-Control": "no-store",
        "Content-Disposition": 'attachment; filename="birdnet-sample.wav"',
    }
    return Response(content=_wav_bytes(samples), media_type="audio/wav", headers=headers)


def api_receipt(kind: str = "card") -> Response:
    """A receipt as the printer would print it, for previews."""
    _require_debug()
    if kind not in RECEIPTS:
        raise HTTPException(status_code=400, detail=f"Unknown receipt {kind!r}")
    image = build_receipt(kind)
    buffer = io.BytesIO()
    image.convert("L").save(buffer, "PNG")
    return Response(content=buffer.getvalue(), media_type="image/png",
                    headers={"X-Paper-mm": str(receipts.paper_mm(image)), "Cache-Control": "no-store"})


def api_print(body: dict) -> dict:
    _require_debug()
    kind = str(body.get("kind", ""))
    if kind not in RECEIPTS:
        raise HTTPException(status_code=400, detail=f"Unknown receipt {kind!r}")
    if not print_receipt(kind):
        raise HTTPException(status_code=409, detail="Printing is off" if not settings["printer_enabled"]
                            else "No printer found")
    return {"ok": True, "kind": kind}


PRINTER_TESTS = ("text", "esc_k", "gs_v0", "esc_star", "dc2_star", "spacing")
SPACING_TRIALS = (24, 20, 16, 12, 8)


def _spacing_test() -> bytes:
    """The same three-band pattern at several ESC * spacings, each labelled in plain text.

    The right spacing shows unbroken vertical bars and a smooth diagonal, with no
    white gaps (too big) or overlapping, squashed bands (too small).
    """
    from PIL import Image, ImageDraw

    from printer import raster_esc_star

    img = Image.new("1", (receipts.WIDTH, 72), 1)
    d = ImageDraw.Draw(img)
    for x in (4, 120, 240, 372):
        d.rectangle((x, 0, x + 7, 71), fill=0)
    d.line((0, 0, receipts.WIDTH - 1, 71), fill=0, width=3)
    out = bytearray()
    for n in SPACING_TRIALS:
        out += f"Spacing {n}:\n".encode() + raster_esc_star(img, n) + b"\n"
    return bytes(out)


def _test_pattern(mode: str):
    """A small pattern that's easy to judge: border, diagonals, text and a black bar."""
    from PIL import Image, ImageDraw

    img = Image.new("1", (receipts.WIDTH, 72), 1)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, receipts.WIDTH - 1, 71), outline=0, width=2)
    d.line((0, 0, receipts.WIDTH - 1, 71), fill=0, width=2)
    d.line((0, 71, receipts.WIDTH - 1, 0), fill=0, width=2)
    d.rectangle((8, 8, 120, 26), fill=0)
    d.text((8, 32), f"Image test: {CHOICES['printer_raster'][mode]}", font=receipts.font(16), fill=0)
    return img


def api_printer_test(body: dict) -> dict:
    """Print a wiring test (plain text) or the test pattern with one image command."""
    _require_debug()
    test = str(body.get("test", ""))
    if test not in PRINTER_TESTS:
        raise HTTPException(status_code=400, detail=f"Unknown test {test!r}")
    if test == "spacing":
        ok = printer.submit_raw(_spacing_test(), "ESC * spacing test")
    elif test == "text":
        ok = printer.submit_text(
            f"BirdBox printer test\n{printer.device}\n0123456789 ABCDEFGHIJKLM abcdefghijklm\n"
            "If this reads correctly, the wiring and baud rate are right.\n", "text test")
    else:
        ok = printer.submit(_test_pattern(test), f"image test ({test})", mode=test)
    if not ok:
        raise HTTPException(status_code=409, detail="No printer found")
    return {"ok": True, "test": test}


web_ui.expose_api("POST", "/api/printer_test", api_printer_test)
web_ui.expose_api("GET", "/api/receipt", api_receipt)
web_ui.expose_api("POST", "/api/print", api_print)
web_ui.expose_api("GET", "/api/sample", api_sample)
web_ui.expose_api("GET", "/api/status", api_status)
web_ui.expose_api("POST", "/api/servo", api_servo)
web_ui.expose_api("POST", "/api/setting", api_setting)
web_ui.expose_api("POST", "/api/mic", api_mic)
web_ui.expose_api("GET", "/api/songs", api_songs)
web_ui.expose_api("POST", "/api/birdsong", api_birdsong)


_last_state: str | None = None
_buzzer_found: bool | None = None
_clear_command = False
_summary_printed_on: date | None = None

_printer_checked_at = 0.0
PRINTER_CHECK_S = 30


def _check_schedule() -> None:
    """Print the daily summary once, at the start of summary_hour."""
    global _summary_printed_on
    hour = settings["summary_hour"]
    now = datetime.now()
    if hour >= 0 and now.hour == hour and _summary_printed_on != now.date():
        _summary_printed_on = now.date()
        logger.info("Printing the scheduled daily summary")
        print_receipt("summary")


def heartbeat() -> None:
    """Keep the Cloud's view of the listener honest."""
    global _last_state, _buzzer_found, _clear_command, _printer_checked_at

    # Fast enough to see the rail state change while testing from the dashboard.
    time.sleep(0.5)
    _roll_over_day()
    cloud.listening = birds.stats["listening"]

    # Reset outside the write handler, so a repeat of the same command is a change.
    if _clear_command:
        _clear_command = False
        cloud.servo_command = ""

    try:
        with _bridge_lock:
            state = RAIL_STATES.get(Bridge.call("servo_state"), "unknown")
            presses = Bridge.call("button_presses")
            if _buzzer_found is None:
                _buzzer_found = bool(Bridge.call("buzzer_present"))
                logger.info(f"Modulino Buzzer {'found' if _buzzer_found else 'not found'}")
    except Exception as err:
        if _last_state is None:
            logger.warning(f"Sketch not answering yet: {err}")
        return
    # Bit n of the sketch's button_presses() is button n+1.
    for n in (1, 2):
        if presses & (1 << (n - 1)):
            action = settings[f"button{n}_action"]
            logger.info(f"Button {n} pressed: {action}")
            if action != "none":
                run_command(None, action)
    _check_schedule()
    if printer.port == "serial" and time.monotonic() - _printer_checked_at > PRINTER_CHECK_S and state == "in":
        # Only while the bird is in: the status query blocks the sketch for up to 150 ms.
        _printer_checked_at = time.monotonic()
        printer.check()
    if state != _last_state:
        if _last_state is None:
            logger.info(f"Sketch connected, rail {state}")
            push_sketch_settings()
        _last_state = state
        cloud.servo_state = state


App.run(user_loop=heartbeat)

# SPDX-License-Identifier: MPL-2.0
"""Receive another BirdBox's birdsong through Arduino Cloud, instead of a microphone.

A unit that listens (the sender) already publishes its last detection to its own
Thing: last_species, last_scientific_name, last_confidence and last_detection_at.
This module reads those four properties from the Cloud API every few seconds. A new
last_detection_at means a new bird, and the caller then plays its song, pushes the
bird out, prints it and logs it, exactly as if this unit's microphone had heard it.

A Thing can't read another Thing's variables from the device, so this polls the
REST API. It uses the API key that tools/setup_cloud.py saved on the board, in
~/.config/arduino-cloud/credentials.json. The sender's Thing ID is the only thing
to configure here: it's shown on that Thing's page at app.arduino.cc/things.

On start-up the sender's current last bird is taken as the baseline, so restarting
the receiver doesn't play the same bird again.
"""

from __future__ import annotations

import re
import sys
import threading
from datetime import datetime
from pathlib import Path

from arduino.app_utils import Logger

from birdnet import Detection

# tools/arduino_cloud.py is the API helper the setup scripts use.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import arduino_cloud  # noqa: E402

logger = Logger("Receiver")

POLL_SECONDS = 5.0
THING_ID = re.compile(r"[A-Za-z0-9-]{8,64}")


class Receiver:
    """Polls one sending Thing and hands each new detection to `on_detection`."""

    def __init__(self, on_detection) -> None:
        self._on_detection = on_detection
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.thing_id = ""
        self.thing_name: str | None = None        # the sending Thing's name, for receipts
        self.received = 0
        self.checked_at: str | None = None
        self.last_error: str | None = None
        self.sender_last: dict | None = None      # what the sender last reported, for the debug page
        self._seen: str | None = None             # last_detection_at already handled

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def set_source(self, thing_id: str) -> None:
        """Start polling `thing_id`, or stop when it's empty. Restarts if it changes."""
        thing_id = thing_id.strip()
        with self._lock:
            if thing_id == self.thing_id and self.running:
                return
            self._halt()
            self.thing_id = thing_id
            self.thing_name = None
            self.received = 0
            self.last_error = None
            self.sender_last = None
            self._seen = None
            if not thing_id:
                return
            if not THING_ID.fullmatch(thing_id):
                self.last_error = "That doesn't look like a Thing ID"
                return
            self._stop = threading.Event()
            self._thread = threading.Thread(target=self._run, args=(self._stop,), name="receiver", daemon=True)
            self._thread.start()
            logger.info(f"Receiving birdsong from Thing {thing_id}")

    def stop(self) -> None:
        with self._lock:
            self._halt()

    def _halt(self) -> None:
        self._stop.set()
        self._thread = None

    def _run(self, stop: threading.Event) -> None:
        while not stop.is_set():
            try:
                self._check()
                self.last_error = None
            except Exception as err:  # noqa: BLE001 - network or credentials: keep polling
                if str(err) != self.last_error:
                    logger.warning(f"Could not read the sending unit: {err}")
                self.last_error = str(err)
            self.checked_at = datetime.now().isoformat(timespec="seconds")
            stop.wait(POLL_SECONDS)

    def _check(self) -> None:
        if self.thing_name is None:
            try:                                    # only for labels: never stops the birds
                thing = arduino_cloud.api("GET", f"/iot/v2/things/{self.thing_id}")
                self.thing_name = str(thing.get("name") or "") or None if isinstance(thing, dict) else None
            except RuntimeError:
                pass
        props = {p["name"]: p.get("last_value") for p in
                 arduino_cloud.api("GET", f"/iot/v2/things/{self.thing_id}/properties")}
        species = str(props.get("last_species") or "")
        scientific = str(props.get("last_scientific_name") or "")
        stamp = str(props.get("last_detection_at") or "")
        self.sender_last = {"species": species, "scientific": scientific, "at": stamp,
                            "confidence": props.get("last_confidence")}
        if not stamp or not scientific:
            return                                  # the sender hasn't heard anything yet
        if self._seen is None:
            self._seen = stamp                      # baseline: don't replay the last bird on start
            return
        if stamp == self._seen:
            return
        self._seen = stamp
        try:
            when = datetime.fromisoformat(stamp)
        except ValueError:
            when = datetime.now()
        detection = Detection(common_name=species or scientific, scientific_name=scientific,
                              confidence=float(props.get("last_confidence") or 0.0), timestamp=when)
        self.received += 1
        logger.info(f"Received {detection} from the sending unit")
        self._on_detection(detection)

    def status(self) -> dict:
        return {"thing_id": self.thing_id, "thing_name": self.thing_name, "running": self.running, "received": self.received,
                "checked_at": self.checked_at, "last_error": self.last_error,
                "sender_last": self.sender_last}

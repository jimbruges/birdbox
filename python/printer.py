# SPDX-License-Identifier: MPL-2.0
"""ESC/POS output to a thermal printer, run from a background queue.

Receipts arrive as 1-bit images and are sent as raster graphics (GS v 0), so
what prints is exactly what the debug page previews.

Two ways to reach the printer:
- "serial" (default): the MCU's hardware serial pins D0/D1. The bytes go to the
  sketch over the Router Bridge in base64 chunks; it buffers them and feeds the
  UART at the printer's baud rate.
- "usb": a USB printer on the hub, written directly from Linux.

With no printer attached, jobs are dropped (USB) or simply go nowhere (serial),
and the rest of the app carries on.
"""

from __future__ import annotations

import base64
import glob
import os
import queue
import termios
import threading
import time

from PIL import Image

from arduino.app_utils import Logger

logger = Logger("Printer")

# Where a USB printer shows up: the printer class driver, USB serial, or a
# USB-to-RS-232 adapter.
CANDIDATES = ("/dev/usb/lp*", "/dev/ttyACM*", "/dev/ttyUSB*")
SERIAL_BAUD = termios.B9600     # only matters for a real RS-232 link
BAND_ROWS = 128                 # rows per raster command; keeps each write small
TEAR_FEED_DOTS = 96             # 12 mm: enough to tear a card off at the bar

ESC_INIT = b"\x1b@"
CHUNK = 144                     # raw bytes per Bridge call: 192 base64 chars, inside the RPC buffer
BAUD_RATES = (9600, 19200, 38400, 57600, 115200)


def find_device(setting: str = "auto") -> str | None:
    if setting and setting != "auto":
        return setting if os.path.exists(setting) else None
    for pattern in CANDIDATES:
        found = sorted(glob.glob(pattern))
        if found:
            return found[0]
    return None


def raster(image: Image.Image) -> bytes:
    """GS v 0 commands for a 1-bit image no wider than the printer (384 dots)."""
    img = image.convert("1")
    width_bytes = (img.width + 7) // 8
    # PIL packs mode "1" with 1 = white; the printer wants 1 = black.
    data = bytes(b ^ 0xFF for b in img.tobytes())
    out = bytearray()
    for top in range(0, img.height, BAND_ROWS):
        rows = min(BAND_ROWS, img.height - top)
        band = data[top * width_bytes:(top + rows) * width_bytes]
        out += b"\x1dv0\x00" + bytes((width_bytes & 0xFF, width_bytes >> 8, rows & 0xFF, rows >> 8)) + band
    return bytes(out)


def feed(dots: int) -> bytes:
    """ESC J: feed paper by `dots` (8 per mm)."""
    out = bytearray()
    while dots > 0:
        step = min(255, dots)
        out += b"\x1bJ" + bytes((step,))
        dots -= step
    return bytes(out)


class Printer:
    """Queues receipts and writes them to the printer one at a time."""

    def __init__(self, bridge_call) -> None:
        self.port = "serial"            # "serial" (MCU D0/D1) or "usb"
        self.baud = 9600
        self.device_setting = "auto"    # USB only
        self.status: int | None = None  # last ESC/POS status byte over serial, -1 = no reply
        self.last_error: str | None = None
        self.printed = 0
        self._bridge_call = bridge_call
        self._jobs: queue.Queue = queue.Queue(maxsize=50)
        threading.Thread(target=self._worker, name="printer", daemon=True).start()

    @property
    def device(self) -> str | None:
        """Where jobs go, or None when there's nowhere to send them."""
        if self.port == "serial":
            return f"MCU serial D0/D1 at {self.baud} baud"
        return find_device(self.device_setting)

    @property
    def busy(self) -> bool:
        return not self._jobs.empty()

    def begin(self) -> None:
        """(Re)start the MCU's UART at the configured baud rate."""
        if self.port == "serial":
            self._bridge_call("printer_begin", self.baud)

    def check(self) -> int | None:
        """Ask a serial printer for its status; -1 means it didn't answer."""
        if self.port != "serial" or self.busy:
            return self.status
        try:
            self.status = int(self._bridge_call("printer_status"))
        except Exception as err:  # noqa: BLE001 - sketch not up yet
            logger.info(f"Printer status unavailable: {err}")
        return self.status

    def describe_status(self) -> str:
        if self.port != "serial":
            return "found" if self.device else "not found"
        if self.status is None:
            return "not checked"
        if self.status == -1:
            return "no reply (printer off, or its TX not wired to D0)"
        if self.status == -2:
            return "printing"
        return "ready" if self.status & 0x08 == 0 else "offline"

    def submit(self, image: Image.Image, label: str, tear: bool = True) -> bool:
        """Queue an image. Returns False (and logs) when there's no printer to send to."""
        if self.device is None:
            logger.info(f"No printer found, skipping {label}")
            return False
        try:
            self._jobs.put_nowait((image, label, tear))
        except queue.Full:
            logger.warning(f"Print queue full, dropping {label}")
            return False
        return True

    def _worker(self) -> None:
        while True:
            image, label, tear = self._jobs.get()
            payload = ESC_INIT + raster(image) + (feed(TEAR_FEED_DOTS) if tear else b"")
            try:
                self._write(payload)
                self.printed += 1
                self.last_error = None
                logger.info(f"Printed {label} ({image.height / 8:.0f} mm)")
            except OSError as err:
                self.last_error = str(err)
                logger.warning(f"Could not print {label}: {err}")

    def _write(self, payload: bytes) -> None:
        if self.port == "serial":
            self._write_serial(payload)
        else:
            self._write_usb(payload)

    def _write_serial(self, payload: bytes) -> None:
        """Stream to the sketch's print buffer, waiting whenever it's full."""
        for start in range(0, len(payload), CHUNK):
            chunk = base64.b64encode(payload[start:start + CHUNK]).decode()
            deadline = time.monotonic() + 30
            while True:
                try:
                    free = int(self._bridge_call("printer_write", chunk))
                except Exception as err:  # noqa: BLE001
                    raise OSError(f"sketch not answering: {err}") from err
                if free >= 0:
                    break
                if time.monotonic() > deadline:
                    raise OSError("printer buffer stayed full for 30 s")
                # The buffer drains at the baud rate (about 1 KB/s at 9600).
                time.sleep(0.05)

    def _write_usb(self, payload: bytes) -> None:
        path = self.device
        if path is None:
            raise OSError("printer disconnected")
        fd = os.open(path, os.O_WRONLY | os.O_NOCTTY)
        try:
            if "tty" in path:
                attrs = termios.tcgetattr(fd)
                attrs[0] = 0                                    # iflag: raw
                attrs[1] = 0                                    # oflag: no CR/LF translation
                attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
                attrs[3] = 0                                    # lflag: raw
                attrs[4] = attrs[5] = SERIAL_BAUD
                termios.tcsetattr(fd, termios.TCSANOW, attrs)
            view = memoryview(payload)
            while view:
                written = os.write(fd, view[:4096])
                view = view[written:]
                time.sleep(0.005)                               # let a slow USB printer keep up
        finally:
            os.close(fd)

# SPDX-License-Identifier: MPL-2.0

"""BirdNET acoustic bird identification, running on-device.

Wraps the BirdNET GLOBAL 6K V2.4 model (Cornell Lab of Ornithology / Chemnitz
University of Technology) behind the usual Brick lifecycle: it opens a
microphone, slices the stream into the 3-second windows the model expects and
reports every species that clears a confidence threshold.

Model weights are CC BY-NC-SA 4.0 - non-commercial use only. See README.md.
"""

from __future__ import annotations

import math
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
from arduino.app_utils import Logger, brick
from arduino.app_peripherals.microphone import Microphone

logger = Logger("BirdNET")

# The V2.4 graph has its own STFT/mel frontend, so it takes a raw waveform:
# exactly 3 seconds of 48 kHz mono float32 in [-1, 1].
SAMPLE_RATE = 48000
WINDOW_SECONDS = 3.0
WINDOW_SAMPLES = int(SAMPLE_RATE * WINDOW_SECONDS)  # 144000
NUM_CLASSES = 6522

# The .tflite files were dropped from the repo at v2.4.0, so the models come
# from the last tag that still carries them; labels come from the current tag.
_REPO_RAW = "https://raw.githubusercontent.com/birdnet-team/BirdNET-Analyzer"
_MODEL_URL = _REPO_RAW + "/v1.5.1/birdnet_analyzer/checkpoints/V2.4/{filename}"
_LABELS_URL = _REPO_RAW + "/v2.4.0/birdnet_analyzer/labels/V2.4/BirdNET_GLOBAL_6K_V2.4_Labels_{locale}.txt"

_MODEL_FILES = {
    "FP16": "BirdNET_GLOBAL_6K_V2.4_Model_FP16.tflite",
    "FP32": "BirdNET_GLOBAL_6K_V2.4_Model_FP32.tflite",
}
_RANGE_MODEL_FILE = "BirdNET_GLOBAL_6K_V2.4_MData_Model_V2_FP16.tflite"

# Species scoring below this in the range filter are treated as absent.
_RANGE_FILTER_THRESHOLD = 0.03

# How often to look for a microphone that is not plugged in yet.
_MIC_RETRY_SECONDS = 10.0

# Debug UI: how many candidates to keep per window, and how many level readings.
_TOP_CANDIDATES = 5
_LEVEL_HISTORY = 120
# How much raw audio is kept for the recorded sample in the debug UI.
_RING_SECONDS = 10


def _to_dbfs(amplitude: float) -> float:
    return 20.0 * math.log10(max(amplitude, 1e-6))


@dataclass(frozen=True)
class Detection:
    """One species heard in one 3-second window."""

    common_name: str
    scientific_name: str
    confidence: float
    timestamp: datetime

    @property
    def label(self) -> str:
        return f"{self.common_name} ({self.scientific_name})"

    def __str__(self) -> str:
        return f"{self.label} {self.confidence:.0%}"


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value == "" else value


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        logger.warning(f"{name} is not a number, falling back to {default}")
        return default


def _week_of_year_48(when: datetime) -> int:
    """BirdNET splits the year into 48 weeks, four per month."""
    return (when.month - 1) * 4 + min((when.day - 1) // 7, 3) + 1


@brick
class BirdNET:
    """Listens on a microphone and identifies the birds it hears.

    ```python
    from birdnet import BirdNET
    from arduino.app_utils import App

    birds = BirdNET()
    birds.on_detection(lambda d: print(d))

    App.run()
    ```
    """

    def __init__(
        self,
        mic: Microphone | None = None,
        min_confidence: float | None = None,
        sensitivity: float | None = None,
        overlap_seconds: float | None = None,
        cooldown_seconds: float | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        birds_only: bool | None = None,
    ):
        self.birds_only = (
            birds_only if birds_only is not None else _env("BIRDNET_BIRDS_ONLY", "true").lower() == "true"
        )
        self.min_confidence = (
            min_confidence if min_confidence is not None else _env_float("BIRDNET_MIN_CONFIDENCE", 0.5)
        )
        self.sensitivity = sensitivity if sensitivity is not None else _env_float("BIRDNET_SENSITIVITY", 1.0)
        self.cooldown_seconds = (
            cooldown_seconds if cooldown_seconds is not None else _env_float("BIRDNET_COOLDOWN_SECONDS", 30.0)
        )

        overlap = overlap_seconds if overlap_seconds is not None else _env_float("BIRDNET_OVERLAP_SECONDS", 0.0)
        overlap = min(max(overlap, 0.0), WINDOW_SECONDS - 0.5)
        self._hop_samples = WINDOW_SAMPLES - int(overlap * SAMPLE_RATE)

        self._latitude, self._longitude = self._normalise_location(
            latitude if latitude is not None else self._optional_float("BIRDNET_LATITUDE"),
            longitude if longitude is not None else self._optional_float("BIRDNET_LONGITUDE"),
        )

        self._model_dir = Path(_env("BIRDNET_MODEL_DIR", "/app/models/birdnet"))
        self._variant = _env("BIRDNET_MODEL_VARIANT", "FP16").upper()
        if self._variant not in _MODEL_FILES:
            logger.warning(f"Unknown model variant {self._variant!r}, using FP16")
            self._variant = "FP16"
        self._locale = _env("BIRDNET_LOCALE", "en_uk")
        self._threads = max(1, min(4, int(_env_float("BIRDNET_THREADS", 2))))

        self._mic = mic
        self._owns_mic = mic is None
        self._interpreter = None
        self._input_index = None
        self._output_index = None
        self._labels: list[tuple[str, str]] = []
        self._is_bird: np.ndarray | None = None
        self._range_mask: np.ndarray | None = None
        self._range_mask_week: int | None = None

        # Rolling capture buffer, kept at a little over one window.
        self._buffer = np.zeros(0, dtype=np.float32)
        self._last_seen: dict[str, float] = {}
        self._listeners: list[Callable[[Detection], None]] = []
        self._species_listeners: dict[str, list[Callable[[Detection], None]]] = {}
        self._running = False
        self._windows_analysed = 0
        self._last_inference_ms = 0.0
        self._mic_retry_at = 0.0
        self._mic_warned = False
        self._gain_db = max(0.0, min(30.0, _env_float("BIRDNET_GAIN_DB", 0.0)))

        # Raw capture (before boost), kept for the debug UI's recorded sample.
        self._ring = np.zeros(_RING_SECONDS * SAMPLE_RATE, dtype=np.float32)
        self._ring_end = 0  # index just past the newest sample
        self._ring_filled = 0
        self._ring_lock = threading.Lock()

        # Debug state, read by the web UI. Each field is replaced whole rather
        # than mutated, so readers on other threads never see a half-written value.
        self._level: dict = {}
        self._level_history: list[float] = []
        self._top: list[dict] = []
        self._top_at: float | None = None
        self._watch: dict = {}
        self._watch_index: int | None = None

        # Periods (monotonic start, end) when the app itself was making sound.
        self._mutes: list[tuple[float, float]] = []
        self._mutes_lock = threading.Lock()
        self._windows_muted = 0
        self._last_window_muted = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_detection(self, callback: Callable[[Detection], None]) -> None:
        """Call `callback(detection)` for every species detected."""
        self._listeners.append(callback)

    def on_detect(self, common_name: str, callback: Callable[[Detection], None]) -> None:
        """Call `callback(detection)` only when this species is detected."""
        self._species_listeners.setdefault(common_name.strip().lower(), []).append(callback)

    def mute(self, start: float, end: float) -> None:
        """Ignore detections from any window that overlaps start..end.

        Times are on the `time.monotonic()` clock. Use it while the app itself is
        making sound the microphone can hear, such as a buzzer playing birdsong.
        """
        now = time.monotonic()
        with self._mutes_lock:
            # Anything that ended more than a window ago can no longer overlap.
            self._mutes = [(s, e) for s, e in self._mutes if e > now - WINDOW_SECONDS * 2]
            self._mutes.append((start, end))

    def _is_muted(self, window_start: float, window_end: float) -> bool:
        with self._mutes_lock:
            return any(s < window_end and e > window_start for s, e in self._mutes)

    def set_location(self, latitude: float | None, longitude: float | None) -> None:
        """Restrict results to species plausible here. Pass None, None to disable."""
        latitude, longitude = self._normalise_location(latitude, longitude)
        if (latitude, longitude) == (self._latitude, self._longitude):
            return
        self._latitude, self._longitude = latitude, longitude
        self._range_mask = None
        self._range_mask_week = None
        logger.info(f"Range filter location set to {latitude}, {longitude}")

    @property
    def stats(self) -> dict:
        return {
            "windows_analysed": self._windows_analysed,
            "last_inference_ms": round(self._last_inference_ms, 1),
            "species_in_range": None if self._range_mask is None else int(self._range_mask.sum()),
            "listening": self._running and self._mic is not None,
            "device": None if self._mic is None else getattr(self._mic, "name", "unknown"),
            "mic_volume": self.mic_volume,
            "level": self._level,
            "level_history": self._level_history,
            "top": self._top,
            "top_at": self._top_at,
            "watch": self._watch,
            "windows_muted": self._windows_muted,
            "last_window_muted": self._last_window_muted,
            "min_confidence": self.min_confidence,
            "sensitivity": self.sensitivity,
            "gain_db": self._gain_db,
            "cooldown_seconds": self.cooldown_seconds,
        }

    @property
    def mic_volume(self) -> int | None:
        """Software gain of the open microphone (0-100), or None if none is open."""
        if self._mic is None:
            return None
        try:
            return int(self._mic.volume)
        except Exception:
            return None

    @property
    def gain_db(self) -> float:
        """Digital boost applied to the captured audio before analysis, in dB (0-30)."""
        return self._gain_db

    @gain_db.setter
    def gain_db(self, value: float) -> None:
        self._gain_db = max(0.0, min(30.0, float(value)))
        logger.info(f"Digital gain set to {self._gain_db:.1f} dB")

    def set_mic_volume(self, volume: int) -> None:
        """Set the software gain of the open microphone (0-100)."""
        if self._mic is None:
            raise RuntimeError("No microphone is open")
        self._mic.volume = max(0, min(100, int(volume)))

    # ------------------------------------------------------------------
    # Brick lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        logger.info("Starting BirdNET")
        self._ensure_assets()
        self._load_labels()
        self._load_interpreter()
        self._running = True

        if self._mic is not None:
            self._mic.start()
            self._announce_listening()

    def loop(self) -> None:
        """Pull whatever audio is ready and analyse any complete window."""
        if not self._running:
            time.sleep(0.05)
            return

        if self._mic is None:
            self._try_open_microphone()
            return

        chunk = self._mic.capture()
        if chunk is None:
            time.sleep(0.005)
            return

        samples = self._to_float32(chunk)
        self._store_raw(samples)
        if self._gain_db > 0:
            # Boost after the hardware capture, so the meter shows what the model gets.
            samples = np.clip(samples * (10.0 ** (self._gain_db / 20.0)), -1.0, 1.0).astype(np.float32)
        self._record_level(samples)
        self._buffer = np.concatenate((self._buffer, samples))
        if self._buffer.size < WINDOW_SAMPLES:
            return

        # When the window's audio was captured, on the monotonic clock: its last
        # sample is as old as whatever is queued behind it in the buffer.
        window_end = time.monotonic() - (self._buffer.size - WINDOW_SAMPLES) / SAMPLE_RATE
        window_start = window_end - WINDOW_SECONDS

        window = self._buffer[:WINDOW_SAMPLES]
        self._buffer = self._buffer[self._hop_samples :]

        # If inference fell behind the microphone, drop the backlog rather than
        # analysing older and older audio forever.
        max_backlog = WINDOW_SAMPLES + self._hop_samples
        if self._buffer.size > max_backlog:
            dropped = self._buffer.size - max_backlog
            self._buffer = self._buffer[-max_backlog:]
            logger.warning(f"Inference behind real time, dropped {dropped / SAMPLE_RATE:.1f}s of audio")

        detections = self._analyse(window)
        self._last_window_muted = self._is_muted(window_start, window_end)
        if self._last_window_muted:
            # The audio overlaps something the app played itself; still analysed,
            # so the debug UI shows what the model heard, but never reported.
            self._windows_muted += 1
            if detections:
                logger.debug(f"Ignored while muted: {', '.join(str(d) for d in detections)}")
            return
        for detection in detections:
            self._emit(detection)

    def stop(self) -> None:
        logger.info("Stopping BirdNET")
        self._running = False
        if self._mic is not None and self._owns_mic:
            try:
                self._mic.stop()
            except Exception as err:  # the mic may already be gone
                logger.debug(f"Microphone stop failed: {err}")
            finally:
                self._mic = None

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def _analyse(self, window: np.ndarray) -> list[Detection]:
        started = time.perf_counter()
        self._interpreter.set_tensor(self._input_index, window.reshape(1, WINDOW_SAMPLES))
        self._interpreter.invoke()
        logits = self._interpreter.get_tensor(self._output_index)[0]
        self._last_inference_ms = (time.perf_counter() - started) * 1000
        self._windows_analysed += 1

        scores = self._flat_sigmoid(logits)

        if self.birds_only:
            scores = scores * self._is_bird

        mask = self._range_filter_mask()
        if mask is not None:
            scores = scores * mask

        # Keep the best few candidates whatever their score, so the debug UI can
        # show how close the model came when nothing clears the threshold.
        best = np.argsort(scores)[::-1][:_TOP_CANDIDATES]
        self._top = [
            {
                "name": self._labels[i][1],
                "scientific": self._labels[i][0],
                "score": round(float(scores[i]), 4),
            }
            for i in best
        ]
        self._top_at = time.time()

        # The species named by BIRDNET_WATCH_SPECIES, scored whatever its rank.
        if self._watch_index is not None:
            score = float(scores[self._watch_index])
            self._watch = {
                "name": self._labels[self._watch_index][1],
                "score": round(score, 4),
                "rank": int(np.count_nonzero(scores > score)) + 1,
            }

        now = datetime.now()
        hits = np.flatnonzero(scores >= self.min_confidence)
        detections = [
            Detection(
                common_name=self._labels[i][1],
                scientific_name=self._labels[i][0],
                confidence=float(scores[i]),
                timestamp=now,
            )
            for i in hits
        ]
        detections.sort(key=lambda d: d.confidence, reverse=True)
        return detections

    def recent_audio(self, seconds: float) -> np.ndarray:
        """The newest `seconds` of raw captured audio, oldest first (float32, 48 kHz mono)."""
        size = self._ring.size
        with self._ring_lock:
            count = min(int(seconds * SAMPLE_RATE), self._ring_filled)
            if count <= 0:
                return np.zeros(0, dtype=np.float32)
            start = (self._ring_end - count) % size
            if start + count <= size:
                return self._ring[start : start + count].copy()
            head = self._ring[start:]
            return np.concatenate((head, self._ring[: count - head.size]))

    def _store_raw(self, samples: np.ndarray) -> None:
        size = self._ring.size
        if samples.size >= size:
            samples = samples[-size:]
        with self._ring_lock:
            end = self._ring_end
            first = min(samples.size, size - end)
            self._ring[end : end + first] = samples[:first]
            self._ring[: samples.size - first] = samples[first:]
            self._ring_end = (end + samples.size) % size
            self._ring_filled = min(size, self._ring_filled + samples.size)

    def _record_level(self, samples: np.ndarray) -> None:
        """Track peak and RMS level of each captured chunk, in dBFS, for the debug UI."""
        if samples.size == 0:
            return
        peak = float(np.max(np.abs(samples)))
        rms = float(np.sqrt(np.mean(np.square(samples))))
        rms_db = _to_dbfs(rms)
        self._level = {
            "peak_dbfs": round(_to_dbfs(peak), 1),
            "rms_dbfs": round(rms_db, 1),
            "clipping": peak >= 0.999,
            "at": time.time(),
        }
        self._level_history = (self._level_history + [round(rms_db, 1)])[-_LEVEL_HISTORY:]

    def _flat_sigmoid(self, logits: np.ndarray) -> np.ndarray:
        """BirdNET's own logit->probability transform (the graph emits raw logits)."""
        return 1.0 / (1.0 + np.exp(-self.sensitivity * np.clip(logits, -15.0, 15.0)))

    def _range_filter_mask(self) -> np.ndarray | None:
        """1.0 for species plausible here and now, 0.0 for the rest."""
        if self._latitude is None or self._longitude is None:
            return None

        week = _week_of_year_48(datetime.now())
        if self._range_mask is not None and self._range_mask_week == week:
            return self._range_mask

        path = self._model_dir / _RANGE_MODEL_FILE
        if not path.exists():
            logger.warning("Range filter model missing, considering all species")
            self._latitude = self._longitude = None
            return None

        from ai_edge_litert.interpreter import Interpreter

        interpreter = Interpreter(model_path=str(path), num_threads=1)
        interpreter.allocate_tensors()
        in_index = interpreter.get_input_details()[0]["index"]
        out_index = interpreter.get_output_details()[0]["index"]
        coords = np.array([[self._latitude, self._longitude, week]], dtype=np.float32)
        interpreter.set_tensor(in_index, coords)
        interpreter.invoke()
        presence = interpreter.get_tensor(out_index)[0]

        self._range_mask = (presence >= _RANGE_FILTER_THRESHOLD).astype(np.float32)
        self._range_mask_week = week
        logger.info(
            f"Range filter: {int(self._range_mask.sum())} of {NUM_CLASSES} species "
            f"plausible at {self._latitude:.3f}, {self._longitude:.3f} in week {week}"
        )
        return self._range_mask

    def _emit(self, detection: Detection) -> None:
        key = detection.common_name.lower()
        now = time.monotonic()
        last = self._last_seen.get(key)
        if last is not None and now - last < self.cooldown_seconds:
            return
        self._last_seen[key] = now

        logger.info(f"Detected {detection}")
        for callback in self._listeners + self._species_listeners.get(key, []):
            try:
                callback(detection)
            except Exception as err:
                logger.error(f"Detection callback failed: {err}")

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_location(
        latitude: float | None, longitude: float | None
    ) -> tuple[float | None, float | None]:
        """0, 0 is the conventional "no location set" value, not the Gulf of Guinea."""
        if latitude is None or longitude is None:
            return None, None
        if latitude == 0.0 and longitude == 0.0:
            return None, None
        return float(latitude), float(longitude)

    @staticmethod
    def _optional_float(name: str) -> float | None:
        raw = os.getenv(name, "").strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            logger.warning(f"{name}={raw!r} is not a number, ignoring")
            return None

    @staticmethod
    def _to_float32(chunk: np.ndarray) -> np.ndarray:
        """Normalise an ALSA chunk to float32 in [-1, 1]."""
        if chunk.dtype == np.float32:
            return chunk
        if chunk.dtype == np.int16:
            return chunk.astype(np.float32) / 32768.0
        if chunk.dtype == np.int32:
            return chunk.astype(np.float32) / 2147483648.0
        if chunk.dtype == np.uint8:
            return (chunk.astype(np.float32) - 128.0) / 128.0
        return chunk.astype(np.float32)

    def _announce_listening(self) -> None:
        logger.info(
            f"Listening at {SAMPLE_RATE} Hz, {WINDOW_SECONDS:g}s windows, "
            f"hop {self._hop_samples / SAMPLE_RATE:.2f}s, threshold {self.min_confidence:.2f}"
        )

    def _try_open_microphone(self) -> None:
        """Wait for a microphone to appear, without taking the app down."""
        now = time.monotonic()
        if now < self._mic_retry_at:
            time.sleep(0.5)
            return
        self._mic_retry_at = now + _MIC_RETRY_SECONDS

        try:
            mic = self._open_microphone()
            mic.start()
        except Exception as err:
            if not self._mic_warned:
                logger.warning(f"No microphone yet ({err}). Retrying every {_MIC_RETRY_SECONDS:g}s.")
                self._mic_warned = True
            return

        self._mic = mic
        self._owns_mic = True
        self._mic_warned = False
        self._buffer = np.zeros(0, dtype=np.float32)
        logger.info(f"Microphone connected: {getattr(mic, 'name', 'unknown')}")
        self._announce_listening()

    def _open_microphone(self) -> Microphone:
        device = _env("BIRDNET_MIC_DEVICE", "auto")
        kwargs = dict(
            sample_rate=SAMPLE_RATE,
            channels=Microphone.CHANNELS_MONO,
            format=np.int16,
            buffer_size=Microphone.BUFFER_SIZE_SAFE,
        )
        # Debug level: this is retried every few seconds while no mic is plugged in.
        if device.lower() == "auto":
            logger.debug("Opening the first available microphone (USB preferred)")
            return Microphone(**kwargs)
        if device.isdigit():
            logger.debug(f"Opening microphone index {device}")
            return Microphone(int(device), **kwargs)
        logger.debug(f"Opening microphone {device!r}")
        return Microphone(device, **kwargs)

    def _ensure_assets(self) -> None:
        self._model_dir.mkdir(parents=True, exist_ok=True)
        model_file = _MODEL_FILES[self._variant]
        self._fetch(_MODEL_URL.format(filename=model_file), self._model_dir / model_file)
        self._fetch(
            _LABELS_URL.format(locale=self._locale),
            self._model_dir / f"labels_{self._locale}.txt",
            fallback_url=_LABELS_URL.format(locale="en_uk"),
        )
        # Only needed when a location is configured, but it is small and
        # fetching it up front keeps the first detection fast.
        self._fetch(
            _MODEL_URL.format(filename=_RANGE_MODEL_FILE),
            self._model_dir / _RANGE_MODEL_FILE,
            required=False,
        )

    @staticmethod
    def _fetch(url: str, destination: Path, fallback_url: str | None = None, required: bool = True) -> None:
        if destination.exists() and destination.stat().st_size > 0:
            return
        partial = destination.with_suffix(destination.suffix + ".part")
        logger.info(f"Downloading {destination.name} (first run only)...")
        try:
            with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as out:
                size = 0
                while True:
                    block = response.read(1 << 16)
                    if not block:
                        break
                    out.write(block)
                    size += len(block)
            partial.rename(destination)
            logger.info(f"Downloaded {destination.name} ({size / 1e6:.1f} MB)")
        except (urllib.error.URLError, OSError) as err:
            partial.unlink(missing_ok=True)
            if fallback_url is not None:
                logger.warning(f"Could not fetch {url} ({err}), trying the default locale")
                BirdNET._fetch(fallback_url, destination, required=required)
                return
            if required:
                raise RuntimeError(f"Could not download {destination.name} from {url}: {err}") from err
            logger.warning(f"Optional asset {destination.name} unavailable: {err}")

    def _load_labels(self) -> None:
        path = self._model_dir / f"labels_{self._locale}.txt"
        lines = path.read_text(encoding="utf-8").splitlines()
        self._labels = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            scientific, _, common = line.partition("_")
            self._labels.append((scientific, common or scientific))
        if len(self._labels) != NUM_CLASSES:
            raise RuntimeError(f"Expected {NUM_CLASSES} labels in {path}, found {len(self._labels)}")

        # BirdNET's output also covers non-bird sounds - Dog, Siren, Fireworks,
        # Engine, Human vocal and so on. Those are the entries whose scientific
        # and common name are identical; real species always differ.
        self._is_bird = np.array(
            [scientific != common for scientific, common in self._labels], dtype=np.float32
        )
        logger.info(f"{len(self._labels)} classes loaded ({int(self._is_bird.sum())} bird species)")

        watch = _env("BIRDNET_WATCH_SPECIES", "Eurasian Blackbird").strip().lower()
        self._watch_index = next((i for i, (_, common) in enumerate(self._labels) if common.lower() == watch), None)
        if self._watch_index is None and watch:
            logger.warning(f"BIRDNET_WATCH_SPECIES {watch!r} is not in the {self._locale} labels")

    def _load_interpreter(self) -> None:
        from ai_edge_litert.interpreter import Interpreter

        path = self._model_dir / _MODEL_FILES[self._variant]
        logger.info(f"Loading {path.name} on {self._threads} thread(s)")
        self._interpreter = Interpreter(model_path=str(path), num_threads=self._threads)
        self._interpreter.allocate_tensors()
        self._input_index = self._interpreter.get_input_details()[0]["index"]
        self._output_index = self._interpreter.get_output_details()[0]["index"]

        # The first invoke costs ~1 s while XNNPACK plans; spend it here rather
        # than on the first window of real audio.
        started = time.perf_counter()
        self._interpreter.set_tensor(self._input_index, np.zeros((1, WINDOW_SAMPLES), dtype=np.float32))
        self._interpreter.invoke()
        logger.info(f"Model warm in {(time.perf_counter() - started) * 1000:.0f} ms")

# SPDX-License-Identifier: MPL-2.0
"""Per-species extras for the bird card: a PhyloPic silhouette and a Wikipedia sentence.

Each is fetched once and cached in data/birdinfo/, so printing never waits on
the network once a species has been seen. Everything here is best-effort: on
any failure the card is printed without the extra.
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from arduino.app_utils import Logger

logger = Logger("BirdInfo")

CACHE = Path(__file__).resolve().parent.parent / "data" / "birdinfo"
USER_AGENT = "BirdBox/2.0 (https://github.com/jimbruges/birdbox)"
PHYLOPIC = "https://api.phylopic.org"
PHYLOPIC_ACCEPT = "application/vnd.phylopic.v2+json"

# PhyloPic licence URLs -> the short name printed in the credit line.
LICENSES = {
    "publicdomain/zero": "CC0",
    "publicdomain/mark": "Public domain",
    "licenses/by/": "CC BY",
    "licenses/by-sa/": "CC BY-SA",
    "licenses/by-nc/": "CC BY-NC",
    "licenses/by-nc-sa/": "CC BY-NC-SA",
}

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _slug(scientific: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", scientific.lower()).strip("_")


def _get(url: str, accept: str = "application/json", timeout: float = 20) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _species_lock(scientific: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(scientific, threading.Lock())


# --- Wikipedia --------------------------------------------------------------


def _first_sentence(extract: str, max_chars: int) -> str:
    """The extract's first sentence, without parentheses, cut at a word if too long."""
    text = re.sub(r"\s*\([^)]*\)", "", extract)            # drop "(Linnaeus, 1758)" and the like
    # Drop ", also known as the X or Y," style asides, which cost paper and say little.
    text = re.sub(r",\s*(?:also |simply |more commonly )?known (?:simply |also )?as [^,]+,", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    match = re.match(r"(.+?[.!?])(\s|$)", text)
    sentence = match.group(1) if match else text
    if len(sentence) > max_chars:
        sentence = sentence[: max_chars - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return sentence


def wikipedia_intro(scientific: str) -> str | None:
    """The introduction of the species' Wikipedia article as plain text (cached)."""
    path = CACHE / f"{_slug(scientific)}.json"
    info = _load(path)
    if "intro" not in info:
        with _species_lock(scientific):
            info = _load(path)
            if "intro" not in info:
                query = urllib.parse.urlencode({"action": "query", "prop": "extracts", "exintro": 1,
                                                "explaintext": 1, "redirects": 1, "format": "json",
                                                "titles": scientific})
                try:
                    data = json.loads(_get(f"https://en.wikipedia.org/w/api.php?{query}"))
                    page = next(iter(data["query"]["pages"].values()))
                    info["intro"] = page.get("extract", "") if "missing" not in page else ""
                except Exception as err:  # noqa: BLE001 - offline or similar: try again next time
                    logger.info(f"Could not fetch Wikipedia text for {scientific}: {err}")
                    return None
                _save(path, info)
    return info["intro"] or None


def description(scientific: str, use_llm: bool = True, max_chars: int = 200) -> tuple[str, str] | None:
    """(text, source) for the bird card, or None.

    Uses the cached LLM encyclopaedia entry when there is one, otherwise the
    first sentence of Wikipedia. Call printed() after printing it, so the next
    print gets a fresh entry.
    """
    intro = wikipedia_intro(scientific)
    if not intro:
        return None
    llm = _load(CACHE / f"{_slug(scientific)}.json").get("llm") if use_llm else None
    if llm and llm.get("text"):
        return llm["text"], "llm"
    return _first_sentence(intro, max_chars), "wikipedia"


# --- Local LLM entries -------------------------------------------------------
# A small model (Qwen 3.5 0.8B on the UNO Q) takes 30-100 s per entry, so each
# species keeps one cached entry, written in the background. Printing uses it
# straight away and queues a replacement, so cards never repeat word for word
# yet never wait for the model. Each new entry rotates its focus to vary it.
#
# The model is asked to condense the Wikipedia text, not to add to it, and each
# reply is checked against that text: any longer word it uses that isn't in the
# source counts against it, and below GROUNDED_MIN the reply is thrown away.

LLM_TIMEOUT_S = 180
GROUNDED_MIN = 0.9
MAX_WORDS = 40
_STOPWORDS = set("a an the of in and or to is are was were it its as by for with on at from that this which be "
                 "has have also known their they there than these those into".split())

_llm = None
_llm_failed = False
_llm_jobs: "queue.Queue[tuple[str, str]]" = queue.Queue()
_llm_queued: set[str] = set()
_exchange: dict = {"species": "", "prompt": "", "raw": "", "text": "", "grounded": None, "status": "idle"}
FOCUS = (
    "appearance and plumage",
    "where it lives and its range",
    "what it eats and how it feeds",
    "its behaviour, voice and habits",
)


def last_exchange() -> dict:
    return dict(_exchange)


def _get_llm():
    """The LLM brick, created on first use; None when the brick or model is missing."""
    global _llm, _llm_failed
    if _llm is None and not _llm_failed:
        try:
            from arduino.app_bricks.llm import LargeLanguageModel
            _llm = LargeLanguageModel(temperature=0.7, max_tokens=200)
        except Exception as err:  # noqa: BLE001 - brick not in app.yaml, no model downloaded, ...
            logger.warning(f"Local LLM unavailable, using Wikipedia sentences: {err}")
            _llm_failed = True
    return _llm


def _prompt(common: str, intro: str, focus: str) -> str:
    return ("You edit entries for an old encyclopaedia of British birds. Below is reference text about the "
            f"{common}. Write a two-sentence entry of at most 35 words, leaning towards {focus} where the "
            "text allows. Use only facts stated in the text; do not add anything. "
            "Plain prose, no markdown, do not start with the bird's name.\n\nText:\n" + intro[:1800]
            + "\n/no_think")


def grounding(text: str, source: str) -> tuple[float, list[str]]:
    """Share of the reply's content words found in the source (by 5-letter stem)."""
    words = [w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 3 and w not in _STOPWORDS]
    src = source.lower()
    missing = [w for w in words if w[:5] not in src]
    return 1 - len(missing) / max(1, len(words)), missing


def _clean(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    text = re.sub(r"[*_#`>]+", "", text)
    text = re.sub(r"\s*\([^)]*\)", "", text)         # the card already shows the scientific name
    text = re.sub(r"\s+", " ", text).strip().strip('"')
    return text


def request_entry(scientific: str, common: str) -> None:
    """Queue a new LLM entry unless an unprinted one is already cached (or queued)."""
    llm = _load(CACHE / f"{_slug(scientific)}.json").get("llm")
    if (llm and llm.get("text") and not llm.get("printed")) or scientific in _llm_queued:
        return
    _llm_queued.add(scientific)
    _llm_jobs.put((scientific, common))


def printed(scientific: str, common: str, use_llm: bool) -> None:
    """The card was printed: mark its entry used and write a fresh one for next time."""
    path = CACHE / f"{_slug(scientific)}.json"
    with _species_lock(scientific):
        info = _load(path)
        if info.get("llm"):
            info["llm"]["printed"] = True
            _save(path, info)
    if use_llm:
        request_entry(scientific, common)


def _llm_worker() -> None:
    while True:
        scientific, common = _llm_jobs.get()
        try:
            _write_entry(scientific, common)
        finally:
            _llm_queued.discard(scientific)


def _write_entry(scientific: str, common: str) -> None:
    intro = wikipedia_intro(scientific)
    llm = _get_llm() if intro else None
    if llm is None:
        return
    previous = _load(CACHE / f"{_slug(scientific)}.json").get("llm") or {}
    focus_index = (previous.get("focus", -1) + 1) % len(FOCUS)
    prompt = _prompt(common, intro, FOCUS[focus_index])
    _exchange.update(species=scientific, prompt=prompt, raw="", text="", grounded=None, status="writing")
    result: dict = {}

    def run() -> None:
        try:
            result["raw"] = llm.chat(prompt)
        except Exception as err:  # noqa: BLE001
            result["error"] = str(err)

    worker = threading.Thread(target=run, daemon=True)
    started = time.monotonic()
    worker.start()
    worker.join(LLM_TIMEOUT_S)
    if worker.is_alive() or "error" in result:
        # Not cached: a timeout or a runner hiccup is worth another try later.
        _exchange.update(status=f"failed: {result.get('error', 'timed out')}")
        logger.warning(f"LLM entry for {scientific} failed: {result.get('error', 'timed out')}")
        return
    raw = result.get("raw", "")
    text = _clean(raw)
    score, missing = grounding(text, intro)
    words = len(text.split())
    ok = score >= GROUNDED_MIN and 6 <= words <= MAX_WORDS
    _exchange.update(raw=raw, text=text, grounded=round(score, 2),
                     status="accepted" if ok else f"rejected ({words} words, grounded {score:.2f}: {missing[:5]})")
    path = CACHE / f"{_slug(scientific)}.json"
    with _species_lock(scientific):
        info = _load(path)
        if ok or not (info.get("llm") or {}).get("text"):
            # A rejected reply never replaces a good entry; it's tried again after the next print.
            info["llm"] = {"text": text if ok else "", "grounded": round(score, 2), "focus": focus_index,
                           "printed": False, "seconds": round(time.monotonic() - started)}
            _save(path, info)
    logger.info(f"LLM entry for {scientific} {_exchange['status']} in {round(time.monotonic() - started)} s")


threading.Thread(target=_llm_worker, name="llm-entries", daemon=True).start()


# --- PhyloPic ---------------------------------------------------------------


def _phylopic_lookup(name: str) -> dict | None:
    """Primary image of the PhyloPic node with this exact name."""
    build = json.loads(_get(f"{PHYLOPIC}/", PHYLOPIC_ACCEPT)).get("build")
    query = urllib.parse.urlencode({"build": build, "filter_name": name.lower(), "page": 0,
                                    "embed_items": "true", "embed_primaryImage": "true"})
    data = json.loads(_get(f"{PHYLOPIC}/nodes?{query}", PHYLOPIC_ACCEPT))
    for node in data.get("_embedded", {}).get("items", []):
        image = node.get("_embedded", {}).get("primaryImage")
        if image:
            return image
    return None


def _license_name(href: str) -> str:
    return next((short for key, short in LICENSES.items() if key in href), "see PhyloPic")


def silhouette(scientific: str) -> tuple[Path, str] | None:
    """(path to a cached PNG silhouette, credit line), or None.

    Tries the species, then the genus. The credit names the artist and licence.
    """
    slug = _slug(scientific)
    path = CACHE / f"{slug}.json"
    info = _load(path)
    if "silhouette" not in info:
        with _species_lock(scientific):
            info = _load(path)
            if "silhouette" not in info:
                found = None
                try:
                    for name in (scientific, scientific.split()[0]):
                        image = _phylopic_lookup(name)
                        if image:
                            links = image["_links"]
                            files = sorted(links.get("rasterFiles", []),
                                           key=lambda f: int(f["sizes"].split("x")[0]))
                            # The smallest raster at least 256 px wide is plenty for a 96 px print.
                            pick = next((f for f in files if int(f["sizes"].split("x")[0]) >= 256), files[-1])
                            CACHE.mkdir(parents=True, exist_ok=True)
                            png = CACHE / f"{slug}.png"
                            png.write_bytes(_get(pick["href"], "image/png"))
                            artist = links.get("contributor", {}).get("title", "unknown")
                            found = {
                                "file": png.name,
                                "credit": f"Silhouette: {artist}, {_license_name(links.get('license', {}).get('href', ''))}, PhyloPic",
                                "match": name,
                            }
                            break
                except Exception as err:  # noqa: BLE001 - offline or similar: try again next time
                    logger.info(f"Could not fetch a PhyloPic silhouette for {scientific}: {err}")
                    return None
                info["silhouette"] = found  # None means PhyloPic has nothing for it
                _save(path, info)
    found = info.get("silhouette")
    if found and (CACHE / found["file"]).exists():
        return CACHE / found["file"], found["credit"]
    return None


def prefetch(scientific: str, common: str, use_llm: bool) -> None:
    """Fetch the extras in the background, so a later print doesn't wait."""
    def run() -> None:
        silhouette(scientific)
        if wikipedia_intro(scientific) and use_llm:
            request_entry(scientific, common)
    threading.Thread(target=run, name="birdinfo", daemon=True).start()


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return {}


def _save(path: Path, info: dict) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info, indent=1))

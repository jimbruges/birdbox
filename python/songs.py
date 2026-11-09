# SPDX-License-Identifier: MPL-2.0

"""Simulated birdsong for the Modulino Buzzer.

A piezo can only play one square-wave pitch at a time, so these are sketches
of each song rather than recordings: the rhythm, pitch range and shape (trill,
two-note call, descending flourish, coo...) of the real thing.

A song is a list of segments `(start_hz, end_hz, ms)`. Equal frequencies are a
steady note, unequal ones a sweep, and 0 Hz is a rest. The sketch plays them.

Species are matched in three steps:
1. a hand-made song for common UK garden birds, keyed by scientific name;
2. otherwise the song of a curated bird from the same genus, re-pitched;
3. otherwise a song generated from the name, so each species always gets the
   same one.
"""

from __future__ import annotations

import random
import zlib

Segment = tuple[int, int, int]

MAX_SEGMENTS = 96          # matches MAX_SEGMENTS in sketch.ino
MIN_HZ, MAX_HZ = 500, 9000  # what the buzzer reproduces usefully


def note(hz: int, ms: int) -> Segment:
    return (hz, hz, ms)


def sweep(start_hz: int, end_hz: int, ms: int) -> Segment:
    return (start_hz, end_hz, ms)


def rest(ms: int) -> Segment:
    return (0, 0, ms)


def trill(start_hz: int, end_hz: int, count: int, note_ms: int, gap_ms: int) -> list[Segment]:
    out: list[Segment] = []
    for _ in range(count):
        out += [sweep(start_hz, end_hz, note_ms), rest(gap_ms)]
    return out


def repeat(phrase: list[Segment], times: int) -> list[Segment]:
    return phrase * times


def harsh(ms: int, high_hz: int = 2600, low_hz: int = 1800, step_ms: int = 10) -> list[Segment]:
    """Rapid down-sweeps, which a piezo renders as a rough, scratchy note."""
    return [sweep(high_hz, low_hz, step_ms)] * max(1, ms // step_ms)


def run(start_hz: int, end_hz: int, count: int, note_ms: int, gap_ms: int) -> list[Segment]:
    """Separate notes stepping evenly from one pitch to another."""
    out: list[Segment] = []
    for i in range(count):
        hz = start_hz + (end_hz - start_hz) * i // max(1, count - 1)
        out += [note(hz, note_ms), rest(gap_ms)]
    return out


def drum(count: int = 18, first_gap_ms: int = 45, last_gap_ms: int = 25) -> list[Segment]:
    """Woodpecker drumming: short knocks that speed up."""
    out: list[Segment] = []
    for i in range(count):
        out += [note(1500, 8), rest(first_gap_ms + (last_gap_ms - first_gap_ms) * i // max(1, count - 1))]
    return out


def warble(seed: int, count: int, low_hz: int, high_hz: int) -> list[Segment]:
    """A fast, varied run of short notes and slurs, the same every time for a seed."""
    rng = random.Random(seed)
    out: list[Segment] = []
    for _ in range(count):
        hz = rng.randint(low_hz, high_hz)
        out += [sweep(hz, max(low_hz, min(high_hz, hz + rng.randint(-700, 700))), rng.randint(25, 60))]
        if rng.random() < 0.6:
            out.append(rest(rng.randint(5, 20)))
    return out


def _chaffinch() -> list[Segment]:
    # An accelerating, descending run, then the terminal flourish.
    out: list[Segment] = []
    for i in range(12):
        out += [note(5200 - i * 130, 45), rest(60 - i * 4)]
    return out + [sweep(3000, 4800, 110), sweep(4800, 2600, 170)]


def _dunnock() -> list[Segment]:
    out: list[Segment] = []
    for i in range(18):
        hz = 4200 + (i * 937) % 1900  # hurried, squeaky, never repeating
        out += [sweep(hz, hz + 400, 40), rest(10)]
    return out


# Common UK garden birds: scientific name -> (common name, song).
CURATED: dict[str, tuple[str, list[Segment]]] = {
    "Turdus merula": ("Eurasian Blackbird", [
        sweep(1800, 2300, 170), sweep(2300, 1900, 140), rest(70),
        sweep(2200, 2700, 120), note(2700, 90), sweep(2700, 2100, 180), rest(90),
        sweep(1900, 2500, 100), sweep(2500, 2000, 150), rest(80),
        *trill(5200, 6400, 6, 25, 15),
    ]),
    "Erithacus rubecula": ("European Robin", [
        sweep(4200, 6800, 70), rest(30), sweep(6500, 3800, 90), rest(40),
        note(7200, 60), sweep(5000, 5600, 50), rest(60),
        sweep(3600, 5200, 80), sweep(5200, 4400, 60), rest(30),
        *trill(6000, 6600, 4, 30, 20), rest(80),
        sweep(7400, 4600, 110), rest(40), note(3900, 80), sweep(3900, 6200, 90),
    ]),
    "Parus major": ("Great Tit", repeat([note(5200, 90), rest(20), note(3600, 120), rest(60)], 5)),
    "Cyanistes caeruleus": ("Eurasian Blue Tit", [
        note(7200, 90), rest(70), note(7000, 90), rest(70),
        *trill(4600, 4200, 10, 30, 20),
    ]),
    "Fringilla coelebs": ("Common Chaffinch", _chaffinch()),
    "Troglodytes troglodytes": ("Eurasian Wren", [
        *trill(6000, 5200, 6, 35, 20), sweep(4500, 7000, 60), rest(25),
        *trill(5600, 6200, 16, 14, 8), rest(40),
        sweep(7200, 4800, 80), *trill(4800, 5400, 8, 20, 12), note(6500, 90),
    ]),
    "Passer domesticus": ("House Sparrow", repeat([sweep(3000, 3900, 60), sweep(3900, 3200, 50), rest(170)], 5)),
    "Columba palumbus": ("Common Woodpigeon", [
        note(700, 250), rest(80), sweep(760, 880, 400), rest(80), note(720, 250), rest(160),
        note(700, 250), rest(80), note(700, 280),
    ]),
    "Streptopelia decaocto": ("Collared Dove", repeat([
        note(750, 200), rest(60), sweep(800, 850, 450), rest(60), note(700, 250), rest(400),
    ], 2)),
    "Turdus philomelos": ("Song Thrush", [
        *repeat([sweep(2600, 3400, 70), sweep(3400, 2800, 70), rest(60)], 3), rest(150),
        *repeat([note(4200, 50), note(3000, 50), rest(40)], 3), rest(150),
        *repeat([sweep(1900, 2900, 120), rest(60)], 2),
    ]),
    "Carduelis carduelis": ("European Goldfinch", [
        note(4800, 40), note(6200, 30), rest(20), sweep(3800, 5600, 50), note(5000, 30), rest(15),
        note(6800, 35), sweep(6000, 4200, 45), rest(20), *trill(5200, 5800, 6, 22, 12),
        note(4400, 40), note(7000, 30), rest(20), sweep(4600, 6400, 60),
    ]),
    "Prunella modularis": ("Dunnock", _dunnock()),
    "Sturnus vulgaris": ("Common Starling", [
        sweep(2000, 4500, 250), rest(60), sweep(4500, 1800, 300), rest(120),
        *trill(2500, 2500, 8, 10, 25), rest(80),
        sweep(3200, 6000, 120), sweep(6000, 5000, 80), rest(60), *trill(1600, 2100, 6, 20, 10),
    ]),
    "Cuculus canorus": ("Common Cuckoo", repeat([note(1050, 220), rest(60), note(880, 320), rest(450)], 3)),
    "Pica pica": ("Common Magpie", repeat([*harsh(80), rest(70)], 8)),
    "Corvus corone": ("Carrion Crow", repeat([*harsh(300, 1400, 1000), rest(300)], 3)),
    "Phylloscopus collybita": ("Common Chiffchaff", repeat([
        sweep(5600, 4800, 70), rest(130), sweep(4600, 3800, 70), rest(130),
    ], 5)),
    "Aegithalos caudatus": ("Long-tailed Tit", repeat([note(7500, 40), rest(30), *trill(4500, 5200, 5, 15, 5), rest(150)], 3)),
    "Sylvia atricapilla": ("Eurasian Blackcap", [
        *trill(4000, 5200, 8, 25, 10), rest(60),
        sweep(2400, 3200, 140), sweep(3200, 2600, 120), sweep(2800, 3800, 120), note(3500, 180),
        sweep(3600, 2700, 160),
    ]),
    "Periparus ater": ("Coal Tit", repeat([note(6400, 80), sweep(5000, 4200, 90), rest(80)], 6)),
    "Chloris chloris": ("European Greenfinch", [*trill(3800, 4400, 10, 25, 12), rest(120), sweep(3500, 4100, 600)]),
    "Strix aluco": ("Tawny Owl", [
        sweep(1600, 2000, 120), sweep(2000, 1500, 150), rest(600),
        note(800, 500), rest(300), sweep(820, 760, 900),
    ]),
}

# More UK birds: woodland, farmland, summer visitors, water, coast and raptors.
CURATED.update({
    "Turdus viscivorus": ("Mistle Thrush", [
        sweep(2400, 3000, 110), sweep(3000, 2500, 90), rest(70), sweep(2800, 3400, 100), rest(60),
        sweep(3200, 2600, 120), rest(250), sweep(2500, 3100, 110), sweep(3100, 2600, 100), rest(70),
        note(3300, 80), sweep(3300, 2700, 110),
    ]),
    "Turdus iliacus": ("Redwing", [*run(3800, 2700, 4, 90, 10), rest(60), *trill(5500, 6200, 8, 20, 12)]),
    "Turdus pilaris": ("Fieldfare", repeat([*harsh(70, 3200, 2200), rest(60)], 5)),
    "Sitta europaea": ("Eurasian Nuthatch", repeat([sweep(2800, 3600, 60), rest(40)], 10)),
    "Certhia familiaris": ("Eurasian Treecreeper", [note(7600, 60), rest(30), *run(7400, 6000, 10, 30, 15), sweep(5500, 7000, 80)]),
    "Dendrocopos major": ("Great Spotted Woodpecker", [*drum(), rest(400), note(5000, 25), rest(300), *drum()]),
    "Picus viridis": ("Eurasian Green Woodpecker", [
        *[seg for i in range(12) for seg in (sweep(2600 - i * 50, 2800 - i * 50, 70), rest(45 - i * 2))],
    ]),
    "Garrulus glandarius": ("Eurasian Jay", [*harsh(300, 3400, 2000), rest(400), *harsh(250, 3400, 2000)]),
    "Corvus monedula": ("Eurasian Jackdaw", repeat([*harsh(80, 2600, 1900), rest(160)], 4)),
    "Corvus frugilegus": ("Rook", repeat([*harsh(350, 1500, 1100), rest(350)], 2)),
    "Motacilla alba": ("Pied Wagtail", repeat([sweep(5200, 6200, 50), rest(40), sweep(6000, 4500, 60), rest(250)], 4)),
    "Pyrrhula pyrrhula": ("Eurasian Bullfinch", repeat([sweep(1800, 1500, 180), rest(500)], 3)),
    "Spinus spinus": ("Eurasian Siskin", [*trill(4800, 5600, 10, 25, 10), rest(60), sweep(5200, 4200, 500)]),
    "Linaria cannabina": ("Common Linnet", [
        note(4200, 40), note(5100, 30), rest(20), sweep(3800, 4600, 50), *trill(4400, 5000, 6, 25, 12),
        note(3900, 50), sweep(5200, 4300, 60), rest(20), note(4700, 40), note(5400, 30),
    ]),
    # "A little bit of bread and no cheese".
    "Emberiza citrinella": ("Yellowhammer", [*repeat([note(5200, 40), rest(25)], 8), note(5600, 250), sweep(4400, 4200, 400)]),
    "Alauda arvensis": ("Eurasian Skylark", warble(7, 45, 3000, 6500)),
    "Hirundo rustica": ("Barn Swallow", [*warble(11, 16, 3500, 6500), *trill(2500, 2500, 12, 10, 8)]),
    "Delichon urbicum": ("Western House Martin", repeat([sweep(3200, 4200, 50), sweep(4200, 3600, 40), rest(80)], 5)),
    "Apus apus": ("Common Swift", [*harsh(400, 7800, 6000), rest(300), *harsh(350, 7800, 6200)]),
    "Regulus regulus": ("Goldcrest", [*repeat([note(8000, 60), note(7200, 60)], 5), sweep(6800, 8500, 120), sweep(8500, 7000, 80)]),
    "Phylloscopus trochilus": ("Willow Warbler", [*run(6000, 3400, 14, 55, 20), sweep(3600, 4200, 120)]),
    "Curruca communis": ("Common Whitethroat", [*warble(23, 14, 3500, 6000), *harsh(80, 4200, 3200)]),
    "Luscinia megarhynchos": ("Common Nightingale", [
        *repeat([note(2400, 150), rest(80)], 3), *trill(4500, 4500, 16, 15, 10),
        sweep(1800, 4500, 200), rest(100), *repeat([sweep(3000, 6000, 40), rest(30)], 6), note(2000, 300),
    ]),
    "Passer montanus": ("Eurasian Tree Sparrow", repeat([sweep(3800, 4700, 50), sweep(4700, 4000, 40), rest(150)], 5)),
    "Larus argentatus": ("Herring Gull", [sweep(1200, 1800, 300), rest(100), *repeat([sweep(1700, 1300, 120), rest(60)], 6)]),
    "Chroicocephalus ridibundus": ("Black-headed Gull", repeat([*harsh(250, 2600, 1800), rest(300)], 2)),
    "Anas platyrhynchos": ("Mallard", repeat([*harsh(150, 1300, 900), rest(150)], 4)),
    "Gallinula chloropus": ("Common Moorhen", repeat([*harsh(120, 1800, 1300), rest(80), note(1600, 60), rest(400)], 2)),
    "Fulica atra": ("Eurasian Coot", repeat([note(1700, 40), rest(300), sweep(2200, 1500, 90), rest(300)], 2)),
    "Phasianus colchicus": ("Common Pheasant", [
        *harsh(150, 1700, 1200), rest(60), *harsh(200, 1700, 1100), rest(100), *trill(900, 900, 15, 10, 10),
    ]),
    "Milvus milvus": ("Red Kite", [sweep(2600, 3200, 400), sweep(3200, 2400, 500), sweep(2600, 3000, 250), sweep(3000, 2300, 300)]),
    "Buteo buteo": ("Common Buzzard", repeat([sweep(3000, 2000, 700), rest(500)], 2)),
    "Falco tinnunculus": ("Common Kestrel", repeat([sweep(3800, 3500, 80), rest(50)], 10)),
    "Tyto alba": ("Barn Owl", harsh(1000, 4000, 2500, step_ms=20)),
    "Athene noctua": ("Little Owl", repeat([sweep(1800, 1400, 350), rest(600)], 2)),
    "Haematopus ostralegus": ("Eurasian Oystercatcher", repeat([sweep(3300, 3000, 70), rest(40)], 12)),
    "Numenius arquata": ("Eurasian Curlew", [
        sweep(1800, 2600, 400), rest(150), sweep(1900, 2700, 400), rest(150), *trill(2400, 2900, 14, 50, 15),
    ]),
    "Vanellus vanellus": ("Northern Lapwing", repeat([sweep(2200, 4000, 180), sweep(3600, 2800, 120), rest(400)], 3)),
    "Branta canadensis": ("Canada Goose", repeat([sweep(900, 1100, 80), *harsh(150, 1200, 900), rest(250)], 3)),
    "Columba livia": ("Rock Dove", [sweep(600, 750, 300), sweep(750, 650, 400), rest(200), sweep(600, 750, 300), sweep(750, 620, 500)]),
    "Columba oenas": ("Stock Dove", repeat([note(650, 350), sweep(700, 600, 200), rest(250)], 3)),
    "Psittacula krameri": ("Ring-necked Parakeet", repeat([*harsh(150, 4500, 3500), rest(120)], 5)),
    "Alcedo atthis": ("Common Kingfisher", repeat([sweep(6500, 7200, 70), rest(80)], 6)),
    "Ardea cinerea": ("Grey Heron", [*harsh(400, 1200, 800, step_ms=20), rest(500), *harsh(300, 1200, 800, step_ms=20)]),
    "Cettia cetti": ("Cetti's Warbler", [note(3000, 80), rest(60), *repeat([note(4500, 50), note(3600, 60), rest(20)], 5)]),
    "Acrocephalus scirpaceus": ("Common Reed Warbler", [
        *repeat([note(3200, 45), note(4200, 35), rest(20)], 3), *repeat([sweep(3800, 5000, 40), rest(20)], 3),
        *repeat([note(2800, 50), note(3600, 40), rest(20)], 3),
    ]),
    "Oriolus oriolus": ("Eurasian Golden Oriole", repeat([
        sweep(1800, 2400, 150), sweep(2400, 1900, 120), sweep(2000, 2800, 150), sweep(2800, 2200, 200), rest(300),
    ], 2)),
    "Upupa epops": ("Eurasian Hoopoe", [*repeat([note(700, 120), rest(110)], 3), rest(500), *repeat([note(700, 120), rest(110)], 3)]),
})

# Genera with a curated relative. Anything else in these genera borrows its song.
_BY_GENUS = {name.split()[0]: name for name in CURATED}
_BY_GENUS.update({"Poecile": "Periparus ater", "Lophophanes": "Periparus ater", "Corvus": "Corvus corone"})


def _seed(name: str) -> int:
    return zlib.crc32(name.strip().lower().encode())


def _transform(segments: list[Segment], pitch: float, tempo: float) -> list[Segment]:
    out = []
    for start, end, ms in segments:
        if start:
            start = int(min(MAX_HZ, max(MIN_HZ, start * pitch)))
            end = int(min(MAX_HZ, max(MIN_HZ, end * pitch)))
        out.append((start, end, max(5, int(ms * tempo))))
    return out


def _generated(name: str) -> list[Segment]:
    """A made-up but stable song, so an unfamiliar species always sounds the same."""
    rng = random.Random(_seed(name))
    base = rng.randint(2400, 5600)
    style = rng.choice(["trill", "whistle", "chirps", "warble", "sweeps"])

    if style == "trill":
        phrase = [note(base + 600, 70), rest(40), *trill(base, base + 500, rng.randint(6, 12), 25, 15)]
    elif style == "whistle":
        phrase = [sweep(base, base + 800, 180), rest(60), sweep(base + 600, base - 300, 220)]
    elif style == "chirps":
        phrase = repeat([sweep(base, base + 900, 50), sweep(base + 900, base + 300, 40), rest(110)], 3)
    elif style == "warble":
        phrase = []
        for _ in range(rng.randint(8, 14)):
            hz = base + rng.randint(-900, 1600)
            phrase += [sweep(hz, hz + rng.randint(-600, 600), rng.randint(30, 70)), rest(rng.randint(5, 25))]
    else:  # sweeps
        phrase = [sweep(base + 1500, base - 500, 120), rest(60), sweep(base - 300, base + 1200, 120), rest(60)]

    song = phrase + [rest(250)] + phrase
    if rng.random() < 0.5:
        song += [rest(250)] + phrase
    return song


def song_for(scientific_name: str) -> tuple[list[Segment], str]:
    """The song to play for a species, and how it was chosen (for logging)."""
    name = scientific_name.strip()
    genus = name.split()[0] if name else ""
    if name in CURATED:
        song, how = CURATED[name][1], "curated"
    elif genus in _BY_GENUS:
        relative = _BY_GENUS[genus]
        rng = random.Random(_seed(name))
        song = _transform(CURATED[relative][1], rng.uniform(0.85, 1.2), rng.uniform(0.85, 1.15))
        how = f"like {CURATED[relative][0]}"
    else:
        song, how = _generated(name or "unknown"), "generated"
    return song[:MAX_SEGMENTS], how


def encode_chunks(song: list[Segment], max_bytes: int = 180) -> list[str]:
    """Split a song into "start,end,ms;..." strings that each fit in one RPC message."""
    chunks, current = [], ""
    for start, end, ms in song:
        part = f"{start},{end},{ms};"
        if current and len(current) + len(part) > max_bytes:
            chunks.append(current)
            current = ""
        current += part
    if current:
        chunks.append(current)
    return chunks

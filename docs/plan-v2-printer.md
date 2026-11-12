# BirdBox v2 plan: thermal printer and buttons

v1.0 is tagged and released. v2 adds an optional thermal printer and one or two
panel-mount buttons on the base of the box. Everything here is optional: with no
printer or buttons connected, BirdBox behaves exactly as v1.0, and every receipt
can still be previewed on the debug page.

## Hardware

| Part | Notes |
|---|---|
| [RS PRO High Speed Thermal Line Panel Printer](https://uk.rs-online.com/web/p/panel-printers/1785731) (RS 178-5731) | 58 mm paper, 384 dots per line (8 dots/mm), USB 2.0 or RS-232. Powered from **3.5–8.5 V, up to 3 A**, so it needs its own supply: it can't run from the UNO Q or the hub's USB ports. |
| 1–2 momentary panel-mount push buttons | Normally open. One side to a digital pin, the other to GND. The sketch uses the internal pull-ups. |

- **Printer data:** USB into a USB-A port on the Arduino USB-C Hub. On Linux it appears
  as `/dev/usb/lp0` (USB printer class) or `/dev/ttyACM0` (USB serial). The app
  container already sees the board's `/dev`, so no extra configuration is needed.
  The RS-232 port uses ±12 V levels, so it can't connect to the UNO Q's pins
  directly; a USB-to-RS-232 adapter (`/dev/ttyUSB0`) also works.
- **Buttons:** D2 (bird card) and D3 (daily summary), each to GND. An unconnected
  pin stays high and never triggers.

## Receipts

All receipts are rendered on the board as 384-pixel-wide black-and-white images, styled
like an old encyclopaedia (serif type, inverted headwords, italic scientific names), and
sent as ESC/POS raster graphics, so the debug page preview is exactly what prints.
Paper use is measured in millimetres from the image height (8 px = 1 mm).

### 1. Bird card (button 1, or the `card` command)

For the last species detected:

- **Always:** common and scientific name, date and time, confidence, and how many
  times it's been heard today and in total.
- **Optional, set from the dashboard:**
  - **Picture:** a silhouette from [PhyloPic](https://www.phylopic.org/), placed
    beside the text so it costs no extra paper. Falls back to the genus when the
    species has none. Each image has its own licence (many are CC BY), so a
    one-line credit is printed when there's a picture.
  - **Song:** the buzzer song for that species, drawn as a pitch contour on a
    five-line staff. It's the same data the buzzer plays, so it exists for every
    species.
  - **Description:** a two-sentence encyclopaedia entry condensed from the species'
    Wikipedia introduction by the local LLM and checked against it, or the article's
    first sentence. Credited to Wikipedia.

Pictures and descriptions are fetched once per species, in the background when the
bird is first detected, and cached in `data/birdinfo/`. A button press then prints
straight away.

### 2. Detection scroll (`print_each_detection`, off by default)

One line per detection, about 3 mm of paper each, with no feed between lines, so the
paper builds up into a scroll of the day's birds. For example:
`07:14 European Robin 92%`.

### 3. Daily summary (button 2, the `summary` command, or at `summary_hour`)

- Date, total detections, distinct species and the busiest hour.
- The top five species, as horizontal bars.
- A 24-hour activity chart covering the last 24 hours.

It prints automatically once a day at `summary_hour` (0–23, or −1 for off).

## Data

Every detection is logged to SQLite at `data/birdbox.db`: time, species and
confidence. That gives the "seen N times" counts, the summary and the 24-hour chart,
and it survives restarts. v1.0 kept counts only in memory.

## Settings

New settings work like the existing ones: editable on the debug page, saved on the
board, and synced with Arduino Cloud where the Thing has the variable. The Pro
dashboard gets a Printer section.

| Setting | Type | Default | |
|---|---|---|---|
| `printer_enabled` | Boolean | `true` | Master switch. With no printer found, prints are skipped and logged. |
| `print_each_detection` | Boolean | `false` | Detection scroll. |
| `card_picture` | Boolean | `true` | Silhouette on the bird card. |
| `card_song` | Boolean | `true` | Song contour on the bird card. |
| `card_description` | Boolean | `true` | Encyclopaedia entry on the bird card. |
| `card_llm` | Boolean | `true` | Write the entry with the local LLM; otherwise the first sentence of Wikipedia. |
| `summary_hour` | Integer | `-1` | Hour for the daily summary, −1 for off. |
| `printer_device` | board only | `auto` | `auto`, or a device path such as `/dev/usb/lp0`. |

The existing `servo_command` Messenger also accepts `card`, `summary` and `line`.

## Ideas tested

- **Local LLM summary.** First attempt: Qwen 3.5 0.8B (already installed on the
  board) given the short Wikipedia summary and asked for one sentence. It took 25–37 s
  and wasn't reliable: two of three were accurate but bland, and for the robin it wrote
  "European robin migrates north to winter", which misreads the source.

  Second attempt, borrowing from *This Fish Does Not Exist* (lazy brick import, a
  timeout thread, a style preamble, cleaning and a fallback): give the model the
  article's whole introduction, ask it to **condense** into a two-sentence entry for
  "an old encyclopaedia of British birds" using only facts stated, then **check the
  reply against the source**. Content words must appear in the source (by five-letter
  stem), and below 90% the reply is rejected. Six test species all came back accurate
  and fully grounded, at 30–100 s each.

  That's too slow to wait for, so each species keeps one cached entry, written in the
  background when it's first heard. Printing uses the cached entry and queues a new
  one with a different focus (plumage, range, food, behaviour), so cards vary without
  waiting. The first sentence of Wikipedia is the fallback. The model takes about
  480 MB, which fits beside BirdNET on the 2 GB board.
- **"Sheet music" for the song.** The songs are pitch sweeps, not notes, so real
  notation would invent rhythm and pitches. A pitch contour drawn on a staff is honest
  about what the buzzer plays and is only about 5 mm tall.
- **PhyloPic.** Has silhouettes rather than line drawings, which print cleanly on a
  thermal printer. Coverage is good for UK garden birds at species or genus level.

## Not doing (yet)

- QR codes linking to recordings or a species page
- Cutting the paper (this printer has no cutter); you tear it at the bar
- Printing from Arduino Cloud chart data; the summary uses the local SQLite log

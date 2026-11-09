# Project Hub draft — BirdBox

Copy each section into the matching field of the Project Hub editor. Replace each
`[PHOTO: …]` or `[VIDEO: …]` placeholder with your own media.

---

## Title

**BirdBox: A Bird Box That Sings Back, with On-Device Bird ID on the UNO Q**

## Short description

A bird box that recognises 6,500 bird species on-device with BirdNET, logs them to
Arduino Cloud, then slides out a model bird that sings the species' song.

## Tags

`uno-q` · `app-lab` · `birdnet` · `machine-learning` · `audio` · `arduino-cloud` ·
`servo` · `modulino` · `wildlife` · `edge-ai`

## Difficulty / time

Intermediate · about 3 hours, plus building the bird box

## Components and supplies

| Qty | Item |
|---|---|
| 1 | Arduino UNO Q (2 GB or 4 GB) |
| 1 | USB microphone, or a TRRS (4-pole) headset mic with the UNO Media Carrier |
| 1 | FS90R continuous-rotation micro servo |
| 1 | Arduino Modulino Buzzer + Qwiic cable |
| 1 | 5 V / 3 A USB-C power supply |
| 1 | USB-C hub (if you use a USB microphone) |
| 1 | Bird box with a small linear rail and a model bird (3D printed or carved) |
| 3 | Jumper wires (servo to D9, 5V and GND) |

## Apps and platforms

- Arduino App Lab
- Arduino Cloud
- BirdNET-Analyzer (model, CC BY-NC-SA 4.0)

---

## Story

[PHOTO: the finished bird box, model bird out of the hole]

### The idea

Bird-ID apps on a phone are great, but you have to be holding the phone at the
moment a bird sings. I wanted a box that sits in the garden and listens all day,
tells me who visited, and does something delightful when a bird calls: a little
wooden bird pops out of the hole and sings back.

The **Arduino UNO Q** suits this well. Its Linux side runs Cornell's **BirdNET**
model in real time, with no cloud inference and no audio leaving the garden. Its
real-time microcontroller drives the servo and buzzer. Arduino App Lab ties the two
together, and Arduino Cloud gives me a dashboard on my phone.

[VIDEO: a bird calls, the model bird slides out, sings, and retracts]

### How it works

```
microphone ─► BirdNET brick (Linux) ─► detection ─┬─► Arduino Cloud dashboard
                                                   └─► Router Bridge ─► MCU ─┬─► servo pushes bird out
                                                                             └─► buzzer sings the species
```

1. **Listen.** A custom App Lab *brick* records 48 kHz audio from the microphone in
   3-second windows.
2. **Identify.** Each window goes through BirdNET GLOBAL 6K V2.4 (6,522 classes)
   with LiteRT. It takes about 225 ms on the UNO Q, about 13× faster than real time.
   An optional range filter keeps only species plausible at your location and time
   of year.
3. **Report.** Detections above a confidence threshold go to Arduino Cloud: species,
   confidence, time, and daily counts.
4. **Perform.** The Python app tells the microcontroller over the Router Bridge to
   push the bird out. Once it reaches the end of the rail, the Modulino Buzzer plays
   a song for that species. The bird retracts when the song ends.

### Building the bird box

[PHOTO: inside the box — rail, servo, end stops]

The model bird rides on a short rail behind the entrance hole, pushed by an FS90R
continuous-rotation servo. A continuous servo has no position control, so I added
a **hard stop at each end of the rail** (about 140° of servo rotation apart). The
sketch simply drives towards a stop for a fixed time plus a small overrun, then
releases the servo. No encoder or homing switch is needed, and the rail can't drift
out of calibration.

Leave room behind the hole for the bird to retract fully, and make sure the
microphone has a clear path to the outside. A small grille or mesh-covered opening
works well, and keeps the mic out of the rain.

### Wiring

[PHOTO or SCHEMATIC: wiring diagram]

| From | To |
|---|---|
| Servo signal (orange) | D9 |
| Servo V+ (red) | 5V |
| Servo GND (brown) | GND |
| Modulino Buzzer | Qwiic connector |
| Microphone | USB-C hub, or the Media Carrier's TRRS jack |

> **Mic tip:** the Media Carrier's 3.5 mm jack is a combined headset socket. It
> needs a 4-pole TRRS (CTIA) plug, like phone headsets. A plain lavalier plug with
> one or two bands will only record noise. A cheap USB microphone avoids the
> question entirely.

### Software

The whole project is one Arduino App. Clone it onto the board:

```bash
cd ~/ArduinoApps
git clone https://github.com/jimbruges/birdbox.git birdbox
```

It shows up in App Lab under **My Apps**. The app has four parts:

- **`bricks/birdnet/`** — a custom brick wrapping BirdNET. It handles the
  microphone, windowing, inference and the range filter. It downloads the model
  (~40 MB) on first run.
- **`python/main.py`** — connects detections to Arduino Cloud, the servo and the
  buzzer, and serves a debug web page.
- **`python/songs.py`** — the birdsong library.
- **`sketch/sketch.ino`** — the microcontroller side: non-blocking servo moves and
  song playback, controlled over the Router Bridge.

### Making a piezo sing like a bird

A buzzer plays one pitch at a time, so each song captures a species' rhythm, pitch
range and shape as a list of pitch sweeps. The sketch plays each sweep smoothly in
10 ms steps.

- **70 UK species** have a hand-written song: the blackbird's fluting phrases, the
  great tit's "teacher-teacher", the chaffinch's descending run and flourish, the
  woodpecker's drum roll, the tawny owl's hoot and more.
- A species **in the same genus** as one of those borrows its relative's song,
  slightly re-pitched and re-timed.
- **Anything else** gets a song generated from its scientific name, so every
  species always sounds the same and recognisably different from the others.

There's one catch: a box that sings bird calls next to a microphone that listens
for bird calls will happily detect itself. The app tells the BirdNET brick to
ignore any audio window that overlaps its own song, so the box never answers itself.

### Arduino Cloud dashboard

[SCREENSHOT: the dashboard]

Everything is tunable from the dashboard: confidence threshold, cooldown per
species, range filter location, servo speed and timing, and birdsong on/off. A
Messenger widget sends test commands like `test`, `out` and `in` for calibrating
the rail.

The repository's `docs/arduino-cloud.md` lists all 23 variables with their types,
plus a suggested dashboard layout. On the Free plan (5 variables per Thing), create
just `listening`, `last_species`, `last_confidence`, `birdsong_enabled` and
`debug_ui`, then set everything else from the debug web UI. Settings are saved on
the board, so a Cloud variable is only needed for what you want on your phone.

### Debug web UI

[SCREENSHOT: debug UI]

Turning on `debug_ui` from the Cloud opens a page on the board at port 7000 with:

- a live microphone level meter
- a 3-second test recording you can play back in the browser
- BirdNET's top five guesses for every window, even below threshold
- every setting, saved on the board, so the box can be fully set up without
  Cloud variables
- servo test buttons
- a song tester for any species

It made diagnosing a dead microphone much faster than reading logs.

### Calibration

1. Send `out` and `in` from the dashboard or the debug page.
2. If the bird stops short of an end, increase `travel_ms`. If the servo grinds
   against the stop, decrease it.
3. Send `test` to see the whole performance, and adjust `hold_ms` to taste.

The defaults (travel 320 ms at 40% speed, 30 ms overrun, 500 ms hold) suit a
140° rail.

### Tips

- **Turn on the range filter** with your coordinates. It cuts 6,522 classes down to
  the ~150 plausible species, and removes the odd "Andean hummingbird" from a noisy
  recording. Latitude comes first: Cambridge, UK is `52.2053, 0.1218`.
- **Raise `cooldown_seconds`** during the dawn chorus so one chatty robin doesn't
  flood your dashboard.
- **Power:** a servo stalling against an end stop draws a few hundred mA from the
  5 V rail. Use a proper 5 V / 3 A supply, or the board may reset.

### What's next

- A solar panel and battery for a fully off-grid box
- Logging detections to a Cloud chart and comparing seasons
- More hand-written songs. PRs welcome!

### Credits and licence

- **BirdNET** by the K. Lisa Yang Center for Conservation Bioacoustics at the
  Cornell Lab of Ornithology and Chemnitz University of Technology. Model weights
  are CC BY-NC-SA 4.0 (non-commercial). Kahl, S. et al., *BirdNET: A deep learning
  solution for avian diversity monitoring*, Ecological Informatics 61 (2021).
- This project's code: Mozilla Public License 2.0 (MPL-2.0).

---

## Code

Link the repository: <https://github.com/jimbruges/birdbox>

## Schematics

Upload the wiring diagram (servo on D9 / 5V / GND, Modulino Buzzer on Qwiic).

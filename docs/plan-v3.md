# BirdBox v3 plan: setup wizard, CSN-A2 printer and birds through Arduino Cloud

v3 goes with the printed enclosure (`hardware/README.md`). It adds a setup wizard,
support for the CSN-A2 printer the enclosure is built around, and lets a BirdBox
play, print and log another unit's birds through Arduino Cloud. Everything is
optional: with nothing changed, BirdBox behaves as v2.

## 1. Setup wizard

`http://<board-ip>:7000/setup.html`, linked from the top of the debug page. It runs
on the debug UI, which is now **on by default** (`debug_ui` still turns it off from
the dashboard). Ten steps, each with renders of the printed enclosure or build
photos, and each testing the real hardware:

| Step | What it checks or sets |
|---|---|
| Welcome | Parts list |
| Arduino Cloud | The board's connection and Thing (from the board's cloud connector); saves an API key; creates the Thing's variables and the Free or Free + Pro dashboards |
| Board and power | The sketch is answering; a wiring diagram drawn from the current pin settings |
| Listening | Microphone (live level meter), another BirdBox, or both; picks the other unit from your Things |
| Buzzer | Modulino found; plays a test song |
| Servo and bird | Signal pin; direction ("did the bird come out?", flips it if not); speed, travel, overrun and hold, with out/in buttons |
| Buttons | Press and hold a button and the wizard finds its pin; what each of the four does |
| Printer | Printer preset; wiring and baud; plain-text test; finds the image command; feed (early, so the later tests clear the slot); proportions from a measured 30 mm square; darkness; which way up; a real card |
| Location | Latitude, longitude, range filter |
| Finished | A summary of the whole setup and the wiring diagram |

`setup.html#printer` (or any step's id) opens a step directly. While the wizard looks
for a button's pin, every button's action is paused, so pressing one doesn't print.

New sketch functions: `servo_set_pin`, `servo_set_direction` (both were constants)
and `pins_scan`, which pulls up the free header pins and reports which read low.

## 2. The CSN-A2 printer

The enclosure holds a CSN-A2 panel printer. It's wired like the RS PRO, to the MCU's
serial pins, and the wizard's **CSN-A2** preset sets what it needs:

| Setting | CSN-A2 | RS PRO 178-5731 |
|---|---|---|
| Image command | **GS v 0** | ESC K |
| Serial speed | 9600 (check its self-test page) | 9600 |
| Feed after card and summary | **51 mm** in the printed base | 22 mm |
| Print darkness | **heat time**, chosen from a test strip | not supported |

**Power and wiring in the printed enclosure** (tested): the CSN-A2's power (VH)
and GND go to the board's **5V** and **GND**, so the servo's red wire moves to
**3V3** (it runs a little slower there, which the travel time allows for). The
buttons' other legs are joined and go to the remaining **GND** pin. The printer
draws a lot of current while printing, so power the hub with a charger of at least
15 W; if prints fade or the board restarts while printing, give the printer its own
5–9 V supply with its GND still joined to the board's. The wizard's wiring diagram
shows this layout when the CSN-A2 preset is chosen.

Found on the way:

- **Wiring:** the board's TX (D1, or SCL) goes to the printer's **RX**. The first
  attempt was on the wrong pin and printed nothing; the self-test page (hold FEED
  while powering on) printed fine and showed 9600 baud.
- **Image command:** this CSN-A2 takes **GS v 0**. DC2 \* (Adafruit's command for
  the family) printed characters. DC2 \* blocks are now 5 rows, like Adafruit's
  driver, for printers that do use it.
- **Proportions:** the CSN-A2 prints GS v 0 images slightly squashed top to bottom
  compared with the RS PRO. `printer_stretch` scales every receipt image vertically
  (whole dot rows, so it stays crisp). The wizard prints a 30 mm square; enter its
  measured width and height and it sets the scale to width ÷ height.
- **Darkness:** `printer_heat` sends `ESC 7` (heating dots 11, heat time, interval
  40) before every job; 0 leaves the printer's own setting. The darkness test prints
  black, grey and fine lines at heat times 60–220 to pick from.
- **USB:** the CSN-A2's mini USB port is a USB printer-class device, but the UNO Q's
  kernel has no `usblp` driver, so no `/dev/usb/lp0` appears. The USB option stays
  for printers that show up as `/dev/ttyACM*`/`/dev/ttyUSB*` (now at the **Serial
  speed** setting, no longer always 9600) or on boards with the driver.

## 3. Birds from another BirdBox, through Arduino Cloud

**Listening** has three modes:

| Mode | Microphone | Another BirdBox's birds |
|---|---|---|
| This unit's microphone | Yes | – |
| Another BirdBox | Not needed | Played, printed and logged as this unit's own |
| Both | Yes | Logged separately, with their own cards and summary |

The sending unit is unchanged: it already publishes `last_species`,
`last_scientific_name`, `last_confidence` and `last_detection_at` to its Thing.
`remote.py` reads them from the Arduino Cloud API every 5 seconds; a new
`last_detection_at` is a new bird. On start-up the sender's last bird is the
baseline, so a restart doesn't replay it. A Thing can't read another Thing's
variables on the device, hence the API and its key.

**Both mode** keeps the two apart. The detection log has a `source` column (`local`
or `cloud`; older logs become `local`), and every count, card and summary is for one
source. The other unit's birds aren't counted in this unit's Cloud variables. They
sing and move the bird only with `cloud_birds_act` on, and their receipts say
"Heard by" and the other unit's Thing name.

**Four buttons.** The enclosure has four holes. Buttons 1 and 2 default to this
unit's card and summary on D2 and D3. Buttons 3 and 4 are optional, unused by
default, and default to the other unit's card and summary. New actions and
`servo_command` words: `card_cloud`, `summary_cloud`, `line_cloud`.

### Dashboards for more than one BirdBox

The setup script used to find "BirdBox Free" and "BirdBox Pro" by name anywhere in
the Cloud space and replace their widgets, so setting up a second unit rewired the
first unit's dashboards to the second Thing. Dashboards are now named after their
Thing ("BirdBox Pro - Birdbox 2"), and the script (and the wizard) only updates a
dashboard whose widgets all show this Thing's variables. Anything else is left alone
and a new dashboard is created. An old unsuffixed dashboard that's entirely this
Thing's is taken over and renamed.

### The API key

The app runs in a container that can't see `~/.config`, so the wizard saves the key
in the app's `data/cloud-credentials.json` (mode 600, gitignored). The tools look
for `ARDUINO_CLOUD_CREDENTIALS`, then `~/.config/arduino-cloud/credentials.json`,
then that file. The wizard checks the key with Arduino Cloud before saving it. It's
sent from the browser to the board over plain HTTP, so enter it on your own network.

### Limits

- Up to about 5 seconds' delay; two birds within one poll arrive as one (the last).
- The sender needs the full variable set (Maker plan), not the Free plan's five.

## Settings that work together

Any part can be missing, and the settings are checked against each other:

- **Pins:** each header pin has one job. Setting a button, the servo or the
  printer's busy line to a pin that's already in use is refused with the name of
  what has it (the sketch used to drop one of them silently). The printer's serial
  pins count too.
- **No microphone:** nothing is heard, and the health check says so. In Both mode
  only the other unit's birds arrive.
- **No printer:** every print is skipped with a log line, including the demo
  scroll; the printer's status isn't polled (each poll paused the sketch for up to
  150 ms).
- **Buttons unwired:** they read high through the pull-ups and never fire.
- **The other unit's receipts** (`*_cloud`): in Both mode they're the other unit's
  birds; in receiver mode they're this unit's (it logs the other unit's birds as its
  own); with only the microphone they're refused rather than printing an empty card.
- **Daily summary** in Both mode prints this unit's summary and then the other
  unit's.

`problems()` lists settings that are valid alone but don't fit together (a button
that prints with printing off, a cloud button with only the microphone, Both or
receiver mode with no unit chosen or an unreadable one, the range filter with no
location, a pin clash already saved, no microphone, no buzzer). The debug page shows
them in its setup card, each linking to the wizard step that fixes it, and the
wizard shows each on its own step and all of them on Finished.

The debug page now opens with a setup card: a large **Open the setup wizard**
button while setup hasn't been finished, then "Setup complete" (or what to check).
It also no longer scrolls sideways on a phone.

While Listening follows another BirdBox ("Another BirdBox" or "Both"), the debug
page also shows a card for that Thing, by its name: whether it's being followed (or
the error), its last bird, today's count and species, its recent birds, and its own
preview and **Print this** for its bird card, daily summary and scroll line. In
receiver mode those are this unit's log (it logs the other unit's birds as its own),
so birds from before the switch to receiver mode appear there too.

## New settings (debug page and wizard; saved on the board, not Cloud variables)

| Setting | Default | |
|---|---|---|
| `listen_mode` | `mic` | `mic`, `cloud` or `both` |
| `source_thing_id` | empty | The other BirdBox's Thing ID |
| `cloud_birds_act` | on | In Both mode, the other unit's birds also sing and move the bird |
| `servo_pin` | 9 | D2, D3, D5–D13 (D4 has no PWM) |
| `servo_reverse` | off | The bird goes in when it should come out |
| `printer_heat` | 0 | Print darkness for CSN-A2 family printers; 0 = the printer's own |
| `printer_stretch` | 100 | Vertical scale in % (70–160): repeats dot rows for printers whose paper step makes pictures look squashed |
| `button3_pin`, `button4_pin` | −1 | Optional buttons |

Any button can use a free digital pin (D2–D13) or an analog pin (A0–A5, which the core numbers 14–19), whichever routes better. The wizard's pin scan reads both kinds.
| `button3_action`, `button4_action` | `card_cloud`, `summary_cloud` | |

## Verified on the board

The app builds and runs; the sketch connects with the new functions; the wizard
renders every step against live data (headless Chromium on the board); the
cloud receipts render; the log migration was tested on a v2-format database.
Not yet tried with the hardware: a button found by the pin scan, the servo
direction flip, the darkness strip and feed test on paper, creating variables
with an API key, and following a second unit.

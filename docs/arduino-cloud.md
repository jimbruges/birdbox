# Arduino Cloud setup

This guide connects the UNO Q to Arduino Cloud, creates the Thing variables the app
syncs, and builds a dashboard to watch detections and tune the bird box.

The app doesn't need Cloud credentials in its code or configuration. The board's
**arduino-cloud-connector** service owns the connection, and the app's
`arduino:arduino_cloud` brick talks to it locally.

## Which plan you need

The app registers **23 variables**. On the [Arduino Cloud plans](https://cloud.arduino.cc/plans/)
page, the **Free** plan allows **5 variables per Thing**; **Maker** and above are
unlimited.

Every variable is optional. The [debug web UI](../README.md#debug-web-ui) can change
every setting, and saves it on the board (`data/settings.json`), so a variable
only needs to be on the Thing if you want it on your dashboard. On the Free plan,
create these five:

| Variable | Why |
|---|---|
| `listening` | Is the box alive? |
| `last_species` | What it last heard |
| `last_confidence` | How sure it was |
| `birdsong_enabled` | Silence the buzzer, e.g. at night |
| `debug_ui` | Lets you turn on the debug web UI, which covers calibration and tuning |

Then switch on `debug_ui`, open `http://<board-ip>:7000`, and set the location,
thresholds and servo calibration in the page's **Settings** card. They're saved on
the board and survive restarts. Settings that are also on the Thing are sent to
the Cloud too.

## 1. Connect the board

1. Open **Arduino App Lab** connected to your UNO Q.
2. Go to **Settings → Arduino Cloud → Connect device**.
3. Sign in, choose the Cloud space, and wait for the status to show **Connected**.

Starting an app that uses the Cloud brick on an unconnected board opens a
**Provisioning required** dialog leading to the same flow.

## 2. Open the board's Thing

Go to [app.arduino.cc/things](https://app.arduino.cc/things) and open the Thing your
UNO Q is associated with. If there isn't one, create a Thing and associate the board
with it under **Associated Device**.

## 3. Add the variables

For each row, click **ADD** in the Thing's **Cloud Variables** panel and fill in:

- **Name:** exactly as below — lower case, with underscores. After typing it, check
  that the **Declaration** line underneath shows the same name. The app matches on
  this name, and a variable whose name differs never syncs. Nothing reports the
  mismatch.
- **Type:** from the basic types list.
- **Permission:** as listed.
- **Update policy:** **On change**.

You don't need to set initial values. The first time the app connects, any variable
with no Cloud value yet gets the board's current value (its saved setting, or the
default).

### Settings — Read & Write

| Name | Type | Default | Range |
|---|---|---|---|
| `min_confidence` | Floating Point Number | `0.5` | 0.01 – 0.99 |
| `sensitivity` | Floating Point Number | `1.0` | 0.5 – 1.5 |
| `cooldown_seconds` | Integer Number | `30` | 0 and up |
| `range_filter` | Boolean | `false` | |
| `latitude` | Floating Point Number | `0.0` | −90 – 90, north positive |
| `longitude` | Floating Point Number | `0.0` | −180 – 180, east positive |
| `servo_enabled` | Boolean | `true` | |
| `birdsong_enabled` | Boolean | `true` | |
| `hold_for_song` | Boolean | `true` | |
| `travel_ms` | Integer Number | `320` | 50 – 3000 |
| `servo_speed` | Integer Number | `40` | 10 – 100 |
| `home_overrun` | Integer Number | `30` | 0 – 1000 |
| `hold_ms` | Integer Number | `500` | 0 – 30000 |
| `servo_command` | Character String | `""` | `in`, `out`, `test`, `stop`, `song` |
| `debug_ui` | Boolean | `false` | |

Out-of-range values are clamped by the app.

### Results — Read Only

| Name | Type |
|---|---|
| `last_species` | Character String |
| `last_scientific_name` | Character String |
| `last_confidence` | Floating Point Number |
| `last_detection_at` | Character String |
| `detections_today` | Integer Number |
| `species_today` | Integer Number |
| `listening` | Boolean |
| `servo_state` | Character String |

Making results **Read Only** stops a dashboard widget overwriting them.

### Check your location

`latitude` is the **north–south** number and comes first. Cambridge, UK is latitude
`52.2053`, longitude `0.1218`. If you enter them the wrong way round, the range
filter ends up in the Indian Ocean and drops almost every species you'll actually
hear. `0.0, 0.0` means "not set" and leaves the filter off.

### Upgrading from an earlier version

If your Thing has `sweep_enabled`, `out_position` or `servo_position`, delete them.
The current app doesn't use them.

## 4. Build the dashboard

Create a dashboard at [app.arduino.cc/dashboards](https://app.arduino.cc/dashboards),
click **ADD → Things**, pick your Thing, then rearrange. Or add widgets one at a time
with **ADD** and link each to its variable. A layout that works well:

### Row 1 — What's singing

| Widget | Variable | Settings |
|---|---|---|
| **Status** | `listening` | Label "Listening" |
| **Value** | `last_species` | Large text |
| **Value** | `last_scientific_name` | |
| **Gauge** | `last_confidence` | Min `0`, max `1` |
| **Value** | `last_detection_at` | |

### Row 2 — Today

| Widget | Variable | Settings |
|---|---|---|
| **Value** | `detections_today` | |
| **Value** | `species_today` | |
| **Chart** | `detections_today` | Shows the day's activity. History length depends on your plan's data retention. |
| **Chart** | `last_confidence` | Optional, shows how confident each detection was |

### Row 3 — Bird box

| Widget | Variable | Settings |
|---|---|---|
| **Switch** | `servo_enabled` | Label "Bird moves" |
| **Switch** | `birdsong_enabled` | Label "Birdsong" |
| **Switch** | `hold_for_song` | Label "Stay out for song" |
| **Value** | `servo_state` | |
| **Messenger** | `servo_command` | Type `test`, `out`, `in`, `stop` or `song` |

### Row 4 — Detection tuning

| Widget | Variable | Settings |
|---|---|---|
| **Value** (editable) | `min_confidence` | Type a number, e.g. `0.6` |
| **Value** (editable) | `sensitivity` | |
| **Slider** | `cooldown_seconds` | Min `0`, max `600` |
| **Switch** | `range_filter` | |
| **Value** (editable) | `latitude` | |
| **Value** (editable) | `longitude` | |

### Row 5 — Calibration and debug

| Widget | Variable | Settings |
|---|---|---|
| **Slider** | `servo_speed` | Min `10`, max `100` |
| **Slider** | `travel_ms` | Min `50`, max `1500` |
| **Stepper** | `home_overrun` | Min `0`, max `200`, step `10` |
| **Slider** | `hold_ms` | Min `0`, max `10000` |
| **Switch** | `debug_ui` | Label "Debug web UI" |

Widgets bound to Read & Write variables are editable. Widgets bound to Read Only
variables only display.

## 5. Check it

Start the app and watch the log:

```bash
arduino-app-cli app logs ~/ArduinoApps/birdbox --follow
```

Flip a switch on the dashboard. Each setting logs a line when it arrives, e.g.:

```
BirdBox:  Birdsong disabled
BirdBox:  Servo speed set to 40%
```

Then type `test` in the Messenger widget. The bird should come out, sing, and go
back in, and `servo_state` should go `moving` → `out` → `moving` → `in`.

If a switch does nothing:

- **Check the variable name.** Compare the Declaration with the tables above.
- **Check the permission.** A Read Only setting can't be written from the dashboard.
- **Check the board is online.** The device status on the Thing page should be
  **Online**, and `listening` should be `true`.
- **Re-send the same value?** Cloud only sends changes. `servo_command` clears
  itself after each command so you can repeat one, but a Switch already on can't be
  turned on again.

## How sync works

- **Settings** are saved on the board whenever they change, from either the Cloud
  or the debug UI. For a variable the Thing defines, the brick's default
  `CLOUD_WINS` policy applies on start-up: the Cloud's stored value replaces the
  saved one. A variable with no Cloud value yet is seeded from the saved value.
- **Results** use `DEVICE_WINS`. On reconnect the board's live values replace
  whatever the Cloud last held.
- A live change from the dashboard is always applied immediately, whatever the
  policy.

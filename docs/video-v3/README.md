# BirdBox v3: CAD renders for the video

Renders of the printed enclosure from SolidCraft, 1920 × 1080. The electronics are
simple stand-ins (boxes in the right place and size), not detailed models.

Every clip comes twice:

- `*-alpha.mov`: ProRes 4444 with a transparent background, for overlays in
  Premiere, Resolve or Final Cut. Large, so they're kept out of git.
- `*.mp4`: H.264 on a light grey background, for previews and the web.

All clips are 30 fps.

## Clips (`clips/`)

| Clip | Length | What it shows |
|---|---|---|
| `turntable` | 6.0 s | The assembled box turning a full 360°. Loops. |
| `turntable-inside` | 6.0 s | The same with the left side and roof hidden, so the electronics show. Loops. |
| `explode` | 4.0 s | The assembled box comes apart into its panels, then holds. |
| `assemble` | 4.0 s | The reverse: the panels come together, then hold. |
| `build` | 10.6 s | The box built up in assembly order, one group at a time, then a 1 s hold. |
| `build-01-base` | 1.2 s | Base tray, buttons and power breakout rise into place |
| `build-02-printer` | 1.2 s | Printer and printer plate drop into the base |
| `build-03-cover` | 1.2 s | Base cover comes up from below. It's hidden from this camera, so use the `underside` still with it. |
| `build-04-front` | 1.2 s | Front panel, servo frame and servo slide in from the front |
| `build-05-right-side` | 1.2 s | Right side with the Modulino Buzzer slides in |
| `build-06-left-side` | 1.2 s | Left side slides in |
| `build-07-back` | 1.2 s | Back plate with the UNO Q and mic cable spool slides in |
| `build-08-roof` | 1.2 s | Roof with the hub drops on |

The eight `build-0*` clips are the eight steps of `build`, so they cut together
seamlessly. Each one starts with the previous step finished.

## Stills (`stills/`)

`name.png` has a transparent background; `name-bg.png` is the same image on light grey.

| Still | What it shows |
|---|---|
| `hero-front-right` | Assembled, from the front right (Modulino grille side) |
| `hero-front-left` | Assembled, from the front left |
| `back` | From the back: keyhole and cable notches |
| `underside` | From below: buttons, paper slot and base cover |
| `inside` | Left side and roof hidden: where everything goes |
| `exploded` | All the panels apart, with the parts that ride on each |
| `base-tray` | Base with buttons, printer, plate, cover and breakout |
| `front-panel-inside` | Front panel from behind: the built-in servo frame, rack and servo |
| `right-side-inside` | Right side from inside, with the Modulino Buzzer |
| `back-plate-inside` | Back plate from inside: UNO Q and the mic cable spool |
| `roof-underside` | Roof from below, with the hub on its tie stubs |

## Colours

| Part | Colour |
|---|---|
| Base | `#e9cf9b` |
| Front | `#dcb878` |
| Sides | `#f1dfb8` |
| Back plate | `#a9d3a0` |
| Roof | `#c27a5f` |
| Printer plate | `#8fb4dd` |
| Base cover | `#e09a8a` |
| UNO Q | `#1f8a8a` |
| Hub | `#2b2b2b` |
| Modulino Buzzer | `#7b4fb3` |
| Servo | `#4a6fd1` |
| USB power breakout | `#d33333` |
| Spare mic cable | `#f0a030` |

## A GIF for Project Hub

```bash
ffmpeg -i clips/turntable.mp4 -vf "fps=15,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse" turntable.gif
```

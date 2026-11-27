# Project Hub draft — BirdBox v3: the printed bird box

This draft adds the third version of BirdBox to the existing Project Hub page
(`docs/project-hub.md`): a fully 3D-printed bird box that replaces the wooden one
and holds everything from stages 1 and 2. Copy each section into the matching
field of the Project Hub editor. Sections marked **(update)** replace the existing
field; the rest are new.

Placeholders:

- `[RENDER: name]` is a still from `docs/video-v3/stills/` (`name.png` has a
  transparent background, `name-bg.png` a light grey one: use the grey one on
  Project Hub).
- `[CLIP: name]` is a clip from `docs/video-v3/clips/`. Project Hub takes
  YouTube or Vimeo links rather than uploads, so either cut it into the build
  video or upload it and link it. GIFs also work: see `docs/video-v3/README.md`
  for a command that converts any clip to one.
- `[PHOTO: …]` and `[VIDEO: …]` are for your own footage from the shoot.

---

## Title (update)

**BirdBox: On-Device Bird Identification with the Arduino UNO Q**

(unchanged; mention v3 in the short description instead)

## Short description (update)

A bird box that identifies birds on-device with BirdNET, logs them to Arduino Cloud,
moves a felt bird out while a buzzer plays the species' song, and prints
encyclopaedia-style notes on a thermal printer. Now in a fully 3D-printed box.

## Tags (update)

`uno-q` · `app-lab` · `birdnet` · `machine-learning` · `audio` · `arduino-cloud` ·
`servo` · `modulino` · `thermal-printer` · `llm` · `wildlife` · `edge-ai` ·
`3d-printing` · `enclosure` · `freecad`

## Difficulty / time (update)

Intermediate · stage 1 about 3 hours, stage 2 about 2 hours, stage 3 (the printed
box) about 2 hours to assemble, plus printing time

## Components and supplies (add a stage 3 table)

**Stage 3: the printed bird box (optional, replaces the wooden box)**

| Qty | Item |
|---|---|
| 1 | CSN-A2 58 mm thermal panel printer (in place of stage 2's RS PRO; same 103 × 57 mm panel size) |
| — | 3D-printed base, front, two sides, back plate, roof, printer plate and base cover (PLA or PETG) |
| 10 | M3 × 10 countersunk self-tapping screws (sides to the front and base) |
| 8 | M3 × 12 countersunk self-tapping screws (back plate and roof) |
| 4 | M3 × 10 pan-head self-tapping screws (printer plate) |
| 8 | M3 × 8 pan-head self-tapping screws (UNO Q and Modulino Buzzer) |
| 2 | Cable ties up to 4.8 mm wide, 150 mm or longer (hub) |
| 2 | Small cable ties, up to 2.5 mm wide (USB power breakout) |
| 2 or 4 | 16 mm panel-mount momentary push buttons ([The Pi Hut](https://thepihut.com/products/16mm-panel-mount-momentary-pushbutton-black)) |
| 1 | USB-C power breakout board, for the printer's power |
| 1 | Wall screw, 4–4.5 mm shank, head up to 9 mm |

3 mm wood screws work in place of the M3 self-tappers.

## Tools (add)

- 3D printer with a bed at least 230 mm in one direction (the sides are 227 mm long)
- Screwdriver (a stubby one helps for the side screws)
- Flush cutters, for the supports under the servo rack

The hole saw and the saw for the printer cutout aren't needed with the printed box.

## Apps and platforms (add)

- FreeCAD 1.1 (only if you want to change the design: it's a parametric script)

---

## Story: add after Stage 2

## Stage 3: a printed bird box

[RENDER: hero-front-right]

The first two versions lived in a wooden bird box: a 60 mm hole saw for the
entrance, a hand-cut 103 × 57 mm opening for the printer, and parts screwed in
wherever they fitted. Version 3 is a box designed around the parts, printed in
eight pieces. From the outside it still looks like a traditional bird box: a
pitched roof that overhangs the front, and nothing on the front but the hole. The
printer is hidden in the base, and receipts come out of a slot underneath, just
behind a row of push buttons. Stage 3 also swaps the RS PRO printer for a CSN-A2,
a common 58 mm panel printer that fits the same 103 × 57 mm opening.

Assembled, it's 138 × 232 × 161 mm (W × H × D, roof included).

[CLIP: turntable]

### What goes where

[RENDER: inside]

| Where | What it holds |
|---|---|
| Front | The 64 mm bird hole, with the linear servo assembly's frame built into the back of the front wall. The rack prints in place inside it. |
| Base | 2 or 4 push buttons, the serrated paper slot in the base cover, and the CSN-A2 thermal printer face down under a flush cover |
| Under the roof | The Arduino USB-C Hub, zip-tied to two stubs |
| Back plate | The UNO Q on standoffs, two spool posts for the spare mic cable, cable notches, and a keyhole for hanging it on a wall |
| Right side | The Modulino Buzzer, next to the UNO Q so its Qwiic cable is short, with a grille behind it |
| Base, at the back | Cable-tie slots for the printer's USB power breakout, and vents |

[RENDER: exploded]

### From one big print to eight small ones

My first printed version had a one-piece body: front, sides and base in a single
print, 124 × 228 mm on the bed and 135 mm tall. It took a long time, and it failed.
A long print is risky, and inside a finished box you can barely reach to screw
anything to the side walls. So version 3 splits it into flat panels:

[RENDER: base-tray] [RENDER: front-panel-inside] [RENDER: right-side-inside]
[RENDER: back-plate-inside] [RENDER: roof-underside]

- **Base tray**: buttons, the hatch for the printer cover, the paper slot, and
  blocks along each side for the printer plate and the side screws. It's only
  11 mm tall.
- **Front panel**: the bird hole and the servo assembly's frame. The frame used to
  be a separate print that screwed behind a 20 mm thick wooden front; now it's
  fused to the back of a 3 mm wall, so there's no collar and no flange screws,
  and one print fewer.
- **Two sides**: flat panels, outside face down. They screw onto strips on the
  front panel and blocks on the base, with countersunk screws from outside.
- **Back plate, roof, printer plate and cover**, as before.

Everything is fitted to its own panel on the bench while it lies flat, and the box
only goes together at the end.

[CLIP: build]

### Printing

| Part | On the bed | Print it | Supports |
|---|---|---|---|
| Base | 118 × 132 × 11 mm | bottom down | none |
| Front | 118 × 205 × 110 mm | front face down, the servo frame pointing up | organic, under the rack only |
| Left side, right side | 227 × 135 × 12 mm each | outside face down | none |
| Back plate | 124 × 227 × 32 mm | wall side down | none |
| Roof | 138 × 164 × 10 mm | top down, so the tie stubs point up | none |
| Printer plate | 117 × 84 × 11 mm | top face down | none |
| Base cover | 113 × 64 × 3 mm | top face down | none |

PLA or PETG, 0.2 mm layers, 3 perimeters, 15 % infill. On a 250 × 210 mm bed the
base, printer plate and cover fit on one plate; everything else prints on its own.
Print the front first: it's the tallest part, and the rack has to slide freely once
its supports are off.

[PHOTO: the eight printed parts laid out]

### The details

**A cover with no magnets or screws.** The printer's paper door is behind a flush
cover in the base. Two tongues on its front edge hook into the base, and at the
back, a 1 mm slot along each side frees a thin strip of the cover that acts as a
spring. A small barb on each strip clicks into a groove in the side of the opening.
To change the paper, pull the back edge down at the fingernail notch, and the
barbs' sloped undersides push the springs in and let go.

[RENDER: underside]

**A paper slot that tears both ways.** The slot is serrated on both edges, so a
receipt tears cleanly whichever way you pull it. It's in the cover rather than the
base: the CSN-A2's paper door only opens with the printer plate turned round, which
moved the paper 5 mm back, and a new cover with the slot in the right place was the
only part I had to reprint.

**The hub hangs from the roof.** In the first printed version the hub sat on a
shelf under the roof, which blocked the way down to the printer mount. Now two
stubs under the roof each have a tunnel for a cable tie, and the hub hangs off them.
It lifts out with the roof.

**A short Qwiic cable.** The Modulino Buzzer sits on the right side near the back,
14.5 mm from the back plate and right beside the UNO Q.

**One screw to hang it.** A keyhole in the back plate drops onto a single wall
screw.

**Checked before printing.** The FreeCAD script that makes the parts also builds
rough models of everything inside (printer and its plugs, buttons, servo, hub and
its plugs, UNO Q with jumper wires, Modulino, breakout, coiled mic cable) and
checks them against the printed parts and each other. It prints `fit check: no
clashes` or lists what collides. It also draws annotated sections showing where
every part and cable goes, with the clearances.

[IMAGE: hardware/drawings/1-side-section.png]

> Upload `hardware/drawings/1-side-section.png` and
> `hardware/drawings/6-exploded-panels.png` from the repository here.

### Assembling the printed box

[IMAGE: docs/assembly/step-00.png] (parts and screws), then one sheet per step below:
`docs/assembly/step-01.png` to `step-13.png`, or all of them in
`docs/assembly/birdbox-v3-assembly.pdf`. The steps there are finer than the list here
(13 rather than 9), in the same order.

1. **Cover.** Try the cover in the base: it should click shut and pull open from
   the notch. If it's stiff, sand the barbs a little.
   [CLIP: build-03-cover]
2. **Base.** Fit the buttons, nut inside. Turn the printer plate so its solid block
   is at the front, so the paper door can open. Push the CSN-A2 through the printer
   plate from underneath, fit its fixing blocks, lay it face down in the base with
   the paper slot to the front, and screw the plate down. Tie the USB power
   breakout to the floor behind it.
   [CLIP: build-01-base] [CLIP: build-02-printer]
3. **Front.** Clear the supports from under the rack and check it slides. Fit the
   gear to the FS90R, mount the servo in the frame so the gear meshes with the
   rack, and attach the bird to the end of the arm.
   [CLIP: build-04-front]
4. **Right side.** Screw the Modulino Buzzer to its standoffs and plug in the
   Qwiic cable.
5. **Box.** Stand the front on the base and screw on the sides: three screws into
   each front strip and two into each side of the base.
   [CLIP: build-05-right-side] [CLIP: build-06-left-side]
6. **Roof and hub.** Tie the hub to the two stubs under the roof, Ethernet end to
   the front.
7. **Back plate.** Screw the UNO Q to its standoffs and plug in the servo, printer,
   button and Qwiic wires. Lay the mic and power cables in the two notches in the
   bottom edge, and wind the spare mic cable round the spool posts.
   [CLIP: build-07-back]
8. **Close up.** Plug the mic and power into the hub and the hub into the UNO Q,
   screw on the roof and the back plate, and fit the cover.
   [CLIP: build-08-roof]
9. **Hang it** on a wall screw through the keyhole.

[VIDEO: assembling the real printed parts]

### Changing the paper

1. Pull the back of the cover down at the notch until the snaps let go, slide it
   back off its tongues and lift it away.
2. Open the printer's door, drop in a new roll, and close the door with the end of
   the paper sticking out of the slot.
3. Hook the cover's tongues in at the front, swing the back up until it clicks, and
   tear off the end of the paper.

[VIDEO: changing the paper roll]

### Make it fit your parts

Every size is a parameter at the top of `hardware/birdbox-enclosure.py`, a FreeCAD
script. Change one and rebuild:

```bash
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd hardware/birdbox-enclosure.py
```

It rewrites the STL and STEP files and runs the fit check again. The ones to check
against your own parts:

- `PR_SLOT`: the distance from the front edge of your printer's face to its paper
  slot. Measure yours. `COVER_SLOT_DY` moves the cover's slot back from the base's,
  and `PLATE_TURNED` says which way round the printer plate is fitted.
- `BUTTONS`: 2 or 4.
- `COVER_CATCH`: `"snap"`, or `"magnet"` for pockets for 6 × 2 mm disc magnets if
  the snaps wear loose.
- `W`: the width, if your printer's fixing blocks stick out more than 7.5 mm.

### What I learned

- **Split big prints into flat panels.** Each part prints quickly and without
  supports, a failure costs one panel rather than the whole box, and you can work
  on every panel with it lying flat on the bench.
- **Merge the parts that don't need to come apart.** The servo frame being part of
  the front panel saved a print, two screws and a 20 mm collar.
- **Model what goes inside, not just the box.** The fit check caught clashes with
  the printer's plugs, the hub's USB plugs and the UNO Q's jumper wires before
  anything was printed.

### Credits (update)

Add to the existing list:

- **Printed enclosure** designed for BirdBox; its servo frame is based on the
  linear servo assembly by lingeswaran (CC BY). Print files CC BY 4.0.

## Code (update)

The enclosure's print files, STEP models, FreeCAD script and drawings are in the
repository's `hardware/` folder: <https://github.com/jimbruges/birdbox/tree/main/hardware>

## CAD (new attachment)

Attach the eight `hardware/birdbox-enclosure-*.step` files, or link the
`hardware/` folder.

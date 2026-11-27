# BirdBox hardware

3D print files for BirdBox. Build instructions are in the main
[README](../README.md#building-the-hardware).

| File | What it is | Printing |
|---|---|---|
| `birdbox-mic-holder.stl` | Outdoor housing for the [Mini USB Microphone](https://thepihut.com/products/mini-usb-microphone) and its USB-C to USB-A adapter | Fill with silicone or hot glue after assembly, keeping the mic port clear |
| `birdbox-mic-holder.step` | Editable model of the mic holder | |
| `birdbox-servo-assembly-print-in-place.stl` | Linear servo assembly for an SG90-size servo (FS90R), printed in one piece | Mounting face on the build plate, organic supports |
| `birdbox-servo-assembly.step` | Editable model of the servo assembly | |
| `servo-gear.stl` | Pinion gear for the servo | |
| `servo-gear.step` | Editable model of the gear | |
| `birdbox-enclosure-base.stl` | Base tray: button holes, paper slot, the hatch for the cover, and blocks for the printer plate and side screws | Bottom down, no supports |
| `birdbox-enclosure-front.stl` | Front panel with the bird hole and the servo assembly's frame, with its rack printed in place | Front face down, organic supports for the rack only |
| `birdbox-enclosure-side-left.stl` / `-side-right.stl` | Side panels: roof rail, back-plate boss, vents; the right one carries the Modulino Buzzer | Outside face down, no supports |
| `birdbox-enclosure-back.stl` | Back plate: hangs on the wall, carries the UNO Q and the spare mic cable | Wall side down, no supports |
| `birdbox-enclosure-roof.stl` | Sloping roof, with zip-tie stubs underneath for the hub | Top face down, no supports |
| `birdbox-enclosure-printer-plate.stl` | Plate the printer clamps into, face down above the base | Top face down |
| `birdbox-enclosure-cover.stl` | Flush cover over the printer's paper door | Top face down |
| `birdbox-enclosure-*.step` | Editable models of the eight parts, in their assembled positions | |
| `birdbox-enclosure.py` | Parametric FreeCAD script that makes all of the above | |
| `drawings/*.png` | Annotated sections: where every part and cable goes, and the clearances and fits | |

## Printed enclosure

A printed replacement for the wooden box, sized around the parts that go inside
it. Assembled it is 138 × 232 × 161 mm (W × H × D, roof included) and looks like a
traditional bird box: a pitched roof that overhangs the front and nothing on the
front but the bird hole. The printer is hidden in the base: receipts come out of a
slot underneath, just behind a row of push buttons.

The body is four flat panels (base, front and two sides) rather than one tall
print, so each part is quick to print and the parts that carry boards are easy
to work on before the box goes together. The sides screw onto strips on the
front panel and blocks on the base, with countersunk M3 screws from outside.
`drawings/6-exploded-panels.png` shows how they fit.

| Where | What it holds |
|---|---|
| Front | The 64 mm bird hole in the 3 mm wall, with the servo assembly's frame fused to the back of it: no collar and no flange screws. Its rack prints in place in the frame. Retracted, the tip of the arm is 10.6 mm behind the front face. |
| Base, front | Two or four 16 mm panel-mount push buttons ([The Pi Hut](https://thepihut.com/products/16mm-panel-mount-momentary-pushbutton-black)) in a row, and behind them the paper slot, which is in the cover |
| Base, middle | CSN-A2 panel printer, face down with its paper slot to the front, clamped into the printer plate. A flush cover hides its paper door. |
| Under the roof | Arduino USB-C Hub (TPX00241), zip-tied up to two stubs on the roof's underside with its Ethernet end to the front, so it lifts off with the roof. The USB-C ports (power in, mic) face left, the USB-A ports face right. |
| Back plate | UNO Q on 8 mm standoffs, component side forward, USB-C to the left. Two spool posts low down for the spare mic cable, two notches in the bottom edge for the mic and power cables, and a keyhole for the wall screw. |
| Right side | Modulino Buzzer on 5 mm standoffs near the back, 14.5 mm from the back plate so its Qwiic cable to the UNO Q is short, with a grille through the side behind it |
| Base, back | Cable-tie slots for the printer's USB power breakout, and vent slots |

### Printer and paper

The printer sits face down in a shallow pocket in the base. Its fixing blocks clamp
it into a separate printer plate, which screws to four blocks on the base. **Fit
the plate turned 180°, with its solid block at the front**: the CSN-A2's paper
door needs the room at the back to open. That puts the printer 8.95 mm further
back than the plate the other way round.

The paper comes out through a slot in the cover, 5 mm behind the slot in the base
(`COVER_SLOT_DY`, measured on the turned plate), with serrated edges on both sides
so a receipt tears cleanly whichever way you pull it. A lip on the front of the
cover fills the base's own slot. Only the cover changed for this: the other
parts print as before.

With the plate turned, its block rests on the thicker floor pad in front of the
printer, so the plate sits about 1.1 mm high there. It still screws down and the
door opens. If the plate rocks, sand 1.1 mm off the underside of the block.

The cover behind the slot hides the paper door, the FEED button and the status
light. Two tongues on its front edge hook into the base, and two printed spring
fingers along its sides click into grooves in the sides of the opening, so it
needs no magnets or screws. To change the paper:

1. Pull the back edge of the cover down firmly with a fingernail in the notch
   until the snaps let go, slide the cover back off its tongues, and lift it away.
2. Open the printer's door (it's hinged at the back), drop in a new roll with the
   paper feeding the way the printer's label shows, and close the door with the end of the
   paper sticking out of the slot.
3. Feed the end of the paper through the cover's slot, hook the cover's tongues
   into the base in front, swing the back up until the snaps click, and tear off
   the end of the paper.

The base's slot comes from `PR_SLOT`, the distance from the front edge of the
printer's face to its paper slot (15 mm, set before it was measured). The cover's
slot is `COVER_SLOT_DY` behind it. If you print everything new, measure your
printer and set `PR_SLOT`, then `COVER_SLOT_DY` to 0 and `PLATE_TURNED` to match
how you fit the plate.

If receipts read upside down from the front once the printer is face down, turn
them round with the setting that flips the receipt 180°.

The Arduino hub was chosen over the Acasis 6-in-1 because its datasheet gives the
dimensions and port positions to design around; the Acasis listings don't. The
Acasis hangs off the same stubs.

### Print

PLA or PETG, 0.2 mm layers, 3 perimeters, 15 % infill. Only the front panel needs
supports, and only under the rack: use organic supports, as for the servo assembly
on its own. The sides are the largest parts on the bed, 227 × 135 mm, but only
12 mm tall. The front is 118 × 205 mm on the bed and 110 mm tall with the frame.

### You also need

| Qty | Part | For |
|---|---|---|
| 10 | M3 × 10 countersunk self-tapping screws | Sides to the front and base (5 per side) |
| 4 | M3 × 12 countersunk self-tapping screws | Back plate to the base and sides |
| 4 | M3 × 12 countersunk self-tapping screws | Roof to the sides |
| 4 | M3 × 10 pan-head self-tapping screws | Printer plate to the base |
| 8 | M3 × 8 pan-head self-tapping screws | UNO Q and Modulino Buzzer |
| 2 | Cable ties up to 4.8 mm wide, 150 mm or longer | Hub to the roof's stubs |
| 2 | Small cable ties (≤ 2.5 mm wide) | Power breakout to the floor |
| 2 or 4 | 16 mm panel-mount momentary push buttons, with 2.8 mm push-on connectors | |
| 1 | Wall screw, 4–4.5 mm shank, head up to 9 mm | Hanging the box |

3 mm wood screws work in place of the M3 self-tappers.

### Assemble

Fit everything to its own panel first, while it lies flat on the bench.

1. **Cover:** try the cover in the base. It should click shut and pull open from
   the notch. If it's too stiff, sand the barbs on its sides a little; if it's
   loose, see `COVER_CATCH` below.
2. **Base:** fit the buttons through their holes, nut inside. Push the printer
   through the printer plate from the underside and fit its two fixing blocks on
   top. Turn the plate so its solid block is at the front, lay it face down in the
   base with the paper slot to the front, and screw the plate to the four blocks. Tie the power breakout to the floor behind
   it and wire it to the printer's power input.
3. **Front:** clear the supports from under the rack, check it slides freely, and
   fit the gear to the FS90R (see the main README). Mount the servo in the frame so
   the gear meshes with the rack, and attach the bird to the end of the arm.
4. **Right side:** screw the Modulino Buzzer to its standoffs and plug in its
   Qwiic cable.
5. **Box:** stand the front on the front edge of the base and screw the sides on:
   three screws into each front strip and two into each side of the base.
6. **Roof and hub:** tie the hub up to the two stubs under the roof, Ethernet end to
   the front, with a tie through each stub's tunnel and round the hub. Plug in the
   USB-A to USB-C cable for the printer's power breakout.
7. **UNO Q:** screw it to the back plate standoffs and plug in the servo, printer,
   button and Qwiic wires.
8. **Mic and power cables:** lay them in the two notches in the bottom of the back
   plate (mic on the left), wind the spare mic cable round the spool posts, and run
   both up the back left corner.
9. **Close up:** hold the roof above the box, plug the mic and power into the hub's
   USB-C ports and the hub's own cable into the UNO Q, then screw the roof onto the
   sides. Screw the back plate to the base and sides, and fit the cover (see
   [Printer and paper](#printer-and-paper)).
10. **Hang it:** put a screw in the wall, leaving the head 3–4 mm proud, and drop
    the box onto it through the keyhole.

### Changing it

Every size is a parameter at the top of `birdbox-enclosure.py`. After changing one,
rebuild with FreeCAD's command-line binary (macOS path shown):

```bash
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd hardware/birdbox-enclosure.py
```

To redraw the annotated drawings in `drawings/` afterwards:

```bash
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd -c "exec(open('hardware/drawings/make-drawings.py').read())"
```

The build rewrites the STL and STEP files, then checks rough envelopes of every part in
the box (printer and its plugs, buttons, servo rack and servo, hub and its
plugs, UNO Q with its jumper wires, Modulino and its Qwiic plug, breakout, coiled
mic cable) against
the printed parts and against each other, and prints `fit check: no clashes` or the clashes it
found.

Check these against your own parts before printing:

- **Paper slot.** Set `PR_SLOT` from your printer, and `COVER_SLOT_DY` and
  `PLATE_TURNED` (see above). If the paper isn't centred on the printer's face, set
  `SLOT_X` too.
- **Buttons.** `BUTTONS` is 4; set it to 2 for two.
- **Cover catch.** `COVER_CATCH` is `"snap"`. If the snaps wear loose, set it to
  `"magnet"` for pockets for four 6 × 2 mm disc magnets instead (two in the
  cover, two in the printer plate), and reprint the base, plate and cover.
- **CSN-A2 fixing blocks.** The inside is 118 mm wide, leaving 7.5 mm each side of
  the printer for its blocks. If yours stick out further, raise `W`.
- **Power breakout.** It's held by cable ties, so any small board fits. The floor
  slots are 26 mm apart across it.

## Credits and licence

The servo assembly is based on, and the servo gear comes from,
[Linear servo using SG90 9g servo](https://www.printables.com/model/1566678-linear-servo-using-sg90-9g-servo) by **lingeswaran** on Printables, licensed
Creative Commons Attribution (CC BY). The assembly has been modified for BirdBox, and its frame is
built into the enclosure's front panel.

These files are licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). If you share or remix
them, credit both BirdBox and the original design.

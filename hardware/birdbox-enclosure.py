"""BirdBox printed enclosure: base, front, sides, back plate, roof, printer plate
and base cover.

A parametric FreeCAD script. Run it headless from the repo root:

    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd hardware/birdbox-enclosure.py

It writes STEP files (assembled position) and STL files (print orientation)
next to this script, then checks every part inside the box against the printed
parts and against each other, and prints a fit report.

Coordinates, assembled: x across the front (+x to the right as you face the
box), y from the front face (0) to the back, z up from the bottom (0).
"""

import math
import os
import sys

import FreeCAD as App
import MeshPart
import Part

V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- parameters

WALL = 3.0             # body walls and floor
W = 124.0              # outside width
DB = 135.0             # body depth, front face to back edge
BACK_T = 4.0           # back plate thickness
ROOF_DEG = 10.0        # roof pitch; the back is taller than the front
ROOF_T = 4.0
ROOF_EAVE = 22.0       # roof overhang at the front
ROOF_SIDE = 7.0        # roof overhang at each side

# Push buttons (16 mm panel mount) in a strip along the front of the base.
BUTTONS = 4            # 2 or 4
BTN_HOLE_D = 16.2
BTN_Y = 14.2
BTN_PITCH = 26.7

# CSN-A2 panel printer, face down in the base with its paper slot to the front:
# 111 x 65 bezel 7 mm thick, 103 x 57 cutout, 50 mm behind the panel. It
# clamps into a separate printer plate that screws in from inside. A flush
# cover hides the paper door; the paper comes out of a slot in front of it.
PR_BEZEL_W, PR_BEZEL_D, PR_BEZEL_T = 111.0, 65.0, 7.0
PR_CUT_W, PR_CUT_D = 103.6, 57.6
PR_EMBED = 50.0
PR_Y0 = 27.4           # front edge of the bezel
PR_SLOT = 15.0         # paper slot, back from the bezel's front edge: measure yours
PR_FACE_Z = 4.3        # bezel face, just above the cover
PR_CL = 0.4            # clearance round the bezel
PLATE_T = 3.0
COVER_T = 3.0
SLOT_GAP = 4.5         # paper slot in the base, edge to edge (teeth take 1 mm each side)
SLOT_LEN = 80.0
SLOT_X = 0.0           # paper centre, if it isn't on the bezel's centre
TEETH = 1.0            # serration depth
# The printer plate is fitted turned 180 degrees, so the printer's paper door
# can open. That puts the printer 8.95 mm further back, and its paper slot 5 mm
# behind the slot in the base (as measured), so the cover carries its own
# serrated slot COVER_SLOT_DY behind the base's, and a lip fills the base's slot.
# Set PLATE_TURNED False and COVER_SLOT_DY 0 for the plate the right way round.
PLATE_TURNED = True
COVER_SLOT_DY = 5.0
# What holds the back of the cover up: "snap" (printed spring fingers that
# click into grooves in the hatch sides) or "magnet" (6 x 2 mm disc magnets).
COVER_CATCH = "snap"
MAGNET_R, MAGNET_T = 3.1, 2.1
SNAP_Y = (68.0, 94.0)  # spring finger, root to tip, along each side of the cover
SNAP_BARB = (84.0, 92.0)

# Bird hole and servo assembly (birdbox-servo-assembly.step). Its frame is
# part of the front panel: the flange that used to screw to the back of a
# 20 mm board is fused to the back of the front wall, and the rack prints in
# place inside it. Retracted, the arm's tip is 10 mm behind the front face.
HOLE_D = 64.0
HOLE_Z = 145.0         # high enough for the servo to clear the printer's plugs
SERVO_DY = WALL - 20.0  # the assembly moves forward from its 20 mm board

# USB hub (Arduino TPX00241, 119 x 27.8 x 16) zip-tied under the roof: two
# stubs hang down with a tie tunnel through each, and the hub hangs off them.
HUB_L, HUB_W, HUB_H = 119.0, 27.8, 16.0
HUB_Y0 = 5.0           # Ethernet end at the front, cable end at the back
TIE_Y = (25.0, 100.0)  # stub centres along the hub
TIE_STUB_H = 6.0       # stub drop: the hub's top rests on the stubs
TIE_HOLE = (5.5, 2.2)  # tunnel for a 4.8 mm tie, width x height
FRONT_H = HOLE_Z + HOLE_D / 2 + 4.0 + HUB_H + TIE_STUB_H   # front wall height
VENT_Z = (FRONT_H - 19.0, FRONT_H - 12.0)

# The body is four flat panels: a base tray, the front, and two sides that
# screw onto the edges of both. Side screws go in from outside, countersunk.
STRIP = 8.0            # square strips on the front panel the sides screw into
SIDE_SCREWS = [(WALL + STRIP / 2, z) for z in (40.0, 105.0, FRONT_H - 25.0)] + \
              [(15.0, 7.3), (118.0, 7.3)]   # front strips, then base blocks

# UNO Q on the back plate, component side forward, USB-C edge on the left.
UNO_X0, UNO_Z0 = -24.0, HOLE_Z - 19.0   # lower-left corner seen from the front
UNO_W, UNO_H = 68.58, 53.34
UNO_HOLES = [(13.97, 2.54), (15.24, 50.8), (66.04, 7.62), (66.04, 35.56)]
UNO_STANDOFF = 8.0

# Modulino Buzzer on the right side, near the back so its Qwiic cable to the
# UNO Q is short, with a grille behind it.
MOD_Y, MOD_Z = 100.0, HOLE_Z + 8.0  # board centre
MOD_L, MOD_H = 41.0, 25.36
MOD_DY, MOD_DZ = 32.0, 16.0        # hole spacing
MOD_STANDOFF = 5.0

# Mic cable spool on the back plate, and the two cable notches below it.
SPOOL_X, SPOOL_Z, SPOOL_L = 40.0, 40.0, 28.0
NOTCH_X = (-40.0, -28.0)           # mic cable, power cable

# USB power breakout for the printer: cable-tie slots in the floor.
BREAKOUT_X = (17.0, 43.0)
BREAKOUT_Y = (114.0, 126.0)

PILOT_R = 1.25         # for M3 self-tapping screws (or 3 mm wood screws)
CLEAR_R = 1.7
CSK_R = 3.3

TAN = math.tan(math.radians(ROOF_DEG))

# Derived: the printer stack and the hatch the cover fills.
PLATE_Z0 = PR_FACE_Z + PR_BEZEL_T              # plate underside = panel face
PLATE_Z1 = PLATE_Z0 + PLATE_T
PR_YC = PR_Y0 + PR_BEZEL_D / 2
POCKET_X = PR_BEZEL_W / 2 + PR_CL
SLOT_Y = PR_Y0 + PR_SLOT
HATCH_Y0 = SLOT_Y + SLOT_GAP / 2               # cover's front edge
HATCH_Y1 = PR_Y0 + PR_BEZEL_D + PR_CL + 8.0    # 8 mm behind the bezel for the magnets
MAGNETS = [(sx * 45.0, HATCH_Y1 - 4.0) for sx in (-1, 1)]
TONGUES = [(sx * 42.0, sx * 54.0) for sx in (-1, 1)]   # outside the paper slot
PLATE_SCREWS = [(sx * 55.5, y) for sx in (-1, 1) for y in (PR_Y0 - 2.65, HATCH_Y1 + 3.2)]
PLATE_YC = (PR_Y0 - 4.9 + HATCH_Y1 + 5.45) / 2   # the plate's centre, and its screws'
PR_SHIFT = 2 * (PLATE_YC - PR_YC) if PLATE_TURNED else 0.0   # printer, back from PR_Y0
COVER_SLOT_Y = SLOT_Y + COVER_SLOT_DY


# Snap catch, in the cover's x: finger 53.4..55.6 behind a 1 mm slot, and a
# diamond barb 0.8 proud of its edge that sits in a groove in the hatch side.
SNAP_SLOT_X = (POCKET_X - 3.5, POCKET_X - 2.5)
SNAP_BARB_PTS = [(POCKET_X - 0.3, 0.8), (POCKET_X + 0.5, 1.6), (POCKET_X - 0.3, 2.4)]
SNAP_GROOVE = (POCKET_X + 0.7, 1.1, 2.5)     # depth to x, z0, z1


def button_xs():
    return [(i - (BUTTONS - 1) / 2) * BTN_PITCH for i in range(BUTTONS)]


def top(y):
    """Height of the roof's underside at depth y."""
    return FRONT_H + y * TAN


# ---------------------------------------------------------------- helpers

def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cyl_x(y, z, r, x0, x1):
    return Part.makeCylinder(r, x1 - x0, V(x0, y, z), V(1, 0, 0))


def cyl_y(x, z, r, y0, y1):
    return Part.makeCylinder(r, y1 - y0, V(x, y0, z), V(0, 1, 0))


def prism_yz(points, x0, x1):
    """Extrude a (y, z) polygon across x."""
    pts = [V(x0, y, z) for y, z in points]
    face = Part.Face(Part.makePolygon(pts + [pts[0]]))
    return face.extrude(V(x1 - x0, 0, 0))


def teeth(x0, x1, y, direction, z0, z1, pitch=1.5):
    """A serrated strip along x at depth y, its teeth pointing in direction (+1/-1)."""
    pts = [V(x0, y - direction * 0.5, z0)]
    x = x0
    while x + pitch <= x1 + 1e-6:
        pts += [V(x, y, z0), V(x + pitch / 2, y + direction * TEETH, z0)]
        x += pitch
    pts += [V(x, y, z0), V(x, y - direction * 0.5, z0), pts[0]]
    return Part.Face(Part.makePolygon(pts)).extrude(V(0, 0, z1 - z0))


def mirror_x(shape):
    return shape.mirror(V(0, 0, 0), V(1, 0, 0))


def both_sides(shape):
    return shape.fuse(mirror_x(shape))


def fuse(shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = out.fuse(s)
    return out.removeSplitter()


# Back plate screws: two low, two high, into bosses in the body's corners.
BACK_SCREWS = [(sx * 54.0, z) for sx in (-1, 1) for z in (7.5, FRONT_H + 9.0)]
# Roof screws, into rails along the top of the side walls.
ROOF_SCREWS = [(sx * 56.25, y) for sx in (-1, 1) for y in (30.0, 110.0)]
ROOF_N = V(0, -math.sin(math.radians(ROOF_DEG)), math.cos(math.radians(ROOF_DEG)))


def roof_point(x, y):
    return V(x, y, top(y))


def under_roof(x0, x1, y0, y1, d0, d1):
    """A block d0..d1 below the roof's underside, sheared to follow its pitch."""
    return prism_yz([(y0, top(y0) - d1), (y1, top(y1) - d1),
                     (y1, top(y1) - d0), (y0, top(y0) - d0)], x0, x1)


def roof_cut():
    """Everything above the roof's underside."""
    hw = W / 2
    return prism_yz([(-30, top(-30)), (DB + 30, top(DB + 30)),
                     (DB + 30, top(DB) + 300), (-30, top(DB) + 300)], -hw - 30, hw + 30)


_SERVO = {}


def servo_parts():
    """Frame, rack and servo from the servo assembly STEP, in place."""
    if not _SERVO:
        step = Part.Shape()
        step.read(os.path.join(HERE, "birdbox-servo-assembly.step"))
        # In the STEP the old front board's outer face is y = 0 with the box
        # behind it at -y, and the hole is at x 55, z 168.63. Turn it round to
        # face -y, put the hole centre on ours, and bring the flange forward
        # onto the back of the front wall.
        m = App.Matrix()
        m.move(V(-55.0, 0, -168.634))
        m.rotateZ(math.pi)
        m.move(V(0, SERVO_DY, HOLE_Z))
        _SERVO["frame"] = step.Solids[1].transformGeometry(m)
        _SERVO["rack"] = step.Solids[0].transformGeometry(m)
        # The FS90R isn't in the STEP: an SG90-size body on the frame's servo screws.
        _SERVO["servo"] = box(65.7, 77.9, -102, -64, 108, 141).transformGeometry(m)
    return _SERVO["frame"], _SERVO["rack"], _SERVO["servo"]


def side_screw_holes(x_out, x_in, pilot):
    """Side screws, from the outside face at x_out to depth x_in (+x side)."""
    out = []
    for y, z in SIDE_SCREWS:
        if pilot:
            out.append(cyl_x(y, z, PILOT_R, x_in, x_out))
        else:
            out.append(cyl_x(y, z, CLEAR_R, x_in, x_out + 1))
            out.append(Part.makeCone(CLEAR_R, CSK_R, CSK_R - CLEAR_R,
                                     V(x_out - (CSK_R - CLEAR_R), y, z), V(1, 0, 0)))
    return fuse(out)


# ---------------------------------------------------------------- base

def make_base():
    """Floor tray: hatch, paper slot, buttons, and blocks along each side for
    the printer plate, the side screws and the back plate's low screws."""
    iw = W / 2 - WALL
    base = box(-iw, iw, WALL, DB, 0, WALL)

    add = []
    # Blocks along both sides, in front of and behind the printer bezel.
    add.append(both_sides(box(iw - 7, iw, WALL, PR_Y0 - PR_CL, WALL - 0.1, PLATE_Z0)))
    add.append(both_sides(box(iw - 9, iw, HATCH_Y1 + 0.5, DB, WALL - 0.1, PLATE_Z0)))
    # Thicker floor under the front of the bezel, for the cover's tongues.
    add.append(box(-POCKET_X, POCKET_X, PR_Y0 - PR_CL, HATCH_Y0,
                   WALL - 0.1, PR_FACE_Z - 0.1))
    # Serrated tear edge on the front side of the paper slot.
    add.append(teeth(SLOT_X - SLOT_LEN / 2, SLOT_X + SLOT_LEN / 2,
                     SLOT_Y - SLOT_GAP / 2, 1, 0, PR_FACE_Z - 0.1))
    base = fuse([base] + add)

    cut = []
    # The hatch the cover fills, the paper slot in front of it, the tunnels
    # the cover's tongues hook into, and a fingernail scoop behind. The back
    # edge is bevelled 45 degrees to match the cover's.
    cut.append(prism_yz([(HATCH_Y0, -1), (HATCH_Y1 + WALL + 1, -1), (HATCH_Y1, WALL),
                         (HATCH_Y1, PR_FACE_Z + 1), (HATCH_Y0, PR_FACE_Z + 1)],
                        -POCKET_X, POCKET_X))
    cut.append(box(SLOT_X - SLOT_LEN / 2, SLOT_X + SLOT_LEN / 2,
                   SLOT_Y - SLOT_GAP / 2, HATCH_Y0 + 0.1, -1, PR_FACE_Z + 1))
    for x0, x1 in TONGUES:
        cut.append(box(min(x0, x1) - 0.4, max(x0, x1) + 0.4, HATCH_Y0 - 5.4,
                       HATCH_Y0 + 0.1, COVER_T - 1.35, COVER_T + 0.15))
    cut.append(box(-8, 8, HATCH_Y1, HATCH_Y1 + WALL + 3.5, -1, 1.5))
    if COVER_CATCH == "snap":
        gx, gz0, gz1 = SNAP_GROOVE
        cut.append(both_sides(box(POCKET_X - 0.1, gx, SNAP_BARB[0] - 0.5,
                                  SNAP_BARB[1] + 0.5, gz0, gz1)))
    for x in button_xs():
        cut.append(Part.makeCylinder(BTN_HOLE_D / 2, WALL + 2, V(x, BTN_Y, -1)))
    for x, y in PLATE_SCREWS:
        cut.append(Part.makeCylinder(PILOT_R, 8, V(x, y, PLATE_Z0 - 7.5)))
    for x, z in BACK_SCREWS:
        if z < PLATE_Z0:
            cut.append(cyl_y(x, z, PILOT_R, DB - 14, DB + 1))
    cut.append(both_sides(side_screw_holes(iw + 0.5, iw - 7, True).common(
        box(0, iw + 1, 0, DB, 0, PLATE_Z0))))
    # Floor vents (cool air in) and cable-tie slots for the USB power breakout.
    for x in (-35, -25, -15):
        cut.append(box(x - 1.5, x + 1.5, HATCH_Y1 + 6, 128, -1, WALL + 1))
    for x in BREAKOUT_X:
        for y in BREAKOUT_Y:
            cut.append(box(x - 1.25, x + 1.25, y - 2, y + 2, -1, WALL + 1))
    return base.cut(fuse(cut)).removeSplitter()


# ---------------------------------------------------------------- front

def make_front():
    """Front wall with the bird hole and the servo assembly's frame, and a
    strip up each edge for the side screws."""
    iw = W / 2 - WALL
    front = box(-iw, iw, 0, WALL, 0, top(WALL) + 1)
    front = front.cut(cyl_y(0, HOLE_Z, HOLE_D / 2, -1, WALL + 1))
    strips = both_sides(box(iw - STRIP, iw, WALL - 0.1, WALL + STRIP, PLATE_Z0, top(DB)))
    frame = servo_parts()[0]
    front = fuse([front, strips, frame]).cut(roof_cut())
    pilots = side_screw_holes(iw + 0.5, iw - STRIP + 1, True).common(
        box(0, iw + 1, 0, WALL + STRIP + 1, PLATE_Z0, 1e3))
    return front.cut(both_sides(pilots)).removeSplitter()


# ---------------------------------------------------------------- sides

def make_side(modulino):
    """The right side (+x); mirror it for the left. It carries the roof rail,
    the bosses for the back plate's top screws, and vents up high."""
    hw = W / 2
    iw = hw - WALL
    side = box(iw, hw, 0, DB, 0, top(DB) + 1)

    add = []
    # Roof rail along the top, behind the front panel's strip.
    add.append(prism_yz([(WALL + STRIP + 0.5, top(WALL + STRIP) - 10), (DB, top(DB) - 10),
                         (DB, top(DB) + 1), (WALL + STRIP + 0.5, top(WALL + STRIP) + 1)],
                        iw - 5.5, iw + 0.1))
    # Boss for the back plate's top screw.
    hz = FRONT_H + 4
    add.append(box(iw - 9, iw + 0.1, 88, DB, hz, hz + 10))
    if modulino:
        for dy in (-1, 1):
            for dz in (-1, 1):
                add.append(cyl_x(MOD_Y + dy * MOD_DY / 2, MOD_Z + dz * MOD_DZ / 2, 3.0,
                                 iw - MOD_STANDOFF, iw + 0.1))
    side = fuse([side] + add).cut(roof_cut())

    cut = [side_screw_holes(hw, iw - 0.5, False)]
    for x, y in ROOF_SCREWS:
        if x > 0:
            p = roof_point(x, y)
            cut.append(Part.makeCylinder(PILOT_R, 10, p - ROOF_N * 9, ROOF_N))
    for x, z in BACK_SCREWS:
        if x > 0 and z > PLATE_Z0:
            cut.append(cyl_y(x, z, PILOT_R, DB - 14, DB + 1))
    for z in VENT_Z:
        cut.append(box(iw - 1, hw + 1, 45, 95, z, z + 3))
    if modulino:
        for dy in (-1, 1):
            for dz in (-1, 1):
                cut.append(cyl_x(MOD_Y + dy * MOD_DY / 2, MOD_Z + dz * MOD_DZ / 2,
                                 PILOT_R, iw - MOD_STANDOFF - 1, iw + 1.5))
        grille = [(0.0, 0.0)] + [(6.0 * math.cos(a), 6.0 * math.sin(a))
                                 for a in [i * math.pi / 3 for i in range(6)]]
        for dy, dz in grille:
            cut.append(cyl_x(MOD_Y + dy, MOD_Z + dz, 1.75, iw - 1, hw + 1))
    return side.cut(fuse(cut)).removeSplitter()


# ---------------------------------------------------------------- back plate

def make_back():
    hw = W / 2
    y0, y1 = DB, DB + BACK_T
    plate = box(-hw, hw, y0, y1, 0, top(DB))

    add = []
    # Keyhole boss, so the screw head has a pocket to slide up into.
    key_z = FRONT_H + 5
    add.append(box(-9, 9, y0 - 5, y0 + 0.1, key_z - 9, key_z + 17))
    # UNO Q standoffs.
    for bx, bz in UNO_HOLES:
        add.append(cyl_y(UNO_X0 + bx, UNO_Z0 + bz, 3.0, y0 - UNO_STANDOFF, y0 + 0.1))
    # Spool posts for the spare mic cable, with a 45 degree lip.
    for sx in (-1, 1):
        x = sx * SPOOL_X
        add.append(cyl_y(x, SPOOL_Z, 6.0, y0 - SPOOL_L + 5.5, y0 + 0.1))
        add.append(Part.makeCone(6.0, 10.0, 4.0, V(x, y0 - SPOOL_L + 5.5, SPOOL_Z),
                                 V(0, -1, 0)))
        add.append(cyl_y(x, SPOOL_Z, 10.0, y0 - SPOOL_L, y0 - SPOOL_L + 1.5))
    plate = fuse([plate] + add)

    cut = []
    for x, z in BACK_SCREWS:
        cut.append(cyl_y(x, z, CLEAR_R, y0 - 1, y1 + 1))
        cut.append(Part.makeCone(CLEAR_R, CSK_R, CSK_R - CLEAR_R,
                                 V(x, y1 - (CSK_R - CLEAR_R), z), V(0, 1, 0)))
        cut.append(cyl_y(x, z, CSK_R, y1 - 0.01, y1 + 1))
    # Keyhole: the head goes in at the bottom, the box drops onto the shank.
    cut.append(cyl_y(0, key_z, 4.75, y0 - 6, y1 + 1))
    cut.append(box(-2.25, 2.25, y0 - 6, y1 + 1, key_z, key_z + 10))
    cut.append(box(-5.5, 5.5, y0 - 6, y1 - 2, key_z - 5, key_z + 15))
    for bx, bz in UNO_HOLES:
        cut.append(cyl_y(UNO_X0 + bx, UNO_Z0 + bz, PILOT_R,
                         y0 - UNO_STANDOFF - 1, y0 + 2))
    # Cable notches in the bottom edge: mic and power come in from below.
    for x in NOTCH_X:
        cut.append(box(x - 3.5, x + 3.5, y0 - 10, y1 + 1, -1, 9))
    return plate.cut(fuse(cut)).removeSplitter()


# ---------------------------------------------------------------- roof

def make_roof():
    """Roof, with zip-tie stubs underneath for the USB hub."""
    y0, y1 = -ROOF_EAVE, DB + BACK_T          # no overhang at the back: it's on a wall
    t = ROOF_T / math.cos(math.radians(ROOF_DEG))
    x = W / 2 + ROOF_SIDE
    roof = prism_yz([(y0, top(y0)), (y1, top(y1)), (y1, top(y1) + t),
                     (y0, top(y0) + t)], -x, x)
    # Zip-tie stubs for the hub, each with a tunnel across it for the tie.
    stubs = [under_roof(-10, 10, y - 5, y + 5, -t / 2, TIE_STUB_H) for y in TIE_Y]
    roof = fuse([roof] + stubs)
    tw, th = TIE_HOLE
    cut = [under_roof(-11, 11, y - tw / 2, y + tw / 2, 1.5, 1.5 + th) for y in TIE_Y]
    for sx, sy in ROOF_SCREWS:
        p = roof_point(sx, sy)
        cut.append(Part.makeCylinder(CLEAR_R, ROOF_T + 2, p - ROOF_N, ROOF_N))
        cut.append(Part.makeCone(CLEAR_R, CSK_R, CSK_R - CLEAR_R,
                                 p + ROOF_N * (ROOF_T - (CSK_R - CLEAR_R)), ROOF_N))
    return roof.cut(fuse(cut)).removeSplitter()


# ---------------------------------------------------------------- printer plate

def make_plate():
    """Panel the printer clamps into, screwed in face down above the hatch."""
    hw = W / 2 - WALL - 0.4
    plate = box(-hw, hw, PR_Y0 - 4.9, HATCH_Y1 + 5.45, PLATE_Z0, PLATE_Z1)
    # Block behind the bezel that holds the cover's magnets.
    plate = plate.fuse(box(-51.5, 51.5, PR_Y0 + PR_BEZEL_D + PR_CL, HATCH_Y1,
                           COVER_T + 0.1, PLATE_Z0 + 0.1))
    cut = [box(-PR_CUT_W / 2, PR_CUT_W / 2, PR_YC - PR_CUT_D / 2, PR_YC + PR_CUT_D / 2,
               PLATE_Z0 - 1, PLATE_Z1 + 1)]
    for x, y in PLATE_SCREWS:
        cut.append(Part.makeCylinder(CLEAR_R, PLATE_T + 2, V(x, y, PLATE_Z0 - 1)))
    if COVER_CATCH == "magnet":
        for x, y in MAGNETS:
            cut.append(Part.makeCylinder(MAGNET_R, MAGNET_T, V(x, y, COVER_T + 0.1 - 0.01)))
    return plate.cut(fuse(cut)).removeSplitter()


def turned(shape):
    """The printer plate as fitted: turned 180 degrees about its centre."""
    if not PLATE_TURNED:
        return shape
    m = App.Matrix()
    m.move(V(0, -PLATE_YC, 0))
    m.rotateZ(math.pi)
    m.move(V(0, PLATE_YC, 0))
    return shape.transformGeometry(m)


# ---------------------------------------------------------------- base cover

def make_cover():
    """Flush cover over the paper door: hooks in at the front, and snaps (or
    magnets) hold the back.

    To open it, pull the back edge down with a fingernail and slide it back off
    its tongues."""
    x = POCKET_X - 0.3
    y0, y1 = HATCH_Y0 + 0.2, HATCH_Y1 - 0.3
    # Back edge bevelled to match the hatch.
    cover = prism_yz([(y0, 0), (y1 + COVER_T, 0), (y1, COVER_T), (y0, COVER_T)], -x, x)
    sx0, sx1 = SLOT_X - SLOT_LEN / 2, SLOT_X + SLOT_LEN / 2
    if COVER_SLOT_DY:
        # The paper comes out through the cover: a lip fills the base's slot to
        # 0.4 from its edge, and the cover's own slot is serrated on both edges.
        # Cut the slot first, so the teeth added into it stay.
        cover = cover.cut(box(sx0, sx1, COVER_SLOT_Y - SLOT_GAP / 2,
                              COVER_SLOT_Y + SLOT_GAP / 2, -1, COVER_T + 1))
        lip = SLOT_Y - SLOT_GAP / 2 + 0.4
        add = [box(sx0 + 0.4, sx1 - 0.4, lip, y0 + 0.5, 0, COVER_T),
               teeth(sx0, sx1, COVER_SLOT_Y - SLOT_GAP / 2, 1, 0, COVER_T),
               teeth(sx0, sx1, COVER_SLOT_Y + SLOT_GAP / 2, -1, 0, COVER_T)]
    else:
        add = [teeth(sx0, sx1, y0, -1, 0, COVER_T)]
    for x0, x1 in TONGUES:
        add.append(box(min(x0, x1), max(x0, x1), y0 - 5, y0 + 0.5,
                       COVER_T - 1.2, COVER_T))
    if COVER_CATCH == "snap":
        # A diamond barb on the outside of each spring finger: closing, its top
        # ramp pushes the finger in; pulling the cover down, the bottom ramp does.
        barb = Part.Face(Part.makePolygon([V(x, SNAP_BARB[0], z) for x, z in
                                           SNAP_BARB_PTS + SNAP_BARB_PTS[:1]]))
        add.append(both_sides(barb.extrude(V(0, SNAP_BARB[1] - SNAP_BARB[0], 0))))
    cover = fuse([cover] + add)
    cut = [box(-8, 8, y1 + COVER_T - 2.5, y1 + COVER_T + 1, -1, 1.2)]   # fingernail notch
    if COVER_CATCH == "snap":
        # An L-shaped slot frees a 2.2 mm spring finger along each side.
        s0, s1 = SNAP_SLOT_X
        cut.append(both_sides(box(s0, s1, SNAP_Y[0], SNAP_Y[1] + 1, -1, COVER_T + 1)))
        cut.append(both_sides(box(s0, x + 1, SNAP_Y[1], SNAP_Y[1] + 1, -1, COVER_T + 1)))
    else:
        for mx, my in MAGNETS:
            cut.append(Part.makeCylinder(MAGNET_R, MAGNET_T + 1, V(mx, my, COVER_T - MAGNET_T)))
    return cover.cut(fuse(cut)).removeSplitter()


# ---------------------------------------------------------------- what goes inside

def components():
    """Rough envelopes of everything that lives in the box, with cable room."""
    iw = W / 2 - WALL
    c = {}
    bw = PR_BEZEL_W / 2
    py0, pyc = PR_Y0 + PR_SHIFT, PR_YC + PR_SHIFT      # the printer as fitted
    c["printer bezel"] = box(-bw, bw, py0, py0 + PR_BEZEL_D, PR_FACE_Z, PLATE_Z0)
    c["printer"] = box(-51.5, 51.5, pyc - 28.5, pyc + 28.5,
                       PLATE_Z0 + 0.01, PLATE_Z0 + PR_EMBED)
    c["printer plugs"] = box(-40, 40, pyc - 22, pyc + 22,
                             PLATE_Z0 + PR_EMBED, PLATE_Z0 + PR_EMBED + 20)
    c["printer clamps"] = both_sides(box(51.5, 58, pyc - 18, pyc + 18,
                                         PLATE_Z1, PLATE_Z1 + 27))
    c["buttons"] = fuse([Part.makeCylinder(7.5, 35, V(x, BTN_Y, WALL)).fuse(
        Part.makeCylinder(11, 3, V(x, BTN_Y, WALL))) for x in button_xs()])
    frame, c["servo rack"], servo = servo_parts()
    c["servo"] = servo.cut(frame)   # it sits in the frame's own mount
    # The hub hangs off the roof's tie stubs, so it follows the roof's pitch.
    d0, hd = TIE_STUB_H, TIE_STUB_H + HUB_H / 2   # top and middle, below the roof
    hy1 = HUB_Y0 + HUB_L
    c["hub"] = under_roof(-HUB_W / 2, HUB_W / 2, HUB_Y0, hy1, d0, d0 + HUB_H)
    c["hub USB-C plugs"] = fuse([under_roof(-HUB_W / 2 - 26, -HUB_W / 2, hy1 - d - 4.5,
                                            hy1 - d + 4.5, hd - 3.5, hd + 3.5)
                                 for d in (40, 49)])
    c["hub USB-A plug"] = under_roof(HUB_W / 2, HUB_W / 2 + 38, hy1 - 73 - 7,
                                     hy1 - 73 + 7, hd - 3.5, hd + 3.5)
    c["hub cable"] = under_roof(-5, 5, hy1, DB - 6, hd - 3, hd + 3)
    by = DB - UNO_STANDOFF
    c["UNO Q"] = box(UNO_X0, UNO_X0 + UNO_W, by - 1.6, by, UNO_Z0, UNO_Z0 + UNO_H)
    c["UNO Q jumpers"] = box(UNO_X0, UNO_X0 + UNO_W, by - 1.6 - 28, by - 1.6,
                             UNO_Z0 + 0.5, UNO_Z0 + UNO_H - 0.5)
    c["UNO Q USB-C plug"] = box(UNO_X0 - 30, UNO_X0, by - 12, by - 1.6,
                                UNO_Z0 + 33, UNO_Z0 + 43)
    mx = iw - MOD_STANDOFF
    c["Modulino"] = box(mx - 1.6 - 7, mx, MOD_Y - MOD_L / 2, MOD_Y + MOD_L / 2,
                        MOD_Z - MOD_H / 2, MOD_Z + MOD_H / 2)
    c["Modulino Qwiic plug"] = box(mx - 1.6 - 6, mx - 1.6, MOD_Y + MOD_L / 2,
                                   MOD_Y + MOD_L / 2 + 10, MOD_Z - 4, MOD_Z + 4)
    c["USB breakout"] = box(BREAKOUT_X[0] + 2, BREAKOUT_X[1] - 2, BREAKOUT_Y[0] - 6,
                            BREAKOUT_Y[1] + 6, WALL, WALL + 12)
    coil_y = DB - SPOOL_L + 5.5
    c["mic cable coil"] = fuse([cyl_y(sx * SPOOL_X, SPOOL_Z, 10.0, coil_y, DB)
                                for sx in (-1, 1)] +
                               [box(-SPOOL_X, SPOOL_X, coil_y, DB,
                                    SPOOL_Z - 10, SPOOL_Z + 10)]).cut(
        fuse([cyl_y(sx * SPOOL_X, SPOOL_Z, 6.2, DB - SPOOL_L, DB + 1) for sx in (-1, 1)]))
    return c


def fit_report(printed, comps, tol=1.0):
    """Report overlaps above tol mm3 between parts and with the printed parts."""
    names = list(comps)
    clashes = []
    pnames = list(printed)
    for i, a in enumerate(pnames):
        for b in pnames[i + 1:]:
            v = printed[a].common(printed[b]).Volume
            if v > tol:
                clashes.append((a, b, v))
    for n in names:
        for pn, p in printed.items():
            v = comps[n].common(p).Volume
            if v > tol:
                clashes.append((n, pn, v))
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if {a, b} <= {"servo rack", "servo"}:
                continue
            v = comps[a].common(comps[b]).Volume
            if v > tol:
                clashes.append((a, b, v))
    # Everything has to be inside the box.
    shell = box(-W / 2, W / 2, -1e3, DB, 0, 1e3)
    for n in names:
        out = comps[n].cut(shell).Volume
        if out > tol:
            clashes.append((n, "outside the box", out))
    return clashes


# ---------------------------------------------------------------- main

def print_pose(name, shape):
    """Move each part into the orientation it prints in, on z = 0."""
    m = App.Matrix()
    if name == "base":
        pass
    elif name == "front":    # front face down: y becomes z
        m.rotateX(math.pi / 2)
    elif name == "side-right":   # outside face down
        m.rotateY(math.pi / 2)
    elif name == "side-left":
        m.rotateY(-math.pi / 2)
    elif name == "back":     # wall side down: z becomes -y
        m.rotateX(-math.pi / 2)
    elif name in ("printer-plate", "cover"):   # upside down: flat face on the bed
        m.rotateX(math.pi)
    else:                    # roof: top down, so the tie stubs point up
        m.rotateX(-math.radians(ROOF_DEG))
        m.rotateX(math.pi)
    mesh = MeshPart.meshFromShape(Shape=shape.transformGeometry(m),
                                  LinearDeflection=0.02, AngularDeflection=0.2)
    b = mesh.BoundBox
    mesh.translate(-(b.XMin + b.XMax) / 2, -(b.YMin + b.YMax) / 2, -b.ZMin)
    return mesh


def make_parts():
    return {"base": make_base(), "front": make_front(),
            "side-left": mirror_x(make_side(False)), "side-right": make_side(True),
            "back": make_back(), "roof": make_roof(),
            "printer-plate": turned(make_plate()), "cover": make_cover()}


def main():
    parts = make_parts()
    for name, shape in parts.items():
        if not shape.isValid() or len(shape.Solids) != 1:
            sys.exit(f"{name}: invalid shape ({len(shape.Solids)} solids)")
        base = os.path.join(HERE, f"birdbox-enclosure-{name}")
        # The rack prints in place inside the front panel's frame.
        out = Part.makeCompound([shape, servo_parts()[1]]) if name == "front" else shape
        out.exportStep(base + ".step")
        # The plate prints the same either way round.
        p = print_pose(name, make_plate() if name == "printer-plate" else out)
        p.write(base + ".stl")
        bb = p.BoundBox
        print(f"{name:13s} {out.Volume / 1000:6.1f} cm3  prints "
              f"{bb.XLength:.0f} x {bb.YLength:.0f} x {bb.ZLength:.0f} mm")

    bb = fuse(list(parts.values())).BoundBox
    print(f"assembled {bb.XLength:.0f} W x {bb.ZLength:.0f} H x {bb.YLength:.0f} D mm")

    clashes = fit_report(parts, components())
    if clashes:
        for a, b, v in clashes:
            print(f"CLASH {a} / {b}: {v:.0f} mm3")
    else:
        print("fit check: no clashes")
    return parts


# freecadcmd runs a script with __name__ set to its file name.
if __name__ in ("__main__", "birdbox-enclosure"):
    main()

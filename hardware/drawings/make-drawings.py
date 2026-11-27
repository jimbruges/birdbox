"""Annotated drawings of the printed bird box, from birdbox-enclosure.py.

Run with FreeCAD's command-line binary from the repo root (macOS path shown):

    /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd -c "exec(open('hardware/drawings/make-drawings.py').read())"

It writes the PNGs next to this script. Cable routes are suggestions.
"""

import importlib.util
import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PolyCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import FreeCAD as App
import Part

OUT = os.path.join(os.getcwd(), "hardware", "drawings")
spec = importlib.util.spec_from_file_location(
    "enc", os.path.join(os.getcwd(), "hardware", "birdbox-enclosure.py"))
enc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(enc)

V = App.Vector
P = enc.make_parts()
P["printer plate"] = P.pop("printer-plate")
C = enc.components()
PCOL = {"base": "#e9cf9b", "front": "#dcb878", "side-left": "#f1dfb8", "side-right": "#f1dfb8",
        "back": "#a9d3a0", "roof": "#c27a5f", "printer plate": "#8fb4dd", "cover": "#e09a8a"}
CCOL = {"printer bezel": "#555", "printer": "#8a8a8a", "printer plugs": "#b0b0b0",
        "printer clamps": "#6d6d6d", "buttons": "#333", "servo rack": "#c9dcef",
        "servo": "#4a6fd1", "hub": "#2b2b2b", "hub USB-C plugs": "#666",
        "hub USB-A plug": "#666", "hub cable": "#666", "UNO Q": "#1f8a8a",
        "UNO Q jumpers": "#9fd8d8", "UNO Q USB-C plug": "#666", "Modulino": "#7b4fb3",
        "Modulino Qwiic plug": "#666", "USB breakout": "#d33", "mic cable coil": "#f0a030"}
Y0, Y1 = enc.HATCH_Y0, enc.HATCH_Y1
DB, FH = enc.DB, enc.FRONT_H
FRAME, RACK, _ = enc.servo_parts()


def T(y, d=14.0):
    """Height of the hub's middle (d below the roof's underside) at depth y."""
    return enc.top(y) - d


def corner(z):
    return (-54, 130, z)


# Suggested cable routes, as 3D polylines: (colour, line style, points).
ROUTES = {
    "USB-C power in (outside -> hub PD port)": ("#d62728", "-", [
        (-28, 160, -12), (-28, 132, 4), (-54, 130, 12), corner(150), (-54, 128, T(128)),
        (-48, 95, T(95)), (-40, 84, T(84))]),
    "Mic USB-C (hub -> spool -> out)": ("#ff9f1c", "-", [
        (-40, 160, -12), (-40, 125, 4), (-40, 122, 28), (40, 122, 28), (52, 122, 40),
        (40, 122, 52), (-40, 122, 52), (-52, 122, 40), (-56, 132, 40), (-56, 132, 150),
        (-56, 126, T(126)), (-48, 90, T(90)), (-40, 75, T(75))]),
    "Hub USB-A -> USB power breakout": ("#c2185b", "-", [
        (51.9, 51, T(51)), (54, 70, T(70) - 2), (55, 70, 50), (55, 95, 45), (50, 108, 20),
        (45, 112, 18), (36, 118, 12)]),
    "Breakout -> printer power": ("#7f1d1d", "-", [
        (26, 116, 12), (24, 100, 22), (30, 88, 70), (28, 76, 81)]),
    "Hub cable -> UNO Q USB-C": ("#1f4fd1", "-", [
        (0, 124, T(124)), (0, 129, T(129) - 3), (-40, 130, 185), (-48, 126, 168),
        (-38, 120, 164), (-24, 120, 164)]),
    "Printer data (TTL) -> UNO Q": ("#2ca02c", "-", [
        (-28, 70, 81), (-40, 86, 84), (-52, 96, 86), (-52, 110, 125), (-18, 114, 145)]),
    "Servo -> UNO Q": ("#8c564b", "-", [(-17, 85, 112), (-17, 100, 122), (-8, 114, 140)]),
    "Buttons -> UNO Q": ("#9467bd", "--", [
        (40, 14.2, 38), (50, 16, 40), (56, 16, 62), (56, 100, 62), (55, 108, 130),
        (40, 114, 150)]),
    "Qwiic UNO Q -> Modulino": ("#17becf", "-", [(40, 124, 176), (48, 127, 165),
                                                 (50, 125, 153)]),
}


# ---------------------------------------------------------------- helpers

def draw_shape(ax, shape, proj, col, alpha=1.0, z=1, tol=0.8):
    """Fill a shape's projection by drawing its triangles."""
    v, f = shape.tessellate(tol)
    if not f:
        return
    v = np.array([proj((p.x, p.y, p.z)) for p in v])
    ax.add_collection(PolyCollection(v[np.array(f)], facecolor=col, edgecolor=col,
                                     linewidth=0.15, alpha=alpha, zorder=z))


def draw_section(ax, shape, normal, d, proj, col, z=3):
    """A printed part cut by a plane: filled, with its outline."""
    wires = shape.slice(normal, d)
    if not wires:
        return
    if not all(w.isClosed() for w in wires):
        # Slicing fails on some imported surfaces: fill a 0.1 mm slab instead.
        n = np.array([normal.x, normal.y, normal.z])
        lo = [-1e3 if c == 0 else d - 0.05 for c in n]
        hi = [1e3 if c == 0 else d + 0.05 for c in n]
        slab = enc.box(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])
        cut = shape.common(slab)
        draw_shape(ax, cut, proj, col, z=z, tol=0.15)
        for e in cut.Edges:
            pts = np.array([proj((p.x, p.y, p.z)) for p in e.discretize(Deflection=0.05)])
            if abs(np.dot(np.array(e.BoundBox.Center) - 0, n) - d) < 0.06:
                ax.plot(pts[:, 0], pts[:, 1], color="#222", lw=0.5, zorder=z + 0.1)
        return
    try:
        draw_shape(ax, Part.makeFace(wires, "Part::FaceMakerBullseye"), proj, col, z=z, tol=0.15)
    except Exception as e:
        print("section not filled:", e)
    for w in wires:
        pts = np.array([proj((p.x, p.y, p.z)) for p in w.discretize(Deflection=0.05)])
        ax.plot(pts[:, 0], pts[:, 1], color="#222", lw=0.7, zorder=z + 0.1)


def outline(ax, shape, proj, col, alpha=0.35, z=2):
    draw_shape(ax, shape, proj, col, alpha, z=z, tol=1.0)


def routes(ax, proj, only=None, z=6):
    for name, (col, ls, pts) in ROUTES.items():
        if only and name not in only:
            continue
        p = np.array([proj(q) for q in pts])
        ax.plot(p[:, 0], p[:, 1], color=col, ls=ls, lw=2.6, zorder=z, solid_capstyle="round")
        ax.plot(p[-1, 0], p[-1, 1], "o", color=col, ms=6, zorder=z + 0.1, mec="white", mew=1)


def dim(ax, a, b, text, off=(0, 0), col="#b00020", fs=8.5, ha="center", rot=0):
    ax.annotate("", xy=b, xytext=a, zorder=9, arrowprops=dict(
        arrowstyle="<|-|>", color=col, lw=1.1, shrinkA=0, shrinkB=0, mutation_scale=8))
    if text:
        m = ((a[0] + b[0]) / 2 + off[0], (a[1] + b[1]) / 2 + off[1])
        ax.text(*m, text, color=col, fontsize=fs, ha=ha, va="center", rotation=rot, zorder=10,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))


def note(ax, xy, text, col="#b00020", fs=8, **kw):
    ax.text(*xy, text, color=col, fontsize=fs, zorder=10, **kw)


def lab(ax, xy, text, xytext, fs=9, bold=False):
    ax.annotate(text, xy=xy, xytext=xytext, fontsize=fs, va="center", zorder=11,
                fontweight="bold" if bold else "normal",
                arrowprops=dict(arrowstyle="-", color="#444", lw=0.7, shrinkA=2, shrinkB=1),
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#bbb", lw=0.5, alpha=0.95))


def finish(ax, fig, title, sub, name, legend_routes=True):
    ax.set_aspect("equal")
    ax.grid(True, color="#eee", lw=0.5, zorder=0)
    ax.tick_params(labelsize=7)
    sw = textwrap.fill(sub, 140)
    ax.text(0, 1.005, sw, transform=ax.transAxes, fontsize=9.5, color="#444", va="bottom")
    ax.annotate(title, xy=(0, 1.005), xycoords="axes fraction",
                xytext=(0, 13 * (sw.count("\n") + 1) + 5), textcoords="offset points",
                fontsize=16, fontweight="bold", va="bottom")
    h = [Patch(fc=c, ec="#222", label=f"printed: {n}") for n, c in PCOL.items()]
    if legend_routes:
        h += [Line2D([0], [0], color=c, ls=ls, lw=2.5, label=n)
              for n, (c, ls, _) in ROUTES.items()]
    ax.legend(handles=h, fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1), framealpha=0.95)
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def side(p):
    return (p[1], p[2])


def front(p):
    return (p[0], p[2])


def below(p):
    return (p[0], -p[1])


# ---------------------------------------------------------------- 1. side section

SX = enc.button_xs()[-2] if enc.BUTTONS == 4 else enc.button_xs()[-1]
fig, ax = plt.subplots(figsize=(17, 15))
for n, s in C.items():
    outline(ax, s, side, CCOL[n], alpha=0.6 if n == "servo rack" else 0.45)
for n, s in P.items():
    draw_section(ax, s, V(1, 0, 0), SX, side, PCOL[n])
routes(ax, side)
ry0 = RACK.BoundBox.YMin
lab(ax, (60, 40), "CSN-A2 printer, face down\n(103 x 57 body, 50 deep)", (-60, 55), bold=True)
lab(ax, (60, 72), "printer plugs: power + TTL\n(keep 20 mm above)", (-60, 80))
lab(ax, (60, 30), "fixing blocks (clamps),\nbehind this section", (-60, 30))
lab(ax, (14.2, 30), "push button, nut inside,\n35 mm deep incl. push-on tabs", (-60, 5))
lab(ax, (55, 100), "servo frame: part of the front panel,\nrack prints in place inside it",
    (-60, 115), bold=True)
lab(ax, (66, 95), "FS90R servo", (-60, 98))
lab(ax, (67, T(67)), "USB hub, zip-tied up to two\nstubs under the roof", (-60, 198), bold=True)
lab(ax, (enc.TIE_Y[0], enc.top(enc.TIE_Y[0]) - 3), "tie stubs: 5.5 x 2.2 tunnel\nfor a 4.8 mm tie",
    (-60, 222))
lab(ax, (126, 150), "UNO Q on 8 mm standoffs,\nheaders face forward", (160, 160), bold=True)
lab(ax, (111, 150), "28 mm for jumper wires", (160, 140))
lab(ax, (enc.MOD_Y, enc.MOD_Z), "Modulino Buzzer on the right side\n(behind this section),"
    " 14.5 from\nthe back for a short Qwiic cable", (160, 120))
lab(ax, (120, 9), "USB power breakout,\ncable-tied to the floor", (160, 20), bold=True)
lab(ax, (124, 40), "spare mic cable wound\non two spool posts", (160, 45), bold=True)
lab(ax, (137, 3), "cable notches in the bottom\nof the back plate", (160, -8))
lab(ax, (137, FH + 5), "keyhole for the wall screw", (160, FH + 5))
lab(ax, (1.5, 175), "64 mm bird hole in the 3 mm\nfront wall: no collar", (-60, 165))
lab(ax, (60, 7), "base tray", (85, 30))
lab(ax, (enc.COVER_SLOT_Y, 0), "paper slot (in the cover)", (35, -14))
lab(ax, (70, 1.5), "flush base cover", (85, -14))
dim(ax, (40, 81.3), (40, 89.2), "7.9 plugs -> servo frame", off=(14, 0), ha="left")
dim(ax, (64, 81.3), (64, 84.4), "3.1 to servo", off=(14, -4), ha="left")
dim(ax, (enc.TIE_Y[1], enc.top(enc.TIE_Y[1]) - enc.TIE_STUB_H), (enc.TIE_Y[1], enc.top(enc.TIE_Y[1])),
    "%.0f" % enc.TIE_STUB_H, off=(3, 0), ha="left")
dim(ax, (8, enc.HOLE_Z + enc.HOLE_D / 2), (8, enc.top(8) - enc.TIE_STUB_H - enc.HUB_H),
    "4.9 hole -> hub", off=(3, 4), ha="left")
dim(ax, (104, 121.6), (104, 126.5), "4.9 frame -> jumpers", off=(3, -6), ha="left")
dim(ax, (25.2, 6), (27.4, 6), "2.2", off=(0, 7))
dim(ax, (108, 14.3), (106.25, 14.3), "")
note(ax, (104, 17.5), "1.7 breakout\n-> plate", fs=7.5, ha="right")
dim(ax, (enc.SLOT_Y, -5), (enc.COVER_SLOT_Y, -5), "%.0f behind the base's slot" % enc.COVER_SLOT_DY, off=(0, -4))
dim(ax, (0, 122), (ry0, 122), "%.1f arm tip behind\nthe face, retracted" % ry0, off=(4, -9),
    ha="left")
dim(ax, (-4, 0), (-4, FH), "front wall %.0f" % FH, off=(-3, 0), ha="right", rot=90)
dim(ax, (0, -22), (DB + enc.BACK_T, -22), "%.0f deep (body 135 + back 4)" % (DB + enc.BACK_T),
    off=(0, -4))
ax.set_xlim(-75, 210)
ax.set_ylim(-32, 240)
finish(ax, fig, "1  Side section",
       f"Cut through the box at x = {SX:+.1f} (through a button, the printer and the hub), seen "
       "from the right side; front of the box on the left. Solid colour = printed part in "
       "section, pale fill = component envelope (whole part, projected). Dimensions in mm, "
       "red = gap / clearance. Cable routes are suggestions.", "1-side-section.png")

# ---------------------------------------------------------------- 2. front section

SY = 60.0
fig, ax = plt.subplots(figsize=(16, 15))
behind = ("UNO Q jumpers", "UNO Q", "UNO Q USB-C plug", "mic cable coil", "USB breakout")
for n in ["UNO Q jumpers", "UNO Q", "UNO Q USB-C plug", "hub cable", "mic cable coil",
          "USB breakout", "servo rack", "servo", "printer plugs", "printer",
          "printer clamps", "printer bezel", "hub", "hub USB-C plugs", "hub USB-A plug",
          "Modulino", "Modulino Qwiic plug"]:
    outline(ax, C[n], front, CCOL[n], alpha=0.25 if n in behind else 0.5)
for n, s in P.items():
    if n != "back":
        draw_section(ax, s, V(0, 1, 0), SY, front, PCOL[n])
routes(ax, front)
lab(ax, (0, 35), "CSN-A2 printer (103 wide)", (-125, 40), bold=True)
lab(ax, (55, 28), "fixing blocks either side", (75, 28))
lab(ax, (0, 8), "printer bezel 111 wide, in a 111.8 pocket", (-125, 18))
lab(ax, (0, 12.8), "printer plate (screws to 4 bosses)", (75, 8))
lab(ax, (0, 1.5), "base cover", (-125, -10))
lab(ax, (0, 99), "servo frame (part of the front panel;\nits flange is 87 wide)", (-125, 110),
    bold=True)
lab(ax, (-17, 100), "servo", (-125, 95))
lab(ax, (49.7, 153), "Modulino Buzzer (further back),\n5 mm standoffs, grille\n"
    "through the side", (75, 150), bold=True)
lab(ax, (60.5, 100), "side panel, 3 thick", (75, 100))
lab(ax, (57.5, 1.5), "base tray", (75, -8))
lab(ax, (0, T(SY)), "hub (28 wide), zip-tied up to\nstubs under the roof", (-125, 210),
    bold=True)
lab(ax, (-27, T(80)), "USB-C plugs:\nPD power in + mic", (-125, 190))
lab(ax, (33, T(51)), "USB-A plug -> breakout", (75, 205))
lab(ax, (10, 150), "UNO Q (on the back plate,\nbehind)", (75, 125))
lab(ax, (-61, enc.VENT_Z[0] + 1.5), "side vents", (-125, 170))
lab(ax, (-30, 40), "spare mic cable on spools (back plate)", (-125, 60))
dim(ax, (51.5, 50), (59, 50), "7.5", off=(0, 3))
dim(ax, (58, 36), (59, 36), "")
note(ax, (60, 33), "1.0 block -> wall")
dim(ax, (55.5, 6), (55.9, 6), "")
note(ax, (57, 3.2), "0.4")
dim(ax, (-59, 13), (-58.6, 13), "")
note(ax, (-57.8, 15.5), "0.4 plate -> wall")
dim(ax, (51.9, T(51)), (59, T(51)), "7.1", off=(0, 5))
dim(ax, (-59, T(80)), (-39.9, T(80)), "19.1 for the C cables", off=(0, 5))
dim(ax, (46.3, 120), (59, 120), "12.7 cable corridor", off=(0, 4))
dim(ax, (-59, 120), (-46.3, 120), "12.7 cable corridor", off=(0, 4))
dim(ax, (-62, -12), (62, -12), "124 wide (138 with the roof)", off=(0, -4))
dim(ax, (-20, 81.3), (-20, 89.2), "7.9", off=(-4, 0), ha="right")
ax.set_xlim(-130, 130)
ax.set_ylim(-22, 240)
finish(ax, fig, "2  Front section",
       f"Cut across the box at y = {SY:.0f} mm from the front (through the printer, the servo and "
       "the servo frame), seen from the front. Solid colour = printed part in section; pale fill = "
       "component envelope (whole part, projected, including the UNO Q on the back plate). "
       "Red = clearance in mm.", "2-front-section.png")

# ---------------------------------------------------------------- 3. base from below

fig, ax = plt.subplots(figsize=(15, 14))
for n in ("printer bezel", "USB breakout", "buttons"):
    outline(ax, C[n], below, CCOL[n], alpha=0.18)
draw_section(ax, P["printer plate"], V(0, 0, 1), 12.8, below, "#cfe0f2", z=1.5)
for n in ("base", "front", "side-left", "side-right"):
    draw_section(ax, P[n], V(0, 0, 1), 1.5, below, PCOL[n])
draw_section(ax, P["cover"], V(0, 0, 1), 1.5, below, PCOL["cover"])
for x0, x1 in enc.TONGUES:
    a, b = min(x0, x1), max(x0, x1)
    ax.add_patch(plt.Rectangle((a, -(Y0 + 0.7)), b - a, 5.5, fill=False, ec="#a33", ls="--",
                               lw=1.2, zorder=8))
    ax.add_patch(plt.Rectangle((a - 0.4, -(Y0 + 0.1)), b - a + 0.8, 5.5, fill=False, ec="#555",
                               ls=":", lw=1.0, zorder=8))
for x, y in enc.PLATE_SCREWS:
    ax.add_patch(plt.Circle((x, -y), 1.7, fill=False, ec="#1f4fd1", lw=1.2, zorder=8))
bx = enc.button_xs()
lab(ax, (bx[0], -enc.BTN_Y), "%d x 16.2 holes for 16 mm buttons\n(0.1 per side)" % enc.BUTTONS,
    (-120, -5), bold=True)
lab(ax, (-20, -enc.COVER_SLOT_Y), "paper slot in the cover, 80 x 4.5, serrated\n"
    "both edges (2.5 clear); its lip fills the base's slot", (-120, -38), bold=True)
lab(ax, (-30, -70), "base cover, flush", (-120, -70), bold=True)
lab(ax, (48, -(Y0 - 2)), "tongue (dashed) hooks into\na 12.8 x 1.5 tunnel (dotted)", (70, -60))
if enc.COVER_CATCH == "snap":
    lab(ax, (54.5, -80), "spring finger: a 1 mm slot frees\n2.2 mm of the cover's edge;\n"
        "its barb clicks into a groove\nin the side of the hatch", (70, -88), bold=True)
    lab(ax, (-54.5, -80), "same on this side", (-120, -88))
lab(ax, (0, -(Y1 + 2)), "fingernail notch: pull down here,\nthen slide the cover back",
    (-120, -120), bold=True)
lab(ax, (-55.5, -(enc.PR_Y0 - 2.65)), "printer plate screws (M3 x 10,\nfrom inside)", (-120, -15))
lab(ax, (-25, -115), "floor vents", (-120, -100))
lab(ax, (30, -120), "breakout cable-tie slots\n(2.5 x 4)", (70, -128))
note(ax, (-120, -146), "pale blue = printer plate above, grey = printer bezel and buttons",
     col="#111")
dim(ax, (bx[1], -enc.BTN_Y - 13), (bx[2], -enc.BTN_Y - 13), "26.7 pitch")
dim(ax, (66, 0), (66, -enc.BTN_Y), "14.2 to button centres", off=(2, 0), ha="left")
dim(ax, (66, -enc.SLOT_Y), (66, -enc.COVER_SLOT_Y), "%.0f: cover slot behind the base's" % enc.COVER_SLOT_DY,
    off=(2, 0), ha="left")
dim(ax, (64, 0), (64, -enc.COVER_SLOT_Y), "")
note(ax, (68, -enc.COVER_SLOT_Y - 4), "%.1f front edge to slot centre" % enc.COVER_SLOT_Y)
dim(ax, (-40, -enc.COVER_SLOT_Y + 8), (40, -enc.COVER_SLOT_Y + 8), "80")
note(ax, (58, -55), "0.3 gap each side", rotation=90, va="center")
note(ax, (0, -(Y1 + 7.5)), "0.3 gap, bevelled", ha="center")
dim(ax, (-62, -140), (62, -140), "124", off=(0, -4))
ax.text(-62, 4, "FRONT OF THE BOX", fontsize=10, fontweight="bold")
ax.set_xlim(-125, 125)
ax.set_ylim(-150, 8)
finish(ax, fig, "3  Base from underneath",
       "Looking up at the base with the front of the box at the top (left and right as you face "
       "the box). Section through the floor; the cover is in place. Red = clearance in mm.",
       "3-base-from-below.png", legend_routes=False)

# ---------------------------------------------------------------- 4. back plate

fig, ax = plt.subplots(figsize=(15, 16))
draw_section(ax, P["back"], V(0, 1, 0), DB + 2.0, front, PCOL["back"])
draw_section(ax, P["back"], V(0, 1, 0), DB - 3.0, front, "#5f9f5a", z=4)
draw_section(ax, P["back"], V(0, 1, 0), DB - enc.SPOOL_L + 0.7, front, "#3f7f3a", z=3.5)
for n in ("UNO Q", "UNO Q USB-C plug", "mic cable coil", "USB breakout", "hub cable"):
    draw_shape(ax, C[n], front, CCOL[n], 0.3, z=4.6, tol=1.0)
routes(ax, front, only=[k for k in ROUTES
                        if k.startswith(("USB-C power", "Mic", "Hub cable", "Hub USB-A"))])
lab(ax, (10, 152), "UNO Q, component side towards you,\nUSB-C on the left; M3 x 8 into\n"
    "8 mm standoffs (pilot 2.5)", (75, 150), bold=True)
lab(ax, (-39, 164), "UNO Q USB-C plug\n(hub's own cable)", (-120, 175))
lab(ax, (0, FH + 5), "keyhole: head in at 9.5,\nslides up onto a 4.5 slot", (75, 212), bold=True)
lab(ax, (-40, 40), "spool posts 12 dia, 20 dia lip,\n28 long: wind the spare mic\n"
    "cable round both", (-120, 60), bold=True)
lab(ax, (-40, 4), "mic cable notch", (-120, 10))
lab(ax, (-28, 4), "power cable notch", (-120, -6))
lab(ax, (54, 7.5), "M3 x 12 countersunk: low ones\ninto the base, high ones into\n"
    "bosses on the side panels", (75, 20))
lab(ax, (-54, 110), "mic + power up the back-left\ncorner to the hub", (-120, 120))
lab(ax, (30, 12), "USB power breakout\n(on the floor, in front)", (75, 45))
dim(ax, (-40, 26), (40, 26), "80 between post centres", off=(0, -4))
dim(ax, (-43.5, -6), (-36.5, -6), "7", off=(0, -3))
dim(ax, (-46, 0), (-46, 9), "9", off=(-3, 0), ha="right")
dim(ax, (-24, 122), (44.6, 122), "68.6 (UNO Q)", off=(0, -3))
dim(ax, (-62, -18), (62, -18), "124", off=(0, -4))
dim(ax, (66, 0), (66, enc.top(DB)), "%.0f" % enc.top(DB), off=(3, 0), ha="left")
ax.set_xlim(-125, 125)
ax.set_ylim(-28, 235)
finish(ax, fig, "4  Back plate, inside face",
       "Seen from the front of the box with the other panels removed. Light green = plate; darker = "
       "standoffs, bosses and spool posts. Pale fills = UNO Q, coiled mic cable, breakout. "
       "Lines = cable routes.", "4-back-plate.png")

# ---------------------------------------------------------------- 5. cover detail + fits

fig = plt.figure(figsize=(17, 22))
gs = fig.add_gridspec(4, 1, height_ratios=[1, 1, 1.1, 1.3], hspace=0.3)


def detail_side(ax, xs):
    for n in ("printer bezel", "printer", "buttons"):
        outline(ax, C[n], side, CCOL[n], alpha=0.25)
    for n in ("base", "front", "printer plate", "cover"):
        draw_section(ax, P[n], V(1, 0, 0), xs, side, PCOL[n])
    ax.set_xlim(0, 115)
    ax.set_ylim(-6, 20)
    ax.set_aspect("equal")
    ax.grid(True, color="#eee", lw=0.5)
    ax.tick_params(labelsize=7)
    ax.text(1, -5.3, "<- front", fontsize=9)


tx = (enc.TONGUES[1][0] + enc.TONGUES[1][1]) / 2 - 2
ax = fig.add_subplot(gs[0])
detail_side(ax, tx)
lab(ax, (Y0 - 2, 2.4), "tongue 1.2 thick, 5.5 long,\nin a 1.5 tunnel: 0.15 above and "
    "below,\n0.6 at the tip", (12, 13), bold=True)
lab(ax, (Y1 + 1.5, 1.5), "45 deg bevel (prints without a bridge);\n0.3 gap", (100, -3))
lab(ax, (70, 1.5), "cover 3.0", (60, -4))
lab(ax, (70, 7.5), "printer bezel", (60, 15.5))
lab(ax, (70, 12.8), "printer plate 3.0", (75, 18))
lab(ax, (32, 7), "plate's block, at the front with the\nplate turned: rests on the floor pad,\n"
    "so the plate sits about 1.1 high", (98, 13))
dim(ax, (66, 3.0), (66, 4.3), "")
note(ax, (64.5, 3.6), "1.3 air gap", fs=8.5, ha="right", va="center")
dim(ax, (Y0, 0.6), (Y0 + 0.2, 0.6), "")
note(ax, (Y0 + 0.6, -0.9), "0.2", fs=8.5)
ax.set_title(f"5a  Cover front, side section at x = {tx:+.0f} (through a tongue)", loc="left",
             fontsize=13, fontweight="bold")

ax = fig.add_subplot(gs[1])
detail_side(ax, 0.3)
lab(ax, (enc.SLOT_Y - enc.SLOT_GAP / 2 - 0.5, 2), "base's old slot edge (plain)", (5, 12), bold=True)
lab(ax, (42.5, 1.5), "cover lip fills the old slot", (58, -4.5))
lab(ax, (Y1 + 2, 0.6), "fingernail notch, 16 wide", (100, -3))
lab(ax, (enc.COVER_SLOT_Y, 1.5), "paper comes out here: cover slot,\n2.5 clear, serrated both edges", (40, 15.5))
lab(ax, (enc.PR_Y0 - 2, 3.7), "4.2 floor pad under the\nfront of the bezel", (2, 16))
dim(ax, (enc.SLOT_Y, -2), (enc.COVER_SLOT_Y, -2), "%.0f (measured)" % enc.COVER_SLOT_DY, off=(0, -1.2), fs=8)
dim(ax, (enc.COVER_SLOT_Y - 2.25, 5.6), (enc.COVER_SLOT_Y + 2.25, 5.6), "4.5", off=(0, 0.8), fs=8)
ax.set_title("5b  Paper slot, side section at x = 0 (through the slot and the fingernail notch)",
             loc="left", fontsize=13, fontweight="bold")

ax = fig.add_subplot(gs[2])
by = (enc.SNAP_BARB[0] + enc.SNAP_BARB[1]) / 2
for n in ("base", "side-right", "printer plate", "cover"):
    draw_section(ax, P[n], V(0, 1, 0), by, front, PCOL[n])
outline(ax, C["printer bezel"], front, CCOL["printer bezel"], alpha=0.25)
px = enc.POCKET_X
s0, s1 = enc.SNAP_SLOT_X
lab(ax, ((s1 + px - 0.3) / 2, 1.5), "spring finger 2.2 wide, 26 long\n(free at the back end)",
    (36, 7), bold=True)
lab(ax, (px + 0.3, 1.6), "barb 0.8 proud, 45 deg ramps both ways", (60, 7), bold=True)
lab(ax, (px + 0.6, 2.4), "groove in the hatch side,\n0.8 deep, 1.4 tall, 10 long", (60, 4.5))
lab(ax, ((s0 + s1) / 2, 0.5), "1 mm slot: room for the finger\nto flex 0.5 in", (36, -2.5))
note(ax, (62.5, -1.2), "closing: the top ramp pushes the finger in and it clicks out into the "
     "groove.\nopening: pull the back down; the bottom ramp pushes it in and it lets go.",
     col="#111", fs=8.5)
dim(ax, (px - 0.3, -0.6), (px, -0.6), "")
note(ax, (px + 0.2, -1.2), "0.3", fs=8)
ax.set_xlim(35, 75)
ax.set_ylim(-3.5, 9)
ax.set_aspect("equal")
ax.grid(True, color="#eee", lw=0.5)
ax.tick_params(labelsize=7)
ax.set_title(f"5c  Snap catch, front section at y = {by:.0f} (right side; the left mirrors it)",
             loc="left", fontsize=13, fontweight="bold")

ax = fig.add_subplot(gs[3])
ax.axis("off")
rows = [
    ("Fit", "Part", "Printed", "Clearance"),
    ("Push button", "16 mm thread", "16.2 hole", "0.1 per side"),
    ("Printer bezel in base pocket", "111 x 65", "111.8 x 65.8", "0.4 per side"),
    ("Printer body in plate cutout", "103 x 57", "103.6 x 57.6", "0.3 per side"),
    ("Fixing blocks to side panels", "printer 103 wide", "118 inside", "7.5 per side (blocks ~6.5)"),
    ("Printer plate to side panels", "", "117.2 wide", "0.4 per side"),
    ("Cover in hatch", "", "", "0.3 sides, 0.2 front, 0.3 back"),
    ("Cover to printer face", "", "", "1.3 air gap (door can't rub)"),
    ("Cover tongues in tunnels", "12 x 1.2 x 5.5", "12.8 x 1.5 x 5.5",
     "0.4 sides, 0.15 top/bottom, 0.6 tip"),
    ("Snap barb in groove", "0.8 proud, 1.6 tall", "0.8 deep, 1.4 tall",
     "0.5 interference to click past"),
    ("Snap finger slot", "finger flexes 0.5", "1.0 slot", "0.5 spare"),
    ("M3 self-tapping pilot", "M3", "2.5 dia", "bite into plastic"),
    ("M3 clearance / countersink", "M3", "3.4 / 6.6 dia", "0.2 per side"),
    ("Keyhole", "screw 4-4.5 shank, head <= 9", "9.5 hole, 4.5 slot, 10 travel", "0.25 on the head"),
    ("Cable notches (back plate)", "USB-C cable ~4 dia", "7 wide x 9 high", "room for two passes"),
    ("Panel joints", "M3 x 10 countersunk", "3 into each front strip, 2 into each base side",
     "panels butt, 0 gap"),
    ("Breakout tie slots / hub tie tunnels", "ties <= 2.5 / 4.8 wide", "2.5 x 4 / 5.5 x 2.2", ""),
    ("Servo rack in frame (print in place)", "", "", "0.14 minimum: organic supports"),
    ("Printer plugs to servo frame", "", "", "7.9 (3.1 to the servo body)"),
    ("Hub to roof", "16 tall", "", "6 tie stubs; 4.9 above the bird hole"),
    ("Hub USB-A plug to right wall", "38 incl. plug", "", "7.1: use a short or right-angle plug"),
    ("UNO Q jumpers to hub / servo frame", "28 deep", "", "19 / 4.9"),
    ("Modulino Qwiic plug to back plate", "", "", "14.5 for plug and bend"),
]
t = ax.table(cellText=rows[1:], colLabels=rows[0], loc="upper center", cellLoc="left",
             colWidths=[0.28, 0.2, 0.22, 0.3])
t.auto_set_font_size(False)
t.set_fontsize(10)
t.scale(1, 1.55)
for (r, c), cell in t.get_celld().items():
    cell.set_edgecolor("#ccc")
    if r == 0:
        cell.set_facecolor("#333")
        cell.set_text_props(color="white", fontweight="bold")
    elif r % 2 == 0:
        cell.set_facecolor("#f6f6f6")
ax.set_title("5d  Fits and tolerances (mm). Tuned for a 0.4 mm nozzle; if your printer prints "
             "holes tight, open the 0.1-0.15 fits first.", loc="left", fontsize=13,
             fontweight="bold")
path = os.path.join(OUT, "5-cover-and-fits.png")
fig.savefig(path, dpi=130, bbox_inches="tight")
plt.close(fig)
print("wrote", path)

# ---------------------------------------------------------------- 6. exploded panels

EYE = np.array([0.62, -0.78, 0.55])
EYE /= np.linalg.norm(EYE)
SR = np.cross(-EYE, [0, 0, 1.0])
SR /= np.linalg.norm(SR)
SU = np.cross(SR, -EYE)
LIGHT = np.array([0.3, -0.6, 0.75])
LIGHT /= np.linalg.norm(LIGHT)
EXPLODE = {"base": (0, 0, -45), "front": (0, -75, 0), "side-left": (-75, 0, 0),
           "side-right": (75, 0, 0), "back": (0, 70, 0), "roof": (0, 0, 55),
           "printer plate": (0, 0, -22), "cover": (0, 0, -75)}


def iso(p):
    p = np.asarray(p, float)
    return np.array([p @ SR, p @ SU])


fig, ax = plt.subplots(figsize=(17, 17))
polys, cols, depth = [], [], []
shapes = dict(P)
shapes["front"] = Part.makeCompound([P["front"], RACK])
# The tie stubs under the roof can't be depth-sorted against its top: leave them out here.
tie_y, enc.TIE_Y = enc.TIE_Y, ()
shapes["roof"] = enc.make_roof()
enc.TIE_Y = tie_y
for n, s in shapes.items():
    off = np.array(EXPLODE[n], float)
    v, f = s.tessellate(0.6)
    v = np.array([(q.x, q.y, q.z) for q in v]) + off
    f = np.array(f)
    tri = v[f]
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(nrm, axis=1)
    keep = ln > 1e-9
    tri, nrm = tri[keep], nrm[keep] / ln[keep][:, None]
    # Only the faces turned towards us, cut small so the depth sort works.
    front_facing = nrm @ EYE > 0
    tri, nrm = tri[front_facing], nrm[front_facing]
    for _ in range(8):
        e = np.max(np.linalg.norm(tri - np.roll(tri, 1, axis=1), axis=2), axis=1)
        big = e > 6.0
        if not big.any():
            break
        t, nb = tri[big], nrm[big]
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
        sub = np.concatenate([np.stack(q, axis=1) for q in
                              ((a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca))])
        tri = np.concatenate([tri[~big], sub])
        nrm = np.concatenate([nrm[~big], np.tile(nb, (4, 1))])
    shade = 0.55 + 0.45 * np.abs(nrm @ LIGHT)
    base = np.array(matplotlib.colors.to_rgb(PCOL[n]))
    polys.append(np.stack([tri @ SR, tri @ SU], axis=2))
    cols.append(np.clip(base[None, :] * shade[:, None], 0, 1))
    depth.append(tri.mean(axis=1) @ EYE)
polys, cols, depth = np.concatenate(polys), np.concatenate(cols), np.concatenate(depth)
order = np.argsort(depth)
ax.add_collection(PolyCollection(polys[order], facecolors=cols[order], edgecolors=cols[order],
                                 linewidths=0.2, zorder=2))
ax.autoscale_view()


def at(n, p):
    return tuple(iso(np.array(p, float) + np.array(EXPLODE[n], float)))


iw = enc.W / 2 - enc.WALL
lab(ax, at("front", (-40, 0, 60)), "front panel: bird hole, servo frame\nand rack (prints in "
    "place), strips\nfor the side screws", (-230, 150), bold=True)
lab(ax, at("side-right", (enc.W / 2, 60, 120)), "right side: Modulino Buzzer\nand grille, "
    "roof rail,\nboss for the back plate", (178, 175), bold=True)
lab(ax, at("side-left", (-enc.W / 2, 10, 20)), "left side (mirror,\nno Modulino)", (-230, 30),
    bold=True)
lab(ax, at("base", (-40, 60, 1.5)), "base tray: buttons, hatch,\npaper slot, side blocks for "
    "the\nprinter plate and side screws", (-230, -75), bold=True)
lab(ax, at("printer plate", (0, 60, 14)), "printer plate", (120, -10))
lab(ax, at("cover", (30, 60, 0)), "base cover (snaps in)", (120, -105))
lab(ax, at("back", (40, enc.DB + 4, 200)), "back plate: UNO Q, spool,\nkeyhole", (178, 255),
    bold=True)
lab(ax, at("roof", (30, 120, enc.top(120) + 4)), "roof, hub tie stubs\nunderneath", (178, 320),
    bold=True)
for y, z in enc.SIDE_SCREWS:
    q = at("side-right", (enc.W / 2, y, z))
    ax.plot(*q, "o", ms=7, mfc="none", mec="#b00020", mew=1.6, zorder=8)
note(ax, (178, 110), "o = side screws, M3 x 10 countersunk:\n3 into each front strip, 2 into "
     "each\nside of the base (same on the left)", fs=9)
ax.set_aspect("equal")
ax.axis("off")
sub = ("Exploded view from the front right. Each panel prints flat: the base right way up, the "
       "sides outside face down, the front face down with the servo frame up (organic "
       "supports for the rack), the roof top down so its tie stubs point up.")
sw = textwrap.fill(sub, 140)
ax.text(0, 1.005, sw, transform=ax.transAxes, fontsize=9.5, color="#444", va="bottom")
ax.annotate("6  How the panels go together", xy=(0, 1.005), xycoords="axes fraction",
            xytext=(0, 13 * (sw.count("\n") + 1) + 5), textcoords="offset points",
            fontsize=16, fontweight="bold", va="bottom")
path = os.path.join(OUT, "6-exploded-panels.png")
fig.savefig(path, dpi=130, bbox_inches="tight")
plt.close(fig)
print("wrote", path)

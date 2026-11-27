import sys, os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(__file__))
from steps import STEPS

D = "/private/var/folders/1m/xl9j3tqn1wgblzhtvy1gqclm0000gn/T/solidcraft-mcp-23528-17346248"
OUT = sys.argv[1]
ONLY = [int(k) for k in sys.argv[2].split(",")] if len(sys.argv) > 2 else None
TOTAL = len(STEPS)
COUNT = dict(s_plate=4, s_sideR=5, s_sideL=5, s_roof=4, s_back=4, s_uno=4, s_mod=4)

AV = "/System/Library/Fonts/Avenir Next.ttc"
def font(size, bold=False):
    return ImageFont.truetype(AV, size, index=2 if bold else (7 if size >= 27 else 5))
F_TITLE, F_NUM, F_LAB, F_LABB, F_TXT, F_SMALL = font(46, True), font(60, True), font(24), font(24, True), font(27), font(21, True)
INK, MUTED, ACCENT, SCREW, PATH = (30, 34, 40), (90, 96, 106), (31, 79, 209), (214, 110, 20), (31, 79, 209)


def projector(cam, W=1920, H=1080):
    T = np.array(cam["target"], float); y, p = cam["yaw"], cam["pitch"]
    e = np.array([-math.cos(p) * math.sin(y), -math.cos(p) * math.cos(y), math.sin(p)])
    r = np.cross([0, 0, 1.0], e); r /= np.linalg.norm(r); u = np.cross(e, r)
    s = H / (0.8 * cam["distance"])
    def proj(P):
        d = np.asarray(P, float) - T
        return (W / 2 + s * (d @ r), H / 2 - s * (d @ u))
    return proj


def rbox(dr, xy, fill, outline=None, w=2, r=12):
    dr.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=w)


def dashed(dr, a, b, col, w=3, dash=12, gap=8):
    (x0, y0), (x1, y1) = a, b
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 1: return
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    t = 0
    while t < L:
        t2 = min(t + dash, L)
        dr.line([(x0 + ux * t, y0 + uy * t), (x0 + ux * t2, y0 + uy * t2)], fill=col, width=w)
        t = t2 + gap
    # arrowhead at b
    ang = math.atan2(uy, ux); h = 16
    pts = [(x1, y1), (x1 - h * math.cos(ang - 0.4), y1 - h * math.sin(ang - 0.4)),
           (x1 - h * math.cos(ang + 0.4), y1 - h * math.sin(ang + 0.4))]
    dr.polygon(pts, fill=col)


def text_size(dr, txt, f):
    b = dr.multiline_textbbox((0, 0), txt, font=f, spacing=6)
    return b[2] - b[0], b[3] - b[1]


for st in STEPS:
    n = st["n"]
    if ONLY and n not in ONLY: continue
    src = f"{D}/asm-{n:02d}/frame-0002.png"
    im = Image.open(src).convert("RGBA")
    dr = ImageDraw.Draw(im, "RGBA")
    proj = projector(st["cam"])
    mv = st["moves"]

    def at(occ, p):
        return proj(np.add(p, mv.get(occ, (0, 0, 0))) if occ else p)

    # travel paths
    for occ, p in st["paths"]:
        if occ not in mv: continue
        a, b = at(occ, p), proj(p)
        dashed(dr, a, b, PATH + (200,))

    # labels
    for txt, occ, p, off, kind in st["labels"]:
        ax, ay = at(occ, p)
        label = (f"{COUNT[occ]} ×  " + txt) if kind == "screw" and occ in COUNT else txt
        f = F_LABB if kind == "screw" else F_LAB
        tw, th = text_size(dr, label, f)
        bx, by = ax + off[0], ay + off[1]
        x0 = bx - tw / 2 - 16 if True else bx
        x0 = min(max(x0, 20), 1900 - tw - 32); y0 = min(max(by - th / 2 - 10, 150), 1050 - th - 20)
        x1, y1 = x0 + tw + 32, y0 + th + 20
        cx = min(max(ax, x0), x1); cy = min(max(ay, y0), y1)
        col = SCREW if kind == "screw" else INK
        dr.line([(ax, ay), (cx, cy)], fill=col + (230,), width=3)
        dr.ellipse([ax - 7, ay - 7, ax + 7, ay + 7], fill=col, outline=(255, 255, 255), width=2)
        rbox(dr, (x0, y0, x1, y1), (255, 255, 255, 240), col, 3 if kind == "screw" else 2)
        dr.multiline_text((x0 + 16, y0 + 8), label, font=f, fill=col, spacing=6)

    # close-up inset
    ins = st.get("inset")
    if ins:
        sub = Image.open(f"{D}/{ins['src']}/frame-0002.png").convert("RGBA")
        ip = projector(ins["cam"], *sub.size)
        sd = ImageDraw.Draw(sub, "RGBA")
        for txt, occ, p, off in ins["labels"]:
            ax, ay = ip(np.add(p, mv.get(occ, (0, 0, 0))))
            tw, th = text_size(sd, txt, F_LAB)
            x0, y0 = ax + off[0] - tw / 2 - 16, ay + off[1] - th / 2 - 10
            x1, y1 = x0 + tw + 32, y0 + th + 20
            cx = min(max(ax, x0), x1); cy = min(max(ay, y0), y1)
            sd.line([(ax, ay), (cx, cy)], fill=INK, width=3)
            sd.ellipse([ax - 7, ay - 7, ax + 7, ay + 7], fill=INK, outline=(255, 255, 255), width=2)
            rbox(sd, (x0, y0, x1, y1), (255, 255, 255, 240), INK, 2)
            sd.multiline_text((x0 + 16, y0 + 8), txt, font=F_LAB, fill=INK, spacing=6)
        cx0, cy0, cx1, cy1 = ins["crop"]
        sub = sub.crop((cx0, cy0, cx1, cy1))
        w = ins["width"]; sub = sub.resize((w, round(w * sub.size[1] / sub.size[0])), Image.LANCZOS)
        bx, by = ins["at"]
        rbox(dr, (bx - 6, by - 50, bx + sub.size[0] + 6, by + sub.size[1] + 6), (255, 255, 255, 255), (200, 205, 212), 2)
        im.alpha_composite(sub, (bx, by))
        dr.text((bx + 8, by - 40), ins["title"], font=F_LABB, fill=INK)

    # front marker
    if st.get("front"):
        fx, fy = proj(st["front"])
        rbox(dr, (fx - 62, fy - 20, fx + 62, fy + 20), (31, 79, 209, 230), None, r=20)
        dr.text((fx, fy), "FRONT", font=F_SMALL, fill="white", anchor="mm")

    # header: number + title
    rbox(dr, (40, 36, 150, 146), ACCENT + (255,), None, r=24)
    dr.text((95, 91), str(n), font=F_NUM, fill="white", anchor="mm")
    dr.text((178, 52), st["title"], font=F_TITLE, fill=INK)
    dr.text((180, 112), f"BirdBox v3 assembly · step {n} of {TOTAL}", font=F_SMALL, fill=MUTED)

    # you need
    lines = [(q, w) for q, w in st["need"]]
    nw = max(text_size(dr, w, F_LAB)[0] for _, w in lines) + 110
    x0 = 1880 - nw; y0 = 40
    h = 58 + 44 * len(lines)
    rbox(dr, (x0, y0, 1880, y0 + h), (255, 255, 255, 235), (200, 205, 212), 2)
    dr.text((x0 + 20, y0 + 14), "YOU NEED", font=F_SMALL, fill=MUTED)
    for i, (q, w) in enumerate(lines):
        yy = y0 + 52 + 44 * i
        rbox(dr, (x0 + 18, yy, x0 + 76, yy + 34), SCREW + (255,) if "screw" in w else INK + (255,), None, r=8)
        dr.text((x0 + 47, yy + 17), q, font=F_SMALL, fill="white", anchor="mm")
        dr.text((x0 + 92, yy + 2), w, font=F_LAB, fill=INK)

    # instructions
    txt = "\n".join(st["text"])
    tw, th = text_size(dr, txt, F_TXT)
    y0 = 1040 - th - 30
    rbox(dr, (40, y0, 40 + tw + 48, 1040), (255, 255, 255, 238), (200, 205, 212), 2)
    dr.multiline_text((64, y0 + 14), txt, font=F_TXT, fill=INK, spacing=8)

    os.makedirs(OUT, exist_ok=True)
    im.convert("RGB").save(os.path.join(OUT, f"step-{n:02d}.png"), optimize=True)
    print("step", n)

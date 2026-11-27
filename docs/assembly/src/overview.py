import sys, os
from PIL import Image, ImageDraw, ImageFont
OUT = "/Users/jimbruges/code/birdbox/docs/assembly"
AV = "/System/Library/Fonts/Avenir Next.ttc"
f = lambda s, i: ImageFont.truetype(AV, s, index=i)
T, H, R, B, SM = f(46, 2), f(28, 2), f(25, 7), f(25, 2), f(21, 2)
INK, MUTED, ACCENT, SCREW = (30, 34, 40), (90, 96, 106), (31, 79, 209), (214, 110, 20)
im = Image.open("/Users/jimbruges/code/birdbox/docs/video-v3/stills/exploded-bg.png").convert("RGB")
im = im.crop((420, 0, 1500, 1080)).resize((1080, 1080))
can = Image.new("RGB", (1920, 1080), (238, 241, 245))
can.paste(im.crop((60, 0, 940, 1080)), (1040, 0))
d = ImageDraw.Draw(can)
d.rounded_rectangle((40, 36, 150, 146), radius=24, fill=ACCENT)
d.text((95, 91), "0", font=f(60, 2), fill="white", anchor="mm")
d.text((178, 52), "Before you start", font=T, fill=INK)
d.text((180, 112), "BirdBox v3 assembly · parts and screws", font=SM, fill=MUTED)
rows = [("Screws (self-tapping)", None),
        ("4", "M3 × 10 pan head", "printer plate to base", "step 3"),
        ("4", "M3 × 8 pan head", "Modulino Buzzer to right side", "step 6"),
        ("10", "M3 × 10 countersunk", "sides to front and base", "steps 7, 8"),
        ("4", "M3 × 8 pan head", "UNO Q to back plate", "step 10"),
        ("4", "M3 × 12 countersunk", "roof to sides", "step 11"),
        ("4", "M3 × 12 countersunk", "back plate to base and sides", "step 12"),
        ("Ties and fixings", None),
        ("2", "cable ties ≤ 2.5 mm", "USB power breakout", "step 4"),
        ("2", "cable ties ≤ 4.8 mm, 150 mm+", "hub to roof stubs", "step 9"),
        ("1", "wall screw, 4–4.5 mm", "hanging the box", "step 13"),
        ("Printed parts", None),
        ("8", "printed parts", "base, front, sides, back, roof,", ""),
        ("", "", "printer plate, cover", ""),
        ]
y = 200
for r in rows:
    if r[1] is None:
        d.text((60, y + 6), r[0].upper(), font=SM, fill=MUTED); y += 46; continue
    q, what, where, step = r
    if not q:
        d.text((500, y + 4 - 14), where, font=R, fill=INK); y += 38; continue
    col = SCREW if "M3" in what else INK
    d.rounded_rectangle((60, y, 124, y + 38), radius=8, fill=col)
    d.text((92, y + 19), q, font=SM, fill="white", anchor="mm")
    d.text((144, y + 4), what, font=B, fill=INK)
    d.text((500, y + 4), where, font=R, fill=INK)
    if step: d.text((1010, y + 4), step, font=R, fill=MUTED, anchor="ra")
    y += 52
d.multiline_text((60, y + 26), "3 mm wood screws work in place of the M3 self-tappers.\n"
                 "Tools: a Phillips screwdriver (a stubby one helps for the side screws)\nand flush cutters for the rack's supports.",
                 font=R, fill=MUTED, spacing=8)
can.save(os.path.join(OUT, "step-00.png"), optimize=True)
pages = [Image.open(os.path.join(OUT, f"step-{i:02d}.png")).convert("RGB") for i in range(0, 14)]
pages[0].save(os.path.join(OUT, "birdbox-v3-assembly.pdf"), save_all=True, append_images=pages[1:], resolution=150)
print("ok")

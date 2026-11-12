# SPDX-License-Identifier: MPL-2.0
"""Receipts for the 58 mm thermal printer, drawn as 384-pixel-wide 1-bit images.

Styled like an entry in an old encyclopaedia: serif type, inverted headwords
("ROBIN, EUROPEAN"), italic scientific names and thin rules.

The printer has 8 dots per mm, so an image's height in pixels / 8 is the paper
it uses in mm. The debug page shows these images, so a preview is exactly what
prints.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH = 384
DOTS_PER_MM = 8
PAD = 4

_FONT_DIRS = ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu")
_fonts: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    name = "DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf"
    key = (name, size)
    if key not in _fonts:
        for folder in _FONT_DIRS:
            path = Path(folder) / name
            if path.exists():
                _fonts[key] = ImageFont.truetype(str(path), size)
                break
        else:
            _fonts[key] = ImageFont.load_default()
    return _fonts[key]


def paper_mm(image: Image.Image) -> float:
    return round(image.height / DOTS_PER_MM, 1)


class Canvas:
    """A tall white strip we draw down, then crop to what was used."""

    def __init__(self, height: int = 1600):
        self.image = Image.new("1", (WIDTH, height), 1)
        self.draw = ImageDraw.Draw(self.image)
        self.y = PAD

    def text_width(self, text: str, fnt) -> int:
        return int(self.draw.textlength(text, font=fnt))

    def wrap(self, text: str, fnt, width: int, max_lines: int | None = None) -> list[str]:
        words, lines, line = text.split(), [], ""
        for word in words:
            trial = f"{line} {word}".strip()
            if self.text_width(trial, fnt) <= width:
                line = trial
                continue
            if line:
                lines.append(line)
            line = word
        if line:
            lines.append(line)
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            last = lines[-1]
            while last and self.text_width(last + "…", fnt) > width:
                last = last[:-1]
            lines[-1] = last.rstrip(" ,;:") + "…"
        return lines

    def lines(self, lines: list[str], fnt, x: int = 0, spacing: int = 2) -> int:
        """Draw lines from the current y; returns the height used."""
        top = self.y
        for line in lines:
            self.draw.text((x, self.y), line, font=fnt, fill=0)
            box = fnt.getbbox("Ag")
            self.y += box[3] + spacing
        return self.y - top

    def gap(self, px: int) -> None:
        self.y += px

    def rule(self, double: bool = False) -> None:
        self.gap(3)
        dashed_rule(self.draw, self.y)
        if double:
            dashed_rule(self.draw, self.y + 4)
            self.y += 4
        self.gap(5)

    def italic(self, xy: tuple[int, int], text: str, fnt) -> int:
        """Draw slanted text (there's no italic serif font on the board). Returns its width."""
        w = self.text_width(text, fnt) + 8
        h = fnt.getbbox("Ag")[3] + 2
        layer = Image.new("L", (w, h), 0)
        ImageDraw.Draw(layer).text((0, 0), text, font=fnt, fill=255)
        slant = 0.2
        layer = layer.transform((w + int(h * slant), h), Image.AFFINE, (1, slant, -h * slant, 0, 1, 0),
                                Image.BICUBIC)
        mask = layer.point(lambda v: 255 if v > 110 else 0)
        self.image.paste(0, xy, mask.convert("1"))
        return w

    def done(self) -> Image.Image:
        return self.image.crop((0, 0, WIDTH, self.y + PAD))


def whole_sentences(c: Canvas, text: str, fnt, width: int, max_lines: int = 5) -> list[str]:
    """As many complete sentences as fit in max_lines, so a description never stops
    mid-sentence. Only if even the first sentence is too long is it cut short."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    best: list[str] = []
    for n in range(1, len(sentences) + 1):
        lines = c.wrap(" ".join(sentences[:n]), fnt, width)
        if len(lines) > max_lines:
            break
        best = lines
    return best or c.wrap(sentences[0], fnt, width, max_lines=max_lines)


def headword(common: str) -> str:
    """'European Robin' -> 'ROBIN, EUROPEAN', as an old encyclopaedia indexes it."""
    words = common.split()
    if len(words) < 2:
        return common.upper()
    return f"{words[-1]}, {' '.join(words[:-1])}".upper()


def truncate(c: Canvas, text: str, fnt, width: int) -> str:
    if c.text_width(text, fnt) <= width:
        return text
    while text and c.text_width(text + "…", fnt) > width:
        text = text[:-1]
    return text.rstrip() + "…"


# --- Pieces -----------------------------------------------------------------
# Thermal heads can only heat so many dots in one row at once, so a full-width,
# one-dot line prints faint or not at all. Lines here are two dots thick and
# dashed, which keeps every row well under the printer's limit.


def dithered_box(img: Image.Image, box: tuple[int, int, int, int], caps: bool = True) -> None:
    """Fill a box with a 2x2-block checker (an even 50% grey that prints cleanly),
    with solid 2-dot caps at the ends so its length still reads exactly."""
    x0, y0, x1, y1 = box
    px = img.load()
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if (x // 2 + y // 2) % 2 == 0:
                px[x, y] = 0
    if caps:
        d = ImageDraw.Draw(img)
        d.rectangle((x0, y0, min(x0 + 1, x1), y1), fill=0)
        d.rectangle((max(x1 - 1, x0), y0, x1, y1), fill=0)


def dashed_rule(draw: ImageDraw.ImageDraw, y: int, x0: int = 0, x1: int = WIDTH - 1,
                dash: int = 4, gap: int = 4, thickness: int = 2) -> None:
    for x in range(x0, x1 + 1, dash + gap):
        draw.rectangle((x, y, min(x + dash - 1, x1), y + thickness - 1), fill=0)


def silhouette_image(path: Path, size: int) -> Image.Image:
    """A PhyloPic PNG (black shape on transparent) as a size x size 1-bit tile."""
    src = Image.open(path).convert("RGBA")
    white = Image.new("RGBA", src.size, (255, 255, 255, 255))
    flat = Image.alpha_composite(white, src).convert("L")
    flat = ImageOps.contain(flat, (size, size), Image.LANCZOS)
    tile = Image.new("L", (size, size), 255)
    tile.paste(flat, ((size - flat.width) // 2, (size - flat.height) // 2))
    return tile.point(lambda v: 0 if v < 140 else 255, "1")


def song_contour(segments: list[tuple[int, int, int]], width: int = WIDTH, height: int = 48) -> Image.Image:
    """The buzzer song as a pitch contour over a dotted five-line staff (log pitch, 1-8 kHz).

    The staff is 2x2 dots every 8 dots. The contour is a solid 2-dot line inside an
    8-dot band of 2x2-block grey, so it reads boldly without heating long solid runs.
    """
    img = Image.new("1", (width, height), 1)
    d = ImageDraw.Draw(img)
    top, bottom = 5, height - 6
    for k in range(5):
        y = round(top + k * (bottom - top) / 4)
        for x in range(0, width, 8):
            d.rectangle((x, y, x + 1, y + 1), fill=0)
    total = sum(ms for _, _, ms in segments) or 1
    lo, hi = math.log(1000), math.log(8000)

    def y_of(hz: float) -> float:
        frac = (math.log(max(1000, min(8000, hz))) - lo) / (hi - lo)
        return bottom - frac * (bottom - top)

    x, path, paths = 2.0, [], []
    scale = (width - 4) / total
    for start, end, ms in segments:
        x2 = x + ms * scale
        if start <= 0 and end <= 0:            # a rest breaks the line
            if len(path) > 1:
                paths.append(path)
            path = []
        else:
            path += [(x, y_of(start)), (x2, y_of(end))]
        x = x2
    if len(path) > 1:
        paths.append(path)

    band = Image.new("1", (width, height), 0)   # 1 = inside the 8-dot band
    bd = ImageDraw.Draw(band)
    for pts in paths:
        bd.line(pts, fill=1, width=8, joint="curve")
    px, mask = img.load(), band.load()
    for yy in range(height):
        for xx in range(width):
            if mask[xx, yy] and (xx // 2 + yy // 2) % 2 == 0:
                px[xx, yy] = 0
    for pts in paths:
        d.line(pts, fill=0, width=2, joint="curve")
    return img


# --- Receipts ---------------------------------------------------------------


def bird_card(*, common: str, scientific: str, when: datetime, confidence: float,
              today: int, total: int, song: list | None = None,
              picture: tuple[Path, str] | None = None, description: str | None = None,
              description_source: str = "wikipedia", credits: bool = True) -> Image.Image:
    """An encyclopaedia entry for the last bird heard, in as little paper as possible."""
    c = Canvas()
    pic_size = 92
    text_w = WIDTH - (pic_size + 8 if picture else 0)
    top = c.y

    head_font = font(24, True)
    for line in c.wrap(headword(common), head_font, text_w, max_lines=2):
        c.lines([line], head_font)
    sci_font = font(18)
    c.italic((0, c.y), truncate(c, scientific, sci_font, text_w - 8), sci_font)
    c.y += sci_font.getbbox("Ag")[3] + 4
    meta = font(15)
    c.lines([f"Heard {when:%a %d %b %Y}, {when:%H:%M}", f"{round(confidence * 100)}% certain"], meta)
    times = "once" if total == 1 else f"{total} times"
    c.lines([f"{today} today; {times} in all"], meta)
    if picture:
        tile = silhouette_image(picture[0], pic_size)
        c.image.paste(tile, (WIDTH - pic_size, top))
        c.y = max(c.y, top + pic_size)

    if description:
        c.rule()
        c.lines(whole_sentences(c, description, font(17), WIDTH, max_lines=5), font(17))

    if song:
        c.rule()
        c.lines(["Vocalisation Chart:"], font(13, True))
        c.gap(1)
        strip = song_contour(song)
        c.image.paste(strip, (0, c.y))
        c.y += strip.height

    notes = []
    if credits and picture:
        notes.append("Fig. " + picture[1].removeprefix("Silhouette: "))
    if credits and description:
        notes.append("Text after Wikipedia, CC BY-SA" if description_source == "llm"
                     else "Text: Wikipedia, CC BY-SA")
    if notes:
        c.gap(3)
        c.lines(c.wrap(". ".join(notes) + ".", font(10), WIDTH), font(10), spacing=0)
    return c.done()


SCROLL_FONT = 10   # px; 9 is the smallest that still reads, 10 is safer on a thermal head


def scroll_line(*, common: str, when: datetime, confidence: float, size: int = SCROLL_FONT) -> Image.Image:
    """One very compact line per detection, with date, time and dot leaders, for a scroll.

    All bold: at this size the regular weight's thin strokes don't survive the head.
    """
    c = Canvas(40)
    c.y = 0
    fnt = font(size, True)
    left = f"{when:%d %b %H:%M}  "
    right = f" {round(confidence * 100)}%"
    name = truncate(c, headword(common).title(), fnt, WIDTH - c.text_width(left + right, fnt) - 10)
    c.draw.text((0, c.y), left + name, font=fnt, fill=0)
    x = c.text_width(left + name, fnt) + 4
    right_x = WIDTH - c.text_width(right, fnt)
    dot_y = c.y + fnt.getbbox("A")[3] - 2
    for dx in range(x + (6 - x % 6), right_x - 4, 6):   # 2x2 leader dots, which print reliably
        c.draw.rectangle((dx, dot_y, dx + 1, dot_y + 1), fill=0)
    c.draw.text((right_x, c.y), right, font=fnt, fill=0)
    c.y += fnt.getbbox("Ag")[3] + 1
    return c.image.crop((0, 0, WIDTH, c.y))


def daily_summary(*, summary: dict, hourly: list[tuple[int, int]], when: datetime) -> Image.Image:
    """The day's register: totals, the top species and a 24-hour activity chart."""
    c = Canvas()
    title = "DAILY REGISTER"
    tf = font(22, True)
    c.draw.text(((WIDTH - c.text_width(title, tf)) // 2, c.y), title, font=tf, fill=0)
    c.y += tf.getbbox("Ag")[3] + 2
    sub = f"{when:%A %d %B %Y}"
    sf = font(15)
    c.draw.text(((WIDTH - c.text_width(sub, sf)) // 2, c.y), sub, font=sf, fill=0)
    c.y += sf.getbbox("Ag")[3]
    c.rule(double=True)

    busiest = max(hourly, key=lambda h: h[1]) if hourly and any(n for _, n in hourly) else None
    stats = f"{summary['total']} detections of {summary['species']} species"
    if busiest:
        stats += f"; busiest at {busiest[0]:02d}:00"
    c.lines(c.wrap(stats + ".", font(16), WIDTH), font(16))

    if summary["top"]:
        c.gap(4)
        most = max(t["count"] for t in summary["top"])
        name_w, count_w = 178, 36
        row_font = font(16)
        for row in summary["top"]:
            y = c.y
            c.draw.text((0, y), truncate(c, headword(row["common"]).title(), row_font, name_w - 6),
                        font=row_font, fill=0)
            bar_max = WIDTH - name_w - count_w
            bar = max(2, round(bar_max * row["count"] / most))
            dithered_box(c.image, (name_w, y + 4, name_w + bar, y + 15))
            count = str(row["count"])
            c.draw.text((WIDTH - c.text_width(count, row_font), y), count, font=row_font, fill=0)
            c.y += 21
    else:
        c.lines(["No birds heard yet today."], font(16))

    if hourly and any(n for _, n in hourly):
        c.rule()
        c.lines(["Activity over the last 24 hours"], font(13))
        c.gap(2)
        chart_h, gap = 52, 2
        bar_w = (WIDTH - gap * 23) // 24
        peak = max(n for _, n in hourly) or 1
        base = c.y + chart_h
        for k, (hour, n) in enumerate(hourly):
            x = k * (bar_w + gap)
            h = round(chart_h * n / peak)
            if n and h < 2:
                h = 2
            if h:
                dithered_box(c.image, (x, base - h, x + bar_w - 1, base), caps=False)
                c.draw.rectangle((x, base - h, x + bar_w - 1, base - h + 1), fill=0)   # solid top
        dashed_rule(c.draw, base + 1)
        c.y = base + 3
        for k, (hour, _) in enumerate(hourly):
            if hour % 6 == 0:
                c.draw.text((k * (bar_w + gap), c.y), f"{hour:02d}", font=font(12), fill=0)
        c.y += 14
    return c.done()

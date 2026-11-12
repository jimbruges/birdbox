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
        self.draw.line((0, self.y, WIDTH - 1, self.y), fill=0)
        if double:
            self.draw.line((0, self.y + 2, WIDTH - 1, self.y + 2), fill=0)
            self.y += 2
        self.gap(4)

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


def silhouette_image(path: Path, size: int) -> Image.Image:
    """A PhyloPic PNG (black shape on transparent) as a size x size 1-bit tile."""
    src = Image.open(path).convert("RGBA")
    white = Image.new("RGBA", src.size, (255, 255, 255, 255))
    flat = Image.alpha_composite(white, src).convert("L")
    flat = ImageOps.contain(flat, (size, size), Image.LANCZOS)
    tile = Image.new("L", (size, size), 255)
    tile.paste(flat, ((size - flat.width) // 2, (size - flat.height) // 2))
    return tile.point(lambda v: 0 if v < 140 else 255, "1")


def song_contour(segments: list[tuple[int, int, int]], width: int = WIDTH, height: int = 44) -> Image.Image:
    """The buzzer song as a pitch contour over a dotted five-line staff (log pitch, 1-8 kHz)."""
    img = Image.new("1", (width, height), 1)
    d = ImageDraw.Draw(img)
    top, bottom = 4, height - 4
    for k in range(5):
        y = round(top + k * (bottom - top) / 4)
        for x in range(0, width, 4):
            d.point((x, y), fill=0)
    total = sum(ms for _, _, ms in segments) or 1
    lo, hi = math.log(1000), math.log(8000)

    def y_of(hz: float) -> float:
        frac = (math.log(max(1000, min(8000, hz))) - lo) / (hi - lo)
        return bottom - frac * (bottom - top)

    x, path = 2.0, []
    scale = (width - 4) / total
    for start, end, ms in segments:
        x2 = x + ms * scale
        if start <= 0 and end <= 0:            # a rest breaks the line
            if len(path) > 1:
                d.line(path, fill=0, width=4, joint="curve")
            path = []
        else:
            path += [(x, y_of(start)), (x2, y_of(end))]
        x = x2
    if len(path) > 1:
        d.line(path, fill=0, width=4, joint="curve")
    return img


# --- Receipts ---------------------------------------------------------------


def bird_card(*, common: str, scientific: str, when: datetime, confidence: float,
              today: int, total: int, song: list | None = None,
              picture: tuple[Path, str] | None = None, description: str | None = None,
              description_source: str = "wikipedia") -> Image.Image:
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
        c.lines(c.wrap(description, font(17), WIDTH, max_lines=4), font(17))

    if song:
        c.rule()
        c.lines(["Song, as the box plays it"], font(13))
        c.gap(1)
        strip = song_contour(song)
        c.image.paste(strip, (0, c.y))
        c.y += strip.height

    credits = []
    if picture:
        credits.append("Fig. " + picture[1].removeprefix("Silhouette: "))
    if description:
        credits.append("Text after Wikipedia, CC BY-SA" if description_source == "llm"
                       else "Text: Wikipedia, CC BY-SA")
    if credits:
        c.rule()
        c.lines(c.wrap(". ".join(credits) + ".", font(12), WIDTH), font(12), spacing=1)
    return c.done()


def scroll_line(*, common: str, when: datetime, confidence: float) -> Image.Image:
    """One very compact line per detection, with dot leaders, for a running scroll."""
    c = Canvas(40)
    c.y = 1
    fnt = font(17)
    left = f"{when:%H:%M}  "
    right = f" {round(confidence * 100)}%"
    name = truncate(c, headword(common).title(), font(17, True),
                    WIDTH - c.text_width(left + right, fnt) - 12)
    c.draw.text((0, c.y), left, font=fnt, fill=0)
    x = c.text_width(left, fnt)
    c.draw.text((x, c.y), name, font=font(17, True), fill=0)
    x += c.text_width(name, font(17, True)) + 4
    right_x = WIDTH - c.text_width(right, fnt)
    dot_y = c.y + fnt.getbbox("A")[3] - 1
    for dx in range(x + (4 - x % 4), right_x - 4, 5):
        c.draw.point((dx, dot_y), fill=0)
    c.draw.text((right_x, c.y), right, font=fnt, fill=0)
    c.y += fnt.getbbox("Ag")[3] + 2
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
            c.draw.rectangle((name_w, y + 5, name_w + bar, y + 14), fill=0)
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
                c.draw.rectangle((x, base - h, x + bar_w - 1, base), fill=0)
        c.draw.line((0, base + 1, WIDTH - 1, base + 1), fill=0)
        c.y = base + 3
        for k, (hour, _) in enumerate(hourly):
            if hour % 6 == 0:
                c.draw.text((k * (bar_w + gap), c.y), f"{hour:02d}", font=font(12), fill=0)
        c.y += 14
    return c.done()

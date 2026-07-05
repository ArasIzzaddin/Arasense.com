from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from random import Random
from textwrap import wrap
from zipfile import ZIP_DEFLATED, ZipFile
import html
import math
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs"
SLIDE_DIR = OUT_DIR / "startcup-visual-pitch-slides"
PDF_PATH = OUT_DIR / "Arasense_StartCup_Puglia_2026.pdf"
PPTX_PATH = OUT_DIR / "Arasense_StartCup_Puglia_2026.pptx"
LOGO_PATH = ROOT / "site" / "linkedin-logo-luxury.png"
WEBSITE_URL = "https://www.arasense.com"
LINKEDIN_URL = "https://www.linkedin.com/company/arasenseai/"
X_URL = "https://x.com/ArasenseAI"
DOWNLOADS = Path.home() / "Downloads"
REAL_ASSETS = {
    "console": DOWNLOADS / "1_arasense.png",
    "trust_report": DOWNLOADS / "model_trust_report.png",
    "projection": DOWNLOADS / "projection.png",
    "aras_diagram": DOWNLOADS / "lnkdin.png",
    "aras_greek": DOWNLOADS / "ARAS_greek.png",
}

W, H = 1920, 1080

COLORS = {
    "ink": (8, 18, 24),
    "ink2": (13, 32, 38),
    "cream": (245, 240, 226),
    "muted": (166, 187, 178),
    "teal": (79, 217, 169),
    "teal2": (18, 130, 116),
    "gold": (235, 183, 90),
    "coral": (229, 91, 74),
    "blue": (76, 145, 232),
    "line": (64, 98, 99),
    "white": (255, 255, 255),
    "panel": (18, 38, 45),
    "panel2": (28, 55, 61),
}


SLIDES = [
    "title",
    "problem",
    "solution",
    "science",
    "product",
    "proof",
    "market",
    "business",
    "roadmap",
    "team",
]


def font_path(*names: str) -> str:
    roots = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"]
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.exists():
                return str(candidate)
    return ""


FONT_REG = font_path("segoeui.ttf", "arial.ttf")
FONT_BOLD = font_path("segoeuib.ttf", "arialbd.ttf")
FONT_SEMI = font_path("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf")
FONT_MONO = font_path("consola.ttf", "cour.ttf")


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    path = FONT_REG
    if weight == "bold":
        path = FONT_BOLD or FONT_REG
    elif weight == "semi":
        path = FONT_SEMI or FONT_BOLD or FONT_REG
    elif weight == "mono":
        path = FONT_MONO or FONT_REG
    return ImageFont.truetype(path, size=size)


def alpha(color: tuple[int, int, int], a: int) -> tuple[int, int, int, int]:
    return color + (a,)


def lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def gradient_bg() -> Image.Image:
    img = Image.new("RGB", (W, H), COLORS["ink"])
    px = img.load()
    for y in range(H):
        t = y / H
        for x in range(W):
            r = lerp(7, 16, t)
            g = lerp(20, 39, t)
            b = lerp(27, 36, t)
            # Subtle warm light from top right and teal from bottom left.
            d1 = math.hypot((x - 1580) / 1200, (y - 120) / 900)
            d2 = math.hypot((x - 220) / 1100, (y - 920) / 850)
            warm = max(0, 1 - d1) * 22
            teal = max(0, 1 - d2) * 24
            px[x, y] = (
                min(255, int(r + warm + teal * 0.2)),
                min(255, int(g + warm * 0.55 + teal)),
                min(255, int(b + warm * 0.12 + teal * 0.65)),
            )
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for x in range(0, W, 64):
        d.line((x, 0, x, H), fill=(255, 255, 255, 10), width=1)
    for y in range(0, H, 64):
        d.line((0, y, W, y), fill=(255, 255, 255, 8), width=1)
    for i in range(7):
        d.arc((140 + i * 26, 170 + i * 8, 1780 - i * 18, 1060 - i * 24), 200, 345, fill=(79, 217, 169, 12), width=2)
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def draw_wrapped(
    d: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int] | tuple[int, int, int, int],
    max_width: int,
    line_gap: int = 10,
    max_lines: int | None = None,
) -> int:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if text_size(d, trial, fnt)[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if max_lines is not None:
        lines = lines[:max_lines]
    x, y = xy
    for line in lines:
        d.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + line_gap
    return y


def wrap_lines(
    d: ImageDraw.ImageDraw,
    text: str,
    fnt: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int | None = None,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if text_size(d, trial, fnt)[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if max_lines is not None:
        return lines[:max_lines]
    return lines


def draw_centered_wrapped(
    d: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int] | tuple[int, int, int, int],
    max_width: int,
    line_gap: int = 10,
) -> None:
    lines = wrap_lines(d, text, fnt, max_width)
    x1, y1, x2, y2 = box
    total_height = len(lines) * fnt.size + max(0, len(lines) - 1) * line_gap
    y = y1 + ((y2 - y1) - total_height) / 2
    for line in lines:
        line_width = text_size(d, line, fnt)[0]
        d.text((x1 + ((x2 - x1) - line_width) / 2, y), line, font=fnt, fill=fill)
        y += fnt.size + line_gap


def panel(
    d: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int] = COLORS["panel"],
    outline: tuple[int, int, int] = COLORS["line"],
    radius: int = 26,
    width: int = 2,
) -> None:
    d.rounded_rectangle(box, radius=radius, fill=alpha(fill, 222), outline=alpha(outline, 150), width=width)


def pill(
    d: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fill: tuple[int, int, int],
    fg: tuple[int, int, int] = COLORS["ink"],
    pad_x: int = 20,
    pad_y: int = 10,
    fnt: ImageFont.FreeTypeFont | None = None,
) -> tuple[int, int, int, int]:
    fnt = fnt or font(28, "semi")
    tw, th = text_size(d, text, fnt)
    x, y = xy
    box = (x, y, x + tw + pad_x * 2, y + th + pad_y * 2)
    d.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=fill)
    d.text((x + pad_x, y + pad_y - 2), text, font=fnt, fill=fg)
    return box


def add_logo(img: Image.Image, x: int = 1640, y: int = 54, size: int = 150) -> None:
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        img.alpha_composite(logo, (x, y))
    else:
        d = ImageDraw.Draw(img)
        d.ellipse((x, y, x + size, y + size), outline=COLORS["teal"], width=4)
        d.text((x + 44, y + 34), "A", font=font(70, "bold"), fill=COLORS["gold"])


def crop_transparent_border(source: Image.Image) -> Image.Image:
    if source.mode != "RGBA":
        source = source.convert("RGBA")
    alpha_channel = source.getchannel("A")
    bbox = alpha_channel.getbbox()
    if bbox:
        return source.crop(bbox)
    return source


def paste_fitted(
    canvas: Image.Image,
    source_path: Path,
    box: tuple[int, int, int, int],
    mode: str = "contain",
    radius: int = 28,
    bg: tuple[int, int, int] = (5, 15, 20),
    border: tuple[int, int, int] = COLORS["line"],
) -> bool:
    if not source_path.exists():
        return False
    src = crop_transparent_border(Image.open(source_path))
    x0, y0, x1, y1 = box
    target_w, target_h = x1 - x0, y1 - y0
    if mode == "cover":
        fitted = ImageOps.fit(src.convert("RGB"), (target_w, target_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.45)).convert("RGBA")
    else:
        fitted = Image.new("RGBA", (target_w, target_h), bg + (255,))
        tmp = src.convert("RGBA")
        tmp.thumbnail((target_w - 34, target_h - 34), Image.Resampling.LANCZOS)
        fitted.alpha_composite(tmp, ((target_w - tmp.width) // 2, (target_h - tmp.height) // 2))

    mask = Image.new("L", (target_w, target_h), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, target_w, target_h), radius=radius, fill=255)
    fitted.putalpha(mask)
    canvas.alpha_composite(fitted, (x0, y0))
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rounded_rectangle(box, radius=radius, outline=alpha(border, 170), width=3)
    return True


def slide_base(kicker: str, title: str, slide_no: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = gradient_bg()
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle((0, 0, 28, H), fill=COLORS["teal2"])
    d.rectangle((28, 0, 34, H), fill=COLORS["gold"])
    d.text((92, 58), kicker.upper(), font=font(25, "semi"), fill=COLORS["teal"])
    d.text((92, 982), f"Arasense | R&D 4 StartCup Puglia 2026 | {slide_no:02d}", font=font(20), fill=COLORS["muted"])
    add_logo(img)
    draw_wrapped(d, (92, 112), title, font(64, "bold"), COLORS["cream"], 1220, line_gap=12, max_lines=2)
    return img, d


def arrow(d: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int], width: int = 5) -> None:
    d.line((*start, *end), fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    length = 20
    p1 = (end[0] - length * math.cos(angle - 0.45), end[1] - length * math.sin(angle - 0.45))
    p2 = (end[0] - length * math.cos(angle + 0.45), end[1] - length * math.sin(angle + 0.45))
    d.polygon([end, p1, p2], fill=color)


def draw_spaghetti(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    panel(d, box, fill=(12, 31, 38), radius=28)
    d.text((x0 + 42, y0 + 34), "Local projections diverge", font=font(34, "semi"), fill=COLORS["cream"])
    d.text((x0 + 42, y0 + 82), "Same location, different model behavior", font=font(23), fill=COLORS["muted"])
    chart = (x0 + 54, y0 + 160, x1 - 54, y1 - 54)
    d.line((chart[0], chart[3], chart[2], chart[3]), fill=alpha(COLORS["line"], 220), width=2)
    d.line((chart[0], chart[1], chart[0], chart[3]), fill=alpha(COLORS["line"], 220), width=2)
    rng = Random(4)
    palette = [COLORS["teal"], COLORS["gold"], COLORS["coral"], COLORS["blue"], (171, 124, 222)]
    for i in range(12):
        pts = []
        base = rng.randint(-25, 35)
        slope = rng.uniform(-0.6, 1.25)
        amp = rng.uniform(6, 18)
        for t in range(11):
            x = chart[0] + t * ((chart[2] - chart[0]) // 10)
            v = base + slope * t * 13 + math.sin(t * 0.8 + i) * amp + rng.uniform(-7, 7)
            y = chart[3] - int((v + 80) / 180 * (chart[3] - chart[1]))
            pts.append((x, y))
        d.line(pts, fill=alpha(palette[i % len(palette)], 150), width=4)
    d.line((chart[0], chart[3] - 110, chart[2], chart[3] - 172), fill=alpha(COLORS["white"], 230), width=8)
    d.text((chart[0], chart[3] + 16), "today", font=font(20), fill=COLORS["muted"])
    d.text((chart[2] - 90, chart[3] + 16), "2050", font=font(20), fill=COLORS["muted"])
    pill(d, (x1 - 275, y0 + 34), "average hides trust", COLORS["coral"], COLORS["white"], fnt=font(20, "semi"))


def draw_pipeline(
    d: ImageDraw.ImageDraw,
    x: int,
    y: int,
    labels: list[tuple[str, str]],
    colors: list[tuple[int, int, int]],
    w: int = 300,
    h: int = 170,
    gap: int = 42,
) -> None:
    for i, (title, sub) in enumerate(labels):
        bx = x + i * (w + gap)
        panel(d, (bx, y, bx + w, y + h), fill=(14, 39, 45), radius=24)
        d.ellipse((bx + 24, y + 28, bx + 68, y + 72), fill=colors[i])
        d.text((bx + 84, y + 30), title, font=font(27, "semi"), fill=COLORS["cream"])
        draw_wrapped(d, (bx + 28, y + 92), sub, font(21), COLORS["muted"], w - 56, line_gap=8)
        if i < len(labels) - 1:
            arrow(d, (bx + w + 10, y + h // 2), (bx + w + gap - 12, y + h // 2), COLORS["gold"], 4)


def draw_aras_diagram(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    panel(d, box, fill=(12, 31, 38), radius=28)
    d.text((x0 + 38, y0 + 30), "Aras Diagram", font=font(38, "semi"), fill=COLORS["cream"])
    d.text((x0 + 38, y0 + 78), "Bias, variability, timing", font=font(24), fill=COLORS["muted"])
    cx, cy = x0 + 430, y0 + 365
    size = 560
    left, top, right, bottom = cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2
    d.rectangle((left, top, right, bottom), outline=alpha(COLORS["line"], 170), width=2)
    d.line((left, cy, right, cy), fill=alpha(COLORS["line"], 220), width=2)
    d.line((cx, top, cx, bottom), fill=alpha(COLORS["line"], 220), width=2)
    for r in (90, 180, 270):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=alpha(COLORS["teal"], 55), width=2)
    d.text((left + 16, bottom + 18), "mean bias ratio error", font=font(22), fill=COLORS["muted"])
    d.text((right - 95, cy + 10), "beta - 1", font=font(20), fill=COLORS["muted"])
    d.text((cx + 14, top - 34), "alpha - 1", font=font(20), fill=COLORS["muted"])
    rng = Random(7)
    for i in range(32):
        dx = rng.gauss(0, 112)
        dy = rng.gauss(0, 105)
        dist = math.hypot(dx, dy)
        col = COLORS["teal"] if dist < 185 else COLORS["gold"] if dist < 260 else COLORS["coral"]
        d.ellipse((cx + dx - 9, cy + dy - 9, cx + dx + 9, cy + dy + 9), fill=alpha(col, 225))
    d.ellipse((cx - 13, cy - 13, cx + 13, cy + 13), fill=COLORS["white"])
    d.text((x0 + 780, y0 + 170), "Why it matters", font=font(28, "semi"), fill=COLORS["cream"])
    items = [
        ("bias", "Is the model systematically high or low?"),
        ("variability", "Does it match the spread of observed climate?"),
        ("timing", "Does it align with observed patterns?"),
        ("trust", "Only skilled models drive the projection."),
    ]
    yy = y0 + 228
    for label, desc in items:
        d.rounded_rectangle((x0 + 780, yy, x1 - 42, yy + 76), radius=18, fill=alpha(COLORS["panel2"], 190), outline=alpha(COLORS["line"], 100), width=1)
        d.text((x0 + 808, yy + 18), label.upper(), font=font(21, "semi"), fill=COLORS["gold"])
        d.text((x0 + 955, yy + 18), desc, font=font(22), fill=COLORS["muted"])
        yy += 94


def draw_console_mockup(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    panel(d, box, fill=(10, 28, 34), radius=30)
    d.rounded_rectangle((x0 + 24, y0 + 24, x1 - 24, y0 + 82), radius=18, fill=alpha((6, 19, 25), 240))
    d.text((x0 + 54, y0 + 40), "Arasense Console", font=font(26, "semi"), fill=COLORS["cream"])
    pill(d, (x1 - 250, y0 + 35), "Bologna demo", COLORS["teal"], COLORS["ink"], fnt=font(18, "semi"), pad_x=16, pad_y=7)
    map_box = (x0 + 42, y0 + 120, x0 + 760, y1 - 46)
    d.rounded_rectangle(map_box, radius=24, fill=alpha((9, 53, 61), 230), outline=alpha(COLORS["line"], 130), width=2)
    for gx in range(map_box[0], map_box[2], 56):
        d.line((gx, map_box[1], gx, map_box[3]), fill=alpha(COLORS["teal"], 20), width=1)
    for gy in range(map_box[1], map_box[3], 56):
        d.line((map_box[0], gy, map_box[2], gy), fill=alpha(COLORS["teal"], 20), width=1)
    d.arc((map_box[0] + 130, map_box[1] + 70, map_box[2] - 90, map_box[3] - 80), 30, 335, fill=alpha(COLORS["teal"], 135), width=5)
    d.rectangle((map_box[0] + 305, map_box[1] + 220, map_box[0] + 505, map_box[1] + 370), fill=alpha(COLORS["gold"], 70), outline=COLORS["gold"], width=4)
    d.ellipse((map_box[0] + 410, map_box[1] + 280, map_box[0] + 438, map_box[1] + 308), fill=COLORS["teal"])
    d.text((map_box[0] + 318, map_box[1] + 180), "Climate point + flood box", font=font(23, "semi"), fill=COLORS["cream"])
    side_x = x0 + 805
    cards = [
        ("Climate Diagnostic", "Aras Diagram + model trust tiers"),
        ("Projection to 2050", "Trusted ensemble, uncertainty, agreement"),
        ("Multi-hazard Report", "Flood-driving rainfall, heat, drought"),
        ("Portfolio Ranking", "Which locations worsen most?"),
    ]
    yy = y0 + 120
    for title, sub in cards:
        d.rounded_rectangle((side_x, yy, x1 - 42, yy + 112), radius=20, fill=alpha(COLORS["panel2"], 200), outline=alpha(COLORS["line"], 120), width=1)
        d.text((side_x + 28, yy + 22), title, font=font(28, "semi"), fill=COLORS["cream"])
        d.text((side_x + 28, yy + 62), sub, font=font(22), fill=COLORS["muted"])
        yy += 132


def draw_stat_card(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int], value: str, label: str, color: tuple[int, int, int]) -> None:
    panel(d, box, fill=(16, 39, 45), radius=28)
    x0, y0, x1, _ = box
    d.text((x0 + 34, y0 + 32), value, font=font(70, "bold"), fill=color)
    draw_wrapped(d, (x0 + 38, y0 + 126), label, font(25), COLORS["muted"], x1 - x0 - 76, line_gap=8)


def draw_market_segments(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    segments = [
        ("Public authorities", "Adaptation plans, heat, flood and drought evidence", COLORS["teal"]),
        ("Infrastructure owners", "Physical-risk screening and asset prioritization", COLORS["gold"]),
        ("Finance & insurance", "Portfolio exposure, disclosure, underwriting context", COLORS["blue"]),
        ("Consulting firms", "Traceable evidence packs for client delivery", COLORS["coral"]),
    ]
    gap = 26
    w = (x1 - x0 - gap * 3) // 4
    for i, (title, desc, col) in enumerate(segments):
        bx = x0 + i * (w + gap)
        panel(d, (bx, y0, bx + w, y1), fill=(14, 36, 42), radius=28)
        d.ellipse((bx + 34, y0 + 34, bx + 94, y0 + 94), fill=col)
        d.text((bx + 34, y0 + 128), title, font=font(30, "semi"), fill=COLORS["cream"])
        draw_wrapped(d, (bx + 34, y0 + 184), desc, font(24), COLORS["muted"], w - 68, line_gap=10)
        d.line((bx + 34, y1 - 82, bx + w - 34, y1 - 82), fill=alpha(col, 190), width=4)
        d.text((bx + 34, y1 - 58), "needs defensible evidence", font=font(19), fill=COLORS["muted"])


def draw_ladder(d: ImageDraw.ImageDraw, x: int, y: int) -> None:
    steps = [
        ("1", "Paid pilot", "One geography or portfolio decision"),
        ("2", "Platform access", "Recurring reports and scenario comparison"),
        ("3", "Portfolio API", "Multi-site analysis priced by exposure"),
    ]
    w, h, gap = 330, 170, 35
    for i, (num, title, sub) in enumerate(steps):
        bx = x + i * (w + gap)
        by = y
        panel(d, (bx, by, bx + w, by + h), fill=(15, 41, 47), radius=28)
        d.ellipse((bx + 30, by + 34, bx + 92, by + 96), fill=[COLORS["teal"], COLORS["gold"], COLORS["blue"]][i])
        d.text((bx + 52, by + 47), num, font=font(27, "bold"), fill=COLORS["ink"])
        d.text((bx + 112, by + 34), title, font=font(27, "semi"), fill=COLORS["cream"])
        draw_wrapped(d, (bx + 112, by + 82), sub, font(20), COLORS["muted"], w - 135, line_gap=6)
        if i < 2:
            arrow(d, (bx + w + 8, by + h // 2), (bx + w + gap - 10, by + h // 2), COLORS["gold"], 4)


def draw_timeline(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    d.line((x0 + 80, y0 + 210, x1 - 80, y0 + 210), fill=COLORS["gold"], width=6)
    phases = [
        ("Now", "Prototype, demo, tests", COLORS["teal"]),
        ("0-3 mo", "Design partner pilots", COLORS["gold"]),
        ("3-6 mo", "PDF reports + validation", COLORS["blue"]),
        ("PNI", "National final (PNI): commercial pilot", COLORS["coral"]),
    ]
    spacing = (x1 - x0 - 160) // 3
    for i, (time, title, col) in enumerate(phases):
        cx = x0 + 80 + i * spacing
        d.ellipse((cx - 26, y0 + 184, cx + 26, y0 + 236), fill=col)
        d.text((cx - 58, y0 + 268), time, font=font(28, "semi"), fill=col)
        draw_wrapped(d, (cx - 112, y0 + 314), title, font(24), COLORS["cream"], 225, line_gap=8)


def title_slide() -> Image.Image:
    img = gradient_bg()
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle((0, 0, 42, H), fill=COLORS["teal2"])
    d.rectangle((42, 0, 54, H), fill=COLORS["gold"])
    add_logo(img, 1420, 110, 260)
    d.text((118, 94), "R&D 4 STARTCUP PUGLIA 2026", font=font(28, "semi"), fill=COLORS["teal"])
    d.text((118, 190), "Arasense", font=font(116, "bold"), fill=COLORS["cream"])
    d.text((124, 332), "The model-trust layer for climate risk", font=font(44, "semi"), fill=COLORS["gold"])
    draw_wrapped(
        d,
        (124, 430),
        "Research transfer from Politecnico di Bari: a peer-reviewed model-evaluation method turned into software that tells institutions which climate models to trust, where, and why.",
        font(34),
        COLORS["muted"],
        1090,
        line_gap=14,
    )
    pill(d, (124, 620), "working prototype", COLORS["teal"], COLORS["ink"], fnt=font(24, "semi"), pad_x=22, pad_y=10)
    pill(d, (412, 620), "real climate outputs", COLORS["gold"], COLORS["ink"], fnt=font(24, "semi"), pad_x=22, pad_y=10)
    pill(d, (748, 620), "pilot-ready path", COLORS["blue"], COLORS["white"], fnt=font(24, "semi"), pad_x=22, pad_y=10)
    draw_pipeline(
        d,
        124,
        745,
        [
            ("Models", "CMIP6 ensemble"),
            ("Trust", "Aras Diagram"),
            ("Risk", "Hazard reports"),
            ("Decision", "Pilots + API"),
        ],
        [COLORS["blue"], COLORS["teal"], COLORS["gold"], COLORS["coral"]],
    )
    d.text((124, 986), "Aras Izzaddin + Marwah Yaseen | Politecnico di Bari connection", font=font(24), fill=COLORS["cream"])
    return img


def problem_slide() -> Image.Image:
    img, d = slide_base("Problem", "Climate models disagree. Decisions still need evidence.", 2)
    draw_wrapped(
        d,
        (94, 270),
        "Risk teams often average a whole ensemble. That blends models that represent the local climate with models that do not, producing a number that is hard to defend.",
        font(31),
        COLORS["muted"],
        780,
        line_gap=13,
    )
    issues = [
        ("No local trust", "Which models work here?"),
        ("Hidden uncertainty", "How much agreement supports the signal?"),
        ("Weak defensibility", "Can this survive technical review?"),
    ]
    yy = 545
    for title, sub in issues:
        d.rounded_rectangle((94, yy, 790, yy + 104), radius=24, fill=alpha((20, 42, 49), 210), outline=alpha(COLORS["line"], 120), width=1)
        d.text((126, yy + 22), title, font=font(30, "semi"), fill=COLORS["cream"])
        d.text((126, yy + 62), sub, font=font(24), fill=COLORS["muted"])
        yy += 124
    draw_spaghetti(d, (910, 260, 1780, 880))
    return img


def solution_slide() -> Image.Image:
    img, d = slide_base("Solution", "Score model trust before projecting risk.", 3)
    draw_wrapped(
        d,
        (94, 270),
        "Arasense is a decision layer between raw climate models and climate-risk decisions. The product explains which models are trusted, which are rejected, and what the trusted models imply.",
        font(31),
        COLORS["muted"],
        1120,
        line_gap=13,
    )
    draw_pipeline(
        d,
        96,
        570,
        [
            ("Observe", "ERA5-Land baseline"),
            ("Score", "Bias, variability, timing"),
            ("Weight", "Reject no-skill models"),
            ("Report", "Hazards + uncertainty"),
        ],
        [COLORS["blue"], COLORS["teal"], COLORS["gold"], COLORS["coral"]],
        w=248,
        h=160,
        gap=32,
    )
    panel(d, (1265, 360, 1775, 850), fill=(13, 35, 42), radius=30)
    d.text((1305, 408), "Output", font=font(39, "bold"), fill=COLORS["cream"])
    outputs = ["Trusted models", "Rejected models", "Hazard change", "Uncertainty band", "Model agreement", "Downloadable report"]
    yy = 490
    for out in outputs:
        d.ellipse((1311, yy + 9, 1333, yy + 31), fill=COLORS["teal"])
        d.text((1353, yy), out, font=font(27), fill=COLORS["muted"])
        yy += 55
    return img


def science_slide() -> Image.Image:
    img, d = slide_base("Scientific Moat", "Peer-reviewed method, built into a usable product.", 4)
    draw_wrapped(
        d,
        (94, 270),
        "The Aras Diagram, authored by Aras Izzaddin and coauthors, decomposes model error into interpretable components. That turns model evaluation into defensible decision evidence.",
        font(30),
        COLORS["muted"],
        710,
        line_gap=13,
    )
    eq = "E = sqrt((1-r)^2 + (beta-1)^2 + (alpha-1)^2)"
    d.rounded_rectangle((96, 495, 785, 585), radius=20, fill=alpha((5, 16, 22), 230), outline=alpha(COLORS["teal"], 130), width=2)
    d.text((124, 522), eq, font=font(27, "mono"), fill=COLORS["teal"])
    draw_wrapped(
        d,
        (102, 635),
        "Differentiation: not another dashboard. A transparent model-trust engine.",
        font(26, "semi"),
        COLORS["gold"],
        700,
        line_gap=9,
    )
    panel(d, (96, 730, 785, 890), fill=(13, 35, 42), radius=24)
    d.text((126, 758), "Research validation", font=font(29, "semi"), fill=COLORS["cream"])
    validation = [
        "7 peer-reviewed papers using the Aras Diagram",
        "Professor Vito Iacobellis supports productization",
    ]
    yy = 810
    for item in validation:
        d.ellipse((132, yy + 10, 150, yy + 28), fill=COLORS["teal"])
        draw_wrapped(d, (168, yy), item, font(22), COLORS["muted"], 560, line_gap=4, max_lines=2)
        yy += 48
    if paste_fitted(img, REAL_ASSETS["aras_greek"], (850, 240, 1778, 800), mode="contain", radius=28, bg=(250, 248, 244)):
        d.rounded_rectangle((890, 815, 1740, 873), radius=18, fill=alpha((5, 15, 20), 220))
        d.text((920, 831), "Canonical Aras Diagram: bias, variability, correlation and total error", font=font(24, "semi"), fill=COLORS["cream"])
    else:
        draw_aras_diagram(d, (850, 240, 1778, 800))
    return img


def product_slide() -> Image.Image:
    img, d = slide_base("Product", "Working climate-risk evidence console.", 5)
    if paste_fitted(img, REAL_ASSETS["console"], (94, 300, 770, 915), mode="contain", radius=30, bg=(5, 15, 20)):
        d.rounded_rectangle((130, 828, 705, 890), radius=20, fill=alpha((5, 15, 20), 220))
        d.text((160, 846), "Actual Arasense console screenshot", font=font(26, "semi"), fill=COLORS["cream"])
        cards = [
            ("Map-first", "Select climate points and flood regions."),
            ("Model trust", "Aras Diagram and trust tiers."),
            ("2050 reports", "Flood, heat and drought projection outputs."),
            ("Portfolio", "Rank locations by worsening hazard signal."),
        ]
        card_w, card_h = 440, 170
        start_x, start_y = 835, 330
        for i, (title, sub) in enumerate(cards):
            cx = start_x + (i % 2) * (card_w + 34)
            cy = start_y + (i // 2) * (card_h + 44)
            d.rounded_rectangle((cx, cy, cx + card_w, cy + card_h), radius=24, fill=alpha(COLORS["panel2"], 205), outline=alpha(COLORS["line"], 120), width=1)
            d.text((cx + 30, cy + 28), title, font=font(34, "semi"), fill=COLORS["cream"])
            draw_wrapped(d, (cx + 30, cy + 82), sub, font(24), COLORS["muted"], card_w - 60, line_gap=8)
        proof_box = (835, 795, 1784, 915)
        panel(d, proof_box, fill=(12, 32, 39), radius=26)
        draw_centered_wrapped(
            d,
            (proof_box[0] + 30, proof_box[1] + 21, proof_box[2] - 30, proof_box[1] + 58),
            "What the product proves",
            font(31, "semi"),
            COLORS["cream"],
            820,
            line_gap=0,
        )
        draw_centered_wrapped(
            d,
            (proof_box[0] + 46, proof_box[1] + 63, proof_box[2] - 46, proof_box[3] - 18),
            "Arasense already connects a map workflow, model diagnostics, projection reports and downloadable evidence outputs.",
            font(21),
            COLORS["muted"],
            800,
            line_gap=6,
        )
    else:
        draw_console_mockup(d, (86, 255, 1780, 910))
    return img


def proof_slide() -> Image.Image:
    img, d = slide_base("Proof", "Prototype proof: real outputs, not a mockup.", 6)
    draw_wrapped(
        d,
        (94, 270),
        "The prototype already runs real model-trust and projection workflows. These numbers summarize the Bologna full-ensemble evidence pack and an Italian portfolio ranking.",
        font(30),
        COLORS["muted"],
        730,
        line_gap=12,
    )
    values = [
        ("+14.2%", "mid-century heaviest 1-day rainfall signal"),
        ("34", "CMIP6 models evaluated in the Bologna run"),
        ("78%", "trusted-model weight agreeing on increase"),
    ]
    yy = 500
    colors = [COLORS["teal"], COLORS["gold"], COLORS["blue"]]
    for i, (value, label) in enumerate(values):
        d.rounded_rectangle((94, yy, 820, yy + 112), radius=26, fill=alpha((16, 39, 45), 225), outline=alpha(COLORS["line"], 125), width=1)
        d.text((132, yy + 18), value, font=font(56, "bold"), fill=colors[i])
        draw_wrapped(d, (340, yy + 28), label, font(25), COLORS["muted"], 410, line_gap=7)
        yy += 132

    panel(d, (900, 285, 1780, 535), fill=(13, 35, 42), radius=28)
    d.text((936, 318), "Bologna evidence pack", font=font(34, "semi"), fill=COLORS["cream"])
    bologna = [
        ("32 of 34", "models passed skill screening"),
        ("+5.73 mm", "max 1-day rainfall change by mid-century"),
        ("-0.26 to +11.73 mm", "uncertainty band reported, not hidden"),
    ]
    yy = 382
    for value, label in bologna:
        d.rounded_rectangle((936, yy, 1740, yy + 42), radius=14, fill=alpha((7, 22, 29), 215), outline=alpha(COLORS["line"], 90), width=1)
        d.text((958, yy + 9), value, font=font(21, "semi"), fill=COLORS["gold"])
        d.text((1230, yy + 9), label, font=font(20), fill=COLORS["muted"])
        yy += 52

    panel(d, (900, 560, 1780, 808), fill=(15, 38, 44), radius=26)
    d.text((936, 590), "Italian flood-risk portfolio", font=font(32, "semi"), fill=COLORS["cream"])
    portfolio = [
        ("Rome", "+19%", COLORS["coral"]),
        ("Milan", "+13%", COLORS["gold"]),
        ("Florence", "+11%", COLORS["teal"]),
        ("Bologna", "+11%", COLORS["teal"]),
        ("Venice", "+3%", COLORS["blue"]),
    ]
    xx = 936
    for city, change, col in portfolio:
        d.rounded_rectangle((xx, 655, xx + 148, 748), radius=18, fill=alpha((7, 22, 29), 215), outline=alpha(col, 145), width=2)
        d.text((xx + 18, 673), change, font=font(28, "bold"), fill=col)
        d.text((xx + 18, 713), city, font=font(19), fill=COLORS["muted"])
        xx += 160
    d.text((936, 770), "Same trust workflow, ranked across locations.", font=font(21), fill=COLORS["muted"])

    panel(d, (900, 835, 1780, 958), fill=(12, 32, 39), radius=26)
    d.text((936, 860), "Product proof", font=font(31, "semi"), fill=COLORS["cream"])
    draw_wrapped(
        d,
        (936, 904),
        "Every result shows trusted models, rejected models, uncertainty, agreement and method before the hazard number is used.",
        font(21),
        COLORS["muted"],
        760,
        line_gap=7,
    )
    panel(d, (92, 890, 820, 958), fill=(12, 32, 39), radius=22)
    d.text((132, 909), "Scientific validation becomes buyer-readable evidence.", font=font(24, "semi"), fill=COLORS["cream"])
    return img


def market_slide() -> Image.Image:
    img, d = slide_base("Market", "Beachhead: organizations that must defend climate-risk decisions.", 7)
    draw_wrapped(
        d,
        (94, 270),
        "The beachhead buyers are public, infrastructure, finance and consulting teams that need climate-risk evidence they can explain to technical reviewers, boards, regulators or clients.",
        font(30),
        COLORS["muted"],
        1400,
        line_gap=13,
    )
    draw_market_segments(d, (94, 435, 1780, 880))
    return img


def business_slide() -> Image.Image:
    img, d = slide_base("Business Model", "Start with paid pilots, then scale into platform access.", 8)
    draw_wrapped(
        d,
        (94, 270),
        "The initial sale is deliberately narrow: one geography, one decision problem, one defensible evidence pack. Repeated portfolio and reporting needs become platform/API access.",
        font(30),
        COLORS["muted"],
        1220,
        line_gap=13,
    )
    draw_ladder(d, 120, 515)
    panel(d, (1260, 505, 1780, 930), fill=(16, 41, 47), radius=28)
    d.text((1300, 545), "Indicative pricing", font=font(34, "semi"), fill=COLORS["cream"])
    pricing = [
        ("Pilot", "EUR 3k-10k"),
        ("Platform", "EUR 15k-50k / year"),
        ("Portfolio API", "per location / asset"),
    ]
    yy = 607
    for label, value in pricing:
        d.rounded_rectangle((1300, yy, 1740, yy + 56), radius=15, fill=alpha((8, 25, 31), 210), outline=alpha(COLORS["line"], 85), width=1)
        d.text((1320, yy + 14), label, font=font(20, "semi"), fill=COLORS["gold"])
        d.text((1510, yy + 14), value, font=font(20), fill=COLORS["muted"])
        yy += 66
    d.text((1300, 810), "Pilot includes", font=font(24, "semi"), fill=COLORS["cream"])
    bullets = ["model-trust audit", "multi-hazard report", "pilot roadmap"]
    yy = 842
    for item in bullets:
        d.ellipse((1306, yy + 9, 1322, yy + 25), fill=COLORS["teal"])
        d.text((1340, yy), item, font=font(19), fill=COLORS["muted"])
        yy += 28
    return img


def roadmap_slide() -> Image.Image:
    img, d = slide_base("Roadmap", "Roadmap from finalist to pilot-ready startup.", 9)
    draw_wrapped(
        d,
        (94, 270),
        "With R&D 4 support, Arasense will move from working prototype to validated pilot: customer discovery, one design-partner geography, stronger Italian and European evidence, and a packaged commercial offer.",
        font(30),
        COLORS["muted"],
        1400,
        line_gap=13,
    )
    draw_timeline(d, (130, 455, 1745, 810))
    panel(d, (114, 835, 1780, 920), fill=(15, 38, 44), radius=22)
    d.text((154, 858), "Pilot milestone: one design partner, one pilot geography, and a validation-ready evidence pack before PNI.", font=font(30, "semi"), fill=COLORS["gold"])
    return img


def team_slide() -> Image.Image:
    img, d = slide_base("Team & Ask", "Research-to-market from Politecnico di Bari.", 10)
    draw_wrapped(
        d,
        (94, 270),
        "Arasense is applying as an informal project team. The aim is to turn peer-reviewed Aras Diagram research and delivered Puglia basin experience into a pilot-ready climate-risk intelligence startup.",
        font(30),
        COLORS["muted"],
        1260,
        line_gap=13,
    )
    team = [
        ("Aras Izzaddin", "Founder and Lead Researcher. Author of the Aras Diagram method, used across seven peer-reviewed papers. Climate-model evaluation and evidence software."),
        ("Marwah Yaseen", "Postdoctoral researcher and project collaborator supporting validation, research development, coordination, and the StartCup pilot pathway."),
    ]
    y = 500
    for i, (name, desc) in enumerate(team):
        panel(d, (96 + i * 830, y, 850 + i * 830, y + 260), fill=(15, 39, 45), radius=30)
        d.ellipse((140 + i * 830, y + 46, 238 + i * 830, y + 144), fill=[COLORS["teal"], COLORS["gold"]][i])
        initials = "".join(part[0] for part in name.split()[:2])
        d.text((169 + i * 830, y + 72), initials, font=font(33, "bold"), fill=COLORS["ink"])
        d.text((270 + i * 830, y + 48), name, font=font(37, "semi"), fill=COLORS["cream"])
        draw_wrapped(d, (270 + i * 830, y + 104), desc, font(24), COLORS["muted"], 500, line_gap=9)
    panel(d, (96, 772, 1780, 950), fill=(12, 32, 39), radius=28)
    d.text((136, 792), "R&D 4 support will help secure pilots, strengthen validation and refine the business model.", font=font(27, "semi"), fill=COLORS["cream"])
    d.text((136, 842), "Ask: R&D 4 mentoring plus introductions to a Puglia/Italy design partner for a paid pilot.", font=font(26, "semi"), fill=COLORS["gold"])
    contact_text = f"{WEBSITE_URL}   |   {LINKEDIN_URL}   |   {X_URL}"
    d.text((136, 898), contact_text, font=font(26, "semi"), fill=COLORS["teal"])
    return img


def make_slides() -> list[Image.Image]:
    makers = [
        title_slide,
        problem_slide,
        solution_slide,
        science_slide,
        product_slide,
        proof_slide,
        market_slide,
        business_slide,
        roadmap_slide,
        team_slide,
    ]
    return [maker().convert("RGB") for maker in makers]


def save_slide_images(slides: list[Image.Image]) -> list[Path]:
    SLIDE_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, slide in enumerate(slides, start=1):
        path = SLIDE_DIR / f"slide-{i:02d}.jpg"
        slide.save(path, "JPEG", quality=91, optimize=True, progressive=True)
        paths.append(path)
    return paths


def create_pdf(slides: list[Image.Image]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slides[0].save(PDF_PATH, save_all=True, append_images=slides[1:], resolution=150, quality=91)
    add_pdf_links()


def add_pdf_links() -> None:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, NumberObject, RectangleObject

    reader = PdfReader(str(PDF_PATH))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    last_page = reader.pages[-1]
    page_width = float(last_page.mediabox.width)
    page_height = float(last_page.mediabox.height)
    scale_x = page_width / W
    scale_y = page_height / H

    text_font = font(26, "semi")
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    x = 136
    y = 898
    link_padding = 8
    parts = [
        (WEBSITE_URL, WEBSITE_URL),
        ("   |   ", None),
        (LINKEDIN_URL, LINKEDIN_URL),
        ("   |   ", None),
        (X_URL, X_URL),
    ]

    for text, uri in parts:
        width = measure.textlength(text, font=text_font)
        if uri:
            x1 = (x - link_padding) * scale_x
            x2 = (x + width + link_padding) * scale_x
            y1 = (H - (y + 42)) * scale_y
            y2 = (H - (y - link_padding)) * scale_y
            writer.add_uri(
                page_number=len(reader.pages) - 1,
                uri=uri,
                rect=RectangleObject([x1, y1, x2, y2]),
                border=ArrayObject([NumberObject(0), NumberObject(0), NumberObject(0)]),
            )
        x += width

    linked_path = PDF_PATH.with_suffix(".linked.pdf")
    with linked_path.open("wb") as f:
        writer.write(f)
    linked_path.replace(PDF_PATH)


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def content_types() -> str:
    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    overrides.extend(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, len(SLIDES) + 1)
    )
    for i in range(1, len(SLIDES) + 1):
        overrides.append(f'<Override PartName="/ppt/media/image{i}.jpg" ContentType="image/jpeg"/>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="xml" ContentType="application/xml"/>\n  '
        + "\n  ".join(overrides)
        + "\n</Types>"
    )


def root_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def core_xml() -> str:
    current = now_iso()
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:dcterms="http://purl.org/dc/terms/"
  xmlns:dcmitype="http://purl.org/dc/dcmitype/"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Arasense StartCup Puglia Visual Pitch</dc:title>
  <dc:creator>Arasense</dc:creator>
  <cp:lastModifiedBy>Arasense</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{current}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{current}</dcterms:modified>
</cp:coreProperties>"""


def app_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
  xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Arasense Visual Pitch Generator</Application>
  <PresentationFormat>On-screen Show (16:9)</PresentationFormat>
  <Slides>{len(SLIDES)}</Slides>
  <Company>Arasense</Company>
</Properties>"""


def presentation_xml() -> str:
    slide_ids = "\n".join(
        f'    <p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, len(SLIDES) + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>
{slide_ids}
  </p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>"""


def presentation_rels() -> str:
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    ]
    for i in range(1, len(SLIDES) + 1):
        rels.append(
            f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n  '
        + "\n  ".join(rels)
        + "\n</Relationships>"
    )


def slide_master_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>"""


def slide_master_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""


def slide_layout_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""


def slide_layout_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""


def theme_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Arasense Visual">
  <a:themeElements>
    <a:clrScheme name="Arasense"><a:dk1><a:srgbClr val="081218"/></a:dk1><a:lt1><a:srgbClr val="F5F0E2"/></a:lt1><a:dk2><a:srgbClr val="0D2026"/></a:dk2><a:lt2><a:srgbClr val="FFFFFF"/></a:lt2><a:accent1><a:srgbClr val="4FD9A9"/></a:accent1><a:accent2><a:srgbClr val="EBB75A"/></a:accent2><a:accent3><a:srgbClr val="E55B4A"/></a:accent3><a:accent4><a:srgbClr val="4C91E8"/></a:accent4><a:accent5><a:srgbClr val="128274"/></a:accent5><a:accent6><a:srgbClr val="A0B3C0"/></a:accent6><a:hlink><a:srgbClr val="4FD9A9"/></a:hlink><a:folHlink><a:srgbClr val="A6BBB2"/></a:folHlink></a:clrScheme>
    <a:fontScheme name="Arasense"><a:majorFont><a:latin typeface="Segoe UI"/></a:majorFont><a:minorFont><a:latin typeface="Segoe UI"/></a:minorFont></a:fontScheme>
    <a:fmtScheme name="Arasense"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme>
  </a:themeElements>
</a:theme>"""


def pptx_link_shapes(index: int) -> str:
    if index != 10:
        return ""

    emu_x = 12192000 / W
    emu_y = 6858000 / H
    text_font = font(26, "semi")
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    x = 136
    y = 898
    link_padding = 8
    shapes: list[str] = []
    parts = [
        (WEBSITE_URL, "rId3", "Website link"),
        ("   |   ", None, ""),
        (LINKEDIN_URL, "rId4", "LinkedIn link"),
        ("   |   ", None, ""),
        (X_URL, "rId5", "X link"),
    ]
    shape_id = 3
    for text, rel_id, name in parts:
        width = measure.textlength(text, font=text_font)
        if rel_id:
            off_x = round((x - link_padding) * emu_x)
            off_y = round((y - link_padding) * emu_y)
            ext_x = round((width + link_padding * 2) * emu_x)
            ext_y = round(52 * emu_y)
            shapes.append(
                f"""      <p:sp>
        <p:nvSpPr><p:cNvPr id="{shape_id}" name="{esc(name)}"><a:hlinkClick r:id="{rel_id}"/></p:cNvPr><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:spPr><a:xfrm><a:off x="{off_x}" y="{off_y}"/><a:ext cx="{ext_x}" cy="{ext_y}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
        <p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>
      </p:sp>"""
            )
            shape_id += 1
        x += width
    return "\n".join(shapes)


def slide_xml(index: int) -> str:
    extra_shapes = pptx_link_shapes(index)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
  xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      <p:pic>
        <p:nvPicPr><p:cNvPr id="2" name="slide-{index:02d}.jpg"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
        <p:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
        <p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="12192000" cy="6858000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
      </p:pic>
{extra_shapes}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def slide_rels(index: int) -> str:
    links = ""
    if index == 10:
        links = f"""
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="{esc(WEBSITE_URL)}" TargetMode="External"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="{esc(LINKEDIN_URL)}" TargetMode="External"/>
  <Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="{esc(X_URL)}" TargetMode="External"/>"""
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image{index}.jpg"/>
{links}
</Relationships>"""


def create_pptx(slide_paths: list[Path]) -> None:
    with ZipFile(PPTX_PATH, "w", ZIP_DEFLATED) as deck:
        deck.writestr("[Content_Types].xml", content_types())
        deck.writestr("_rels/.rels", root_rels())
        deck.writestr("docProps/core.xml", core_xml())
        deck.writestr("docProps/app.xml", app_xml())
        deck.writestr("ppt/presentation.xml", presentation_xml())
        deck.writestr("ppt/_rels/presentation.xml.rels", presentation_rels())
        deck.writestr("ppt/theme/theme1.xml", theme_xml())
        deck.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
        deck.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels())
        deck.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
        deck.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels())
        for i, path in enumerate(slide_paths, start=1):
            deck.writestr(f"ppt/slides/slide{i}.xml", slide_xml(i))
            deck.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", slide_rels(i))
            deck.write(path, f"ppt/media/image{i}.jpg")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slides = make_slides()
    slide_paths = save_slide_images(slides)
    create_pdf(slides)
    create_pptx(slide_paths)
    print(PDF_PATH)
    print(PPTX_PATH)
    for path in slide_paths:
        print(path)


if __name__ == "__main__":
    main()

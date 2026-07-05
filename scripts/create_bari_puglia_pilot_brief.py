from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DOCS_PDF = ROOT / "docs" / "bari-puglia-climate-risk-brief.pdf"
SITE_PDF = ROOT / "site" / "bari-puglia-climate-risk-brief.pdf"
COVER_JPG = ROOT / "site" / "bari-puglia-brief-cover.jpg"
PRODUCT_SHOT = ROOT / "site" / "product-console.jpg"

W, H = 1400, 1980
BG = "#07141b"
PANEL = "#0d212b"
PANEL_2 = "#102a32"
TEXT = "#edf8f3"
MUTED = "#a9c2bb"
ACCENT = "#65d9ad"
GOLD = "#f2c166"
BLUE = "#72a7ff"
CORAL = "#ef675c"
LINE = "#31534f"


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    candidates = {
        "regular": [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ],
        "semibold": [
            "C:/Windows/Fonts/seguisb.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ],
        "bold": [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ],
    }[weight]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


F_TITLE = font(82, "bold")
F_H1 = font(54, "bold")
F_H2 = font(36, "semibold")
F_BODY = font(28)
F_SMALL = font(22)
F_LABEL = font(20, "semibold")
F_BIG_NUM = font(48, "bold")


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(text: str, chars: int) -> list[str]:
    lines = []
    for part in text.split("\n"):
        if not part:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(part, width=chars, break_long_words=False))
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.ImageFont,
    fill: str = MUTED,
    chars: int = 58,
    line_gap: int = 10,
) -> int:
    x, y = xy
    for line in wrap_text(text, chars):
        draw.text((x, y), line, font=fnt, fill=fill)
        _, line_h = text_size(draw, line or "A", fnt)
        y += line_h + line_gap
    return y


def rounded(draw: ImageDraw.ImageDraw, box, fill=PANEL, outline=LINE, radius=24, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def pill(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, fill: str, color="#061117"):
    tw, th = text_size(draw, text, F_LABEL)
    pad_x, pad_y = 22, 12
    draw.rounded_rectangle(
        (x, y, x + tw + pad_x * 2, y + th + pad_y * 2),
        radius=28,
        fill=fill,
    )
    draw.text((x + pad_x, y + pad_y - 1), text, font=F_LABEL, fill=color)


def header(draw: ImageDraw.ImageDraw, title: str, page: str):
    draw.rectangle((0, 0, W, H), fill=BG)
    for x in range(0, W, 64):
        draw.line((x, 0, x, H), fill="#0d252b", width=1)
    for y in range(0, H, 64):
        draw.line((0, y, W, y), fill="#0d252b", width=1)
    draw.rectangle((0, 0, 18, H), fill="#128274")
    draw.rectangle((18, 0, 26, H), fill=GOLD)
    draw.text((80, 70), "ARASENSE", font=F_LABEL, fill=ACCENT)
    draw.text((80, H - 72), title, font=F_SMALL, fill=MUTED)
    draw.text((W - 170, H - 72), page, font=F_SMALL, fill=MUTED)


def card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    heading: str,
    body: str,
    accent: str = ACCENT,
):
    rounded(draw, box, fill=PANEL, outline=LINE, radius=26)
    x0, y0, x1, _ = box
    draw.ellipse((x0 + 36, y0 + 36, x0 + 82, y0 + 82), fill=accent)
    draw.text((x0 + 104, y0 + 36), label.upper(), font=F_LABEL, fill=accent)
    draw.text((x0 + 36, y0 + 112), heading, font=F_H2, fill=TEXT)
    draw_wrapped(draw, (x0 + 36, y0 + 172), body, F_BODY, chars=34, line_gap=8)


def create_cover() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(d, "Bari / Puglia Climate-Risk Evidence Brief", "01")

    d.text((80, 170), "Bari / Puglia", font=F_TITLE, fill=TEXT)
    d.text((80, 270), "Climate-Risk Evidence Brief", font=F_TITLE, fill=TEXT)
    draw_wrapped(
        d,
        (84, 390),
        "A regional application of Arasense model-trust intelligence for adaptation, infrastructure, and advisory teams.",
        F_H2,
        fill=MUTED,
        chars=46,
        line_gap=14,
    )

    pill(d, 84, 550, "model trust", ACCENT)
    pill(d, 310, 550, "2050 hazards", GOLD)
    pill(d, 560, 550, "evidence reports", BLUE, "#ffffff")

    rounded(d, (80, 690, 1320, 1180), fill=PANEL, outline=LINE, radius=30)
    d.text((130, 740), "Purpose", font=F_H1, fill=TEXT)
    y = draw_wrapped(
        d,
        (130, 820),
        "Arasense evaluates which climate models are credible for a specific location before using them for projections. For Bari and Puglia, the workflow can support flood-driving rainfall, heat, and drought evidence for planning and investment-facing decisions.",
        F_BODY,
        chars=67,
        line_gap=12,
    )
    draw_wrapped(
        d,
        (130, y + 28),
        "The output is not a single black-box number. It is a traceable evidence pack: trusted models, rejected models, projected hazard signal, uncertainty range, and model agreement.",
        F_BODY,
        chars=67,
        line_gap=12,
    )

    if PRODUCT_SHOT.exists():
        shot = Image.open(PRODUCT_SHOT).convert("RGB")
        shot.thumbnail((560, 360))
        x = 760
        y = 1270
        rounded(d, (x - 20, y - 20, x + shot.width + 20, y + shot.height + 20), fill="#061117", outline=LINE, radius=26)
        img.paste(shot, (x, y))

    card(
        d,
        (80, 1250, 650, 1585),
        "Regional fit",
        "Bari and Puglia",
        "Coastal rainfall, heat exposure, infrastructure resilience, and adaptation planning are natural applications for a first regional evidence pack.",
        GOLD,
    )
    rounded(d, (80, 1625, 650, 1880), fill=PANEL, outline=LINE, radius=26)
    d.ellipse((116, 1661, 162, 1707), fill=ACCENT)
    d.text((184, 1661), "CONTACT", font=F_LABEL, fill=ACCENT)
    d.text((116, 1734), "Aras Izzaddin", font=F_H2, fill=TEXT)
    draw_wrapped(
        d,
        (116, 1794),
        "Founder & Lead Researcher, Arasense. Politecnico di Bari. arasbotan.izzaddin@poliba.it",
        F_SMALL,
        chars=38,
        line_gap=6,
    )
    return img


def create_details() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(d, "Bari / Puglia Climate-Risk Evidence Brief", "02")

    d.text((80, 160), "What the evidence pack contains", font=F_H1, fill=TEXT)
    draw_wrapped(
        d,
        (84, 230),
        "A focused regional study can evaluate selected Bari and Puglia locations through the same Arasense workflow used for existing Bologna and Italian portfolio examples.",
        F_BODY,
        chars=70,
        line_gap=10,
    )

    items = [
        ("1", "Select locations", "City points, infrastructure assets, coastal zones, or a small portfolio of sites.", ACCENT),
        ("2", "Score model trust", "Compare model history against observations and decompose error with the Aras Diagram.", GOLD),
        ("3", "Project hazards", "Estimate mid-century rainfall, heat, and drought signals using skill-weighted models.", BLUE),
        ("4", "Package evidence", "Deliver a concise report with uncertainty, agreement, interpretation, and method notes.", CORAL),
    ]
    y = 380
    for num, title, body, color in items:
        rounded(d, (80, y, 1320, y + 205), fill=PANEL, outline=LINE, radius=26)
        d.ellipse((122, y + 48, 222, y + 148), fill=color)
        nw, nh = text_size(d, num, F_BIG_NUM)
        d.text((172 - nw / 2, y + 94 - nh / 2), num, font=F_BIG_NUM, fill="#061117")
        d.text((260, y + 44), title, font=F_H2, fill=TEXT)
        draw_wrapped(d, (260, y + 96), body, F_BODY, chars=58, line_gap=8)
        y += 235

    d.text((80, 1360), "Evidence already demonstrated", font=F_H1, fill=TEXT)
    metrics = [
        ("Bologna", "+14.2%", "max 1-day rainfall by mid-century; 32 of 34 models passed skill screening."),
        ("Italian portfolio", "Rome #1", "sample flood-driving rainfall ranking across five cities."),
        ("Method", "Aras Diagram", "peer-reviewed model-evaluation basis for trust scoring."),
    ]
    x = 80
    for label, value, body in metrics:
        rounded(d, (x, 1450, x + 390, 1760), fill=PANEL_2, outline=LINE, radius=24)
        d.text((x + 30, 1488), label.upper(), font=F_LABEL, fill=ACCENT)
        d.text((x + 30, 1545), value, font=F_BIG_NUM, fill=TEXT)
        draw_wrapped(d, (x + 30, 1620), body, F_SMALL, chars=30, line_gap=8)
        x += 425

    draw_wrapped(
        d,
        (84, 1830),
        "Flood-screening outputs are validation-stage evidence interpreted alongside local data, field knowledge, and engineering analysis.",
        F_SMALL,
        fill=MUTED,
        chars=82,
        line_gap=6,
    )
    return img


def main() -> None:
    pages = [create_cover(), create_details()]
    DOCS_PDF.parent.mkdir(parents=True, exist_ok=True)
    SITE_PDF.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(DOCS_PDF, save_all=True, append_images=pages[1:], resolution=150, quality=92)
    pages[0].save(SITE_PDF, save_all=True, append_images=pages[1:], resolution=150, quality=92)
    cover = pages[0].resize((700, 990))
    cover.save(COVER_JPG, quality=92)
    print(DOCS_PDF)
    print(SITE_PDF)
    print(COVER_JPG)


if __name__ == "__main__":
    main()

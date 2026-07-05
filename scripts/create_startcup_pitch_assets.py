from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from textwrap import wrap
from zipfile import ZIP_DEFLATED, ZipFile
import html


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs"
PPTX_PATH = OUT_DIR / "arasense-startcup-pitch.pptx"
PDF_PATH = OUT_DIR / "arasense-startcup-pitch.pdf"


SLIDES = [
    {
        "kicker": "R&D 4 StartCup Puglia 2026",
        "title": "Arasense",
        "subtitle": "The model-trust layer for climate risk",
        "bullets": [
            "Climate-risk evidence that shows which models can be trusted, where, and why.",
            "Project by Aras Izzaddin and Marwah Yaseen, connected to Politecnico di Bari.",
        ],
    },
    {
        "kicker": "Problem",
        "title": "Climate models disagree. Decisions still need evidence.",
        "subtitle": "Averages can hide weak local models.",
        "bullets": [
            "Institutions use climate models for adaptation, insurance, finance, and infrastructure planning.",
            "Common workflows average whole ensembles, mixing credible local models with weak ones.",
            "The final number may look precise but can be difficult to defend to a board, regulator, or technical reviewer.",
        ],
    },
    {
        "kicker": "Solution",
        "title": "Score trust before projecting risk.",
        "subtitle": "Arasense adds a model-trust layer to climate-risk analysis.",
        "bullets": [
            "Compare each model with observations for a specific location and hazard.",
            "Reject models that fail a skill benchmark.",
            "Weight trusted models by skill and report uncertainty and model agreement.",
            "Generate transparent reports for flood-driving rainfall, heat, and drought.",
        ],
    },
    {
        "kicker": "Scientific Core",
        "title": "The Aras Diagram",
        "subtitle": "A peer-reviewed model-evaluation method authored by Aras Izzaddin and coauthors.",
        "bullets": [
            "Decomposes model error into bias, variability, and timing components.",
            "Explains why a model is credible or weak, instead of returning only one score.",
            "Turns scientific model evaluation into practical decision evidence.",
        ],
    },
    {
        "kicker": "Product",
        "title": "From model diagnosis to decision-ready reports.",
        "subtitle": "A working prototype already exists.",
        "bullets": [
            "Map-first climate diagnostic console.",
            "Model Trust Report and Aras Diagram visualization.",
            "Trust-weighted 2050 projections and scenario comparison.",
            "Multi-hazard reports, portfolio ranking, and downloadable evidence files.",
        ],
    },
    {
        "kicker": "Proof",
        "title": "Working on real climate data today.",
        "subtitle": "Bologna is a current demonstration case.",
        "bullets": [
            "Mid-century heaviest 1-day rainfall: about +14 percent in a full-ensemble Bologna run.",
            "32 of 34 models trusted, with about 78 percent agreeing on the rainfall direction.",
            "Hottest day example: about 37 C to 41 C.",
            "Automated tests cover the scientific and reporting core.",
        ],
    },
    {
        "kicker": "Market",
        "title": "B2B and institutional climate-risk users.",
        "subtitle": "The buyer needs defensible evidence, not only a dashboard.",
        "bullets": [
            "Municipalities, regions, and public authorities planning adaptation.",
            "Infrastructure owners, utilities, and transport operators assessing exposure.",
            "Banks, asset managers, insurers, and reinsurers evaluating portfolios.",
            "Engineering, environmental, and risk-consulting firms.",
        ],
    },
    {
        "kicker": "Business Model",
        "title": "Pilot, platform, portfolio API.",
        "subtitle": "Start with focused B2B pilots, then scale through recurring access.",
        "bullets": [
            "Paid pilots for one geography, portfolio, or decision question.",
            "Platform subscriptions for recurring climate-risk analysis and reports.",
            "Portfolio/API pricing by location, asset, or exposure set.",
            "Specialist evidence packs for public authorities, insurers, and consultants.",
        ],
    },
    {
        "kicker": "Roadmap",
        "title": "Move from prototype to validated pilots.",
        "subtitle": "The next milestone is market validation with design partners.",
        "bullets": [
            "Secure first design partners or pilot users.",
            "Convert reports into polished PDF outputs.",
            "Expand validation case studies in Italy and Europe.",
            "Harden public demo access and package commercial pilot offers.",
        ],
    },
    {
        "kicker": "Team and Ask",
        "title": "Research-to-market from Politecnico di Bari.",
        "subtitle": "Aras Izzaddin and Marwah Yaseen",
        "bullets": [
            "Aras Izzaddin: founder, lead researcher, author of the Aras Diagram method.",
            "Marwah Yaseen: team member supporting the project development path.",
            "StartCup support will help convert the prototype into pilots, demo assets, and validation evidence.",
            "Goal: build a defensible climate-risk intelligence startup from Puglia.",
        ],
    },
]


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def text_run(text: str, size: int, color: str, bold: bool = False) -> str:
    bold_attr = ' b="1"' if bold else ""
    return (
        f'<a:r><a:rPr lang="en-US" sz="{size}"{bold_attr}>'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        '<a:latin typeface="Aptos"/>'
        "</a:rPr>"
        f"<a:t>{esc(text)}</a:t></a:r>"
    )


def paragraph(text: str, size: int, color: str, bold: bool = False) -> str:
    return (
        '<a:p><a:pPr marL="0" indent="0"/>'
        f"{text_run(text, size, color, bold)}"
        f'<a:endParaRPr lang="en-US" sz="{size}"/>'
        "</a:p>"
    )


def text_box(
    shape_id: int,
    name: str,
    x: int,
    y: int,
    w: int,
    h: int,
    lines: list[str],
    size: int,
    color: str,
    bold: bool = False,
) -> str:
    paras = "".join(paragraph(line, size, color, bold) for line in lines)
    return f"""
<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="{esc(name)}"/>
    <p:cNvSpPr txBox="1"/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    <a:noFill/>
    <a:ln><a:noFill/></a:ln>
  </p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square" anchor="t"/>
    <a:lstStyle/>
    {paras}
  </p:txBody>
</p:sp>"""


def rect(shape_id: int, name: str, x: int, y: int, w: int, h: int, color: str) -> str:
    return f"""
<p:sp>
  <p:nvSpPr>
    <p:cNvPr id="{shape_id}" name="{esc(name)}"/>
    <p:cNvSpPr/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    <a:solidFill><a:srgbClr val="{color}"/></a:solidFill>
    <a:ln><a:noFill/></a:ln>
  </p:spPr>
</p:sp>"""


def slide_xml(slide: dict[str, object], index: int) -> str:
    bullets = [f"- {item}" for item in slide["bullets"]]  # type: ignore[index]
    shape_id = 2
    shapes = [
        rect(shape_id, "Accent", 0, 0, 300000, 6858000, "0F766E"),
        rect(shape_id + 1, "Corner", 10200000, 0, 1920000, 6858000, "F2C94C"),
        text_box(shape_id + 2, "Kicker", 780000, 520000, 7800000, 420000, [slide["kicker"]], 1500, "0F766E", True),  # type: ignore[list-item]
        text_box(shape_id + 3, "Title", 760000, 1080000, 9300000, 1200000, [slide["title"]], 3500, "10231F", True),  # type: ignore[list-item]
        text_box(shape_id + 4, "Subtitle", 790000, 2250000, 9000000, 800000, [slide["subtitle"]], 2000, "3F4F49", False),  # type: ignore[list-item]
        text_box(shape_id + 5, "Bullets", 820000, 3320000, 9000000, 2300000, bullets, 1650, "10231F", False),
        text_box(shape_id + 6, "Footer", 780000, 6250000, 7500000, 250000, [f"Arasense | Slide {index}"], 900, "5F6F69", False),
    ]
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}">
  <p:cSld>
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="F7F3EA"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      {''.join(shapes)}
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def rels_for_slide() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>"""


def presentation_xml() -> str:
    slide_ids = "\n".join(
        f'    <p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, len(SLIDES) + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}">
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
  <dc:title>Arasense StartCup Puglia Pitch</dc:title>
  <dc:creator>Arasense</dc:creator>
  <cp:lastModifiedBy>Arasense</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{current}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{current}</dcterms:modified>
</cp:coreProperties>"""


def app_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
  xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Arasense Pitch Generator</Application>
  <PresentationFormat>On-screen Show (16:9)</PresentationFormat>
  <Slides>{len(SLIDES)}</Slides>
  <Company>Arasense</Company>
</Properties>"""


def slide_master_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles>
    <p:titleStyle><a:lvl1pPr algn="l"><a:defRPr sz="4400"/></a:lvl1pPr></p:titleStyle>
    <p:bodyStyle><a:lvl1pPr marL="0" indent="0" algn="l"><a:defRPr sz="1800"/></a:lvl1pPr></p:bodyStyle>
    <p:otherStyle><a:lvl1pPr algn="l"><a:defRPr sz="1800"/></a:lvl1pPr></p:otherStyle>
  </p:txStyles>
</p:sldMaster>"""


def slide_master_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""


def slide_layout_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:p="{P_NS}" type="blank" preserve="1">
  <p:cSld name="Blank">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""


def slide_layout_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""


def theme_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="{A_NS}" name="Arasense">
  <a:themeElements>
    <a:clrScheme name="Arasense">
      <a:dk1><a:srgbClr val="10231F"/></a:dk1>
      <a:lt1><a:srgbClr val="F7F3EA"/></a:lt1>
      <a:dk2><a:srgbClr val="3F4F49"/></a:dk2>
      <a:lt2><a:srgbClr val="FFFFFF"/></a:lt2>
      <a:accent1><a:srgbClr val="0F766E"/></a:accent1>
      <a:accent2><a:srgbClr val="E85D3F"/></a:accent2>
      <a:accent3><a:srgbClr val="F2C94C"/></a:accent3>
      <a:accent4><a:srgbClr val="2F80ED"/></a:accent4>
      <a:accent5><a:srgbClr val="27AE60"/></a:accent5>
      <a:accent6><a:srgbClr val="9B51E0"/></a:accent6>
      <a:hlink><a:srgbClr val="0F766E"/></a:hlink>
      <a:folHlink><a:srgbClr val="3F4F49"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Arasense">
      <a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont>
      <a:minorFont><a:latin typeface="Aptos"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Arasense"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme>
  </a:themeElements>
</a:theme>"""


def create_pptx() -> None:
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
        for i, slide in enumerate(SLIDES, start=1):
            deck.writestr(f"ppt/slides/slide{i}.xml", slide_xml(slide, i))
            deck.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", rels_for_slide())


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def page_stream(slide: dict[str, object], index: int) -> str:
    commands = [
        "0.969 0.953 0.918 rg",
        "0 0 842 595 re f",
        "0.059 0.463 0.431 rg",
        "0 0 24 595 re f",
        "0.949 0.788 0.298 rg",
        "742 0 100 595 re f",
        "BT",
        "/F1 11 Tf",
        "0.059 0.463 0.431 rg",
        f"58 535 Td ({pdf_escape(str(slide['kicker']).upper())}) Tj",
        "ET",
        "BT",
        "/F2 34 Tf",
        "0.063 0.137 0.122 rg",
        f"58 482 Td ({pdf_escape(str(slide['title']))}) Tj",
        "ET",
    ]

    subtitle_lines = wrap(str(slide["subtitle"]), 72)
    y = 432
    commands.extend(["BT", "/F1 17 Tf", "0.247 0.310 0.286 rg"])
    for line in subtitle_lines:
        commands.append(f"58 {y} Td ({pdf_escape(line)}) Tj")
        y -= 23
    commands.append("ET")

    y = 340
    commands.extend(["BT", "/F1 14 Tf", "0.063 0.137 0.122 rg"])
    for bullet in slide["bullets"]:  # type: ignore[index]
        wrapped = wrap(str(bullet), 82)
        commands.append(f"78 {y} Td (- {pdf_escape(wrapped[0])}) Tj")
        y -= 20
        for line in wrapped[1:]:
            commands.append(f"92 {y} Td ({pdf_escape(line)}) Tj")
            y -= 20
        y -= 8
    commands.append("ET")

    commands.extend(
        [
            "BT",
            "/F1 9 Tf",
            "0.373 0.435 0.412 rg",
            f"58 35 Td (Arasense | R&D 4 StartCup Puglia 2026 | Slide {index}) Tj",
            "ET",
        ]
    )
    return "\n".join(commands)


def create_pdf() -> None:
    objects: list[bytes] = []

    def add(obj: str | bytes) -> int:
        objects.append(obj.encode("latin-1") if isinstance(obj, str) else obj)
        return len(objects)

    catalog_id = add("<< /Type /Catalog /Pages 2 0 R >>")
    pages_id = add("PLACEHOLDER")
    font_regular_id = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font_bold_id = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

    page_ids = []
    for i, slide in enumerate(SLIDES, start=1):
        stream = page_stream(slide, i).encode("latin-1")
        stream_id = add(f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream")
        page_id = add(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 842 595] "
            f"/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R >> >> "
            f"/Contents {stream_id} 0 R >>"
        )
        page_ids.append(page_id)

    objects[pages_id - 1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {len(page_ids)} >>"
    ).encode("latin-1")

    output = bytearray()
    output.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj_id, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{obj_id} 0 obj\n".encode("latin-1"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "latin-1"
        )
    )
    PDF_PATH.write_bytes(output)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    create_pptx()
    create_pdf()
    print(PPTX_PATH)
    print(PDF_PATH)


if __name__ == "__main__":
    main()

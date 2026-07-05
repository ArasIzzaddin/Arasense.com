"""
Render one 1200x630 OG card per trust-profile city into site/og/trust/.

Reads site/atlas-data.js (same numbers as the pages), writes a temp HTML per
city and screenshots it with headless Edge. Design mirrors the site OG cards:
deep-green field, grid, glows, Instrument Serif city line, mono facts, and a
confidence/rank chip.

    python scripts/make_city_ogs.py
"""

import json
import os
import subprocess
import tempfile
import time

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ATLAS_JS = "site/atlas-data.js"
OUT_DIR = "site/og/trust"
TMP = "scripts/_tmp_city_og.html"

CARD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><style>
  @font-face {{ font-family:"Instrument Serif"; src:url("../site/fonts/instrument-serif-400.woff2") format("woff2"); font-weight:400; font-style:normal; }}
  @font-face {{ font-family:"Instrument Serif"; src:url("../site/fonts/instrument-serif-400-italic.woff2") format("woff2"); font-weight:400; font-style:italic; }}
  @font-face {{ font-family:"Inter"; src:url("../site/fonts/inter-var.woff2") format("woff2"); font-weight:100 900; }}
  @font-face {{ font-family:"JetBrains Mono"; src:url("../site/fonts/jetbrains-mono-var.woff2") format("woff2"); font-weight:100 800; }}
  * {{ margin:0; box-sizing:border-box; }}
  html,body {{ width:1200px; height:630px; overflow:hidden; }}
  body {{ background:#050d0b; color:#eaf6f0; font-family:"Inter",sans-serif; position:relative; }}
  .grid {{ position:absolute; inset:0;
    background-image:linear-gradient(rgba(110,231,183,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(110,231,183,.045) 1px,transparent 1px);
    background-size:46px 46px;
    -webkit-mask-image:linear-gradient(180deg,rgba(0,0,0,.8),transparent 80%); }}
  .glow {{ position:absolute; right:-320px; top:-380px; width:900px; height:900px; border-radius:50%;
    background:radial-gradient(circle,rgba(52,211,153,.16),rgba(52,211,153,.05) 40%,transparent 65%); }}
  .frame {{ position:absolute; inset:26px; border:1px solid rgba(110,231,183,.16); border-radius:20px; }}
  .content {{ position:absolute; inset:26px; padding:54px 62px; display:flex; flex-direction:column; }}
  .brand {{ display:flex; align-items:center; gap:15px; }}
  .brand img {{ width:46px; height:46px; }}
  .brand strong {{ font-family:"JetBrains Mono",monospace; font-size:21px; letter-spacing:.16em; font-weight:600; }}
  .chip {{ position:absolute; right:62px; top:58px; font-family:"JetBrains Mono",monospace; font-size:15px;
    letter-spacing:.14em; border:1.5px solid {chip_border}; color:{chip_color};
    background:{chip_bg}; border-radius:999px; padding:12px 20px; }}
  .eyebrow {{ margin-top:52px; font-family:"JetBrains Mono",monospace; font-size:17px; letter-spacing:.24em; color:#34d399; }}
  h1 {{ margin-top:16px; font-family:"Instrument Serif",serif; font-weight:400; font-size:82px; line-height:1.04;
    letter-spacing:-.015em; max-width:1010px; }}
  h1 em {{ font-style:italic; color:#7df0c3; text-shadow:0 0 44px rgba(52,211,153,.45); }}
  .meter {{ margin-top:34px; width:520px; }}
  .meter .lbl {{ display:flex; justify-content:space-between; font-family:"JetBrains Mono",monospace; font-size:14px; color:#5f8073; margin-bottom:10px; }}
  .meter .lbl b {{ color:#7df0c3; font-weight:500; }}
  .meter .track {{ height:10px; border-radius:999px; background:rgba(110,231,183,.12); }}
  .meter .fill {{ height:100%; width:{agree}%; border-radius:999px; background:linear-gradient(90deg,#34d399,#7df0c3); }}
  .foot {{ margin-top:auto; display:flex; gap:34px; align-items:center; font-family:"JetBrains Mono",monospace;
    font-size:16.5px; letter-spacing:.06em; color:#5f8073; }}
  .foot b {{ color:#93b4a7; font-weight:500; }}
  .foot .gem {{ color:#34d399; font-size:11px; }}
</style></head><body>
  <div class="glow"></div><div class="grid"></div><div class="frame"></div>
  <div class="content">
    <div class="brand"><img src="../site/brand-mark-classic.svg" alt=""><strong>ARASENSE</strong></div>
    <div class="chip">{chip_text}</div>
    <div class="eyebrow">{eyebrow}</div>
    <h1>{city}. <em>{pct} by 2050.</em></h1>
    <div class="meter">
      <div class="lbl"><span>trusted-model agreement on direction</span><b>{agree}%</b></div>
      <div class="track"><div class="fill"></div></div>
    </div>
    <div class="foot"><b>www.arasense.com/trust/{cid}</b><span class="gem">&#9670;</span>max 1-day precipitation<span class="gem">&#9670;</span>SSP2-4.5 &middot; 2040&ndash;2059</div>
  </div>
</body></html>
"""

CHIP = {
    "strong": ("rgba(52,211,153,.5)", "#7df0c3", "rgba(52,211,153,.08)"),
    "moderate": ("rgba(244,199,125,.5)", "#f4c77d", "rgba(244,199,125,.08)"),
    "weak": ("rgba(240,143,132,.5)", "#f08f84", "rgba(240,143,132,.08)"),
}


def main() -> None:
    src = open(ATLAS_JS, encoding="utf-8").read()
    payload = json.loads(src.split("window.ATLAS = ", 1)[1].rstrip().rstrip(";"))
    os.makedirs(OUT_DIR, exist_ok=True)

    jobs = []
    for c in payload["cities"]:
        if "rank" in c:
            jobs.append((c, f"RANK {c['rank']} / {payload['n_ranked']}",
                         CHIP["strong"], "CLIMATE MODEL TRUST PROFILE"))
    for c in payload.get("world", {}).get("cities", []):
        jobs.append((c, f"REFERENCE DATA · {c['conf'].upper()}",
                     CHIP[c["conf"]], "GLOBAL PREVIEW · TRUST PROFILE"))

    # The msedge launcher can return before its child finishes writing the
    # screenshot, so never trust the exit alone: launch once per city with an
    # isolated profile, then poll until the PNG exists and its size is stable.
    # Overlapping retries are what produced cross-city contamination before.
    def render(tmp_html, out):
        profile = tempfile.mkdtemp(prefix="arasense_og_")
        subprocess.run([
            EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
            "--user-data-dir=" + profile,
            "--window-size=1200,630", "--force-device-scale-factor=1",
            "--virtual-time-budget=3000",
            "--screenshot=" + out,
            "file:///" + tmp_html.replace("\\", "/"),
        ], capture_output=True)
        last = -1
        for _ in range(40):  # up to ~20 s for the child to finish
            if os.path.exists(out):
                size = os.path.getsize(out)
                if size > 10000 and size == last:
                    return True
                last = size
            time.sleep(0.5)
        return False

    for c, chip_text, (border, color, bg), eyebrow in jobs:
        sign = "+" if c["pct"] >= 0 else ""
        html = CARD.format(
            city=c["name"], cid=c["id"], pct=f"{sign}{c['pct']:.1f}%",
            agree=c["agree"], eyebrow=eyebrow, chip_text=chip_text,
            chip_border=border, chip_color=color, chip_bg=bg)
        tmp_html = os.path.abspath(f"scripts/_tmp_og_{c['id']}.html")
        with open(tmp_html, "w", encoding="utf-8") as f:
            f.write(html)
        out = os.path.abspath(f"{OUT_DIR}/{c['id']}.png")
        if os.path.exists(out):
            os.remove(out)
        ok = render(tmp_html, out) or render(tmp_html, out)
        os.remove(tmp_html)
        if not ok:
            raise RuntimeError(f"failed to render {c['id']}")
        print(f"{c['id']}.png", flush=True)

    print(f"done: {len(jobs)} cards in {OUT_DIR}")


if __name__ == "__main__":
    main()

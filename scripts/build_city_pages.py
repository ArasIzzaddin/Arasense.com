"""
Build the per-city Trust Profile pages under site/trust/.

Reads the same generated atlas data the Trust Atlas uses (site/atlas-data.js,
built by scripts/build_atlas_data.py from the portfolio JSONs) so every page
carries exactly the numbers the atlas shows; no hand-edited values.

Outputs:
- site/trust/<city>.html   one profile page per ranked atlas city (24)
- site/trust/index.html    the hub page listing every profile
- site/sitemap.xml         regenerated with static pages + trust profiles

    python scripts/build_city_pages.py
"""

import datetime
import json
import re
from string import Template

ATLAS_JS = "site/atlas-data.js"
OUT_DIR = "site/trust"
SITEMAP = "site/sitemap.xml"
BASE = "https://www.arasense.com"

COUNTRIES = {
    "Oslo": "Norway", "Amsterdam": "Netherlands", "Warsaw": "Poland",
    "London": "United Kingdom", "Rome": "Italy", "Brussels": "Belgium",
    "Budapest": "Hungary", "Zurich": "Switzerland", "Milan": "Italy",
    "Florence": "Italy", "Bologna": "Italy", "Berlin": "Germany",
    "Barcelona": "Spain", "Lisbon": "Portugal", "Copenhagen": "Denmark",
    "Prague": "Czechia", "Madrid": "Spain", "Athens": "Greece",
    "Venice": "Italy", "Dublin": "Ireland", "Vienna": "Austria",
    "Munich": "Germany", "Paris": "France", "Stockholm": "Sweden",
    # global preview
    "New York": "United States", "Miami": "United States",
    "Sao Paulo": "Brazil", "Lagos": "Nigeria", "Nairobi": "Kenya",
    "Cape Town": "South Africa", "Mumbai": "India", "Singapore": "Singapore",
    "Jakarta": "Indonesia", "Tokyo": "Japan", "Sydney": "Australia",
    "Mexico City": "Mexico",
}

CONF_LABEL = {"strong": "strong", "moderate": "moderate", "weak": "weak · read with care"}
CONF_TEXT = {
    "strong": "Long-record ground observations strongly constrain the ERA5-Land "
              "baseline here, so the trust scores rest on solid reference data.",
    "moderate": "Ground observations moderately constrain the ERA5-Land baseline "
                "here: solid for screening, worth deepening for decisions.",
    "weak": "Sparse ground observations only weakly constrain the ERA5-Land "
            "baseline here; the trust scores inherit that uncertainty and "
            "should be read with the care the flag implies.",
}


def load_cities():
    src = open(ATLAS_JS, encoding="utf-8").read()
    payload = json.loads(src.split("window.ATLAS = ", 1)[1].rstrip().rstrip(";"))
    ranked = [c for c in payload["cities"] if "rank" in c]
    ranked.sort(key=lambda c: c["rank"])
    world = payload.get("world", {}).get("cities", [])
    return ranked, payload["n_ranked"], world


# ---------------------------------------------------------------- copy logic

def signal_words(c):
    """Direction and support level, stated the way the atlas states them."""
    up = c["pct"] >= 0
    support = c["agree"] if up else 100 - c["agree"]
    direction = "heavier" if up else "lighter"
    return up, support, direction


def verdict_paragraphs(c, n_ranked, prev_c, next_c):
    up, support, direction = signal_words(c)
    sign = "+" if c["pct"] >= 0 else ""
    pct = f"{sign}{c['pct']:.1f}%"

    if support >= 90:
        reading = (f"{c['agree']}% of trusted-model weight points the same way, which makes this "
                   f"one of the more consistent signals in the atlas. The models that earned trust "
                   f"in {c['name']} broadly agree: the worst rain day gets {direction}.")
    elif support >= 70:
        reading = (f"{support}% of trusted-model weight backs this direction: a solid signal, "
                   f"but not a unanimous one. The full spread is part of the evidence, "
                   f"not a footnote.")
    elif support >= 50:
        reading = (f"Only {support}% of trusted-model weight backs this direction. The number is "
                   f"reported with its doubt attached; if a decision hangs on {c['name']}, "
                   f"this is a signal to deepen, not to quote alone.")
    else:
        reading = (f"The trusted-model weight is split ({c['agree']}% points up, the rest down), "
                   f"so the direction itself is contested here. Most tools would still print one "
                   f"confident number; the honest reading is that {c['name']} needs a full-ensemble "
                   f"deep dive before any number is quoted.")

    def link(other):
        return (f'<a href="{other["id"]}.html">{other["name"]}</a> '
                f'({"+" if other["pct"] >= 0 else ""}{other["pct"]:.1f}%)')
    if prev_c and next_c:
        position = f"between {link(prev_c)} and {link(next_c)}"
    elif next_c:
        position = f"just above {link(next_c)}"
    else:
        position = f"just below {link(prev_c)}"
    rank_line = (f"{c['name']} ranks <strong>#{c['rank']} of {n_ranked}</strong> in the European "
                 f"Trust Atlas, {position}, computed with the same method and settings "
                 f"as every other city, so the ranking is comparable by construction.")

    return (f"<p>The trust-weighted screening signal for {c['name']} is <strong>{pct}</strong> "
            f"change in maximum 1-day precipitation by 2040–2059 under SSP2-4.5: "
            f"{c['hist']:.2f}&nbsp;mm → {c['fut']:.2f}&nbsp;mm on the baseline worst rain day. "
            f"{reading}</p>\n          <p>{rank_line}</p>")


def meta_description(c):
    sign = "+" if c["pct"] >= 0 else ""
    return (f"Trust-weighted climate signal for {c['name']}: {sign}{c['pct']:.1f}% change in "
            f"maximum 1-day rainfall by 2050, {c['agree']}% trusted-model agreement on increase. "
            f"See which climate models earned trust in {c['name']} and how the number was earned.")


def world_verdict_paragraphs(c):
    up, support, direction = signal_words(c)
    sign = "+" if c["pct"] >= 0 else ""
    pct = f"{sign}{c['pct']:.1f}%"
    if support >= 90:
        reading = (f"{support}% of trusted-model weight points the same way: an unusually "
                   f"consistent screening signal: the worst rain day gets {direction}.")
    elif support >= 70:
        reading = (f"{support}% of trusted-model weight backs this direction: a solid signal, "
                   f"but not a unanimous one.")
    else:
        reading = (f"Only {support}% of trusted-model weight backs this direction. The number is "
                   f"reported with its doubt attached: a signal to deepen, not to quote alone.")
    return (f"<p>The trust-weighted screening signal for {c['name']} is <strong>{pct}</strong> "
            f"change in maximum 1-day precipitation by 2040–2059 under SSP2-4.5: "
            f"{c['hist']:.2f}&nbsp;mm → {c['fut']:.2f}&nbsp;mm on the baseline worst rain day. "
            f"{reading}</p>\n          <p>{c['name']} is part of the atlas's <strong>global "
            f"preview tier</strong>: the same pipeline as the ranked European cities, published "
            f"unranked while coverage grows. One thing changes outside Europe: "
            f"{CONF_TEXT[c['conf']]}</p>")


def faq_items(c):
    sign = "+" if c["pct"] >= 0 else ""
    pct = f"{sign}{c['pct']:.1f}%"
    return [
        ("What does “trust-weighted” mean?",
         f"Every climate model in the screening ensemble is scored against roughly 20 years of "
         f"observed climate behaviour near {c['name']} (ERA5-Land) using the Aras Diagram, a "
         f"peer-reviewed skill-decomposition method (Izzaddin et al. 2024). Models that track "
         f"local reality earn weight in the projection; models that fail screening are rejected. "
         f"The weights and rejections are reported, never hidden."),
        (f"Can I use the {pct} figure in a report?",
         f"As screening-level evidence, yes, always alongside its {c['agree']}% model-agreement "
         f"figure. It is built for prioritisation and planning conversations. For site-specific or "
         f"engineering-grade decisions, the next step is a full-ensemble deep dive for {c['name']}, "
         f"which names every trusted and rejected model with its weight."),
        ("Why not just average all climate models?",
         f"Averaging treats a model that mistracks {c['name']}’s observed climate the same as one "
         f"that nails it, and it buries how much credible models disagree. Trust-weighting measures "
         f"each model’s local skill first, then lets the skilful ones carry the projection, and "
         f"reports the remaining disagreement as part of the answer."),
        ("What exactly was computed?",
         "Maximum 1-day precipitation (rx1day) within a 50 km radius of the city, baseline "
         "1995–2014 versus future 2040–2059, scenario SSP2-4.5, using the 5-model trust-screening "
         "ensemble shared by every Trust Atlas city. Bologna additionally has a 34-model deep "
         "dive, which is why its two published numbers differ, on purpose."),
    ]


# ---------------------------------------------------------------- templates

PAGE = Template("""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$title</title>
  <meta name="description" content="$description">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="canonical" href="$canonical">
  <meta property="og:type" content="article">
  <meta property="og:title" content="$title">
  <meta property="og:description" content="$og_description">
  <meta property="og:url" content="$canonical">
  <meta property="og:image" content="$og_image">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:image" content="$og_image">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="alternate" type="application/json" href="/trust/$cid.json" title="$city trust signal (JSON)">
  <link rel="preload" href="/fonts/instrument-serif-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/fonts/instrument-serif-400-italic.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/fonts/inter-var.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/fonts/jetbrains-mono-var.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/styles.css?v=6">
  <script type="application/ld+json">$jsonld</script>
  <style>
    .page-hero { padding: 64px 0 0; }
    .page-hero h1 { max-width: 880px; margin: 0 0 22px; }

    .profile-grid {
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 16px;
      margin-top: 40px;
      align-items: stretch;
    }
    .verdict-panel {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: linear-gradient(170deg, var(--panel-2), var(--panel));
      padding: 30px;
      display: flex;
      flex-direction: column;
    }
    .verdict-panel .metric-label {
      font-family: var(--font-mono);
      font-size: 12px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--faint);
      margin-bottom: 14px;
    }
    .verdict-change {
      font-family: var(--font-mono);
      font-size: clamp(52px, 6vw, 76px);
      color: var(--accent-bright);
      line-height: 1;
      margin: 2px 0 6px;
      font-variant-numeric: tabular-nums;
    }
    .verdict-change.negative { color: var(--amber); }
    .verdict-values {
      font-family: var(--font-mono);
      font-size: 14px;
      color: var(--muted);
      margin-bottom: 22px;
    }
    .agree-row .lbl {
      display: flex;
      justify-content: space-between;
      font-family: var(--font-mono);
      font-size: 12px;
      color: var(--faint);
      margin-bottom: 8px;
    }
    .agree-row .lbl b { color: var(--accent-bright); font-weight: 500; }
    .agree-bar {
      height: 8px;
      border-radius: 999px;
      background: rgba(110, 231, 183, 0.1);
      overflow: hidden;
    }
    .agree-bar i {
      display: block;
      height: 100%;
      width: $agree%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--accent), var(--accent-bright));
    }
    .verdict-reading {
      border-top: 1px solid var(--line);
      margin-top: 22px;
      padding-top: 18px;
    }
    .verdict-reading p { font-size: 14.5px; line-height: 1.7; }
    .verdict-reading p:last-child { margin-bottom: 0; }
    .verdict-reading a { color: var(--accent-bright); }

    .rank-panel {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
      padding: 26px;
      display: flex;
      flex-direction: column;
    }
    .rank-panel h2 { font-size: 26px; }
    .rank-rows { margin-top: 12px; flex: 1; }
    .rank-row {
      display: grid;
      grid-template-columns: 44px 1fr 84px;
      align-items: center;
      gap: 12px;
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      text-decoration: none;
      border-radius: 8px;
    }
    .rank-row:last-child { border-bottom: 0; }
    .rank-row:hover { background: rgba(110, 231, 183, 0.05); }
    .rank-row.current {
      background: rgba(52, 211, 153, 0.08);
      border: 1px solid var(--line-strong);
    }
    .rank-row .pos { font-family: var(--font-mono); font-size: 12px; color: var(--faint); }
    .rank-row .cname { font-size: 14.5px; color: var(--muted); }
    .rank-row.current .cname { color: var(--text); font-weight: 600; }
    .rank-row .rval {
      font-family: var(--font-mono);
      font-size: 13px;
      color: var(--accent-bright);
      text-align: right;
      font-variant-numeric: tabular-nums;
    }
    .rank-row .rval.negative { color: var(--amber); }
    .rank-panel .all-link {
      margin-top: 16px;
      font-size: 14px;
      color: var(--accent-bright);
      text-decoration: none;
    }
    .rank-panel .all-link:hover { text-decoration: underline; }

    .settings-list { list-style: none; margin: 0; padding: 0; }
    .settings-list li {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      padding: 9px 0;
      border-bottom: 1px solid var(--line);
      font-size: 13.5px;
      color: var(--muted);
    }
    .settings-list li:last-child { border-bottom: 0; }
    .settings-list b { font-family: var(--font-mono); font-weight: 500; color: var(--text); white-space: nowrap; }

    .conf-chip {
      display: inline-block;
      align-self: flex-start;
      font-family: var(--font-mono);
      font-size: 11px;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      border-radius: 999px;
      padding: 6px 12px;
      margin-bottom: 14px;
      border: 1px solid rgba(52, 211, 153, 0.4);
      color: var(--accent-bright);
      background: rgba(52, 211, 153, 0.07);
    }
    .conf-chip.c-m { border-color: rgba(244, 199, 125, 0.4); color: var(--amber); background: rgba(244, 199, 125, 0.07); }
    .conf-chip.c-w { border-color: rgba(240, 143, 132, 0.4); color: var(--red); background: rgba(240, 143, 132, 0.07); }

    .faq details {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
      padding: 0 22px;
      margin-bottom: 10px;
    }
    .faq summary {
      cursor: pointer;
      padding: 18px 0;
      font-weight: 600;
      font-size: 16px;
      color: var(--text);
      list-style: none;
    }
    .faq summary::-webkit-details-marker { display: none; }
    .faq summary::before {
      content: "+";
      font-family: var(--font-mono);
      color: var(--accent);
      margin-right: 12px;
    }
    .faq details[open] summary::before { content: "−"; }
    .faq details p { padding-bottom: 18px; font-size: 14.5px; }

    @media (max-width: 920px) {
      .page-hero { padding-top: 44px; }
      .profile-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="nav-wrap">
    <header class="nav">
      <a class="brand" href="/">
        <img src="/brand-mark-classic.svg" alt="Arasense logo">
        <strong>Arasense</strong>
      </a>
      <button class="nav-toggle" aria-expanded="false" aria-controls="nav-links">Menu</button>
      <nav class="nav-links" id="nav-links" aria-label="Main navigation">
        <a href="/atlas.html" class="active">Atlas</a>
        <a href="/demo.html">Demo</a>
        <a href="/case-studies.html">Case studies</a>
        <a href="/evidence.html">Evidence</a>
        <a href="/bari-puglia.html">Bari / Puglia</a>
        <a class="nav-cta" href="mailto:arasbotan.izzaddin@poliba.it?subject=Arasense%20briefing">Request briefing</a>
      </nav>
    </header>
  </div>

  <div class="shell">
    <main>
      <section class="page-hero">
        <span class="eyebrow">$hero_eyebrow</span>
        <h1>Which climate models can you trust in <em>$city?</em></h1>
        <p class="lead">
          This page is a real Arasense run, not a brochure: climate models scored against observed
          climate near $city, the skilful ones trust-weighted into a mid-century signal for the
          city&rsquo;s worst rain day, with model agreement reported, because a projection without
          it is just a guess with confidence.
        </p>
      </section>

      <div class="profile-grid">
        <div class="verdict-panel reveal">
          <div class="metric-label">Max 1-day precipitation · SSP2-4.5 · 1995–2014 → 2040–2059</div>
          $conf_chip_html<div class="verdict-change num$neg_class">$pct_str</div>
          <div class="verdict-values">$hist mm → $fut mm ($chg_str mm)</div>
          <div class="agree-row">
            <div class="lbl"><span>trusted-model agreement on increase</span><b>$agree%</b></div>
            <div class="agree-bar"><i></i></div>
          </div>
          <div class="verdict-reading">
          $verdict_html
          $deep_dive_html</div>
        </div>

        <aside class="rank-panel reveal">
          <span class="eyebrow" style="margin-bottom:10px;">Where $city sits</span>
          <h2>$rank_heading</h2>
          <div class="rank-rows">
$rank_rows
          </div>
          <a class="all-link" href="/trust/">All trust profiles →</a>
          <a class="all-link" href="$atlas_link">Open the interactive atlas →</a>
        </aside>
      </div>

      <hr class="hr">

      <section class="section">
        <div class="section-head reveal">
          <span class="eyebrow">How the number was earned</span>
          <h2>Trust first. <em>Then</em> project.</h2>
        </div>
        <div class="grid-2">
          <div class="steps">
            <article class="step reveal">
              <h3>Score model trust at $city</h3>
              <p>Each climate model is compared against observed climate behaviour near $city and
              decomposed with the Aras Diagram: bias, variability, and phase alignment, not one
              opaque score. Models that fail screening are rejected, and you see why.</p>
            </article>
            <article class="step reveal">
              <h3>Project with the models that earned it</h3>
              <p>Skill-weighted models estimate the mid-century change in $city&rsquo;s maximum
              1-day rainfall, with the spread and the $agree% directional agreement reported,
              never hidden.</p>
            </article>
            <article class="step reveal">
              <h3>Escalate where it matters</h3>
              <p>Atlas signals are screening-level evidence. Where a decision depends on $city,
              the same pipeline runs the full CMIP6 ensemble: every trusted and rejected model
              named, weighted, and auditable.</p>
            </article>
          </div>
          <div class="card reveal">
            <span class="label">Run settings · identical for every atlas city</span>
            <h3>What was computed</h3>
            <ul class="settings-list">
              <li><span>Metric</span><b>rx1day (max 1-day precipitation)</b></li>
              <li><span>Scenario</span><b>SSP2-4.5</b></li>
              <li><span>Baseline window</span><b>1995–2014</b></li>
              <li><span>Future window</span><b>2040–2059</b></li>
              <li><span>Spatial footprint</span><b>50 km radius</b></li>
              <li><span>Ensemble</span><b>5-model trust screening</b></li>
              <li><span>Observations</span><b>ERA5-Land</b></li>
              <li><span>Skill method</span><b>Aras Diagram (peer-reviewed)</b></li>
            </ul>
          </div>
        </div>
        <div class="notice reveal" style="margin-top:16px;">
          <strong>Scope note.</strong> This is screening-level evidence for prioritisation and
          planning conversations, not a substitute for site-specific engineering studies. The
          screening ensemble is small by design; a full-ensemble deep dive is how this number
          becomes decision evidence.
        </div>
      </section>

      <hr class="hr">

      <section class="section" id="brief">
        <div class="panel reveal" style="padding:44px;">
          <div class="section-head" style="margin-bottom:22px;">
            <span class="eyebrow">Next step</span>
            <h2 style="margin-bottom:12px;">Get the full $city <em>trust brief</em></h2>
            <p style="max-width:560px;">
              The brief behind this page: the screening run in full, what a 34-model deep dive
              would add for $city, and how the evidence holds up in front of a technical reviewer.
              Prepared per request from the same pipeline; tell us where to send it.
            </p>
          </div>
          <form class="lead-form" data-city="$city">
            <input type="email" name="email" required placeholder="you@organisation.com" aria-label="Work email">
            <input type="text" name="org" placeholder="Organisation (optional)" aria-label="Organisation">
            <input type="text" name="website" class="lf-hp" tabindex="-1" autocomplete="off" aria-hidden="true">
            <button type="submit" class="button">Request the $city brief</button>
            <p class="lf-msg" aria-live="polite"></p>
          </form>
        </div>
      </section>

      <hr class="hr">

      <section class="section faq">
        <div class="section-head reveal">
          <span class="eyebrow">Questions reviewers ask</span>
          <h2>Reading this number <em>responsibly</em></h2>
        </div>
$faq_html
      </section>

      <section class="section">
        <div class="card reveal">
          <span class="label">Machine-readable</span>
          <h3>This evidence is also an API</h3>
          <p>Every trust profile publishes its signal as JSON, so risk platforms, notebooks, and reviewers can pull the number with its uncertainty attached:</p>
          <pre style="background:#050f0c; border:1px solid var(--line); border-radius:10px; padding:16px 18px; overflow-x:auto; font-family:var(--font-mono); font-size:13px; color:#bfe8da; margin-top:12px;">curl https://www.arasense.com/trust/$cid.json</pre>
        </div>
      </section>

      <footer class="footer">
        <div class="footer-grid">
          <div>
            <span class="eyebrow">Founder</span>
            <h3>Aras Izzaddin</h3>
            <p>Founder &amp; Lead Researcher · Politecnico di Bari</p>
            <p><a href="mailto:arasbotan.izzaddin@poliba.it">arasbotan.izzaddin@poliba.it</a></p>
          </div>
          <div>
            <span class="eyebrow">Explore</span>
            <p><a href="/atlas.html">Trust Atlas</a></p>
            <p><a href="/trust/">All trust profiles</a></p>
            <p><a href="/case-studies.html">Case studies</a></p>
            <p><a href="/evidence.html">Sample evidence</a></p>
            <p><a href="/bari-puglia.html">Bari / Puglia regional brief</a></p>
          </div>
        </div>
        <div class="footer-meta">
          <span>© 2026 Arasense · www.arasense.com</span>
          <span>Guided demos, pilot studies, and selected collaborations</span>
        </div>
      </footer>
    </main>
  </div>

  <script src="/site.js?v=5" defer></script>
</body>
</html>
""")

HUB = Template("""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>City Trust Profiles · Which climate models to trust, city by city · Arasense</title>
  <meta name="description" content="Trust-weighted mid-century rainfall signals for $n_ranked European cities, one consistent peer-reviewed method. Open any city to see which climate models earned trust there.">
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="canonical" href="https://www.arasense.com/trust/">
  <meta property="og:type" content="website">
  <meta property="og:title" content="City Trust Profiles · Arasense">
  <meta property="og:description" content="Which climate models can you trust in each European city? $n_ranked profiles, one method.">
  <meta property="og:url" content="https://www.arasense.com/trust/">
  <meta property="og:image" content="https://www.arasense.com/og/atlas.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:image" content="https://www.arasense.com/og/atlas.png">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="preload" href="/fonts/instrument-serif-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/fonts/instrument-serif-400-italic.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/fonts/inter-var.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/fonts/jetbrains-mono-var.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/styles.css?v=6">
  <style>
    .page-hero { padding: 64px 0 0; }
    .page-hero h1 { max-width: 880px; margin: 0 0 22px; }
    .profile-list {
      margin-top: 40px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
      padding: 12px 18px;
    }
    .profile-row {
      display: grid;
      grid-template-columns: 48px 1.1fr 1fr 92px 92px;
      align-items: center;
      gap: 14px;
      padding: 13px 8px;
      border-bottom: 1px solid var(--line);
      text-decoration: none;
      border-radius: 8px;
    }
    .profile-row:last-child { border-bottom: 0; }
    .profile-row:hover { background: rgba(110, 231, 183, 0.05); }
    .profile-row .pos { font-family: var(--font-mono); font-size: 12px; color: var(--faint); }
    .profile-row .cname { font-size: 15.5px; color: var(--text); font-weight: 600; }
    .profile-row .cname small { display: block; font-weight: 400; font-size: 12.5px; color: var(--faint); }
    .profile-row .bar { height: 8px; border-radius: 999px; background: rgba(110,231,183,.08); overflow: hidden; }
    .profile-row .bar i { display: block; height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--accent), var(--accent-bright)); }
    .profile-row .bar i.negative { background: linear-gradient(90deg, var(--amber), #f8dba8); }
    .profile-row .rval { font-family: var(--font-mono); font-size: 13.5px; color: var(--accent-bright); text-align: right; font-variant-numeric: tabular-nums; }
    .profile-row .rval.negative { color: var(--amber); }
    .profile-row .agr { font-family: var(--font-mono); font-size: 12px; color: var(--faint); text-align: right; font-variant-numeric: tabular-nums; }
    @media (max-width: 920px) {
      .page-hero { padding-top: 44px; }
      .profile-row { grid-template-columns: 34px 1fr 76px; }
      .profile-row .bar, .profile-row .agr { display: none; }
    }
  </style>
</head>
<body>
  <div class="nav-wrap">
    <header class="nav">
      <a class="brand" href="/">
        <img src="/brand-mark-classic.svg" alt="Arasense logo">
        <strong>Arasense</strong>
      </a>
      <button class="nav-toggle" aria-expanded="false" aria-controls="nav-links">Menu</button>
      <nav class="nav-links" id="nav-links" aria-label="Main navigation">
        <a href="/atlas.html" class="active">Atlas</a>
        <a href="/demo.html">Demo</a>
        <a href="/case-studies.html">Case studies</a>
        <a href="/evidence.html">Evidence</a>
        <a href="/bari-puglia.html">Bari / Puglia</a>
        <a class="nav-cta" href="mailto:arasbotan.izzaddin@poliba.it?subject=Arasense%20briefing">Request briefing</a>
      </nav>
    </header>
  </div>

  <div class="shell">
    <main>
      <section class="page-hero">
        <span class="eyebrow">City trust profiles · Europe</span>
        <h1>Which climate models can you trust, <em>city by city?</em></h1>
        <p class="lead">
          $n_ranked European cities, one consistent peer-reviewed method: models scored against
          observed local climate, trust-weighted into a mid-century signal for each city&rsquo;s
          worst rain day. Open a city to see its full profile, including the doubt.
        </p>
      </section>

      <div class="profile-list reveal">
$rows
      </div>

      <section class="section">
        <div class="card reveal">
          <span class="label">Machine-readable</span>
          <h3>The atlas is also an API</h3>
          <p>Every profile publishes its trust signal as JSON with agreement and uncertainty attached. One index, one file per city, no key required:</p>
          <pre style="background:#050f0c; border:1px solid var(--line); border-radius:10px; padding:16px 18px; overflow-x:auto; font-family:var(--font-mono); font-size:13px; color:#bfe8da; margin-top:12px;">curl https://www.arasense.com/trust/index.json
curl https://www.arasense.com/trust/lagos.json</pre>
        </div>
      </section>

      <section class="section">
        <div class="panel reveal" style="padding:44px; text-align:center;">
          <span class="eyebrow" style="justify-content:center;">Your geography</span>
          <h2 style="max-width:620px; margin:0 auto 14px;">Your city isn&rsquo;t listed. <em>That&rsquo;s the point.</em></h2>
          <p style="max-width:520px; margin:0 auto 26px;">
            A pilot engagement starts with your locations and ends with them profiled here,
            trust-scored, projected, and defensible.
          </p>
          <div class="actions" style="justify-content:center;">
            <a class="button" href="mailto:arasbotan.izzaddin@poliba.it?subject=Arasense%20trust%20profile%20pilot">Put your region on the map</a>
            <a class="button-secondary" href="/atlas.html">Open the interactive atlas</a>
          </div>
        </div>
      </section>

      <footer class="footer">
        <div class="footer-grid">
          <div>
            <span class="eyebrow">Founder</span>
            <h3>Aras Izzaddin</h3>
            <p>Founder &amp; Lead Researcher · Politecnico di Bari</p>
            <p><a href="mailto:arasbotan.izzaddin@poliba.it">arasbotan.izzaddin@poliba.it</a></p>
          </div>
          <div>
            <span class="eyebrow">Explore</span>
            <p><a href="/atlas.html">Trust Atlas</a></p>
            <p><a href="/case-studies.html">Case studies</a></p>
            <p><a href="/evidence.html">Sample evidence</a></p>
            <p><a href="/bari-puglia.html">Bari / Puglia regional brief</a></p>
          </div>
        </div>
        <div class="footer-meta">
          <span>© 2026 Arasense · www.arasense.com</span>
          <span>Guided demos, pilot studies, and selected collaborations</span>
        </div>
      </footer>
    </main>
  </div>

  <script src="/site.js?v=5" defer></script>
</body>
</html>
""")


# ---------------------------------------------------------------- builders

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_jsonld(c, canonical, faqs):
    plain = re.compile(r"<[^>]+>")
    return json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Arasense", "item": BASE + "/"},
                    {"@type": "ListItem", "position": 2, "name": "Trust profiles", "item": BASE + "/trust/"},
                    {"@type": "ListItem", "position": 3, "name": c["name"], "item": canonical},
                ],
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {"@type": "Question", "name": plain.sub("", q),
                     "acceptedAnswer": {"@type": "Answer", "text": plain.sub("", a)}}
                    for q, a in faqs
                ],
            },
        ],
    }, ensure_ascii=False)


def build_rank_rows(c, cities):
    """A five-row window of the ranking centred on this city."""
    idx = c["rank"] - 1
    lo = max(0, min(idx - 2, len(cities) - 5))
    rows = []
    for other in cities[lo:lo + 5]:
        sign = "+" if other["pct"] >= 0 else ""
        neg = " negative" if other["pct"] < 0 else ""
        cur = " current" if other["id"] == c["id"] else ""
        rows.append(
            f'            <a class="rank-row{cur}" href="{other["id"]}.html">'
            f'<span class="pos">#{other["rank"]}</span>'
            f'<span class="cname">{other["name"]}</span>'
            f'<span class="rval{neg}">{sign}{other["pct"]:.1f}%</span></a>')
    return "\n".join(rows)


def build_world_rows(c, world):
    """A five-row window of the (pct-ordered) preview list centred on this city."""
    idx = next(i for i, x in enumerate(world) if x["id"] == c["id"])
    lo = max(0, min(idx - 2, len(world) - 5))
    rows = []
    for other in world[lo:lo + 5]:
        sign = "+" if other["pct"] >= 0 else ""
        neg = " negative" if other["pct"] < 0 else ""
        cur = " current" if other["id"] == c["id"] else ""
        rows.append(
            f'            <a class="rank-row{cur}" href="{other["id"]}.html">'
            f'<span class="pos">GP</span>'
            f'<span class="cname">{other["name"]}</span>'
            f'<span class="rval{neg}">{sign}{other["pct"]:.1f}%</span></a>')
    return "\n".join(rows)


def build_deep_dive(c):
    if not c.get("deep"):
        return ""
    return ('\n          <p><strong style="color:var(--accent-bright);">Deep dive available.</strong> '
            'Bologna also has a full 34-model CMIP6 run: <strong>+14.2%</strong> with 32 of 34 '
            'models passing skill screening. Comparing it with the +10.8% screening signal above '
            'is exactly the transparency this method exists for; see the '
            '<a href="/case-studies.html#bologna">Bologna case study</a>.</p>')


def build_city_page(c, cities, n_ranked, world=None):
    """One profile page. `world` set -> global-preview variant."""
    country = COUNTRIES[c["name"]]
    sign = "+" if c["pct"] >= 0 else ""
    canonical = f"{BASE}/trust/{c['id']}"
    title = f"Which climate models can you trust in {c['name']}? · Arasense"
    faqs = faq_items(c)

    if world is None:
        idx = c["rank"] - 1
        prev_c = cities[idx - 1] if idx > 0 else None
        next_c = cities[idx + 1] if idx < len(cities) - 1 else None
        hero_eyebrow = f"Climate model trust profile · {c['name']}, {country} · #{c['rank']} of {n_ranked}"
        rank_heading = f"Ranked against {n_ranked} cities, <em>one method</em>"
        atlas_link = "/atlas.html"
        conf_chip_html = ""
        verdict_html = verdict_paragraphs(c, n_ranked, prev_c, next_c)
        rank_rows = build_rank_rows(c, cities)
        og_extra = ""
    else:
        hero_eyebrow = (f"Global preview · {c['name']}, {country} · "
                        f"reference data: {CONF_LABEL[c['conf']]}")
        rank_heading = "The global preview tier, <em>one method</em>"
        atlas_link = "/atlas.html#world"
        cls = {"strong": "", "moderate": " c-m", "weak": " c-w"}[c["conf"]]
        conf_chip_html = (f'<span class="conf-chip{cls}">reference data · '
                          f'{c["conf"]}</span>\n          ')
        verdict_html = world_verdict_paragraphs(c)
        rank_rows = build_world_rows(c, world)
        og_extra = f" Reference-data confidence: {c['conf']}."
        faqs.insert(1, (
            "What does the reference-data confidence flag mean?",
            f"Trust scores are only as good as the observations behind them. The flag is a "
            f"qualitative tier for how densely long-record ground observations constrain the "
            f"ERA5-Land baseline in each region. For {c['name']} it reads "
            f"“{CONF_LABEL[c['conf']]}”. {CONF_TEXT[c['conf']]} Publishing the flag, instead of "
            f"pretending every baseline is equally solid, is part of the method."))

    faq_html = "\n".join(
        f'        <details class="reveal">\n          <summary>{q}</summary>\n'
        f'          <p>{a}</p>\n        </details>'
        for q, a in faqs)

    return PAGE.substitute(
        cid=c["id"],
        og_image=f"{BASE}/og/trust/{c['id']}.png?v=1",
        title=esc(title),
        description=esc(meta_description(c) + og_extra),
        og_description=esc(f"Trust-weighted signal for {c['name']}: {sign}{c['pct']:.1f}% change in "
                           f"max 1-day rainfall by 2050, {c['agree']}% model agreement; see how "
                           f"the number was earned." + og_extra),
        canonical=canonical,
        jsonld=build_jsonld(c, canonical, faqs),
        city=c["name"],
        country=country,
        hero_eyebrow=esc(hero_eyebrow) if world is None else hero_eyebrow,
        rank_heading=rank_heading,
        atlas_link=atlas_link,
        conf_chip_html=conf_chip_html,
        n_ranked=n_ranked,
        neg_class=" negative" if c["pct"] < 0 else "",
        pct_str=f"{sign}{c['pct']:.1f}%",
        hist=f"{c['hist']:.2f}",
        fut=f"{c['fut']:.2f}",
        chg_str=f"{'+' if c['chg'] >= 0 else ''}{c['chg']:.2f}",
        agree=c["agree"],
        verdict_html=verdict_html,
        deep_dive_html=build_deep_dive(c),
        rank_rows=rank_rows,
        faq_html=faq_html,
    )


def build_hub(cities, n_ranked, world):
    def row(c, pos_label, extra=""):
        sign = "+" if c["pct"] >= 0 else ""
        neg = " negative" if c["pct"] < 0 else ""
        return (
            f'        <a class="profile-row" href="{c["id"]}.html">'
            f'<span class="pos">{pos_label}</span>'
            f'<span class="cname">{c["name"]}<small>{COUNTRIES[c["name"]]}</small></span>'
            f'<span class="bar"><i class="{neg.strip()}" style="width:{c["_w"]:.0f}%"></i></span>'
            f'<span class="rval{neg}">{sign}{c["pct"]:.1f}%</span>'
            f'<span class="agr">{c["agree"]}% agree{extra}</span></a>')

    max_pct = max(abs(c["pct"]) for c in cities)
    rows = []
    for c in cities:
        c["_w"] = abs(c["pct"]) / max_pct * 100
        rows.append(row(c, f"#{c['rank']}"))

    if world:
        wmax = max(abs(c["pct"]) for c in world)
        rows.append('        <div style="padding:22px 8px 10px;">'
                    '<span class="eyebrow">Global preview · unranked, '
                    'reference-data confidence flagged</span></div>')
        for c in world:
            c["_w"] = abs(c["pct"]) / wmax * 100
            rows.append(row(c, "GP", f" · {c['conf']} data"))

    return HUB.substitute(n_ranked=n_ranked, rows="\n".join(rows))


def build_sitemap(cities, world):
    today = datetime.date.today().isoformat()
    static = [
        ("/", "1.0"), ("/atlas", "0.9"), ("/trust/", "0.9"),
        ("/case-studies", "0.8"), ("/evidence", "0.8"),
        ("/demo", "0.7"), ("/bari-puglia", "0.7"),
    ]
    urls = [f"  <url><loc>{BASE}{path}</loc><lastmod>{today}</lastmod><priority>{pr}</priority></url>"
            for path, pr in static]
    urls += [f"  <url><loc>{BASE}/trust/{c['id']}</loc><lastmod>{today}</lastmod><priority>0.7</priority></url>"
             for c in cities + world]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(urls) + "\n</urlset>\n")


def build_city_json(c, n_ranked, world=False):
    d = {
        "city": c["name"],
        "country": COUNTRIES[c["name"]],
        "tier": "global-preview" if world else "ranked",
        "metric": "maximum 1-day precipitation (rx1day)",
        "scenario": "SSP2-4.5",
        "baseline_window": "1995-2014",
        "future_window": "2040-2059",
        "spatial_footprint_km": 50,
        "baseline_mm": c["hist"],
        "projected_mm": c["fut"],
        "change_mm": c["chg"],
        "change_pct": c["pct"],
        "model_agreement_pct": c["agree"],
        "evidence_level": "screening (5-model trust ensemble)",
        "method": "Aras Diagram trust screening vs ERA5-Land observations "
                  "(Izzaddin et al. 2024, SERRA 38:2261-2281)",
        "profile_html": f"{BASE}/trust/{c['id']}.html",
        "source": "Arasense, www.arasense.com",
    }
    if world:
        d["reference_data_confidence"] = c["conf"]
    else:
        d["atlas_rank"] = c["rank"]
        d["atlas_rank_of"] = n_ranked
    return d


def main():
    import os
    cities, n_ranked, world = load_cities()
    os.makedirs(OUT_DIR, exist_ok=True)

    index_json = []
    for c in cities:
        with open(f"{OUT_DIR}/{c['id']}.html", "w", encoding="utf-8", newline="\n") as f:
            f.write(build_city_page(c, cities, n_ranked))
        d = build_city_json(c, n_ranked)
        d["json"] = f"{BASE}/trust/{c['id']}.json"
        index_json.append(d)
        with open(f"{OUT_DIR}/{c['id']}.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(build_city_json(c, n_ranked), f, indent=1)
    for c in world:
        with open(f"{OUT_DIR}/{c['id']}.html", "w", encoding="utf-8", newline="\n") as f:
            f.write(build_city_page(c, cities, n_ranked, world=world))
        d = build_city_json(c, n_ranked, world=True)
        d["json"] = f"{BASE}/trust/{c['id']}.json"
        index_json.append(d)
        with open(f"{OUT_DIR}/{c['id']}.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(build_city_json(c, n_ranked, world=True), f, indent=1)

    with open(f"{OUT_DIR}/index.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({
            "title": "Arasense Climate Model Trust Atlas",
            "description": "Trust-weighted mid-century rx1day signals; ranked European "
                           "tier plus confidence-flagged global preview tier.",
            "cities": index_json,
        }, f, indent=1)

    with open(f"{OUT_DIR}/index.html", "w", encoding="utf-8", newline="\n") as f:
        f.write(build_hub(cities, n_ranked, world))
    with open(SITEMAP, "w", encoding="utf-8", newline="\n") as f:
        f.write(build_sitemap(cities, world))
    print(f"{OUT_DIR}: {len(cities)} ranked + {len(world)} preview profiles, "
          f"{len(index_json)} JSON signals + index.json; {SITEMAP} regenerated")


if __name__ == "__main__":
    main()

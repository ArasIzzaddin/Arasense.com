"""
Build site/atlas-data.js for the European Trust Atlas.

Combines:
- scripts/atlas-europe-geometry.json  (clipped Natural Earth country outlines
  + city pin coordinates, generated once from cartopy/Natural Earth 50m)
- docs/portfolios/italian-flood-portfolio.json  (original five cities)
- docs/portfolios/european-trust-atlas.json     (cities added by
  scripts/run_atlas_europe.py)

All projections share one method: rx1day, SSP2-4.5, 50 km radius, 1995-2014 vs
2040-2059, fast_mode 5-model screening ensemble. Cities are ranked across the
combined set. Bari stays a pilot pin (no fabricated numbers).

    python scripts/build_atlas_data.py
"""

import json
import os

GEO = "scripts/atlas-europe-geometry.json"
GEO_WORLD = "scripts/atlas-world-geometry.json"
ITALIAN = "docs/portfolios/italian-flood-portfolio.json"
EUROPEAN = "docs/portfolios/european-trust-atlas.json"
WORLD = "docs/portfolios/world-trust-atlas.json"
OUT = "site/atlas-data.js"

# Qualitative reference-data confidence: how strongly long-record ground
# observations constrain the ERA5-Land baseline at each preview city.
CONF_TEXT = {
    "strong": "Long-record ground observations strongly constrain the ERA5-Land "
              "baseline here, so the trust scores rest on solid reference data.",
    "moderate": "Ground observations moderately constrain the ERA5-Land baseline "
                "here: solid for screening, worth deepening for decisions.",
    "weak": "Sparse ground observations only weakly constrain the ERA5-Land "
            "baseline here; the trust scores inherit that uncertainty and "
            "should be read with the care the flag implies.",
}

# bespoke notes for the original cities; others get generated text
NOTES = {
    "Bologna": "The atlas benchmark city: screening says {pct} with full agreement, "
               "and the 34-model deep dive refines it to +14.2%. Comparing the two "
               "is exactly the transparency this method exists for.",
    "Venice": "The cautionary tale: {pct} sounds reassuring until you see only "
              "{agree} model agreement. A single ranking score would bury that "
              "doubt; the atlas shows it.",
}


def gen_note(name: str, pct: float, agree: int) -> str:
    if name in NOTES:
        return NOTES[name].format(pct=f"+{pct:.1f}%", agree=f"{agree}%")
    if agree >= 90:
        conf = f"with {agree}% of trusted-model weight agreeing on the direction, this signal is unusually consistent"
    elif agree >= 70:
        conf = f"{agree}% model agreement makes this a solid but not unanimous signal"
    else:
        conf = f"only {agree}% model agreement: read this number with the doubt it deserves"
    return (f"Trust-weighted mid-century change in maximum 1-day precipitation: "
            f"{pct:+.1f}%; {conf}.")


def main() -> None:
    geo = json.load(open(GEO, encoding="utf-8"))
    italian = json.load(open(ITALIAN, encoding="utf-8"))
    european = json.load(open(EUROPEAN, encoding="utf-8"))

    rows = []
    for r in italian["ranked"]:
        rows.append({"name": r["name"], "hist": r["historical"], "fut": r["future"],
                     "chg": r["change"], "pct": r["pct_change"],
                     "agree": round(r["agreement"] * 100)})
    for name, r in european["cities"].items():
        if "error" in r:
            print(f"skipping {name}: {r['error'][:80]}")
            continue
        rows.append({"name": name, "hist": r["historical"], "fut": r["future"],
                     "chg": r["change"], "pct": r["pct_change"],
                     "agree": round(r["agreement"] * 100)})

    rows.sort(key=lambda r: r["pct"], reverse=True)
    cities = []
    for i, r in enumerate(rows):
        x, y = geo["pins"][r["name"]]
        cities.append({
            "id": r["name"].lower().replace(" ", "-"), "name": r["name"],
            "x": x, "y": y, "rank": i + 1,
            "hist": round(r["hist"], 2), "fut": round(r["fut"], 2),
            "chg": round(r["chg"], 2), "pct": round(r["pct"], 1),
            "agree": r["agree"],
            "deep": r["name"] == "Bologna",
            "note": gen_note(r["name"], r["pct"], r["agree"]),
        })
    bx, by = geo["pins"]["Bari"]
    cities.append({
        "id": "bari", "name": "Bari", "x": bx, "y": by, "pilot": True,
        "note": "Current pilot region. The Bari / Puglia evidence pack applies the "
                "same trust-first workflow to Puglia locations; the regional brief "
                "is available now, and atlas numbers will follow the pilot.",
    })

    payload = {"w": geo["w"], "h": geo["h"], "paths": geo["paths"],
               "cities": cities, "n_ranked": len(rows)}

    # ---- global preview tier (optional: present once the world runner has run) ----
    # Cities excluded from publication: we do not publish numbers we believe
    # are artifacts. See docs/mexico-city-rx1day-investigation.md.
    WORLD_EXCLUDE = {
        "Mexico City": "diagnosed: several NEX-GDDP-CMIP6 models produce "
                       "physically impossible rx1day baselines (up to 1,513 mm) "
                       "over this high-relief domain, a downscaling artifact "
                       "that mean-climate trust screening does not catch. "
                       "Withheld until the pipeline screens extremes explicitly.",
    }
    if os.path.exists(WORLD) and os.path.exists(GEO_WORLD):
        wgeo = json.load(open(GEO_WORLD, encoding="utf-8"))
        wdata = json.load(open(WORLD, encoding="utf-8"))
        wrows = []
        for name, r in wdata["cities"].items():
            if "error" in r:
                print(f"world: skipping {name}: {r['error'][:80]}")
                continue
            if name in WORLD_EXCLUDE:
                print(f"world: excluding {name}: {WORLD_EXCLUDE[name][:70]}")
                continue
            if name not in wgeo["pins"]:
                print(f"world: no pin for {name}, skipping")
                continue
            wrows.append((name, r))
        wrows.sort(key=lambda nr: nr[1]["pct_change"], reverse=True)
        wcities = []
        for name, r in wrows:
            x, y = wgeo["pins"][name]
            pct = r["pct_change"]
            agree = round(r["agreement"] * 100)
            conf = r.get("confidence", "moderate")
            wcities.append({
                "id": name.lower().replace(" ", "-"), "name": name,
                "x": x, "y": y,
                "hist": round(r["historical"], 2), "fut": round(r["future"], 2),
                "chg": round(r["change"], 2), "pct": round(pct, 1),
                "agree": agree, "conf": conf,
                "note": (f"Global preview, same method as Europe: {pct:+.1f}% "
                         f"mid-century change in maximum 1-day precipitation, "
                         f"{agree}% trusted-model agreement. {CONF_TEXT[conf]}"),
            })
        if wcities:
            payload["world"] = {"w": wgeo["w"], "h": wgeo["h"],
                                "paths": wgeo["paths"], "cities": wcities}
            print(f"world tier: {len(wcities)} preview cities")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("/* Generated by scripts/build_atlas_data.py - do not edit by hand. */\n")
        f.write("window.ATLAS = " + json.dumps(payload, separators=(",", ":")) + ";\n")
    print(f"{OUT}: {len(cities)} pins ({len(rows)} ranked + Bari pilot)")


if __name__ == "__main__":
    main()

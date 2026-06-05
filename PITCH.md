# Arasense — Pitch Deck Outline

**The trust layer for climate risk.**
*We tell institutions which climate models to trust — for their location, across every hazard — and turn that into defensible, decision-ready evidence.*

> How to use this file: each slide has a **Headline** (on screen), **Say** (your ~15–20s of narration), and **Show** (the visual). One idea per slide. Target ~10 slides, ~3 minutes, then a live demo. Fill every `‹…›` placeholder with a real, sourced number before presenting — judges reward specificity and punish vagueness.

---

## Slide 1 — Title / Hook
- **Headline:** Arasense — the trust layer for climate risk.
- **Say:** "Institutions make billion-euro decisions on climate models they can't fully trust. I'm Aras Izzaddin — I published the method that fixes that, and built it into a platform that works, today, anywhere on Earth."
- **Show:** Logo, one-line tagline, your name + Poliba.

## Slide 2 — The Problem
- **Headline:** Everyone has climate models. Nobody knows which to believe — here.
- **Say:** "There are 30+ CMIP6 models, and they disagree. Teams either pick one 'best' model on a single score, or average the whole ensemble — blending skilful models with broken ones. The result is a risk number nobody can defend to a regulator or a board."
- **Show:** Spaghetti of diverging model projections for one location; "which one?"

## Slide 3 — Why It Matters
- **Headline:** Undefendable climate evidence is a liability.
- **Say:** "Flood, heat, and drought risk now sit on balance sheets, in insurance pricing, and under EU disclosure mandates. A risk decision you can't justify methodologically is a legal and financial exposure."
- **Show:** Three buyer pains — reinsurers (pricing), banks/asset funds (TCFD/EU-taxonomy-mandated), authorities (adaptation). One stat each ‹add source›.

## Slide 4 — The Moat
- **Headline:** The Aras Diagram (Izzaddin et al., 2024, *SERRA*).
- **Say:** "My peer-reviewed method decomposes a model's total error into bias, variability, and timing — so we score *which* models to trust and weight them by skill, not average blind. I'm the author: this is defensible IP, not a wrapper."
- **Show:** The Aras Diagram + the Model Trust Report (tiers, total Aras error %, skill weights). Citation badge.

## Slide 5 — The Product
- **Headline:** Score trust → project the hazard → defensible evidence. Multi-hazard, global.
- **Say:** "For any location on Earth, Arasense screens every CMIP6 model, keeps only those that earn trust, and projects how the hazard changes — across **flood-driving rainfall, heat, and drought** — with honest uncertainty and emission-scenario range. One platform, every hazard, anywhere."
- **Show:** The multi-hazard city report (flood/heat/drought in one table) + the world (global coverage).

## Slide 6 — Live Demo (anchor)
- **Headline:** See it decide. (switch to the app)
- **Say:** see the demo script in Appendix A.
- **Show:** The running console — pick a city → Model Trust Report → multi-hazard projection → scenario compare → download the one-page report.

## Slide 7 — Traction / Proof
- **Headline:** It works, on real data, today — and it's honest about what it can't do.
- **Say:** "This isn't a mockup. Live, full-ensemble result for Bologna: max 1-day rainfall +14% by mid-century (32 of 34 models trusted, 78% agree); the hottest day 37→41°C. Verified across cities on five continents. And where models have no skill, it says so — that integrity is the product."
- **Show:** The full-ensemble Bologna result + the multi-hazard report + a portfolio ranking of cities. *(Land a design partner / LOI before competing — see checklist.)*

## Slide 8 — Business Model
- **Headline:** Pilot → platform → portfolio API.
- **Say:** "Land with a paid pilot on a geography and decision question. Convert to platform access, then a portfolio API priced per exposure for insurers and asset managers. ‹€X pilot, €Y/yr platform, €Z/asset API›."
- **Show:** Three-tier funnel with indicative pricing ‹fill in›. High-trust B2B, not mass-market.

## Slide 9 — Market & Why Now
- **Headline:** ‹TAM / SAM / SOM› — and the timing.
- **Say:** "Climate-risk analytics is a ‹$X B› market growing ‹Y%›. Why now: EU/ISSB disclosure mandates, CMIP6 maturity, and Earth Engine making petabyte-scale data accessible. We're the defensible interpretability layer on top."
- **Show:** TAM/SAM/SOM circles ‹sources›; a 'why now' timeline.

## Slide 10 — Team & Ask
- **Headline:** ‹€amount› to ‹milestone›.
- **Say:** "I'm the inventor of the core method, from Poliba. I'm seeking ‹€X / accelerator place› to convert ‹N› design partners to paid and harden the platform across ‹M› regions in ‹months›."
- **Show:** Your photo + 1-line bio, advisors, the specific ask and the milestones it buys.

---

## Appendix A — 90-second live demo script
1. **(0:00)** "This is the Arasense console. I'll pick Bologna." → click the map.
2. **(0:15)** "Run a climate diagnostic." → the **Aras Diagram** + **Model Trust Report** render: "Each model scored by total Aras error; the ones with no skill here get zero weight."
3. **(0:35)** "Now project mid-century — across hazards." → **Multi-hazard report**: "Flood-driving rainfall up double digits, the hottest day several degrees hotter, drought shifting — only trusted models, agreement shown."
4. **(0:55)** "And the emissions choice?" → **Compare SSP2-4.5 vs SSP5-8.5**: "the gap is the policy decision space."
5. **(1:15)** "Download the one-page report" → hand it over. "Every number traces to peer-reviewed math, and it's all under automated test."
6. **(1:30)** Stop.

> Demo safety: use a **frozen demo build** with cached results so nothing depends on a live API call on stage. Rehearse an offline fallback (screenshots) in case Wi-Fi dies.

## Appendix B — Anticipated judge questions
- **"What's your moat? Can't someone copy this?"** → "The method is peer-reviewed and authored by me; the defensibility is scientific credibility plus the integrated trust→multi-hazard→portfolio pipeline."
- **"How many models?"** → "The full CMIP6 ensemble (34), not a subset — and we report how many passed skill screening per location."
- **"Traction?"** → working platform + verified global results + ‹design partner / LOI›. *(Have a real partner answer before competing.)*
- **"Isn't the flood model risky to over-claim?"** → "The forward projection is the validated core. The flood-*event* GNN is labelled validation-stage R&D — we don't claim it operationally. Honesty is the pitch."
- **"Why pay vs. free climate dashboards?"** → "Dashboards show data; we deliver *defensible interpretation* — what a regulator or board actually needs."

## Appendix C — Pre-competition checklist (close the gaps that lose points)
- [ ] Land 1 design partner or signed LOI (highest-value action).
- [ ] Fill every ‹…› (market sizes with sources, pricing, the ask, competition name/date).
- [ ] Build and freeze a demo build with cached results.
- [ ] Rehearse the 3-minute script + 90-second demo to time.
- [ ] CI green + badge (proof of engineering rigor — done).
- [ ] Have the full-ensemble numbers and a portfolio ranking ready as slides.

---

## What's actually built (reality behind the pitch — keep, don't present verbatim)
- **Model Trust Engine** on the peer-reviewed Aras Diagram: per-model total Aras error, skill tiers, skill weights; rejects out-of-skill models. Tested, in CI.
- **Forward projection** across three hazards — flood-driving rainfall (rx1day, heavy-rain days, p95), heat (max temperature, hot-day frequency), drought (dry-day frequency) — trust-weighted, with uncertainty and model agreement.
- **Scenario comparison** (SSP2-4.5 vs SSP5-8.5), **multi-hazard city profile**, and **portfolio ranking** of locations.
- **Global** — verified live across cities on five continents (land only; flood-*event* GNN still Italy-stage).
- **Console UI** + server-rendered **downloadable reports**. ~51 automated tests, CI on every push.
- **Honest by design:** declines metrics it can't compute (e.g. consecutive-dry-days server-side) and locations where no model earns trust.

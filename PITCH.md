# Arasense — Pitch Deck Outline

**The trust layer for climate risk.**
*We tell institutions which climate models to trust — for their location — and prove it with peer-reviewed math.*

> How to use this file: each slide has a **Headline** (what's on screen), **Say** (your 15–20s of narration), and **Show** (the visual). Keep one idea per slide. Target: 10 slides, ~3 minutes, then live demo. Fill every `‹…›` placeholder with a real number before presenting — judges reward specificity and punish vagueness.

---

## Slide 1 — Title / Hook
- **Headline:** Arasense — The trust layer for climate risk.
- **Say:** "Institutions make billion-euro decisions on climate models they can't fully trust. I'm Aras Izzaddin — I published the method that fixes that, and turned it into a product."
- **Show:** Logo, one-line tagline, your name + Poliba affiliation. Clean, no clutter.

## Slide 2 — The Problem
- **Headline:** Everyone has climate models. Nobody knows which to believe — here.
- **Say:** "There are 30+ CMIP6 climate models. For any given city or asset, they disagree wildly. Today teams pick one 'best' model on a single score, or naively average all of them — blending good models with broken ones. That produces risk numbers no one can defend to a regulator or a board."
- **Show:** A spaghetti chart of many model projections diverging for one location; a question mark over "which one?"

## Slide 3 — Why It Matters (Market Pain)
- **Headline:** Undefendable climate evidence is a liability.
- **Say:** "Flood and climate risk now sit on balance sheets, insurance pricing, and EU adaptation mandates. A risk decision you can't justify methodologically is a legal and financial exposure."
- **Show:** 3 buyer pains — insurers/reinsurers (pricing), authorities/utilities (adaptation mandates), consultancies (defensible deliverables). One stat each ‹add source›.

## Slide 4 — The Insight / Moat
- **Headline:** The Aras Diagram (Izzaddin et al., 2024, *SERRA*).
- **Say:** "My peer-reviewed method decomposes *why* a model is right or wrong — into bias, variability, and timing error. That's the missing ingredient: not just 'how good', but 'good how'. I'm the author, so this is genuinely defensible IP, not a wrapper."
- **Show:** The Aras Diagram with 3–4 models plotted; circles/triangles labeled bias α / variability β / phase. Citation badge.

## Slide 5 — The Product
- **Headline:** Score trust → drive risk → show the evidence.
- **Say:** "Arasense turns that method into a decision engine. For your location, it scores every model, drops the ones that fail a hydrological skill benchmark, and builds a trust-weighted ensemble. Flood screening is our first vertical — driven only by the models that earned trust, with honest uncertainty."
- **Show:** The 3-step pipeline diagram: Aras Diagram → Model Trust Engine → Trust-driven flood. Screenshot of the **Model Trust Report** panel (tiers + skill-weight bars).

## Slide 6 — Live Demo (anchor slide)
- **Headline:** See it decide. (then switch to the app)
- **Say:** see the 90-second demo script in the appendix.
- **Show:** The running console. Pick a location → run diagnostic → Aras Diagram + Trust Report populate → run trust-driven flood → map + uncertainty.

## Slide 7 — Traction
- **Headline:** ‹Design partner / LOI / pilot›.
- **Say:** "We validated the engine on the 2023 Emilia-Romagna floods: ‹IoU X%, recall Y%› against Sentinel-1. We're now running a pilot with ‹partner›." *(This is the slide to make real before competing — see roadmap.)*
- **Show:** Emilia-Romagna validation map (predicted vs. Sentinel-1), the headline accuracy numbers, partner logo or signed-LOI note.

## Slide 8 — Business Model
- **Headline:** Pilot → platform → API.
- **Say:** "Land with a paid pilot on one geography and decision question. Convert to platform access and a private API as value is proven. ‹€X pilot, €Y/yr platform›."
- **Show:** Three-tier funnel with indicative pricing ‹fill in›. Note: not mass-market self-serve — high-trust B2B.

## Slide 9 — Market & Why Now
- **Headline:** ‹TAM / SAM / SOM› — and the timing.
- **Say:** "Climate-risk analytics is a ‹$X B› market growing ‹Y%›. Why now: EU adaptation regulation, CMIP6 maturity, and Earth Engine making petabyte-scale data accessible. We're the interpretability layer on top."
- **Show:** TAM/SAM/SOM circles ‹add sources›; a 'why now' timeline.

## Slide 10 — Team & Ask
- **Headline:** ‹€amount› to ‹milestone›.
- **Say:** "I'm the inventor of the core method, from Poliba. I'm raising / seeking ‹€X / partnership / accelerator place› to run 3 validated regional pilots and convert 1 design partner to paid in ‹N months›."
- **Show:** Your photo + 1-line bio, any advisors, the specific ask and the 3 milestones it buys.

---

## Appendix A — 90-second live demo script
1. **(0:00)** "This is the Arasense console. I'll pick Bologna." → click the map.
2. **(0:15)** "Run a climate diagnostic." → the **Aras Diagram** renders the CMIP6 ensemble. "Each point is a model; distance from centre is total error, decomposed into bias and variability."
3. **(0:35)** "Here's the engine's verdict." → the **Model Trust Report** panel: "Two models trusted, one rejected — it failed the mean-flow benchmark, so it gets zero weight. The engine even says which error to bias-correct first."
4. **(0:55)** "Now drive flood from only the trusted models." → run trust-driven flood. "The flood signal is a skill-weighted ensemble, with an uncertainty band the single-best-model approach can't give."
5. **(1:20)** "Every number here traces back to peer-reviewed math, and it's all under automated test." Land on the result. Stop.

> Demo safety: use a **frozen demo build** with cached results so it never depends on a live API call on stage. Rehearse the offline fallback (screenshots) in case Wi-Fi dies.

## Appendix B — Anticipated judge questions
- **"What's your moat? Can't someone copy this?"** → "The method is peer-reviewed and authored by me; the defensibility is scientific credibility plus the integrated trust→risk pipeline, not just code."
- **"Traction?"** → point to the Emilia-Romagna validation + pilot/LOI. *(Have a real answer here before competing.)*
- **"Isn't the flood model risky to over-claim?"** → "We label it validation-stage screening, not engineering-grade forecasting. Honesty is part of the credibility pitch."
- **"Why will customers pay vs. free climate dashboards?"** → "Dashboards show data; we deliver *defensible interpretation* — the thing a regulator or board actually needs."
- **"Team — can one person execute?"** → state hiring plan tied to the ask (hydrology/ML hire).

## Appendix C — Pre-competition checklist (close the gaps that lose points)
- [ ] Land 1 design partner or signed LOI (highest-value action).
- [ ] Finish the Emilia-Romagna 2023 validation with real accuracy numbers.
- [ ] Build and freeze a demo build with cached results.
- [ ] Fill every ‹…› placeholder (market sizes with sources, pricing, the ask).
- [ ] Rehearse the 3-minute script + 90-second demo to time.
- [ ] Push CI green + add the badge (proof of engineering rigor).

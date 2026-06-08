# Paper 1 — Abstract, Introduction, Discussion (working draft)

*Companion to `methods-and-validation.md`. Real prose; honest about the findings.*

---

## Abstract

Multi-model climate ensembles disagree, and the common practice of equal-weight
averaging gives a model with no skill at a location the same say as one that
captures it. Performance-weighting schemes exist but are often opaque — weights
that cannot be explained are hard to defend in a risk decision. We present a
weighting scheme built on the Aras Diagram (Izzaddin et al., 2024), an
interpretable two-dimensional decomposition of model error into bias, variability,
and timing, from which we derive transparent trust tiers, benchmark-anchored
rejection of unskilful models, and skill weights. Applying it to the NASA
GDDP-CMIP6 ensemble over Mediterranean locations, we evaluate whether the weighting
improves projections with a leave-one-out perfect-model test. We find that weighting
the ensemble by its skill at the broad monthly climatology does **not** improve the
projection of a future extreme over a simple ensemble mean. However, scoring trust
on the target metric's **own** historical behaviour (e.g. the annual maximum 1-day
precipitation) recovers a modest but real improvement. The decisive factor is the
alignment between the evaluation metric and the projection target — performance
weighting is conditional, not free skill. The contribution is an interpretable,
auditable model-evaluation and weighting framework, together with a candid
demonstration of when performance weighting helps and when it does not.

---

## 1. Introduction

Coupled climate models disagree, sometimes substantially, about regional change —
and the disagreement matters most precisely where the stakes are highest: pricing
risk, planning adaptation, satisfying disclosure. Faced with an ensemble, the
default is to average it, which implicitly assumes every model is equally
informative. It is not: at any given location some models reproduce the observed
climate well and others poorly, and blending them dilutes the skilful with the
unskilful.

Performance-based weighting has been proposed to address this (Giorgi & Mearns,
2002; Tebaldi & Knutti, 2007), most prominently the ClimWIP scheme that weights by
both performance and inter-model independence (Knutti et al., 2017; Brunner et al.,
2020). Two difficulties recur. First, **interpretability**: weights derived from a
single aggregate skill score are hard to explain, and a weight you cannot justify is
hard to put in front of a regulator or a board. Second, **validity**: historical
performance is, in general, a weak predictor of the accuracy of future projections,
which is why the broader "emergent constraints" programme exists and why weighting
schemes remain contested.

We take up both. Building on the Aras Diagram (Izzaddin et al., 2024) — a
peer-reviewed decomposition that locates each model in an interpretable space of
bias, variability, and timing error — we derive trust tiers, a benchmark-anchored
rejection rule, and skill weights whose every value is traceable to *why* a model
is (un)trusted. We then confront the validity question directly with a perfect-model
test, and report a result that is, we argue, the useful one: whether weighting helps
depends entirely on **what the models are scored on**. Our contributions are: (i) an
interpretable, benchmark-anchored weighting scheme; (ii) explicit declination of
out-of-skill locations rather than spurious projection; and (iii) a candid
perfect-model evaluation showing that performance weighting improves extreme
projections only when trust is scored on the target quantity's own behaviour.

---

## 7. Discussion

Our central result is a caution and a remedy. Scored against the broad monthly
climatology, trust-weighting did not beat a plain ensemble mean at projecting a
future extreme — consistent with the literature's finding that historical skill is a
weak guide to projection accuracy. This is worth stating plainly because it is easy,
with a polished tool, to *assume* that "weighting by skill" must help; in our test it
did not. The remedy is alignment: scoring trust on the target metric's own historical
series restored a modest improvement. The information that constrains a future
extreme is skill at that extreme, not at the seasonal cycle.

Two implications follow. For practitioners, a weighting scheme should be evaluated,
per target quantity, with a perfect-model or out-of-sample test before its weighted
projection is claimed to be more accurate than the mean; an unvalidated weighting is
at best decorative and at worst overconfident. For the present framework, the value
that does **not** depend on the validity question is the interpretability: the
decomposition tells a user which models are trusted and why, and the benchmark rule
removes models that fail to beat the observed mean. These properties make the basis
of a projection transparent and auditable regardless of whether the weighting
sharpens the central estimate.

**Limitations.** The improvement, where present, is single-digit and demonstrated
for a limited set of locations and one extreme metric; generalisation across
regions, metrics, and scenarios, an out-of-sample test over a held-out historical
period, and a like-for-like comparison with ClimWIP are necessary before any general
accuracy claim. The scheme weights for performance only; model interdependence
(genealogy) is not yet accounted for and is a natural extension. Downscaled-data
resolution and the choice of observational reference also bound the conclusions.

**Outlook.** The natural next steps are a metric-aligned scoring mode as the default
for extreme targets, an independence term, and a systematic perfect-model evaluation
across the hazard set — turning a candid negative-then-positive result into a
calibrated, validated weighting standard.

/* Arasense evidence receipts — every marked number can show where it came
   from: values, method chain, settings, caveats, and the raw run JSON.
   Elements opt in with <button class="receipt-tag" data-receipt="id">. */
(function () {
  "use strict";

  var CHAIN = ["ERA5-Land observed baseline", "Aras Diagram skill scores",
               "trust weights (rejects dropped)", "trust-weighted projection"];

  var BOLOGNA_ITEMS = [
    ["baseline 1995–2014", "40.23 mm"],
    ["future 2040–2059", "45.97 mm"],
    ["change", "+5.73 mm (+14.2%)"],
    ["spread across models", "−0.26 … +11.73 mm"],
    ["agreement on increase", "78%"],
    ["models trusted", "32 of 34"]
  ];

  var R = {
    "bologna-pct": {
      title: "Bologna · max 1-day rainfall",
      value: "+14.2% by mid-century",
      items: BOLOGNA_ITEMS,
      settings: "SSP2-4.5 · 50 km radius · CMIP6 × ERA5-Land",
      caveat: "Full 34-model deep dive. Spread and agreement reported, not hidden.",
      src: "data/bologna-rx1day-deep-dive.json"
    },
    "bologna-levels": {
      title: "Bologna · max 1-day rainfall",
      value: "40.2 → 46.0 mm",
      items: BOLOGNA_ITEMS,
      settings: "SSP2-4.5 · 50 km radius · CMIP6 × ERA5-Land",
      caveat: "Full 34-model deep dive. Spread and agreement reported, not hidden.",
      src: "data/bologna-rx1day-deep-dive.json"
    },
    "bologna-models": {
      title: "Bologna · skill screening",
      value: "32 of 34 models trusted",
      items: BOLOGNA_ITEMS,
      settings: "Reject threshold KGE ≤ −0.41 (Knoben et al. 2019)",
      caveat: "Every weight and both rejections are in the raw file.",
      src: "data/bologna-rx1day-deep-dive.json"
    },
    "bologna-agree": {
      title: "Bologna · model agreement",
      value: "78% of trusted weight",
      items: BOLOGNA_ITEMS,
      settings: "SSP2-4.5 · 50 km radius · CMIP6 × ERA5-Land",
      caveat: "Agreement is weight on “increase”, not a head-count.",
      src: "data/bologna-rx1day-deep-dive.json"
    },
    "miroc": {
      title: "Bologna · two models, one ensemble",
      value: "MIROC-ES2L vs MIROC6",
      items: [
        ["MIROC-ES2L", "40.9 → 35.5 mm (−5.3)"],
        ["MIROC6", "37.0 → 54.7 mm (+17.7)"],
        ["same ensemble", "CMIP6"],
        ["same location", "Bologna · 50 km"]
      ],
      settings: "SSP2-4.5 · 1995–2014 → 2040–2059",
      caveat: "Opposite answers from credible models — the reason trust must be measured.",
      src: "data/bologna-rx1day-deep-dive.json"
    },
    "rome-pct": {
      title: "Rome · portfolio rank 1 of 5",
      value: "+19% max 1-day rainfall",
      items: [
        ["baseline", "39.91 mm"],
        ["mid-century", "47.40 mm"],
        ["change", "+7.49 mm (+19%)"],
        ["agreement on increase", "100%"]
      ],
      settings: "SSP2-4.5 · 50 km radius · 5-model screening ensemble",
      caveat: "Screening-level ranking across a five-city Italian portfolio.",
      src: "data/italian-flood-portfolio.json"
    },
    "scenario": {
      title: "Bologna · scenario comparison",
      value: "SSP2-4.5 vs SSP5-8.5",
      items: [
        ["SSP2-4.5 change", "+14.2% · 78% agree"],
        ["SSP5-8.5 change", "+13.5% · 74% agree"],
        ["shared baseline", "40.23 mm"],
        ["shared trust weights", "32 models"]
      ],
      settings: "Only the emissions scenario changes between runs",
      caveat: "The scenario gap is small here — and reported as small.",
      src: "data/bologna-ssp245-vs-ssp585.json"
    }
  };

  var card = null;

  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  }

  function build() {
    card = document.createElement("div");
    card.className = "receipt";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-label", "Evidence receipt");
    document.body.appendChild(card);
    document.addEventListener("click", function (e) {
      if (card.classList.contains("open") &&
          !card.contains(e.target) && !e.target.closest(".receipt-tag")) hide();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") hide();
    });
  }

  function hide() {
    if (card) card.classList.remove("open");
    document.querySelectorAll(".receipt-tag.on").forEach(function (t) {
      t.classList.remove("on");
    });
  }

  function show(tag, r) {
    if (!card) build();
    var rows = r.items.map(function (it) {
      return "<tr><td>" + esc(it[0]) + "</td><td>" + esc(it[1]) + "</td></tr>";
    }).join("");
    var chain = CHAIN.map(function (s, i) {
      return "<span>" + (i ? "↓ " : "") + esc(s) + "</span>";
    }).join("");
    card.innerHTML =
      '<button class="rc-close" aria-label="Close receipt">×</button>' +
      '<div class="rc-brand">ARASENSE</div>' +
      '<div class="rc-kind">◆ EVIDENCE RECEIPT · OPEN DATA ◆</div>' +
      '<div class="rc-rule"></div>' +
      '<div class="rc-title">' + esc(r.title) + "</div>" +
      '<div class="rc-value">' + esc(r.value) + "</div>" +
      '<div class="rc-rule"></div>' +
      "<table>" + rows + "</table>" +
      '<div class="rc-rule"></div>' +
      '<div class="rc-chain">' + chain + "</div>" +
      '<div class="rc-settings">' + esc(r.settings) + "</div>" +
      '<div class="rc-caveat">' + esc(r.caveat) + "</div>" +
      '<a class="rc-src" href="' + r.src + '">RAW RUN FILE → ' +
        esc(r.src.split("/").pop()) + "</a>" +
      '<div class="rc-bar" aria-hidden="true"></div>' +
      '<div class="rc-foot">recomputable · auditable · www.arasense.com</div>';
    card.querySelector(".rc-close").addEventListener("click", hide);

    card.classList.add("open");
    var rect = tag.getBoundingClientRect();
    var w = card.offsetWidth || 330;
    var x = rect.left + window.scrollX + rect.width / 2 - w / 2;
    x = Math.max(12, Math.min(x, window.scrollX + document.documentElement.clientWidth - w - 12));
    card.style.left = x + "px";
    card.style.top = (rect.bottom + window.scrollY + 14) + "px";
    tag.classList.add("on");
  }

  document.querySelectorAll(".receipt-tag").forEach(function (tag) {
    var r = R[tag.getAttribute("data-receipt")];
    if (!r) { tag.style.display = "none"; return; }
    tag.setAttribute("title", "Show the evidence receipt");
    tag.addEventListener("click", function (e) {
      e.stopPropagation();
      if (tag.classList.contains("on")) { hide(); return; }
      hide();
      show(tag, r);
    });
  });
})();

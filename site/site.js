/* Arasense shared interactions: scroll reveal, stat counters, mobile nav */
(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Ambient aurora backdrop (behind everything, pure decoration) */
  var aurora = document.createElement("div");
  aurora.className = "aurora";
  aurora.setAttribute("aria-hidden", "true");
  document.body.prepend(aurora);

  /* Scroll progress hairline */
  var progress = document.createElement("div");
  progress.className = "progress";
  progress.setAttribute("aria-hidden", "true");
  document.body.prepend(progress);
  var ticking = false;
  function paintProgress() {
    var max = document.documentElement.scrollHeight - window.innerHeight;
    progress.style.transform = "scaleX(" + (max > 0 ? window.scrollY / max : 0) + ")";
    ticking = false;
  }
  window.addEventListener("scroll", function () {
    if (!ticking) { ticking = true; requestAnimationFrame(paintProgress); }
  }, { passive: true });
  paintProgress();

  /* Cursor spotlight on surfaces (drives --mx/--my in CSS) */
  document.addEventListener("pointermove", function (e) {
    var t = e.target.closest ? e.target.closest(".card, .kpi, .step, .panel") : null;
    if (!t) return;
    var r = t.getBoundingClientRect();
    t.style.setProperty("--mx", (e.clientX - r.left) + "px");
    t.style.setProperty("--my", (e.clientY - r.top) + "px");
  }, { passive: true });

  /* Word-by-word headline reveal: <h1 data-word-reveal> */
  document.querySelectorAll("[data-word-reveal]").forEach(function (h) {
    if (reduced) return;
    var i = 0;
    function split(node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (child) {
        if (child.nodeType === 3) {
          var frag = document.createDocumentFragment();
          child.textContent.split(/(\s+)/).forEach(function (part) {
            if (!part) return;
            if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(part)); return; }
            var w = document.createElement("span");
            w.className = "wr";
            w.style.setProperty("--wi", i++);
            w.textContent = part;
            frag.appendChild(w);
          });
          node.replaceChild(frag, child);
        } else if (child.nodeType === 1 && child.tagName !== "BR") {
          split(child);
        }
      });
    }
    split(h);
  });

  /* Scroll reveal */
  var revealed = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && !reduced) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    revealed.forEach(function (el) { io.observe(el); });
  } else {
    revealed.forEach(function (el) { el.classList.add("in"); });
  }

  /* Animated counters: <span data-count="14.2" data-decimals="1" data-prefix="+" data-suffix="%"> */
  function animateCount(el) {
    var target = parseFloat(el.getAttribute("data-count"));
    var decimals = parseInt(el.getAttribute("data-decimals") || "0", 10);
    var prefix = el.getAttribute("data-prefix") || "";
    var suffix = el.getAttribute("data-suffix") || "";
    if (reduced) {
      el.textContent = prefix + target.toFixed(decimals) + suffix;
      return;
    }
    var dur = 1100;
    var start = null;
    function tick(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = prefix + (target * eased).toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  var counters = document.querySelectorAll("[data-count]");
  if ("IntersectionObserver" in window) {
    var cio = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          animateCount(e.target);
          cio.unobserve(e.target);
        }
      });
    }, { threshold: 0.5 });
    counters.forEach(function (el) { cio.observe(el); });
  } else {
    counters.forEach(animateCount);
  }

  /* Mobile nav */
  var toggle = document.querySelector(".nav-toggle");
  var links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", function () {
      links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", links.classList.contains("open") ? "true" : "false");
    });
  }

  /* Lead capture forms → POST /api/lead, mailto fallback */
  document.querySelectorAll("form.lead-form").forEach(function (form) {
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var msg = form.querySelector(".lf-msg");
      var btn = form.querySelector("button");
      var data = {
        email: (form.email.value || "").trim(),
        org: form.org ? (form.org.value || "").trim() : "",
        city: form.getAttribute("data-city") || "",
        page: location.pathname,
        website: form.website ? form.website.value : ""
      };
      if (!data.email) return;
      btn.disabled = true;
      msg.className = "lf-msg";
      msg.textContent = "Sending…";
      fetch("/api/lead", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(data)
      }).then(function (r) {
        if (!r.ok) throw new Error("lead endpoint " + r.status);
        return r.json();
      }).then(function () {
        form.classList.add("sent");
        msg.className = "lf-msg ok";
        msg.textContent = "Request received — the " + (data.city ? data.city + " " : "") +
          "brief will come from arasbotan.izzaddin@poliba.it.";
      }).catch(function () {
        btn.disabled = false;
        msg.className = "lf-msg err";
        msg.innerHTML = 'That didn’t go through — please email ' +
          '<a href="mailto:arasbotan.izzaddin@poliba.it?subject=' +
          encodeURIComponent("Trust brief request: " + (data.city || "my region")) +
          '&body=' + encodeURIComponent("Please send the " + (data.city || "") +
          " trust brief to: " + data.email) + '">arasbotan.izzaddin@poliba.it</a> directly.';
      });
    });
  });

  /* Highlight current page in nav */
  var here = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-links a").forEach(function (a) {
    var href = a.getAttribute("href") || "";
    if (href === here) a.classList.add("active");
  });
})();

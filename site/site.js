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
  var navWrap = document.querySelector(".nav-wrap");
  var ticking = false;
  function paintProgress() {
    var max = document.documentElement.scrollHeight - window.innerHeight;
    var y = window.scrollY;
    progress.style.transform = "scaleX(" + (max > 0 ? y / max : 0) + ")";
    if (!reduced) aurora.style.transform = "translateY(" + (y * 0.06).toFixed(1) + "px)";
    if (navWrap) navWrap.classList.toggle("scrolled", y > 10);
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
        msg.textContent = "Request received. The " + (data.city ? data.city + " " : "") +
          "brief will come from arasbotan.izzaddin@poliba.it.";
      }).catch(function () {
        btn.disabled = false;
        msg.className = "lf-msg err";
        msg.innerHTML = 'That didn’t go through. Please email ' +
          '<a href="mailto:arasbotan.izzaddin@poliba.it?subject=' +
          encodeURIComponent("Trust brief request: " + (data.city || "my region")) +
          '&body=' + encodeURIComponent("Please send the " + (data.city || "") +
          " trust brief to: " + data.email) + '">arasbotan.izzaddin@poliba.it</a> directly.';
      });
    });
  });

  /* 3D tilt on cards + magnetic buttons (fine pointers, motion allowed) */
  var finePointer = window.matchMedia("(pointer: fine)").matches;
  if (finePointer && !reduced) {
    document.querySelectorAll(".card").forEach(function (c) {
      c.addEventListener("pointermove", function (e) {
        var r = c.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width - 0.5;
        var py = (e.clientY - r.top) / r.height - 0.5;
        c.style.transform = "perspective(700px) rotateX(" + (py * -3.5).toFixed(2) +
          "deg) rotateY(" + (px * 4.5).toFixed(2) + "deg) translateY(-2px)";
      });
      c.addEventListener("pointerleave", function () { c.style.transform = ""; });
    });

    document.querySelectorAll(".button, .button-secondary").forEach(function (b) {
      b.addEventListener("pointermove", function (e) {
        var r = b.getBoundingClientRect();
        b.style.transform = "translate(" + ((e.clientX - r.left - r.width / 2) * 0.12).toFixed(1) +
          "px," + (((e.clientY - r.top - r.height / 2) * 0.25) - 1).toFixed(1) + "px)";
      });
      b.addEventListener("pointerleave", function () { b.style.transform = ""; });
    });

    /* hero headline drifts gently against the cursor */
    var heroH1 = document.querySelector(".hero h1");
    if (heroH1) {
      document.addEventListener("pointermove", function (e) {
        var dx = e.clientX / window.innerWidth - 0.5;
        var dy = e.clientY / window.innerHeight - 0.5;
        heroH1.style.transform = "translate(" + (dx * -7).toFixed(1) + "px," + (dy * -5).toFixed(1) + "px)";
      }, { passive: true });
    }
  }

  /* ---- Trust command palette (Ctrl/Cmd+K or /) ---- */
  (function () {
    var PAGES = [
      ["Home", "/"], ["Why not just average?", "/why.html"], ["Trust Atlas", "/atlas.html"], ["Demo console", "/demo.html"],
      ["Case studies", "/case-studies.html"], ["Sample evidence", "/evidence.html"],
      ["Bari / Puglia pilot", "/bari-puglia.html"], ["Aras' Diagram Studio", "/aras-diagram.html"],
      ["All trust profiles", "/trust/"]
    ];
    var ACTIONS = [
      ["Request a briefing", "mailto:arasbotan.izzaddin@poliba.it?subject=Arasense%20briefing"],
      ["Download the Bari / Puglia brief (PDF)", "/bari-puglia-climate-risk-brief.pdf"]
    ];

    var overlay, input, list, items, sel;

    function cities() {
      if (!window.ATLAS) return [];
      var out = [];
      (window.ATLAS.cities || []).forEach(function (c) {
        if (c.pilot) return;
        out.push({ name: c.name, url: "/trust/" + c.id + ".html", pct: c.pct, agree: c.agree, dot: "" });
      });
      ((window.ATLAS.world || {}).cities || []).forEach(function (c) {
        out.push({ name: c.name, url: "/trust/" + c.id + ".html", pct: c.pct, agree: c.agree,
                   dot: c.conf === "weak" ? "w" : c.conf === "moderate" ? "m" : "" });
      });
      return out;
    }

    function ensureData(cb) {
      if (window.ATLAS) { cb(); return; }
      var s = document.createElement("script");
      s.src = "/atlas-data.js?v=4";
      s.onload = cb;
      s.onerror = cb;
      document.head.appendChild(s);
    }

    function build() {
      if (overlay) return;
      overlay = document.createElement("div");
      overlay.className = "pal-overlay";
      overlay.innerHTML =
        '<div class="pal" role="dialog" aria-label="Site search">' +
        '<input type="text" placeholder="Search a city, a page, an action…" aria-label="Search">' +
        '<div class="pal-list"></div>' +
        '<div class="pal-hint"><span><b>↑↓</b> navigate</span><span><b>↵</b> open</span><span><b>esc</b> close</span></div>' +
        "</div>";
      document.body.appendChild(overlay);
      input = overlay.querySelector("input");
      list = overlay.querySelector(".pal-list");
      overlay.addEventListener("mousedown", function (e) { if (e.target === overlay) close(); });
      input.addEventListener("input", function () { render(input.value); });
      input.addEventListener("keydown", function (e) {
        if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
        else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
        else if (e.key === "Enter" && items[sel]) { location.href = items[sel].getAttribute("href"); }
        else if (e.key === "Escape") { close(); }
      });
    }

    function fmt(pct) { return (pct >= 0 ? "+" : "") + pct.toFixed(1) + "%"; }

    function render(q) {
      q = (q || "").trim().toLowerCase();
      var html = "";
      var cs = cities().filter(function (c) { return !q || c.name.toLowerCase().indexOf(q) !== -1; });
      if (cs.length) {
        html += '<div class="pal-group">City trust profiles</div>';
        cs.slice(0, q ? 24 : 6).forEach(function (c) {
          html += '<a class="pal-item" href="' + c.url + '"><span class="pdot ' + c.dot + '"></span>' +
            c.name + '<span class="meta' + (c.pct < 0 ? " neg" : "") + '">' + fmt(c.pct) +
            " · " + c.agree + "%</span></a>";
        });
      }
      var ps = PAGES.filter(function (p) { return !q || p[0].toLowerCase().indexOf(q) !== -1; });
      if (ps.length) {
        html += '<div class="pal-group">Pages</div>';
        ps.forEach(function (p) {
          html += '<a class="pal-item" href="' + p[1] + '"><span class="pdot page"></span>' + p[0] + "</a>";
        });
      }
      var as = ACTIONS.filter(function (a) { return !q || a[0].toLowerCase().indexOf(q) !== -1; });
      if (as.length) {
        html += '<div class="pal-group">Actions</div>';
        as.forEach(function (a) {
          html += '<a class="pal-item" href="' + a[1] + '"><span class="pdot page"></span>' + a[0] + "</a>";
        });
      }
      if (!html) html = '<div class="pal-empty">Nothing matches. Try a city name, e.g. Lagos or Bologna.</div>';
      list.innerHTML = html;
      items = list.querySelectorAll(".pal-item");
      sel = 0;
      if (items[0]) items[0].classList.add("sel");
    }

    function move(d) {
      if (!items || !items.length) return;
      items[sel].classList.remove("sel");
      sel = (sel + d + items.length) % items.length;
      items[sel].classList.add("sel");
      items[sel].scrollIntoView({ block: "nearest" });
    }

    function open() {
      build();
      ensureData(function () {
        overlay.classList.add("open");
        input.value = "";
        render("");
        input.focus();
      });
    }

    function close() { if (overlay) overlay.classList.remove("open"); }

    document.addEventListener("keydown", function (e) {
      if ((e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey)) { e.preventDefault(); open(); }
      else if (e.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || "")) {
        e.preventDefault(); open();
      }
    });

    var navLinks = document.querySelector(".nav-links");
    if (navLinks) {
      var k = document.createElement("button");
      k.className = "nav-k";
      k.type = "button";
      k.innerHTML = "⌘K";
      k.setAttribute("aria-label", "Search the site");
      k.addEventListener("click", open);
      navLinks.insertBefore(k, navLinks.querySelector(".nav-cta"));
    }
  })();

  /* Chapter rail: fixed dot nav built from .section[data-chapter] */
  (function () {
    var chapters = document.querySelectorAll(".section[data-chapter]");
    if (chapters.length < 3) return;
    var rail = document.createElement("nav");
    rail.className = "rail";
    rail.setAttribute("aria-label", "Page chapters");
    var dots = [];
    chapters.forEach(function (s) {
      var a = document.createElement("a");
      a.href = "#" + s.id;
      a.setAttribute("aria-label", s.getAttribute("data-chapter"));
      var label = document.createElement("span");
      label.textContent = s.getAttribute("data-chapter");
      a.appendChild(label);
      rail.appendChild(a);
      dots.push(a);
    });
    document.body.appendChild(rail);
    if ("IntersectionObserver" in window) {
      var active = null;
      var cio = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) {
            if (active) active.classList.remove("on");
            active = dots[Array.prototype.indexOf.call(chapters, e.target)];
            if (active) active.classList.add("on");
          }
        });
      }, { rootMargin: "-40% 0px -50% 0px" });
      chapters.forEach(function (s) { cio.observe(s); });
    }
  })();

  /* Highlight current page in nav */
  var here = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-links a").forEach(function (a) {
    var href = a.getAttribute("href") || "";
    if (href === here) a.classList.add("active");
  });
})();

(function () {
  var root = document.documentElement;
  var nav = document.getElementById("nav");
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var LOOKS = {
    swe: { wave: "grid", cell: 26, speed: 7, freq: 1.1, width: 4, fade: 1.3, lift: 46, frame: ["▀", "▄", "█"] },
    sentry: { wave: "grid", cell: 34, speed: 9, freq: 0.95, width: 4.6, fade: 1.5, lift: 58, frame: ["▀", "▄", "█"] },
    ml: { wave: "dots", frame: ["▒", "▒", "▒"] }
  };
  var look = LOOKS[document.body.dataset.look] || LOOKS.swe;

  var PATTERNS = {
    copy: [".....", ".#####....#####.", ".#...#....#...#.", ".#...#.##.#...#.", ".#...#....#...#.", ".#####....#####."],
    bump: ["", ".......##.......", "......####......", ".....######.....", "....########....", ".......##.......", ".......##......."],
    diff: ["", ".####.##########", ".####...........", ".####.######....", ".....#..........", ".####.#####.....", ".####..........."],
    file: ["", "....#######.....", "....#.....##....", "....#.###..#....", "....#.....##....", "....#.###..#....", "....#######....."]
  };

  var themeBusy = false;
  var wave = { wake: function () {}, refresh: function () {} };

  function startTheme() {
    var saved = null;
    try { saved = localStorage.getItem("theme"); } catch (e) {}
    root.dataset.theme = saved === "light" ? "light" : "dark";
    root.classList.add("js");
  }

  function toggleTheme(e) {
    if (themeBusy) return;
    var next = root.dataset.theme === "light" ? "dark" : "light";
    var apply = function () {
      root.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch (err) {}
      wave.refresh();
    };
    if (!document.startViewTransition || reduce) { apply(); wave.wake(); return; }
    var x = e.clientX, y = e.clientY;
    var radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    themeBusy = true;
    var done = function () { themeBusy = false; wave.wake(); };
    var t = document.startViewTransition(apply);
    t.finished.then(done, done);
    t.ready.then(function () {
      root.animate(
        { clipPath: ["circle(0px at " + x + "px " + y + "px)", "circle(" + radius + "px at " + x + "px " + y + "px)"] },
        { duration: 900, easing: "cubic-bezier(.4,0,.2,1)", pseudoElement: "::view-transition-new(root)" }
      );
    }, done);
  }

  function setupThemeButtons() {
    document.querySelectorAll("[data-theme-toggle]").forEach(function (b) { b.addEventListener("click", toggleTheme); });
  }

  function setupReveal() {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { threshold: 0.15 });
    document.querySelectorAll(".reveal").forEach(function (el) { io.observe(el); });
  }

  function revealNow() {
    var vh = window.innerHeight;
    document.querySelectorAll(".reveal:not(.in)").forEach(function (el) {
      var r = el.getBoundingClientRect();
      if (r.top < vh * 0.92 && r.bottom > 0) el.classList.add("in");
    });
  }

  function setupRipple() {
    document.addEventListener("pointerdown", function (e) {
      var el = e.target.closest && e.target.closest(".rip");
      if (!el) return;
      var r = el.getBoundingClientRect();
      el.style.setProperty("--rx", (e.clientX - r.left) + "px");
      el.style.setProperty("--ry", (e.clientY - r.top) + "px");
      el.classList.remove("go");
      void el.offsetWidth;
      el.classList.add("go");
    });
  }

  function placeAmbient() {
    var a = nav.querySelector(".figlink.on") || nav.querySelector(".figlink") || nav.querySelector(".startlink");
    if (!a) return;
    var r = nav.getBoundingClientRect(), ar = a.getBoundingClientRect();
    nav.style.setProperty("--ax", (ar.left - r.left + ar.width / 2) + "px");
  }

  function navState() {
    revealNow();
    var mid = window.innerHeight * 0.5;
    var current = null;
    var s = document.getElementById("lifecycle");
    if (s) { var r = s.getBoundingClientRect(); if (r.top <= mid && r.bottom > mid) current = "lifecycle"; }
    document.querySelectorAll("[data-sec]").forEach(function (a) { a.classList.toggle("on", a.dataset.sec === current); });
    placeAmbient();
    var y = window.scrollY || root.scrollTop || 0;
    var min = nav.classList.contains("min");
    if (!min && y > 110) nav.classList.add("min");
    else if (min && y < 50) { nav.classList.remove("min"); setTimeout(placeAmbient, 900); }
  }

  function setupPointer() {
    var raf = 0;
    document.addEventListener("pointermove", function (e) {
      if (raf) return;
      raf = requestAnimationFrame(function () {
        raf = 0;
        if (!nav.classList.contains("min")) {
          var nr = nav.getBoundingClientRect();
          nav.style.setProperty("--sx", (e.clientX - nr.left) + "px");
          nav.classList.toggle("hot", e.clientY >= 0 && e.clientY < nr.bottom + 12);
        } else {
          nav.classList.remove("hot");
        }
        root.style.setProperty("--cx", e.clientX + "px");
        root.style.setProperty("--cy", e.clientY + "px");
        var foot = document.getElementById("figwrap");
        if (foot) {
          var r = foot.getBoundingClientRect();
          foot.style.setProperty("--fx", (e.clientX - r.left) + "px");
          foot.style.setProperty("--fy", (e.clientY - r.top) + "px");
        }
      });
    }, { passive: true });
  }

  function slideCards() {
    var wrap = document.getElementById("evwrap");
    var cfs = document.getElementById("cfs");
    if (!wrap || !cfs) return;
    var r = wrap.getBoundingClientRect();
    var travel = wrap.offsetHeight - window.innerHeight + 90;
    var p = Math.min(1, Math.max(0, (90 - r.top) / Math.max(1, travel)));
    cfs.scrollLeft = p * (cfs.scrollWidth - cfs.clientWidth);
  }

  function setupSmoothScroll() {
    if (reduce) return;
    var target = window.scrollY, cur = target, raf = 0, last = 0;
    var max = function () { return Math.max(0, root.scrollHeight - window.innerHeight); };
    var loop = function (t) {
      var dt = Math.min(48, t - last) || 16;
      last = t;
      cur += (target - cur) * (1 - Math.pow(1 - 0.075, dt / 16.67));
      if (Math.abs(target - cur) < 0.4) { cur = target; window.scrollTo(0, cur); raf = 0; return; }
      window.scrollTo(0, cur);
      raf = requestAnimationFrame(loop);
    };
    var go = function () { if (!raf) { last = performance.now(); raf = requestAnimationFrame(loop); } };
    root.classList.add("sm");
    window.addEventListener("wheel", function (e) {
      if (e.ctrlKey || e.defaultPrevented) return;
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
      var n = e.target;
      while (n && n !== root && n.nodeType === 1) {
        var st = getComputedStyle(n);
        if ((st.overflowY === "auto" || st.overflowY === "scroll") && n.scrollHeight > n.clientHeight + 1) return;
        n = n.parentElement;
      }
      e.preventDefault();
      var d = e.deltaMode === 1 ? e.deltaY * 34 : e.deltaMode === 2 ? e.deltaY * window.innerHeight : e.deltaY;
      target = Math.min(max(), Math.max(0, target + d));
      go();
    }, { passive: false });
    window.addEventListener("scroll", function () { if (!raf) { target = cur = window.scrollY; } }, { passive: true });
    document.addEventListener("click", function (e) {
      var a = e.target.closest && e.target.closest('a[href^="#"]');
      if (!a) return;
      var id = a.getAttribute("href").slice(1);
      var el = id ? document.getElementById(id) : null;
      if (!el) return;
      e.preventDefault();
      target = Math.min(max(), Math.max(0, el.getBoundingClientRect().top + window.scrollY - 16));
      go();
    });
  }

  function makePre(cls, text, style) {
    var pre = document.createElement("pre");
    pre.className = cls;
    pre.textContent = text;
    Object.keys(style).forEach(function (k) { pre.style[k] = style[k]; });
    return pre;
  }

  function framePart(cls, W, H, c, r, ls, lh) {
    var part = document.createElement("div");
    part.className = "fl " + cls;
    part.style.letterSpacing = ls + "px";
    part.style.lineHeight = lh + "px";
    var side = new Array(Math.max(1, r - 2)).fill(look.frame[2]).join("\n");
    var sideH = (H - 2 * lh) + "px";
    part.appendChild(makePre("t", look.frame[0].repeat(c), { left: "0", top: "0", width: W + "px" }));
    part.appendChild(makePre("b", look.frame[1].repeat(c), { left: "0", bottom: "0", width: W + "px" }));
    part.appendChild(makePre("l", side, { left: "0", top: lh + "px", height: sideH }));
    part.appendChild(makePre("r", side, { right: (-ls) + "px", top: lh + "px", height: sideH }));
    return part;
  }

  function buildFrames() {
    var probe = document.createElement("span");
    probe.style.cssText = "position:absolute;left:-9999px;visibility:hidden;font:600 10px 'JetBrains Mono',monospace;white-space:pre;line-height:1";
    probe.textContent = "█".repeat(20);
    document.body.appendChild(probe);
    var cw = probe.getBoundingClientRect().width / 20 || 6;
    probe.remove();
    document.querySelectorAll(".pxb").forEach(function (el) {
      var old = el.querySelector(":scope > .fbx");
      if (old) old.remove();
      var iv = parseFloat(getComputedStyle(el).getPropertyValue("--fi"));
      var inset = isNaN(iv) ? 0 : iv;
      var W = el.clientWidth - inset * 2, H = el.clientHeight - inset * 2;
      if (W < 60 || H < 60) return;
      var c = Math.max(6, Math.round(W / cw)), r = Math.max(5, Math.round(H / 10));
      var ls = (W - c * cw) / c, lh = H / r;
      var box = document.createElement("div");
      box.className = "fbx";
      box.setAttribute("aria-hidden", "true");
      ["shd", "base", "shine", "lit"].forEach(function (cls) { box.appendChild(framePart(cls, W, H, c, r, ls, lh)); });
      el.appendChild(box);
    });
  }

  function setupFrames() {
    var timer = 0;
    var later = function () { clearTimeout(timer); timer = setTimeout(buildFrames, 120); };
    window.addEventListener("resize", later);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(buildFrames);
    setTimeout(buildFrames, 250);
    setTimeout(buildFrames, 1400);
    if (window.ResizeObserver) {
      var ro = new ResizeObserver(later);
      document.querySelectorAll(".pxb").forEach(function (el) { ro.observe(el); });
    }
    document.querySelectorAll(".guard img").forEach(function (im) { im.addEventListener("load", later); });
  }

  function fitFigures() {
    document.querySelectorAll(".figbox").forEach(function (box) {
      var pres = box.querySelectorAll(".fig");
      var first = pres[0];
      if (!first) return;
      if (!first.dataset.size) pres.forEach(function (p) { p.dataset.size = parseFloat(getComputedStyle(p).fontSize); });
      pres.forEach(function (p) { p.style.fontSize = p.dataset.size + "px"; });
      var avail = box.parentElement.clientWidth;
      var need = first.scrollWidth;
      if (need > avail && avail > 0) pres.forEach(function (p) { p.style.fontSize = (p.dataset.size * avail / need) + "px"; });
    });
  }

  function setupTips() {
    var tip = document.getElementById("ccf");
    if (!tip) return;
    var grid = tip.querySelector(".px16");
    var text = tip.querySelector("p");
    var pos = { tx: 0, ty: 0, x: 0, y: 0, raf: 0 };
    for (var i = 0; i < 128; i++) grid.appendChild(document.createElement("i"));
    var cells = grid.children;
    var paint = function (key) {
      var rows = PATTERNS[key] || [];
      for (var k = 0; k < 128; k++) {
        var row = rows[Math.floor(k / 16)] || "";
        cells[k].className = row.charAt(k % 16) === "#" ? "l" : "";
      }
    };
    var loop = function () {
      pos.x += (pos.tx - pos.x) * 0.2;
      pos.y += (pos.ty - pos.y) * 0.2;
      tip.style.transform = "translate3d(" + pos.x + "px," + pos.y + "px,0)";
      pos.raf = tip.classList.contains("show") ? requestAnimationFrame(loop) : 0;
    };
    var open = function (el, x, y) {
      paint(el.dataset.v);
      text.textContent = el.dataset.tip;
      pos.tx = pos.x = Math.max(8, x - 125);
      pos.ty = pos.y = y + 22;
      tip.classList.add("show");
      if (!pos.raf) pos.raf = requestAnimationFrame(loop);
    };
    document.querySelectorAll(".cc").forEach(function (el) {
      el.setAttribute("tabindex", "0");
      el.setAttribute("aria-description", el.dataset.tip);
      el.addEventListener("focus", function () { var r = el.getBoundingClientRect(); open(el, r.left, r.bottom); });
      el.addEventListener("blur", function () { tip.classList.remove("show"); });
    });
    document.addEventListener("pointerover", function (e) {
      var t = e.target.closest && e.target.closest(".cc");
      if (t) open(t, e.clientX, e.clientY);
    });
    document.addEventListener("pointermove", function (e) {
      if (!tip.classList.contains("show")) return;
      pos.tx = Math.min(window.innerWidth - 262, Math.max(8, e.clientX - 125));
      pos.ty = e.clientY + 22 > window.innerHeight - 220 ? e.clientY - 220 : e.clientY + 22;
    }, { passive: true });
    document.addEventListener("pointerout", function (e) {
      if (e.target.closest && e.target.closest(".cc")) tip.classList.remove("show");
    });
  }

  function setupBars() {
    var bars = document.getElementById("bars");
    if (!bars) return;
    bars.querySelectorAll(".pxbar").forEach(function (bar) {
      var on = Math.round(parseFloat(bar.dataset.pct) * 40 / 100);
      for (var i = 0; i < 120; i++) {
        var col = Math.floor(i / 3), row = i % 3;
        var cell = document.createElement("i");
        if (col < on) { cell.className = "on"; cell.dataset.k = col + row * 0.25; }
        bar.appendChild(cell);
      }
    });
    var running = false, raf = 0;
    var start = function () {
      var t0 = performance.now();
      var cells = Array.prototype.slice.call(bars.querySelectorAll("i.on"));
      cells.forEach(function (c) { c.classList.remove("f"); });
      cancelAnimationFrame(raf);
      var tick = function (now) {
        if (!running) return;
        var elapsed = now - t0, left = 0;
        cells.forEach(function (c) {
          if (c.classList.contains("f")) return;
          if (parseFloat(c.dataset.k) * 34 <= elapsed) c.classList.add("f"); else left++;
        });
        if (left > 0) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    };
    var check = function () {
      var r = bars.getBoundingClientRect(), vh = window.innerHeight;
      var inView = r.top < vh * 0.78 && r.bottom > vh * 0.22;
      if (inView && !running) { running = true; start(); }
      else if (!inView && running && (r.bottom < 0 || r.top > vh)) {
        running = false;
        cancelAnimationFrame(raf);
        bars.querySelectorAll("i.on").forEach(function (c) { c.classList.remove("f"); });
      }
    };
    window.addEventListener("scroll", check, { passive: true });
    setTimeout(check, 400);
  }

  function colorOf(cs, name) {
    var s = cs.getPropertyValue(name).trim();
    if (s[0] === "#") {
      if (s.length === 4) s = "#" + s[1] + s[1] + s[2] + s[2] + s[3] + s[3];
      return [parseInt(s.slice(1, 3), 16), parseInt(s.slice(3, 5), 16), parseInt(s.slice(5, 7), 16)];
    }
    var m = s.match(/\d+/g);
    return m ? m.slice(0, 3).map(Number) : [0, 0, 0];
  }
  function lerp(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
  function rgb(c) { return "rgb(" + Math.round(c[0]) + "," + Math.round(c[1]) + "," + Math.round(c[2]) + ")"; }
  function mix(a, b, t) { return rgb(lerp(a, b, t)); }

  function setupWaveGrid(cv) {
    var ctx = cv.getContext("2d");
    var cell = look.cell, SPEED = look.speed, FREQ = look.freq, WIDTH = look.width, FADE = look.fade, LIFT = look.lift;
    var MAXP = 96, SPACING = 5, COOL = 10000, LIGHT_AMP = 0.12, LIGHT_GAP = 160, LIGHT_SPACING = 30;
    var trail = [];
    var cols = 0, rows = 0, w = 0, ht = 0, colors, frame = 0, last = 0, dirty = true, field, total;
    var lastPt = null, strongAt = -1e9, lightAt = 0, tilt = 0, olw = 0;
    var read = function () {
      var cs = getComputedStyle(root);
      colors = { bg: colorOf(cs, "--bg"), fg: colorOf(cs, "--fg"), panel: colorOf(cs, "--panel"), line: colorOf(cs, "--line"), acc: colorOf(cs, "--acc") };
      olw = parseFloat(cs.getPropertyValue("--olw")) || 0;
    };
    var size = function () {
      var r = cv.parentElement.getBoundingClientRect();
      var dpr = Math.min(2, window.devicePixelRatio || 1);
      w = r.width; ht = r.height;
      cv.width = Math.max(1, w * dpr); cv.height = Math.max(1, ht * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cols = Math.ceil(w / cell) + 2; rows = Math.ceil(ht / cell) + 2;
      field = new Float32Array(cols * rows);
    };
    var heights = function () {
      field.fill(0);
      if (!trail.length) return;
      if (!total || total.length !== field.length) total = new Float32Array(field.length);
      total.fill(0);
      for (var k = 0; k < trail.length; k++) {
        var pt = trail[k];
        var front = SPEED * pt.age;
        var fade = Math.exp(-pt.age / FADE);
        if (fade < 0.02) continue;
        var r1 = front + WIDTH * 2.6, r0 = Math.max(0, front - WIDTH * 2.6);
        var x0 = Math.max(0, Math.floor(pt.x - r1)), x1 = Math.min(cols - 1, Math.ceil(pt.x + r1));
        var y0 = Math.max(0, Math.floor(pt.y - r1)), y1 = Math.min(rows - 1, Math.ceil(pt.y + r1));
        for (var y = y0; y <= y1; y++) for (var x = x0; x <= x1; x++) {
          var dx = x - pt.x, dy = y - pt.y;
          var dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < r0 || dist > r1) continue;
          var rel = dist - front;
          var wt = pt.amp * fade * Math.exp(-(rel * rel) / (WIDTH * WIDTH)) / (1 + dist * 0.08);
          var i = y * cols + x;
          field[i] += wt * Math.cos(FREQ * rel);
          total[i] += wt;
        }
      }
      for (var j = 0; j < field.length; j++) field[j] /= Math.max(total[j], 1);
    };
    var quad = function (a1, a2, a3, a4) {
      ctx.beginPath(); ctx.moveTo(a1[0], a1[1]); ctx.lineTo(a2[0], a2[1]); ctx.lineTo(a3[0], a3[1]); ctx.lineTo(a4[0], a4[1]); ctx.closePath();
    };
    var draw = function () {
      ctx.clearRect(0, 0, w, ht);
      var gap = mix(colors.bg, colors.line, 0.55);
      var sz = cell - 2;
      var x, y, px, py;
      for (y = 1; y < rows - 1; y++) for (x = 1; x < cols - 1; x++) {
        px = (x - 1) * cell + 1; py = (y - 1) * cell + 1;
        ctx.fillStyle = gap; ctx.fillRect(px, py, sz, sz);
        ctx.fillStyle = mix(colors.panel, colors.fg, 0.04); ctx.fillRect(px, py, sz, sz);
      }
      var deep = function (t) { return mix(lerp(colors.bg, colors.acc, 0.5), colors.acc, t); };
      for (y = 1; y < rows - 1; y++) for (x = 1; x < cols - 1; x++) {
        var v = field[y * cols + x];
        if (v < 0.05) continue;
        var t = Math.min(1, v * 3);
        var lift = v * LIFT;
        px = (x - 1) * cell + 1; py = (y - 1) * cell + 1;
        var tx = px - lift * (0.3 - tilt * 0.25), ty = py - lift;
        ctx.fillStyle = mix(lerp(colors.bg, colors.acc, 0.2), colors.acc, t * 0.8);
        ctx.fillRect(px - 1, py - 1, sz + 2, sz + 2);
        ctx.lineJoin = "round";
        ctx.lineWidth = olw ? Math.min(olw, 2.5) : 0;
        ctx.strokeStyle = "#000";
        ctx.fillStyle = deep(t);
        quad([tx, ty + sz], [tx + sz, ty + sz], [px + sz, py + sz], [px, py + sz]); ctx.fill(); if (olw) ctx.stroke();
        ctx.fillStyle = mix(lerp(colors.bg, colors.acc, 0.35), colors.acc, t * 0.85);
        quad([tx + sz, ty], [tx + sz, ty + sz], [px + sz, py + sz], [px + sz, py]); ctx.fill(); if (olw) ctx.stroke();
        ctx.fillStyle = mix(colors.panel, colors.fg, 0.1 + 0.16 * t);
        ctx.fillRect(tx, ty, sz, sz);
      }
    };
    var loop = function (ts) {
      requestAnimationFrame(loop);
      if (document.hidden || themeBusy) return;
      var dt = Math.min(0.05, (ts - last) / 1000);
      if (ts - last < 24) return;
      last = ts;
      var themeCheck = false;
      if (frame++ % 40 === 0) { read(); themeCheck = true; }
      if (!trail.length && !dirty && !themeCheck) return;
      for (var k = trail.length - 1; k >= 0; k--) { trail[k].age += dt; if (trail[k].age > FADE * 4) trail.splice(k, 1); }
      heights(); draw();
      dirty = trail.length > 0;
    };
    var addPoint = function (px, py, amp) {
      if (trail.length >= MAXP) trail.shift();
      trail.push({ x: px / cell + 1, y: py / cell + 1, age: 0, amp: amp });
    };
    var onMove = function (e) {
      if (themeBusy) return;
      var r = cv.getBoundingClientRect();
      var px = e.clientX - r.left, py = e.clientY - r.top;
      if (px < 0 || py < 0 || px > r.width || py > r.height) { lastPt = null; return; }
      tilt = Math.max(-1, Math.min(1, (px / r.width - 0.5) * 2));
      var now = performance.now();
      var dist = lastPt ? Math.hypot(px - lastPt.x, py - lastPt.y) : 1e9;
      if (now - strongAt > COOL) {
        if (dist < SPACING) return;
        strongAt = now; lightAt = now; lastPt = { x: px, y: py };
        addPoint(px, py, 1);
      } else {
        if (now - lightAt < LIGHT_GAP || dist < LIGHT_SPACING) return;
        lightAt = now; lastPt = { x: px, y: py };
        addPoint(px, py, LIGHT_AMP);
      }
      dirty = true;
    };
    read(); size(); heights(); draw();
    wave.wake = function () { dirty = true; };
    wave.refresh = function () { read(); heights(); draw(); dirty = trail.length > 0; };
    document.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerdown", onMove, { passive: true });
    window.addEventListener("resize", function () { size(); dirty = true; });
    if (!reduce) requestAnimationFrame(loop);
  }

  function setupWaveDots(cv) {
    var ctx = cv.getContext("2d");
    var gap = 28, reach = 200;
    var w = 0, ht = 0, colors, olw = 0, px = -9999, py = -9999, power = 0, want = 0, lastMove = 0, frame = 0, dirty = true;
    var read = function () {
      var cs = getComputedStyle(root);
      colors = { line: colorOf(cs, "--line"), acc: colorOf(cs, "--acc") };
      olw = parseFloat(cs.getPropertyValue("--olw")) || 0;
    };
    var size = function () {
      var r = cv.parentElement.getBoundingClientRect();
      var dpr = Math.min(2, window.devicePixelRatio || 1);
      w = r.width; ht = r.height;
      cv.width = Math.max(1, w * dpr); cv.height = Math.max(1, ht * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    var draw = function () {
      ctx.clearRect(0, 0, w, ht);
      var cols = Math.ceil(w / gap), rows = Math.ceil(ht / gap);
      for (var r = 0; r < rows; r++) for (var c = 0; c < cols; c++) {
        var x = c * gap + gap / 2, y = r * gap + gap / 2;
        var dx = px - x, dy = py - y, d = Math.hypot(dx, dy);
        var f = power * Math.max(0, 1 - d / reach);
        var ox = d > 0 ? dx / d * f * 9 : 0, oy = d > 0 ? dy / d * f * 9 : 0;
        ctx.fillStyle = f > 0.02 ? mix(colors.line, colors.acc, Math.min(1, f * 1.5)) : rgb(colors.line);
        ctx.beginPath(); ctx.arc(x + ox, y + oy, 1.6 + f * 5, 0, 6.2832); ctx.fill();
        if (olw && f > 0.3) { ctx.lineWidth = 1; ctx.strokeStyle = "#000"; ctx.stroke(); }
      }
    };
    var loop = function (ts) {
      requestAnimationFrame(loop);
      if (document.hidden || themeBusy) return;
      if (frame++ % 40 === 0) { read(); dirty = true; }
      want = (ts - lastMove < 700) ? 1 : 0;
      var next = power + (want - power) * 0.12;
      var changed = Math.abs(next - power) > 0.002 || dirty;
      power = Math.abs(next - want) < 0.004 ? want : next;
      if (changed) { draw(); dirty = false; }
    };
    read(); size(); draw();
    wave.wake = function () { dirty = true; };
    wave.refresh = function () { read(); draw(); };
    document.addEventListener("pointermove", function (e) {
      if (themeBusy) return;
      var r = cv.getBoundingClientRect();
      px = e.clientX - r.left; py = e.clientY - r.top;
      lastMove = performance.now();
    }, { passive: true });
    window.addEventListener("resize", function () { size(); dirty = true; });
    if (!reduce) requestAnimationFrame(loop);
  }

  function setupWave() {
    var cv = document.getElementById("wave");
    if (!cv) return;
    if (look.wave === "dots") setupWaveDots(cv); else setupWaveGrid(cv);
  }

  startTheme();
  setupThemeButtons();
  setupReveal();
  setupRipple();
  setupPointer();
  setupTips();
  setupBars();
  setupFrames();
  setupSmoothScroll();
  setupWave();
  fitFigures();
  window.addEventListener("resize", fitFigures);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitFigures);
  window.addEventListener("scroll", slideCards, { passive: true });
  window.addEventListener("scroll", navState, { passive: true });
  window.addEventListener("resize", placeAmbient);
  slideCards();
  placeAmbient();
  navState();
  setTimeout(revealNow, 300);
})();

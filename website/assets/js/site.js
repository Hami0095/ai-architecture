/* ArchAI website: renders content from data.js, plays terminal demos, and runs the
   halftone, reveal and marquee animations. Vanilla JS, no dependencies. */
(function () {
  "use strict";

  const D = window.ARCHAI;
  const T = window.ARCHAI_TRANSCRIPTS || {};
  const META = window.ARCHAI_TRANSCRIPTS_META || {};
  // ?static renders the final state without motion (used for mockup screenshots).
  const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches || /[?&]static(?:[=&]|$)/.test(location.search);
  if (REDUCED) document.documentElement.classList.add("static");
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const agentById = (id) => D.agents.find((a) => a.id === id);
  const familyById = (id) => D.families.find((f) => f.id === id);
  const icon = (id, size = 28) => `<img class="agent-icon" src="assets/icons/${id}.svg" width="${size}" height="${size}" alt="">`;
  const badge = (familyId) => `<img class="family-badge" src="assets/icons/family-${familyId}.svg" height="22" alt="${esc(familyById(familyId).name)} family">`;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  /* ---- Facts parsed from real transcripts (never hand-typed) ------------- */
  const facts = (() => {
    const out = { modules: null, edges: null, rules: [], findings: [], evidence: [] };
    const check = T.check ? T.check.stdout : [];
    for (const line of check) {
      const g = line.match(/Graph: (\d+) modules, (\d+) import edges/);
      if (g) { out.modules = +g[1]; out.edges = +g[2]; }
      const r = line.match(/^ (VIOLATION|PASS|RISK|NO-EVIDENCE)\s+(\S+)\s+(\S+)\s+(\d+)\s*$/);
      if (r) out.rules.push({ outcome: r[1], id: r[2], findings: +r[4] });
      const f = line.match(/(F-[0-9a-f]{12})/);
      if (f && !out.findings.includes(f[1])) out.findings.push(f[1]);
    }
    for (const line of (T.finding ? T.finding.stdout : [])) {
      const e = line.match(/^ \* (ai_architect\/[\w/]+\.py:\d+) \(import_statement\): `([^`]+?)\s+\[scope/);
      if (e) out.evidence.push({ where: e[1], stmt: e[2] });
    }
    out.receipts = out.rules.reduce((n, r) => n + r.findings, 0);
    return out;
  })();

  /* ---- Navigation ------------------------------------------------------- */
  function nav() {
    const bar = $(".nav");
    if (bar) {
      const onScroll = () => bar.classList.toggle("scrolled", window.scrollY > 8);
      onScroll();
      window.addEventListener("scroll", onScroll, { passive: true });
    }
    const toggle = $(".nav-toggle");
    if (toggle) toggle.addEventListener("click", () => {
      const links = $(".nav-links");
      const open = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    const page = document.body.dataset.page;
    $$(".nav-links a[data-page]").forEach((a) => { if (a.dataset.page === page) a.setAttribute("aria-current", "page"); });
  }

  /* ---- Headline word reveal --------------------------------------------- */
  function splitHeadlines() {
    $$("[data-split]").forEach((el) => {
      const words = el.innerHTML.split(/(\s+|<[^>]+>)/).filter((w) => w.length);
      let i = 0, html = "";
      for (const w of words) {
        if (/^\s+$/.test(w) || /^</.test(w)) { html += w; continue; }
        html += `<span class="word" style="animation-delay:${(i++ * 0.07).toFixed(2)}s">${w}</span>`;
      }
      el.innerHTML = html;
    });
  }

  /* ---- Scroll reveal ---------------------------------------------------- */
  function reveal() {
    const items = $$(".reveal");
    if (REDUCED || !("IntersectionObserver" in window)) { items.forEach((el) => el.classList.add("in")); return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { threshold: 0.12 });
    items.forEach((el) => io.observe(el));
  }

  /* ---- Animated halftone dot field (dithered, drifting, pauses offscreen) */
  function halftone(canvas) {
    const ctx = canvas.getContext("2d");
    const bayer = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => (v + 0.5) / 16);
    const blobs = [
      { x: 0.12, y: 0.3, r: 0.28, vx: 0.012, vy: 0.008 },
      { x: 0.86, y: 0.25, r: 0.24, vx: -0.01, vy: 0.012 },
      { x: 0.55, y: 0.95, r: 0.3, vx: 0.008, vy: -0.01 },
      { x: 0.35, y: 0.1, r: 0.16, vx: -0.006, vy: 0.009 },
    ];
    const cell = 5;
    let w = 0, h = 0, running = false, last = 0, t = 0;
    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth; h = canvas.clientHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    function draw() {
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#141414";
      const aspect = w / Math.max(h, 1);
      for (let y = 0, j = 0; y < h; y += cell, j++) {
        for (let x = 0, i = 0; x < w; x += cell, i++) {
          const nx = x / w, ny = y / h;
          let v = 0;
          for (const b of blobs) {
            const dx = (nx - b.x) * aspect, dy = ny - b.y;
            const d = Math.sqrt(dx * dx + dy * dy) / b.r;
            if (d < 1) v = Math.max(v, Math.pow(1 - d, 1.25));
          }
          v += 0.05 * Math.sin(nx * 18 + t * 0.6) * Math.cos(ny * 14 - t * 0.4);
          if (v > bayer[(j % 4) * 4 + (i % 4)]) ctx.fillRect(x, y, 2, 2);
        }
      }
    }
    function step(now) {
      if (!running) return;
      const dt = Math.min((now - last) / 1000, 0.05); last = now; t += dt;
      for (const b of blobs) {
        b.x += b.vx * dt; b.y += b.vy * dt;
        if (b.x < -0.1 || b.x > 1.1) b.vx *= -1;
        if (b.y < -0.1 || b.y > 1.1) b.vy *= -1;
      }
      draw();
      requestAnimationFrame(step);
    }
    resize(); draw();
    window.addEventListener("resize", () => { resize(); draw(); });
    if (REDUCED || !("IntersectionObserver" in window)) return;
    new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !running) { running = true; last = performance.now(); requestAnimationFrame(step); }
      else if (!e.isIntersecting) running = false;
    }).observe(canvas);
  }

  /* ---- Terminal demos --------------------------------------------------- */
  function colorize(line) {
    let s = esc(line);
    if (/^\s*==/.test(line)) return `<span class="o">${s}</span>`;
    s = s.replace(/\b(VERIFIED_VIOLATION|VERIFIED VIOLATION|VIOLATION)\b/g, '<span class="o">$1</span>')
         .replace(/\b(PASS)\b/g, '<span class="ok">$1</span>')
         .replace(/\b(POTENTIAL_RISK|RISK)\b/g, '<span class="rk">$1</span>')
         .replace(/\b(INSUFFICIENT_GRAPH_EVIDENCE|NO-EVIDENCE)\b/g, '<span class="gp">$1</span>')
         .replace(/(F-[0-9a-f]{12})/g, '<span class="c">$1</span>')
         .replace(/([\w./-]+\.py:\d+)/g, '<span class="c">$1</span>');
    return s;
  }

  function demoFor(spec) {
    // Returns { title, command, pre: [lines], spinner, lines: [lines], illustrative, note }
    if (spec.transcript) {
      const t = T[spec.transcript];
      if (!t) return null;
      return { command: t.command, pre: t.stderr.map((l) => ({ text: l, dim: true })), lines: t.stdout,
               illustrative: false, note: spec.note };
    }
    const agent = agentById(spec.agent);
    const d = agent.demo;
    if (d.transcript) return demoFor(d);
    return { command: d.command, pre: (d.before || []).map((l) => ({ text: l })), spinner: d.spinner,
             lines: d.lines, illustrative: true, note: d.note };
  }

  function terminal(el) {
    const spec = el.dataset.agent ? { agent: el.dataset.agent } : { transcript: el.dataset.transcript };
    const agent = el.dataset.agent ? agentById(el.dataset.agent) : null;
    const demo = demoFor(agent && agent.demo.transcript ? agent.demo : spec);
    if (!demo) { el.remove(); return; }
    const title = el.dataset.title || (agent ? `${agent.name.toUpperCase()} · ${agent.command.split(" ")[0]}` : "TERMINAL");
    el.classList.add("term", "win");
    if (demo.illustrative) el.classList.add("illus");
    el.innerHTML = `
      <div class="win-title"><span class="name">${esc(title)}</span>
        <span class="term-actions">
          ${demo.illustrative ? '<span class="illus-tag">ILLUSTRATIVE</span>' : '<span class="real-tag">REAL OUTPUT</span>'}
          <button type="button" data-act="copy" aria-label="Copy command">copy</button>
          <button type="button" data-act="replay" aria-label="Replay demo">replay</button>
        </span></div>
      <pre tabindex="0" aria-label="${esc(demo.command)}"></pre>
      <div class="term-foot">${demo.illustrative
        ? "Illustrative: AI output varies."
        : `Real output, captured at commit ${esc(META.commit || "?")} by scripts/capture_website_transcripts.py.`}${
        demo.note ? " " + esc(demo.note) : ""}</div>`;
    const pre = $("pre", el);
    let run = 0;

    async function play() {
      const id = ++run;
      const alive = () => id === run;
      pre.innerHTML = "";
      const add = (html) => { pre.insertAdjacentHTML("beforeend", html + "\n"); pre.scrollTop = pre.scrollHeight; };
      if (REDUCED) {
        add(`<span class="p">$</span> <span class="c">${esc(demo.command)}</span>`);
        demo.pre.forEach((l) => add(l.dim ? `<span class="d">${esc(l.text)}</span>` : colorize(l.text)));
        demo.lines.forEach((l) => add(colorize(l)));
        pre.scrollTop = 0;
        return;
      }
      // typed command
      const line = document.createElement("span");
      line.innerHTML = `<span class="p">$</span> <span class="c"></span><span class="cursor"></span>`;
      pre.appendChild(line);
      const cmdSpan = $(".c", line);
      const perChar = Math.max(8, Math.min(28, 1100 / demo.command.length));
      for (const ch of demo.command) {
        if (!alive()) return;
        cmdSpan.textContent += ch;
        await sleep(perChar);
      }
      $(".cursor", line).remove();
      pre.insertAdjacentText("beforeend", "\n");
      await sleep(250);
      for (const l of demo.pre) {
        if (!alive()) return;
        add(l.dim ? `<span class="d">${esc(l.text)}</span>` : colorize(l.text));
        await sleep(120);
      }
      if (demo.spinner) {
        const frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏";
        const sp = document.createElement("span");
        pre.appendChild(sp);
        const start = performance.now();
        for (let i = 0; performance.now() - start < 1800; i++) {
          if (!alive()) return;
          const secs = ((performance.now() - start) / 1000).toFixed(1).padStart(4);
          sp.innerHTML = `  <span class="o">${frames[i % frames.length]}</span> ${esc(demo.spinner)}<span class="d">  ${secs}s</span>`;
          await sleep(80);
        }
        sp.remove();
      }
      const per = Math.max(10, Math.min(45, 2200 / Math.max(demo.lines.length, 1)));
      for (const l of demo.lines) {
        if (!alive()) return;
        add(colorize(l));
        await sleep(per);
      }
      pre.insertAdjacentHTML("beforeend", `<span class="p">$</span> <span class="cursor"></span>`);
    }

    el.addEventListener("click", (e) => {
      const act = e.target.closest("button") && e.target.closest("button").dataset.act;
      if (act === "replay") play();
      if (act === "copy") copy(demo.command, e.target.closest("button"));
    });
    if (REDUCED || !("IntersectionObserver" in window)) { play(); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { io.disconnect(); play(); } }, { threshold: 0.3 });
    io.observe(el);
  }

  function copy(text, button) {
    const done = () => { if (button) { const old = button.textContent; button.textContent = "copied"; setTimeout(() => (button.textContent = old), 1200); } };
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, () => {});
  }

  /* ---- Renderers -------------------------------------------------------- */
  const renderers = {
    outcomes(el) {
      el.innerHTML = D.outcomes.map((o, i) => `
        <article class="card outcome reveal d${i % 4}">
          <div class="win-title"><span class="name">0${i + 1}</span><span class="outcome-icons">${o.agents.map((id) => icon(id, 18)).join("")}</span></div>
          <div class="win-body">
            <h3>${esc(o.title)}</h3>
            <dl>
              <dt>You get</dt><dd>${esc(o.gives)}</dd>
              <dt>You provide</dt><dd>${esc(o.needs)}</dd>
            </dl>
            <code class="outcome-cmd" tabindex="0" data-copy="${esc(o.cmd)}" title="Click to copy">${esc(o.cmd)}</code>
          </div>
        </article>`).join("");
    },

    requirements(el) {
      const R = D.requirements;
      const list = (items) => items.map((r) => `<li><b>${esc(r.what)}</b><span>${esc(r.why)}</span></li>`).join("");
      el.innerHTML = `
        <div class="win req reveal"><div class="win-title"><span class="name">REQUIRED</span><span class="ctrl"></span></div>
          <div class="win-body"><ul class="req-list">${list(R.needs)}</ul></div></div>
        <div class="win req reveal d1"><div class="win-title"><span class="name">ONLY IF YOU WANT IT</span><span class="ctrl"></span></div>
          <div class="win-body"><ul class="req-list">${list(R.optional)}</ul></div></div>
        <div class="win req req-not reveal d2"><div class="win-title"><span class="name">NOT NEEDED</span><span class="ctrl"></span></div>
          <div class="win-body"><ul class="req-list">${R.notNeeded.map((t) => `<li><span>${esc(t)}</span></li>`).join("")}</ul></div></div>`;
    },

    quickstart(el) {
      el.innerHTML = D.quickstart.map((q, i) => `
        <li class="reveal d${i % 4}"><span class="qs-n">${i + 1}</span><div><b>${esc(q.step)}</b>
          <code tabindex="0" data-copy="${esc(q.cmd)}" title="Click to copy">${esc(q.cmd)}</code></div></li>`).join("");
    },

    "ai-agents"(el) {
      const A = D.aiAgents;
      el.innerHTML = `
        <div class="ai-copy reveal">
          <p class="label">Works with ${A.clients.map(esc).join(" · ")}</p>
          <h2 class="big">Your AI Agent, With Receipts.</h2>
          <ul class="ai-points">${A.points.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>
          <p class="ai-setup"><code tabindex="0" data-copy="${esc(A.setup)}" title="Click to copy">${esc(A.setup)}</code></p>
          <p class="doclink"><a href="${esc(A.docs)}">Set up Claude Code or Codex →</a></p>
        </div>
        <div class="win ai-tools reveal d1"><div class="win-title"><span class="name">MCP · ${A.toolCount} TOOLS</span><span class="ctrl"></span></div>
          <div class="win-body">${D.agents.filter((a) => a.mcp && a.mcp.length).map((a) => `
            <div class="tool-row">${icon(a.id, 20)}<b>${esc(a.name)}</b><span>${a.mcp.map((t) => `<code>${esc(t)}</code>`).join(" ")}</span></div>`).join("")}
          </div></div>`;
    },

    "whats-new"(el) {
      el.innerHTML = D.whatsNew.map((n, i) => `
        <li class="reveal d${i % 4}"><span class="new-date">${esc(n.date)}</span>
          <div><a href="${esc(n.link)}"><b>${esc(n.title)}</b></a><p>${esc(n.text)}</p></div></li>`).join("");
    },

    marquee(el) {
      const items = D.agents.map((a) => `<span>${esc(a.name.toUpperCase())} <b>${esc(a.command.split(" ")[0])}</b></span>`).join("");
      el.innerHTML = `<div class="track" aria-hidden="true">${items}${items}</div><span class="sr-only">ArchAI agents: ${D.agents.map((a) => a.name).join(", ")}</span>`;
    },

    ticker(el) {
      const ids = facts.findings.concat(facts.evidence.map((e) => e.where)).join("  ·  ");
      el.innerHTML = `<span>${esc(ids)}  ·  ${esc(ids)}</span>`;
    },

    statuses(el) {
      el.innerHTML = D.statuses.map((s, i) => `
        <div class="card status-card reveal d${i % 4}">
          <div class="win-title"><span class="name">${esc(s.short)}</span><span class="ctrl"></span></div>
          <div class="win-body"><code class="mono status-id st-${s.short.toLowerCase()}">${esc(s.id)}</code><p>${esc(s.text)}</p></div>
        </div>`).join("");
    },

    families(el) {
      el.innerHTML = D.families.map((f, i) => {
        const agents = D.agents.filter((a) => a.family === f.id);
        return `
        <a class="card family-card fam-${f.id} reveal d${i % 4}" href="agents.html#family-${f.id}">
          <div class="win-title"><span class="name">${esc(f.name.toUpperCase())}</span><span class="ctrl"></span></div>
          <div class="win-body">
            ${badge(f.id)}
            <h3>${esc(f.promise)}</h3>
            <p>${esc(f.blurb)}</p>
            <ul class="agent-chips">${agents.map((a) => `<li>${icon(a.id, 24)}<span><b>${esc(a.name)}</b>${a.hero ? ' <em class="hero-tag">hero</em>' : ""}<small>${esc(a.role)}</small></span></li>`).join("")}</ul>
            <span class="more">Meet the ${esc(f.name)} agents →</span>
          </div></a>`;
      }).join("");
    },

    arc(el) {
      el.innerHTML = D.storyArc.map((s, i) => {
        const a = agentById(s.agent);
        return `<div class="arc-step reveal d${i}">${icon(a.id, 40)}<b>${esc(a.name)}</b><span>${esc(s.verb)}</span></div>`;
      }).join('<div class="arc-arrow" aria-hidden="true">→</div>');
    },

    desk(el) {
      const ruleRows = facts.rules.map((r) => `
        <div class="stat-row"><span>${esc(r.id)}</span><span class="st-${r.outcome.toLowerCase()}">${esc(r.outcome)}</span></div>`).join("");
      const ev = facts.evidence.slice(0, 5).map((e) => `<div class="stat-row"><span>${esc(e.where)}</span></div>`).join("");
      const maxv = Math.max(facts.modules || 1, facts.edges || 1);
      $(".w1 .win-body", el).innerHTML = `
        <div class="stat-row"><span>modules</span><b data-count="${facts.modules}">0</b></div>
        <div class="bar"><i style="--w:${(100 * (facts.modules || 0) / maxv).toFixed(0)}%"></i></div>
        <div class="stat-row"><span>import edges</span><b data-count="${facts.edges}">0</b></div>
        <div class="bar"><i style="--w:${(100 * (facts.edges || 0) / maxv).toFixed(0)}%"></i></div>
        <div class="stat-row"><span>LLM used</span><b>no</b></div>`;
      $(".w2 .win-body", el).innerHTML = ruleRows || "<div>no rules</div>";
      $(".w3 .win-body", el).innerHTML = `<div class="stat-row"><b>cli.py fan-out</b></div>${ev}<div class="stat-row d">… full receipt in Atlas</div>`;
      $(".w4 .win-body", el).innerHTML = `
        <div class="stat-row"><span>commit</span><b>${esc(META.commit || "?")}</b></div>
        <div class="stat-row"><span>captured</span><b>${esc((META.captured_at || "").slice(0, 10))}</b></div>
        <div class="stat-row"><span>clock</span><b data-clock>--:--:--</b></div>`;
    },

    numbers(el) {
      el.innerHTML = `<span data-count="${facts.modules}">0</span> modules.<br><span data-count="${facts.edges}">0</span> import edges.<br><span class="accent-ink"><span data-count="${facts.receipts}">0</span> receipts.</span>`;
    },

    pipeline(el) {
      const stages = [
        ["01", "Read", "Python's <code>ast</code> parses every file. Nothing is executed."],
        ["02", "Graph", "Imports become typed edges with line numbers and scope."],
        ["03", "Rules", "Your standards, evaluated as pure functions of the graph."],
        ["04", "Receipts", "Findings with file:line evidence, or an honest \"could not verify\"."],
        ["05", "Knowledge", "An Open Knowledge Format bundle that Atlas can browse anywhere."],
      ];
      el.innerHTML = `<div class="pulse" aria-hidden="true"></div>` + stages.map(([n, h, p], i) =>
        `<div class="stage reveal d${i % 4}"><span class="n">${n}</span><h4>${h}</h4><p>${p}</p></div>`).join("");
    },

    "research-teaser"(el) {
      const p = D.papers[0];
      el.innerHTML = paperCard(p, true);
    },

    filters(el) {
      const buttons = [{ id: "all", name: "All agents" }].concat(D.families);
      el.innerHTML = buttons.map((b, i) => `<button type="button" data-family="${b.id}" aria-pressed="${i === 0}">${esc(b.name)}</button>`).join("");
      el.addEventListener("click", (e) => {
        const btn = e.target.closest("button");
        if (!btn) return;
        $$("button", el).forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
        $$(".family-section").forEach((s) => { s.hidden = btn.dataset.family !== "all" && s.dataset.family !== btn.dataset.family; });
      });
    },

    decisions(el) {
      el.innerHTML = `<div class="row"><div>When you are…</div><div>Use</div></div>` + D.decisions.map((d) => `
        <div class="row"><div>${esc(d.situation)}</div><div>${d.agents.map((id) => {
          const a = agentById(id);
          return `<a href="#agent-${a.id}">${icon(a.id, 18)} ${esc(a.name)}</a>`;
        }).join(' <span aria-hidden="true">then</span> ')}</div></div>`).join("");
    },

    agents(el) {
      el.innerHTML = D.families.map((f) => {
        const agents = D.agents.filter((a) => a.family === f.id);
        return `
        <section class="family-section fam-${f.id}" id="family-${f.id}" data-family="${f.id}">
          <header class="family-head reveal">
            ${badge(f.id)}
            <h2 class="big">${esc(f.promise)}</h2>
            <p class="lede">${esc(f.blurb)}</p>
          </header>
          ${agents.map(agentBlock).join("")}
        </section>`;
      }).join("");
    },

    "case-studies"(el) {
      el.innerHTML = D.caseStudies.map((c) => `
        <article class="study" id="${esc(c.id)}">
          <aside class="meta reveal">
            <div class="study-agents">${c.agents.map((id) => `${icon(id, 40)}`).join("")}</div>
            ${c.agents.map((id) => { const a = agentById(id); return `<div class="kv"><b>${esc(a.name)}</b>${esc(a.command)}</div>`; }).join("")}
            ${c.measured ? `<div class="kv"><b>Measured at</b>${esc(c.measured.commit)}</div><div class="kv"><b>Date</b>${esc(c.measured.date)}</div>` : `<div class="kv"><b>Status</b>Case study, off by default</div>`}
          </aside>
          <div>
            <h2 class="reveal">${esc(c.title)}</h2>
            <p class="lede reveal">${esc(c.subtitle)}</p>
            <div class="facts reveal">${c.facts.map((f) => `<div><b>${esc(f.value)}</b><span>${esc(f.label)}</span></div>`).join("")}</div>
            ${c.sections.map((s) => `<h3>${esc(s.h)}</h3><div class="prose">${s.html}</div>`).join("")}
            <h3>Reproduce</h3>
            <pre class="syntax">${esc(c.reproduce)}</pre>
            <div class="study-demo reveal">${c.demo.transcript ? `<div data-transcript="${c.demo.transcript}" data-title="${esc(c.agents.map((id) => agentById(id).name.toUpperCase()).join(" + "))}"></div>` : `<div data-agent="${c.demo.agent}"></div>`}</div>
          </div>
        </article>`).join("") + `<div class="placeholder">More case studies are on the way. Each one names the commit it was measured at, so you can reproduce it.</div>`;
    },

    papers(el) {
      el.innerHTML = D.papers.map((p) => paperCard(p, false)).join("") +
        `<div class="placeholder">More papers will appear here as they are published.</div>`;
    },
  };

  function agentBlock(a) {
    const f = familyById(a.family);
    return `
      <article class="cmd agent-${a.family}" id="agent-${a.id}">
        <div class="reveal">
          <div class="agent-head">${icon(a.id, 56)}<div><span class="persona">${esc(f.name)} family · ${esc(a.nature)}</span>
          <h2>${esc(a.name)}${a.hero ? ' <em class="hero-tag">hero</em>' : ""}</h2>
          <span class="role">${esc(a.role)} · <code>${esc(a.command)}</code></span></div></div>
          <p>${esc(a.summary)}</p>
          ${a.gives ? `<div class="give-need">
            <div><h3>You get</h3><ul>${a.gives.map((g) => `<li>${esc(g)}</li>`).join("")}</ul></div>
            <div><h3>It needs</h3><ul>${a.needs.map((n) => `<li>${esc(n)}</li>`).join("")}</ul></div>
          </div>` : ""}
          <h3>When to use it</h3>
          <ul>${a.when.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>
          <h3>How to use it</h3>
          <pre class="syntax">${esc(a.syntax)}</pre>
          <ul class="examples">${a.examples.map((x) => `<li><code tabindex="0" data-copy="${esc(x.cmd)}" title="Click to copy">${esc(x.cmd)}</code>${x.note ? `<small>${esc(x.note)}</small>` : ""}</li>`).join("")}</ul>
          ${a.mcp && a.mcp.length ? `<h3>For AI agents (MCP)</h3><p class="mcp-tools">${a.mcp.map((t) => `<code>${esc(t)}</code>`).join(" ")}</p>` : ""}
          <p class="doclink"><a href="${esc(a.docs)}">Full reference in the docs →</a></p>
        </div>
        <div class="sticky"><div data-agent="${a.id}"></div></div>
      </article>`;
  }

  function paperCard(p, teaser) {
    return `
      <article class="paper win reveal" id="${esc(p.id)}">
        <div class="win-title"><span class="name">${esc(p.type.toUpperCase())} · ${esc(p.version)}</span><span class="ctrl"></span></div>
        <div class="win-body">
          <span class="label">${esc(p.date)} · DOI <a href="https://doi.org/${esc(p.doi)}">${esc(p.doi)}</a></span>
          <h2>${esc(p.title)}</h2>
          ${p.subtitle ? `<p class="paper-sub">${esc(p.subtitle)}</p>` : ""}
          <p class="authors">${p.authors.map(esc).join(", ")}</p>
          <p>${esc(p.summary)}</p>
          <div class="facts">${p.facts.map((f) => `<div><b>${esc(f.value)}</b><span>${esc(f.label)}</span></div>`).join("")}</div>
          ${teaser ? `<div class="actions"><a class="btn" href="research.html#${esc(p.id)}">Read about the paper</a><a class="btn ghost" href="${esc(p.url)}">Zenodo record</a></div>` : `
          <div class="chips">${p.keywords.map((k) => `<span class="badge">${esc(k)}</span>`).join("")}</div>
          <p class="label">License: ${esc(p.license)}</p>
          <div class="actions">${p.files.map((f) => `<a class="btn${f.name.startsWith("Paper") ? "" : " ghost"}" href="${esc(f.url)}">${esc(f.name)}</a>`).join("")}</div>
          <h3 class="label cite-h">Cite</h3>
          <div class="bib"><pre>${esc(p.bibtex)}</pre><button type="button" class="btn copy" data-copy-bib="${esc(p.id)}">Copy BibTeX</button></div>`}
        </div>
      </article>`;
  }

  /* ---- Counters and clock ---------------------------------------------- */
  function counters() {
    const items = $$("[data-count]");
    const run = (el) => {
      const target = +el.dataset.count;
      if (!Number.isFinite(target)) { el.textContent = "?"; return; }
      if (REDUCED) { el.textContent = target; return; }
      const start = performance.now();
      const tick = (now) => {
        const p = Math.min(1, (now - start) / 1200);
        el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };
    if (REDUCED || !("IntersectionObserver" in window)) items.forEach(run);
    else {
      const io = new IntersectionObserver((entries) => entries.forEach((e) => { if (e.isIntersecting) { run(e.target); io.unobserve(e.target); } }));
      items.forEach((el) => io.observe(el));
    }
    const clock = $("[data-clock]");
    if (clock) {
      const tick = () => { clock.textContent = new Date().toLocaleTimeString([], { hour12: false }); };
      tick(); setInterval(tick, 1000);
    }
  }

  /* ---- Copy handlers ---------------------------------------------------- */
  function copyHandlers() {
    document.addEventListener("click", (e) => {
      const code = e.target.closest("[data-copy]");
      if (code) { copy(code.dataset.copy); code.classList.add("copied"); setTimeout(() => code.classList.remove("copied"), 900); }
      const bib = e.target.closest("[data-copy-bib]");
      if (bib) copy(D.papers.find((p) => p.id === bib.dataset.copyBib).bibtex, bib);
    });
  }

  /* ---- Boot ------------------------------------------------------------- */
  document.addEventListener("DOMContentLoaded", () => {
    nav();
    $$("[data-render]").forEach((el) => renderers[el.dataset.render] && renderers[el.dataset.render](el));
    splitHeadlines();
    $$("canvas.halftone").forEach(halftone);
    $$("[data-agent], [data-transcript]").forEach(terminal);
    counters();
    copyHandlers();
    reveal();
    const year = $("[data-year]");
    if (year) year.textContent = new Date().getFullYear();
    if (location.hash) { const target = document.getElementById(location.hash.slice(1)); if (target) setTimeout(() => target.scrollIntoView(), 50); }
  });
})();

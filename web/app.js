// Sprinto Outbound CRM. Everything shown comes from scraped websites: render with textContent only, never innerHTML.
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const MANUAL_S = [900, 1200];   // 15-20 minutes by hand (case brief baseline)
const BAR = 60;                 // ICP qualify threshold (config/icp.yaml)
const TARGET = 7;               // reviewer score the drafter aims for (pipeline/compose.py MIN_REVIEW)
const STATE = { accounts: [], stages: [], view: "home", filter: "all", open: null, pane: "overview", detail: null, intro: false };

const VERDICT = { QUALIFY: "Qualify", PRIORITY: "Priority", INSUFFICIENT_DATA: "Unsure", NURTURE: "Nurture", REJECT: "Reject", DISQUALIFIED: "Out" };
const GATE = { existing_sprinto_customer: "Already a Sprinto customer", too_large: "Too large", not_software: "Not software", too_small: "Too small" };
const SIGNAL = { A1_b2b_software: "B2B software", A2_stage: "Funding stage", A3_headcount: "Headcount",
  B1_enterprise_motion: "Enterprise plan or sales", B2_enterprise_logos: "Enterprise customers", B3_sensitive_data: "Sensitive data",
  B4_procurement_markers: "Procurement signals", C1_certification_gap: "Certification gap", C2_in_flight_statement: "Compliance in progress",
  C3_security_hiring: "Security hiring", C4_recent_funding: "Recent funding", C5_geo_expansion: "US or EU expansion",
  D1_stack_integrates: "Cloud stack fit", D2_multi_framework_pull: "Multiple frameworks", D3_recent_enterprise_win: "Recent enterprise win" };
const TOOL = { web_research: "web search", job_postings: "job boards", fetch_page: "page fetch" };
const LANES = [["qualified", "No contact yet"], ["needs_review", "Email held"], ["contacted", "Emailed"], ["replied", "Replied"],
  ["meeting", "Meeting"], ["won", "Won"], ["lost", "Lost"], ["needs_data", "Needs data"], ["not_fit", "Not a fit"]];
const ICON = {
  alert: "M10 3.5 2.5 16.5h15z M10 8.5v3.5 M10 14.5v.01",
  person: "M10 10a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4z M3.8 17c.9-3 3.3-4.6 6.2-4.6s5.3 1.6 6.2 4.6",
  retry: "M15.5 7A6 6 0 1 0 16 12 M16 3.5V7h-3.5",
  mail: "M3 5.5h14v9H3z M3.5 6l6.5 5 6.5-5",
  check: "M10 17.5a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15z M6.8 10.2l2.2 2.2 4.3-4.6",
  arrow: "M4 10h12 M11.5 5.5 16 10l-4.5 4.5",
};

function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k === "on") Object.entries(v).forEach(([e, f]) => n.addEventListener(e, f));
    else if (k === "style") Object.assign(n.style, v);
    else if (k === "href") { if (/^https?:\/\//i.test(v)) n.href = v; }   // never javascript: URLs from scraped data
    else n.setAttribute(k, v);
  }
  for (const c of kids.flat(Infinity)) if (c != null && c !== false) n.append(c instanceof Node ? c : String(c));
  return n;
}
function icon(name) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 20 20"); s.setAttribute("aria-hidden", "true");
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path"); p.setAttribute("d", ICON[name]); s.append(p);
  return s;
}
async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}
const pct = (n, d) => (d ? Math.round((100 * n) / d) : 0);
const avg = (xs) => xs.reduce((s, x) => s + x, 0) / xs.length;
const tag = (text, tone) => el("span", { class: `tag ${tone || ""}` }, text);
const when = (iso) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "");
const first = (contact) => (contact || "").split(" (")[0];
const activate = (fn) => ({ click: fn, keydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fn(); } } });

// ---------- what each account means ----------
function status(a) {
  return ({ sent: ["Emailed", "lime"], held: ["Email held", "amber"], no_contact: ["No contact", "amber"], not_qualified: ["Not a fit", "coral"],
    insufficient_data: ["Needs data", ""], failed: ["Error", "coral"], running: ["Researching", "blue"] })[a.status] || [a.status, ""];
}
function why(a) {          // [reason, tone]: coral = out, amber = needs you, slate = unknown
  const gate = /Disqualified \((\w+)\)/.exec(a.reason || "");
  if (gate) return [GATE[gate[1]] || "Disqualified", "coral"];
  if (a.status === "running") return ["Researching", "blue"];
  if (a.status === "insufficient_data" && !a.verdict) return ["Site unreadable", ""];
  if (a.status === "failed") return ["Error", "coral"];
  if (a.verdict === "INSUFFICIENT_DATA") return ["Not enough evidence", ""];
  if (["REJECT", "NURTURE"].includes(a.verdict)) return [`Below ${BAR}`, "coral"];
  if (a.status === "no_contact") return ["No contact found", "amber"];
  if (a.status === "held") return ["Email held", "amber"];
  if (a.status === "sent") return [`Emailed ${first(a.contact)}`.trim(), "lime"];
  return [a.reason || "", ""];
}
function plainCheck(err) { // the validator's message, in a sentence a person can act on
  const n = /\[(.*)\]/.exec(err)?.[1]?.replace(/'/g, "");
  const rules = [[/numbers not backed/, `It used a number (${n}) that the evidence does not show in that form.`],
    [/write numbers as digits/, "It spelled a number out in words, so it could not be checked."],
    [/subject must/, "The subject line was too generic."], [/first sentence must/, "The opening did not say what the company sells."],
    [/exactly one question/, "It did not end on exactly one question."], [/hedging/, "It hedged too much."],
    [/list frameworks/, "It listed too many frameworks."], [/recent/, "It called funding recent without dated evidence."],
    [/banned phrase/, "It used a phrase on the banned list."], [/words \(max/, "It ran over 110 words."], [/hook_id/, "It did not use a valid hook."]];
  return (rules.find(([re]) => re.test(err)) || [null, err.charAt(0).toUpperCase() + err.slice(1)])[1];
}
const checks = (a) => (a.reason || "").replace(/^email held for review, failed checks: /, "").split("; ").filter(Boolean).map(plainCheck);
const qualified = (a) => ["QUALIFY", "PRIORITY"].includes(a.verdict);
const changed = (a) => a.fixed && a.fixed !== a.verdict;
const needsYou = (a) => ["held", "no_contact", "insufficient_data", "failed"].includes(a.status);

// ---------- home ----------
function renderHome() {
  const A = STATE.accounts, n = A.length;
  if (!n) {
    $("#headline").textContent = "Add domains to start.";
    $("#chips").replaceChildren();
    ["#time", "#dumbbell", "#funnel", "#mail", "#quality", "#queue"].forEach((s) => $(s).replaceChildren(el("p", { class: "muted" }, "No data yet")));
    return;
  }
  const q = A.filter(qualified), sent = A.filter((a) => a.sent_at), held = A.filter((a) => a.status === "held");
  $("#headline").textContent = `${q.length} of ${n} companies qualified.`;
  const last = A.map((a) => a.started).filter(Boolean).sort().pop();
  const chip = (c, t) => el("span", {}, el("b", { style: { background: c } }), t);
  $("#chips").replaceChildren(chip("var(--lime)", `${sent.length} emailed`), held.length && chip("var(--amber)", `${held.length} held`),
    chip("var(--blue)", `${A.filter(changed).length} verdicts fixed by research`), last && chip("var(--slate)", `Last run ${when(last)}`));
  timeTile(A); dumbbell(A); funnel(A); mailTile(q, sent, held); qualityTile(A); queue(A);
  $$(".tile").forEach((t) => t.addEventListener("pointermove", (e) => {      // SpotlightCard, after React Bits
    const r = t.getBoundingClientRect();
    t.style.setProperty("--mx", `${e.clientX - r.left}px`); t.style.setProperty("--my", `${e.clientY - r.top}px`);
  }));
}

function timeTile(A) {
  const secs = A.map((a) => a.seconds).filter(Boolean), s = Math.round(secs.length ? avg(secs) : 0), manual = avg(MANUAL_S);
  $("#time").replaceChildren(el("div", { class: "big" }, el("span", { "data-count": s }, s), el("small", {}, "sec")),
    el("div", { class: "race" },
      el("div", { class: "race-row" }, el("span", {}, "Autopilot"), el("div", { class: "track" }, el("div", { class: "fill", style: { width: `${Math.max(1.5, (100 * s) / MANUAL_S[1])}%` } })), el("span", {}, `${s}s`)),
      el("div", { class: "race-row" }, el("span", {}, "By hand"), el("div", { class: "track" }, el("div", { class: "fill slate", style: { width: `${(100 * manual) / MANUAL_S[1]}%` } })), el("span", {}, "15–20 min"))),
    el("p", { class: "foot" }, `${pct(manual - s, manual)}% faster`));
}

function highlight(domain, on) { if (domain) $$(`[data-domain="${CSS.escape(domain)}"]`).forEach((n) => n.classList.toggle("hl", on)); }
const hover = (d) => ({ mouseenter: () => highlight(d, true), mouseleave: () => highlight(d, false), focus: () => highlight(d, true), blur: () => highlight(d, false) });

function dumbbell(A) {
  const rows = A.filter((a) => a.tool_calls).sort((x, y) => y.score - x.score);
  $("#h-loop").textContent = rows.length ? `Agent loop · ${A.filter(changed).length} verdicts overturned` : "Agent loop";
  if (!rows.length) { $("#dumbbell").replaceChildren(el("div", { class: "empty" }, icon("check"), "Not needed this run")); return; }
  const x = (v) => Math.max(0, Math.min(100, ((v - 20) / 80) * 100));   // axis 20-100: no researched score sits lower
  const list = rows.map((a) => {
    const lo = x(Math.min(a.fixed_score, a.score)), hi = x(Math.max(a.fixed_score, a.score));
    const via = [...new Set(a.loop.map((l) => TOOL[l.tool]))].join(" + ");
    return el("div", { class: "db-row", "data-domain": a.domain, tabindex: "0", role: "button",
      "aria-label": `${a.name}: ${VERDICT[a.fixed]} ${a.fixed_score} from the website alone, ${VERDICT[a.verdict]} ${a.score} after ${via}`,
      on: { ...activate(() => openAccount(a.domain)), ...hover(a.domain) } },
      el("div", {}, el("div", { class: "db-name" }, a.name), el("div", { class: "db-via" }, via)),
      el("div", { class: "db-track" }, el("div", { class: "bar60", style: { left: `${x(BAR)}%` } }),
        el("div", { class: "db-line", style: { left: `${lo}%`, width: `${hi - lo}%` } }),
        el("div", { class: "db-dot from", style: { left: `${x(a.fixed_score)}%` } }),
        el("div", { class: "db-dot to", style: { left: `${x(a.score)}%` }, "data-shift": x(a.fixed_score) - x(a.score) })),
      el("div", { class: "db-result" }, el("b", {}, `${VERDICT[a.fixed]} → `, el("em", {}, VERDICT[a.verdict])), `${a.fixed_score} → ${a.score}`));
  });
  $("#dumbbell").replaceChildren(
    el("div", { class: "legend" }, el("span", {}, el("i", { class: "ring" }), "Website only"), el("span", {}, el("i", { class: "solid" }), "After research"),
      el("span", {}, el("i", { class: "dash" }), `${BAR} = qualifies`)),
    el("div", { class: "db-axis" }, el("span", {}), el("div", { class: "db-scale" }, [20, 40, 60, 80, 100].map((v) => el("span", { style: { left: `${x(v)}%` } }, v))), el("span", {})),
    ...list);
}

function funnel(A) {
  const steps = [["Researched", () => true], ["Readable", (a) => a.verdict], ["Qualified", qualified], ["Contact found", (a) => a.contact], ["Emailed", (a) => a.sent_at]];
  let prev = A;
  $("#funnel").replaceChildren(el("div", { class: "fn" }, steps.map(([label, test], i) => {
    const kept = prev.filter(test), groups = new Map();
    prev.filter((a) => !test(a)).forEach((a) => { const [w, t] = why(a); const g = groups.get(w) || { t, n: 0 }; g.n++; groups.set(w, g); });
    prev = kept;
    return el("div", { class: `fn-row${i === steps.length - 1 ? " last" : ""}` },
      el("div", { class: "fn-top" }, el("span", {}, label), el("span", {}, el("b", {}, kept.length), ` / ${A.length}`)),
      el("div", { class: "fn-bar" }, el("span", { style: { width: `${Math.max(2, pct(kept.length, A.length))}%` } })),
      groups.size ? el("div", { class: "fn-out" }, [...groups].map(([w, g]) => tag(g.n > 1 ? `${w} · ${g.n}` : w, g.t))) : null);
  })));
}

function mailTile(q, sent, held) {
  const none = q.length - sent.length - held.length;
  const seg = (k, c) => k ? el("span", { style: { flex: k, background: c } }) : null;
  const key = (c, label, k) => el("div", {}, el("span", {}, el("i", { style: { background: c } }), label), el("b", {}, k));
  $("#mail").replaceChildren(el("div", { class: "mid" }, el("span", { "data-count": sent.length }, sent.length), el("small", {}, `of ${q.length} sent`)),
    el("div", { class: "stack", role: "img", "aria-label": `${sent.length} sent, ${held.length} held, ${none} without a contact` },
      seg(sent.length, "var(--lime)"), seg(held.length, "var(--amber)"), seg(none, "var(--slate)")),
    el("div", { class: "keys" }, key("var(--lime)", "Sent", sent.length), key("var(--amber)", "Held, failed a check", held.length), key("var(--slate)", "No contact", none)));
}

function qualityTile(A) {
  const scored = A.filter((a) => a.ai_score != null);
  if (!scored.length) { $("#quality").replaceChildren(el("p", { class: "muted" }, "No emails scored yet")); return; }
  const m = avg(scored.map((a) => a.ai_score)), hit = scored.filter((a) => a.ai_score >= TARGET).length;
  $("#quality").replaceChildren(el("div", { class: "mid" }, el("span", { "data-count": m.toFixed(1), "data-dec": "1" }, m.toFixed(1)), el("small", {}, "/ 10 avg")),
    el("div", { class: "gauge" }, el("div", { class: "target", style: { left: `${TARGET * 10}%` } }),
      scored.map((a) => el("div", { class: "mark", "data-domain": a.domain, tabindex: "0", role: "button", title: `${a.name}: ${a.ai_score}`,
        "aria-label": `${a.name} email scored ${a.ai_score}`, style: { left: `${a.ai_score * 10}%`, background: a.sent_at ? "var(--lime)" : "var(--amber)" },
        on: { ...activate(() => openAccount(a.domain, "email")), ...hover(a.domain) } }))),
    el("div", { class: "gauge-scale" }, el("span", {}, "0"), el("span", {}, "10")),
    el("p", { class: "foot" }, hit ? `${hit} of ${scored.length} reached ${TARGET}` : `None reached ${TARGET} yet, even after rewrites`));
}

function queue(A) {
  const items = [];
  A.filter((a) => a.status === "held").forEach((a) => items.push(["amber", "alert", `Held email to ${first(a.contact) || a.name}`,
    checks(a)[0] || "It failed a check, so it was not sent.", "Open email", () => openAccount(a.domain, "email"), a.domain]));
  A.filter((a) => a.status === "no_contact").forEach((a) => items.push(["amber", "person", `No contact at ${a.name}`,
    "Add a decision-maker to contacts.csv, then re-run.", "Open", () => openAccount(a.domain, "contact"), a.domain]));
  A.filter((a) => ["insufficient_data", "failed"].includes(a.status)).forEach((a) => items.push(["slate", "retry", a.domain,
    why(a)[0], "Re-run", () => run([a.domain]), a.domain]));
  const waiting = A.filter((a) => a.sent_at && !a.review.replied && !a.review.stage);
  if (waiting.length) items.push(["lime", "mail", `${waiting.length} awaiting a reply`, waiting.map((a) => a.name).join(", "), "Log replies",
    () => { STATE.filter = "sent"; go("accounts"); }, null]);
  $("#h-queue").textContent = items.length ? `Needs you · ${items.length}` : "Needs you";
  $("#queue").replaceChildren(items.length ? el("div", { class: "q" }, items.map(([tone, ic, what, w, label, act, d]) =>
    el("div", { class: `q-row ${tone}`, "data-domain": d || "" }, el("div", { class: "q-ic" }, icon(ic)),
      el("div", {}, el("div", { class: "what" }, what), el("div", { class: "why" }, w), el("button", { class: "btn small", on: { click: act } }, label)))))
    : el("div", { class: "empty" }, icon("check"), "All clear"));
}

// ---------- accounts table ----------
const FILTERS = [["all", "All", () => true], ["sent", "Emailed", (a) => a.sent_at], ["you", "Needs you", needsYou], ["out", "Not a fit", (a) => a.status === "not_qualified"]];
function renderAccounts() {
  const A = STATE.accounts;
  $("#filters").replaceChildren(...FILTERS.map(([k, label, f]) => el("button", { class: `chip${STATE.filter === k ? " on" : ""}`, role: "tab",
    "aria-selected": String(STATE.filter === k), on: { click: () => { STATE.filter = k; renderAccounts(); } } }, label, el("span", {}, A.filter(f).length))));
  const q = $("#search").value.trim().toLowerCase(), f = FILTERS.find(([k]) => k === STATE.filter)[2];
  const rows = A.filter(f).filter((a) => !q || [a.name, a.domain, a.contact].join(" ").toLowerCase().includes(q)).sort((x, y) => (y.score ?? -1) - (x.score ?? -1));
  if (!rows.length) { $("#table").replaceChildren(el("div", { class: "empty" }, A.length ? "Nothing matches" : "No companies yet")); return; }
  $("#table").replaceChildren(el("table", {}, el("thead", {}, el("tr", {}, ["Company", "Status", "Why", "Agent loop", "ICP score", "Contact", "Email"].map((h) => el("th", { scope: "col" }, h)))),
    el("tbody", {}, rows.map((a) => {
      const [label, tone] = status(a);
      return el("tr", { tabindex: "0", on: activate(() => openAccount(a.domain)) },
        el("td", { class: "acct" }, el("b", {}, a.name), el("span", {}, a.domain)),
        el("td", {}, tag(label, tone)),
        el("td", { class: "why-cell" }, why(a)[0]),
        el("td", { class: "change" }, a.fixed ? (changed(a) ? [`${VERDICT[a.fixed]} → `, el("b", {}, VERDICT[a.verdict])] : VERDICT[a.verdict]) : "–"),
        el("td", {}, a.score != null ? el("div", { class: "score" }, el("span", {}, a.score),
          el("div", { class: "track" }, el("div", { class: "fill", style: { width: `${a.score}%`, background: a.score >= BAR ? "var(--blue)" : "var(--slate)" } }))) : "–"),
        el("td", {}, a.contact || "–"),
        el("td", {}, a.ai_score != null ? `${a.ai_score} / 10` : "–"));
    }))));
}

// ---------- pipeline board ----------
function renderPipeline() {
  const by = {};
  STATE.accounts.forEach((a) => (by[a.lane] ||= []).push(a));
  $("#board").replaceChildren(...LANES.map(([k, label]) => el("section", { class: "lane", "aria-label": label },
    el("h3", {}, label, el("span", {}, (by[k] || []).length)),
    (by[k] || []).map((a) => el("div", { class: "card", tabindex: "0", role: "button", on: activate(() => openAccount(a.domain)) },
      el("b", {}, a.name), el("div", { class: "d" }, a.domain), a.contact && el("div", { class: "who" }, a.contact),
      el("div", { class: "row" }, a.verdict && tag(`${VERDICT[a.verdict]} ${a.score}`, qualified(a) ? "blue" : ""),
        a.ai_score != null && tag(`email ${a.ai_score}`, a.ai_score >= TARGET ? "lime" : "amber")))))));
}

// ---------- drawer ----------
const evd = (t, id) => t.evidence.find((e) => e.id === id);
function evLine(t, id) {
  const e = evd(t, id);
  if (!e) return null;
  return el("span", { class: "ev" }, `“${e.quote.slice(0, 150)}” `, el("a", { href: e.source_url, target: "_blank", rel: "noopener noreferrer" }, "source"),
    e.verified ? " · on their site" : " · web search");
}
function plain(q) {
  const top = q.signals.filter((s) => s.points).sort((x, y) => y.points - x.points).slice(0, 3);
  const unknown = q.signals.filter((s) => s.state === "unknown");
  return [top.length && `Strongest: ${top.map((s) => `${SIGNAL[s.signal_id] || s.signal_id} +${s.points}`).join(", ")}.`,
    unknown.length && `Unknown: ${unknown.map((s) => SIGNAL[s.signal_id] || s.signal_id).join(", ")}.`,
    q.caps.length && `Capped: ${q.caps.map((c) => c.replace(/_/g, " ")).join(", ")}.`].filter(Boolean).join(" ");
}
function paneOverview(t) {
  const q = t.steps.qualify, a = STATE.accounts.find((x) => x.domain === t.domain) || {};
  if (!q) return [el("div", { class: "banner amber" }, why(a)[0] || "Not scored")];
  const sig = q.signals.map((s) => el("tr", {}, el("td", {}, SIGNAL[s.signal_id] || s.signal_id),
    el("td", {}, s.state === "unknown" ? tag("Unknown") : tag(s.bucket.replace(/_/g, " "), s.points ? "lime" : "")),
    el("td", {}, `${s.points} / ${s.max}`), el("td", {}, s.evidence_ids.map((i) => evLine(t, i)))));
  return [
    el("div", { class: "verdicts" },
      el("div", { class: "verdict" }, el("div", { class: "k" }, "Website only"), el("div", { class: "v" }, `${VERDICT[a.fixed] || VERDICT[q.verdict]} · ${a.fixed_score ?? q.score}`)),
      icon("arrow"),
      el("div", { class: "verdict final" }, el("div", { class: "k" }, `After ${q.iterations.length} research step${q.iterations.length === 1 ? "" : "s"}`), el("div", { class: "v" }, `${VERDICT[q.verdict]} · ${q.score}`))),
    el("p", { class: "muted" }, plain(q)),
    q.disqualifier && el("div", { class: "banner amber" }, `${GATE[q.disqualifier.gate_id] || q.disqualifier.gate_id}. `, q.disqualifier.evidence_ids.map((i) => evLine(t, i))),
    el("div", { class: "sec" }, el("h3", {}, "Score, with its evidence"),
      el("div", { class: "sig-wrap" }, el("table", { class: "sig" }, el("thead", {}, el("tr", {}, ["Signal", "Finding", "Points", "Evidence"].map((h) => el("th", {}, h)))), el("tbody", {}, sig)))),
  ];
}
function paneContact(t) {
  const c = t.steps.contact;
  if (!c) return [el("div", { class: "banner amber" }, "Only qualified companies get a contact search.")];
  const w = c.chosen;
  return [
    w ? el("div", { class: "person" }, el("b", {}, `${w.first_name} ${w.last_name}`), el("span", {}, w.position),
      el("span", { class: "muted" }, `${w.email} · ${w.source}`), w.linkedin && el("a", { href: w.linkedin, target: "_blank", rel: "noopener noreferrer" }, "LinkedIn"))
      : el("div", { class: "banner amber" }, "No eligible decision-maker. Add one to contacts.csv and re-run."),
    el("div", { class: "sec" }, el("h3", {}, "Why this person"), el("p", {}, c.reason), c.fallback && el("p", { class: "muted" }, c.fallback)),
    el("div", { class: "sec" }, el("h3", {}, "Considered"), el("ul", {}, (c.considered.length ? c.considered : ["Nobody"]).map((x) => el("li", {}, x)))),
    t.steps.pains && el("div", { class: "sec" }, el("h3", {}, "Likely pain points"), el("ul", {}, t.steps.pains.map((p) => el("li", {}, p.text, p.evidence_ids.map((i) => evLine(t, i)))))),
  ];
}
function paneEmail(t, gmail) {
  const d = t.steps.draft, s = t.steps.send;
  if (!d) return [el("div", { class: "banner amber" }, "No email: not qualified or no contact.")];
  const rv = d.review;
  return [
    t.status === "held" ? el("div", { class: "banner amber" }, "Held, not sent. ", d.validator_errors.map(plainCheck).join(" "))
      : s?.id ? el("div", { class: "banner lime" }, `Sent to ${s.to} · ${when(s.sent_at)}`) : null,
    rv && el("div", { class: "scores" }, [["Overall", rv.score], ["Specific", rv.specificity], ["Relevant", rv.relevance], ["Would reply", rv.reply_likelihood]]
      .map(([l, v]) => el("div", {}, el("b", { style: { color: v >= TARGET ? "var(--lime)" : v >= 5 ? "var(--amber)" : "var(--coral)" } }, v), el("span", {}, l)))),
    rv && el("p", { class: "muted" }, rv.critique),
    el("div", { class: "sec" }, el("div", { class: "subj" }, d.subject), el("div", { class: "mail" }, d.text),
      d.hook && el("p", { class: "muted" }, `Hook: ${SIGNAL[d.hook.signal_id] || d.hook.signal_id}`, evLine(t, d.hook.evidence_id)),
      gmail && el("a", { href: gmail, target: "_blank", rel: "noopener noreferrer" }, "Open in Gmail, to yourself")),
  ];
}
function paneActivity(t) {
  const st = t.steps, items = [];
  if (st.scrape) items.push(["Read the website", st.scrape.map((p) => `${p.path} ${p.outcome.toLowerCase()}`).join(" · ")]);
  if (st.extract) items.push(["Profile", `${st.extract.name}: ${st.extract.one_liner}`]);
  (st.qualify?.iterations || []).forEach((it) => items.push([`Research: ${TOOL[it.tool] || it.tool}`, `${it.rationale} Score ${it.score_before} → ${it.score_after ?? "?"}.`]));
  if (st.qualify) items.push([`Verdict: ${VERDICT[st.qualify.verdict]}`, st.qualify.stop_reason]);
  if (st.contact) items.push(["Contact", st.contact.chosen ? `${st.contact.chosen.first_name} ${st.contact.chosen.last_name}` : "None found"]);
  (st.draft?.attempts || []).forEach((a, i) => items.push([`Draft ${i + 1}`, a.review ? `Reviewer ${a.review.score} / 10` : a.validator_errors.map(plainCheck).join(" ")]));
  if (st.send) items.push(["Sent", st.send.id ? `${st.send.to} · ${when(st.send.sent_at)}` : st.send.error]);
  items.push([`Done: ${status(t)[0]}`, `${t.seconds ?? "?"}s · ${t.llm_calls.length} model calls`]);
  return [el("ul", { class: "timeline" }, items.map(([h, b]) => el("li", {}, el("b", {}, h), el("div", { class: "t" }, b))))];
}
function drawPane() {
  const { trace, gmail } = STATE.detail;
  const panes = { overview: paneOverview, contact: paneContact, email: (t) => paneEmail(t, gmail), activity: paneActivity };
  $$(".tabs .tab").forEach((b) => b.classList.toggle("on", b.dataset.pane === STATE.pane));
  $("#d-body").replaceChildren(...panes[STATE.pane](trace).flat(3).filter(Boolean));
  $("#d-body").scrollTop = 0;
  if (motionOK()) gsap.from("#d-body > *", { y: 8, autoAlpha: 0, stagger: 0.04, duration: 0.4, ease: "expo.out" });
}
let lastFocus = null;
async function openAccount(domain, pane = "overview") {
  try { STATE.detail = await api(`/api/account/${encodeURIComponent(domain)}`); }
  catch (e) { showJob({ running: false, done: [], error: e.message }); return; }
  STATE.open = domain; STATE.pane = pane; lastFocus = document.activeElement;
  const t = STATE.detail.trace, ext = t.steps.extract || {};
  $("#d-name").textContent = ext.name || domain;
  $("#d-domain").textContent = domain; $("#d-domain").href = `https://${domain}`;
  $("#d-liner").textContent = ext.one_liner || "";
  const f = $("#review"), rv = STATE.detail.review;
  f.stage.replaceChildren(el("option", { value: "" }, "Auto"), ...STATE.stages.map((s) => el("option", { value: s }, s[0].toUpperCase() + s.slice(1))));
  ["stage", "lead_agrees", "edit_level", "replied", "notes"].forEach((k) => (f[k].value = rv[k] || ""));
  $("#saved").textContent = "";
  $("#drawer").hidden = $("#scrim").hidden = false;
  window.lenis?.stop();
  if (motionOK()) { gsap.fromTo("#drawer", { x: 56, autoAlpha: 0 }, { x: 0, autoAlpha: 1, duration: 0.5, ease: "expo.out" }); gsap.fromTo("#scrim", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.3 }); }
  drawPane();
  $("#d-close").focus();
}
function closeDrawer() {
  if ($("#drawer").hidden) return;
  $("#drawer").hidden = $("#scrim").hidden = true; STATE.open = null;
  window.lenis?.start();
  lastFocus?.focus?.();
}
function trapFocus(e) {     // aria-modal: Tab stays inside the drawer
  if (e.key !== "Tab" || $("#drawer").hidden) return;
  const f = $$('#drawer a[href], #drawer button, #drawer select, #drawer textarea, #drawer [tabindex="0"]').filter((n) => n.offsetParent);
  if (!f.length) return;
  const [a, z] = [f[0], f[f.length - 1]];
  if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
  else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
}

// ---------- views, runs, motion ----------
function go(view) {
  STATE.view = view;
  $$(".nav").forEach((b) => b.classList.toggle("on", b.dataset.view === view));
  $$(".view").forEach((v) => (v.hidden = v.id !== `view-${view}`));
  render();
  window.scrollTo(0, 0);
  if (motionOK() && view !== "home") gsap.from(`#view-${view} > *`, { y: 10, autoAlpha: 0, stagger: 0.05, duration: 0.45, ease: "expo.out" });
}
function render() {
  $("#n-accounts").textContent = STATE.accounts.length || "";
  if (STATE.view === "home") renderHome();
  if (STATE.view === "accounts") renderAccounts();
  if (STATE.view === "pipeline") renderPipeline();
}
async function load() {
  const data = await api("/api/accounts");
  Object.assign(STATE, { accounts: data.accounts, stages: data.stages });
  showJob(data.job);
  render();
  if (!STATE.intro && STATE.view === "home") { STATE.intro = true; intro(); }
}
let polling = null;
function showJob(j) {
  const box = $("#job");
  box.classList.toggle("err", !!j.error);
  $("#run-btn").disabled = j.running;
  box.replaceChildren(...(j.running ? [el("span", { class: "dot" }), `Researching ${j.current || "…"}${j.queue.length ? ` · ${j.queue.length} queued` : ""}`]
    : j.error ? [`Run stopped: ${j.error}`] : j.done.length ? [`Done: ${j.done.map((d) => `${d.domain} ${status(d)[0].toLowerCase()}`).join(", ")}`] : []));
  if (j.running && !polling) polling = setInterval(async () => showJob(await api("/api/job")), 3000);
  if (!j.running && polling) { clearInterval(polling); polling = null; load(); }
}
async function run(domains) {
  try { showJob(await api("/api/run", { domains })); }
  catch (e) { showJob({ running: false, done: [], error: e.message }); }
}

const motionOK = () => typeof gsap !== "undefined" && !matchMedia("(prefers-reduced-motion: reduce)").matches;
function intro() {        // the one authored moment: tiles rise in, numbers count, every chart draws itself once
  if (!motionOK()) return;
  const tl = gsap.timeline({ defaults: { ease: "expo.out", duration: 0.9 } });
  tl.from("#headline", { y: 18, autoAlpha: 0, duration: 0.8 })
    .from(".hero-chips span", { y: 8, autoAlpha: 0, stagger: 0.05, duration: 0.5 }, "-=0.5")
    .from(".bento > .tile", { y: 24, autoAlpha: 0, stagger: 0.07 }, "-=0.35")
    .from(".race .fill, .fn-bar span, .stack span", { scaleX: 0, transformOrigin: "left center", stagger: 0.05, duration: 1.2 }, "<0.15")
    .from(".db-line", { scaleX: 0, transformOrigin: "left center", stagger: 0.12, duration: 1 }, "<0.1")
    .from(".db-dot.to", { x: (i, n) => (Number(n.dataset.shift) / 100) * n.parentElement.clientWidth, stagger: 0.12, duration: 1.3 }, "<")
    .from(".gauge .mark", { scale: 0, stagger: 0.1, duration: 0.6, ease: "back.out(2.2)" }, "<0.3")
    .from(".fn-out .tag, .q-row", { y: 6, autoAlpha: 0, stagger: 0.03, duration: 0.5 }, "<");
  $$("[data-count]").forEach((n) => {          // CountUp, after React Bits, in plain GSAP
    const end = Number(n.dataset.count), dec = Number(n.dataset.dec || 0), o = { v: 0 };
    gsap.to(o, { v: end, duration: 1.6, ease: "expo.out", delay: 0.35, onUpdate: () => (n.textContent = o.v.toFixed(dec)) });
  });
}

// ---------- wiring ----------
$$(".nav").forEach((b) => b.addEventListener("click", () => go(b.dataset.view)));
$$(".tabs .tab").forEach((b) => b.addEventListener("click", () => { STATE.pane = b.dataset.pane; drawPane(); }));
$("#search").addEventListener("input", renderAccounts);
$("#d-close").addEventListener("click", closeDrawer);
$("#scrim").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); trapFocus(e); });
$("#run-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const domains = $("#run-input").value.split(/[\s,]+/).filter(Boolean);
  if (domains.length) { run(domains); $("#run-input").value = ""; }
});
$("#review").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target, body = Object.fromEntries(["stage", "lead_agrees", "edit_level", "replied", "notes"].map((k) => [k, f[k].value]));
  if (body.stage === "replied" && !body.replied) body.replied = f.replied.value = "y";
  try { await api(`/api/account/${encodeURIComponent(STATE.open)}/review`, body); $("#saved").textContent = "Saved"; await load(); }
  catch (err) { $("#saved").textContent = `Not saved: ${err.message}`; }
});
if (motionOK() && typeof Lenis !== "undefined") {     // smooth main scroll only when motion is welcome; the drawer keeps native scroll
  window.lenis = new Lenis({ lerp: 0.12, anchors: true });
  gsap.ticker.add((t) => window.lenis.raf(t * 1000));
  gsap.ticker.lagSmoothing(0);
}
$("#headline").replaceChildren(el("span", { class: "skel", style: { width: "520px", maxWidth: "100%", height: "44px" } }));
load().catch((err) => { $("#headline").textContent = "Could not load accounts."; $("#chips").replaceChildren(el("span", {}, `${err.message}. Is app.py running?`)); });

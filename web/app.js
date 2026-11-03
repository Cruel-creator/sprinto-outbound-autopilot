// Outbound CRM. Everything shown comes from scraped websites: render with textContent only, never innerHTML.
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const MANUAL = 1050;            // 17.5 minutes: midpoint of the case brief's 15-20 minutes by hand
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
const LANES = [["qualified", "No contact"], ["needs_review", "Held"], ["contacted", "Emailed"], ["replied", "Replied"],
  ["meeting", "Meeting"], ["won", "Won"], ["lost", "Lost"], ["needs_data", "Needs data"], ["not_fit", "Not a fit"]];

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
function arrow() {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 20 20"); s.setAttribute("aria-hidden", "true");
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path"); p.setAttribute("d", "M4 10h12 M11 5l5 5-5 5"); s.append(p);
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
const when = (iso) => (iso ? new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "");
const first = (c) => (c || "").split(" (")[0];
const clock = (t) => { const s = Math.max(0, Math.round(t)); return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`; };
const activate = (fn) => ({ click: fn, keydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fn(); } } });

// ---------- meaning ----------
function status(a) {
  return ({ sent: ["Emailed", "accent"], held: ["Held", "ember"], no_contact: ["No contact", "ember"], not_qualified: ["Not a fit", "dim"],
    insufficient_data: ["Needs data", "ember"], failed: ["Error", "ember"], running: ["Researching", "accent"] })[a.status] || [a.status, ""];
}
function why(a) {          // [reason, needs-you?]
  const gate = /Disqualified \((\w+)\)/.exec(a.reason || "");
  if (gate) return [GATE[gate[1]] || "Disqualified", false];
  if (a.status === "running") return ["Researching", false];
  if (a.status === "insufficient_data" && !a.verdict) return ["Site unreadable", true];
  if (a.status === "failed") return ["Error", true];
  if (a.verdict === "INSUFFICIENT_DATA") return ["Not enough evidence", true];
  if (["REJECT", "NURTURE"].includes(a.verdict)) return [`Scored under ${BAR}`, false];
  if (a.status === "no_contact") return ["No contact found", true];
  if (a.status === "held") return ["Email held", true];
  if (a.status === "sent") return [`Emailed ${first(a.contact)}`.trim(), false];
  return [a.reason || "", false];
}
function plainCheck(err) {
  const n = /\[(.*)\]/.exec(err)?.[1]?.replace(/'/g, "");
  const rules = [[/numbers not backed/, `It used a number (${n}) the evidence does not show in that form.`],
    [/write numbers as digits/, "It spelled a number out, so it could not be checked."], [/subject must/, "The subject line was too generic."],
    [/first sentence must/, "The opening did not say what the company sells."], [/exactly one question/, "It did not end on exactly one question."],
    [/hedging/, "It hedged too much."], [/list frameworks/, "It listed too many frameworks."], [/recent/, "It called funding recent without dated evidence."],
    [/banned phrase/, "It used a phrase on the banned list."], [/words \(max/, "It ran over 110 words."], [/hook_id/, "It did not use a valid hook."]];
  return (rules.find(([re]) => re.test(err)) || [null, err.charAt(0).toUpperCase() + err.slice(1)])[1];
}
const checks = (a) => (a.reason || "").replace(/^email held for review, failed checks: /, "").split("; ").filter(Boolean).map(plainCheck);
const qualified = (a) => ["QUALIFY", "PRIORITY"].includes(a.verdict);
const changed = (a) => a.fixed && a.fixed !== a.verdict;
const needsYou = (a) => ["held", "no_contact", "insufficient_data", "failed"].includes(a.status);
function highlight(d, on) { if (d) $$(`[data-domain="${CSS.escape(d)}"]`).forEach((n) => n.classList.toggle("hl", on)); }
const hover = (d) => ({ mouseenter: () => highlight(d, true), mouseleave: () => highlight(d, false), focus: () => highlight(d, true), blur: () => highlight(d, false) });

// ---------- home: one claim per chapter, drawn in its final state ----------
function renderHome() {
  const A = STATE.accounts, n = A.length;
  const q = A.filter(qualified), sent = A.filter((a) => a.sent_at), held = A.filter((a) => a.status === "held");
  $("#headline").replaceChildren(...(n ? [`${n} companies researched.`, el("br"), el("span", { class: "dim" }, `${q.length} worth writing to.`)] : ["Add a domain to begin."]));
  const last = A.map((a) => a.started).filter(Boolean).sort().pop();
  $("#hero-facts").replaceChildren(...(n ? [[sent.length, "Emailed"], [held.length, "Held for you"], [A.filter(changed).length, "Verdicts fixed by research"], [last ? new Date(last).toLocaleDateString([], { month: "short", day: "numeric" }) : "–", "Last run"]] : [])
    .map(([v, l]) => el("li", {}, el("b", {}, v), el("span", {}, l))));
  chTime(A); chLoop(A); chFunnel(A, sent); chMail(A, sent, held); chQueue(A);
}

function chTime(A) {
  const secs = A.map((a) => a.seconds).filter(Boolean), s = secs.length ? avg(secs) : 0;
  $("#clock").textContent = clock(s);
  $("#clock").dataset.end = s;
  $("#clock-who").textContent = "Autopilot, per company";
  $("#clock-note").textContent = s ? `${pct(MANUAL - s, MANUAL)}% faster than 15–20 min by hand` : "";
  $("#clock-bar").style.transform = `scaleX(${s / MANUAL})`;
}

function chLoop(A) {
  const rows = A.filter((a) => a.tool_calls).sort((x, y) => y.score - x.score), k = A.filter(changed).length;
  $("#loop-big").replaceChildren(...(rows.length ? ["Research overturned ", el("em", {}, `${k} of ${A.length}`), " verdicts that the website alone would have got wrong."] : ["Every verdict was clear from the website alone."]));
  const x = (v) => Math.max(0, Math.min(100, ((v - 20) / 80) * 100));
  $("#dumbbell").replaceChildren(rows.length ? el("div", { class: "db" },
    el("div", { class: "db-axis" }, el("span", {}, "○ website only   ● researched"), el("div", { class: "db-scale" },
      [20, 40, BAR, 80, 100].map((v) => el("span", { class: v === BAR ? "is-bar" : "", style: { left: `${x(v)}%` } }, v === BAR ? `${BAR} qualifies` : v))), el("span", {})),
    rows.map((a) => {
      const lo = x(Math.min(a.fixed_score, a.score)), hi = x(Math.max(a.fixed_score, a.score));
      return el("div", { class: "db-row", "data-domain": a.domain, tabindex: "0", role: "button",
        "aria-label": `${a.name}: ${VERDICT[a.fixed]} ${a.fixed_score} from the website, ${VERDICT[a.verdict]} ${a.score} after research`,
        on: { ...activate(() => openAccount(a.domain)), ...hover(a.domain) } },
        el("div", {}, el("div", { class: "db-name" }, a.name), el("div", { class: "db-via" }, [...new Set(a.loop.map((l) => TOOL[l.tool]))].join(" + "))),
        el("div", { class: "db-track" }, el("div", { class: "bar60", style: { left: `${x(BAR)}%` } }),
          el("div", { class: "db-line", style: { left: `${lo}%`, width: `${hi - lo}%` } }),
          el("div", { class: "db-dot from", style: { left: `${x(a.fixed_score)}%` } }),
          el("div", { class: "db-dot to", style: { left: `${x(a.score)}%` }, "data-shift": x(a.fixed_score) - x(a.score) })),
        el("div", { class: "db-result" }, el("div", { class: "db-verdict" }, el("span", { class: "v-from", style: { transform: "translateY(-100%)" } }, VERDICT[a.fixed]),
          el("span", { class: "v-to" }, VERDICT[a.verdict])), el("div", { class: "db-score" }, `was ${VERDICT[a.fixed]} ${a.fixed_score} → ${a.score}`)));
    })) : null);
}

function chFunnel(A, sent) {
  $("#funnel-big").replaceChildren(...(A.length ? [`${A.length} in. `, el("em", {}, `${sent.length} emailed`), ". Every exit has a reason."] : []));
  const steps = [["Researched", () => true], ["Readable", (a) => a.verdict], ["Qualified", qualified], ["Contact found", (a) => a.contact], ["Emailed", (a) => a.sent_at]];
  let prev = A;
  $("#funnel").replaceChildren(el("div", { class: "fn" }, steps.map(([label, test], i) => {
    const kept = prev.filter(test), groups = new Map();
    prev.filter((a) => !test(a)).forEach((a) => { const [w, you] = why(a); const g = groups.get(w) || { you, n: 0 }; g.n++; groups.set(w, g); });
    prev = kept;
    return el("div", { class: `fn-row${i === steps.length - 1 ? " last" : ""}` },
      el("div", { class: "fn-label" }, label),
      el("div", { class: "fn-bar" }, el("span", { style: { width: `${Math.max(1.5, pct(kept.length, A.length))}%` } })),
      el("div", { class: "fn-n" }, el("span", { "data-count": kept.length }, kept.length), el("small", {}, `/ ${A.length}`)),
      groups.size ? el("div", { class: "fn-out" }, [...groups].map(([w, g], j) => [j ? " · " : "", el("i", { class: g.you ? "em" : "" }, g.n > 1 ? `${w} (${g.n})` : w)])) : null);
  })));
}

function chMail(A, sent, held) {
  const drafts = A.filter((a) => a.draft), scored = drafts.filter((a) => a.ai_score != null);
  $("#mail-big").replaceChildren(...(drafts.length ? [`${sent.length} sent, ${held.length} held. `, scored.length ? el("em", {}, `${avg(scored.map((a) => a.ai_score)).toFixed(1)} / 10`) : "", scored.length ? " average, scored by a reviewer that rewrites anything under 7." : ""] : ["No emails drafted yet."]));
  $("#stack").replaceChildren(...drafts.map((a) => el("article", { class: "letter", "data-domain": a.domain, tabindex: "0", role: "button",
    "aria-label": `Email to ${first(a.contact)} at ${a.name}`, on: { ...activate(() => openAccount(a.domain, "email")), ...hover(a.domain) } },
    el("div", {}, el("div", { class: "letter-to" }, `To ${a.contact || "—"} · ${a.name}`), el("div", { class: "letter-subj" }, a.draft.subject)),
    el("div", { class: "letter-score" }, el("b", {}, a.ai_score ?? "—"), el("span", {}, a.ai_score != null ? "reviewer score" : "not scored")),
    el("p", { class: "letter-body" }, a.draft.body),
    el("div", { class: `letter-state ${a.sent_at ? "sent" : "held"}` }, a.sent_at ? "Sent to your inbox" : `Held · ${checks(a)[0] || "failed a check"}`))));
}

function chQueue(A) {
  const items = [];
  A.filter((a) => a.status === "held").forEach((a) => items.push([`Held email to ${first(a.contact) || a.name}`, checks(a)[0] || "It failed a check.", "Open email", () => openAccount(a.domain, "email"), a.domain]));
  A.filter((a) => a.status === "no_contact").forEach((a) => items.push([`No contact at ${a.name}`, "Add one to contacts.csv, then re-run.", "Open", () => openAccount(a.domain, "contact"), a.domain]));
  A.filter((a) => ["insufficient_data", "failed"].includes(a.status)).forEach((a) => items.push([a.domain, why(a)[0], "Re-run", () => run([a.domain]), a.domain]));
  const waiting = A.filter((a) => a.sent_at && !a.review.replied && !a.review.stage);
  if (waiting.length) items.push([`${waiting.length} awaiting a reply`, waiting.map((a) => a.name).join(", "), "Log replies", () => { STATE.filter = "sent"; go("accounts"); }, null]);
  $("#queue-big").textContent = items.length ? `${items.length} ${items.length === 1 ? "thing needs" : "things need"} you.` : "Nothing needs you.";
  $("#queue").replaceChildren(items.length ? el("div", { class: "q" }, items.map(([what, w, label, act, d]) =>
    el("div", { class: "q-row", "data-domain": d || "" }, el("div", {}, el("div", { class: "q-what" }, el("i", {}, "●"), what), el("div", { class: "q-why" }, w)),
      el("button", { class: "pill-btn", on: { click: act } }, label)))) : el("div", { class: "empty-line" }, "Every company has been decided."));
}

// ---------- accounts & pipeline ----------
const FILTERS = [["all", "All", () => true], ["sent", "Emailed", (a) => a.sent_at], ["you", "Needs you", needsYou], ["out", "Not a fit", (a) => a.status === "not_qualified"]];
function renderAccounts() {
  const A = STATE.accounts;
  $("#filters").replaceChildren(...FILTERS.map(([k, label, f]) => el("button", { class: `filter${STATE.filter === k ? " on" : ""}`, role: "tab",
    "aria-selected": String(STATE.filter === k), on: { click: () => { STATE.filter = k; renderAccounts(); } } }, label, el("span", {}, A.filter(f).length))));
  const s = $("#search").value.trim().toLowerCase(), f = FILTERS.find(([k]) => k === STATE.filter)[2];
  const rows = A.filter(f).filter((a) => !s || [a.name, a.domain, a.contact].join(" ").toLowerCase().includes(s)).sort((x, y) => (y.score ?? -1) - (x.score ?? -1));
  if (!rows.length) { $("#table").replaceChildren(el("div", { class: "empty-line" }, A.length ? "Nothing matches." : "No companies yet.")); return; }
  $("#table").replaceChildren(el("table", {}, el("thead", {}, el("tr", {}, ["Company", "Status", "Why", "Agent loop", "Score", "Contact", "Email"].map((h) => el("th", { scope: "col" }, h)))),
    el("tbody", {}, rows.map((a) => {
      const [label, tone] = status(a);
      return el("tr", { tabindex: "0", on: activate(() => openAccount(a.domain)) },
        el("td", { class: "acct" }, el("b", {}, a.name), el("span", {}, a.domain)),
        el("td", {}, el("span", { class: `st ${tone}` }, label)),
        el("td", { class: "why-cell" }, why(a)[0]),
        el("td", { class: "why-cell" }, a.fixed ? (changed(a) ? `${VERDICT[a.fixed]} → ${VERDICT[a.verdict]}` : VERDICT[a.verdict]) : "–"),
        el("td", { class: "num-cell" }, a.score ?? "–"),
        el("td", { class: "why-cell" }, a.contact || "–"),
        el("td", { class: "num-cell" }, a.ai_score ?? "–"));
    }))));
}
function renderPipeline() {
  const by = {};
  STATE.accounts.forEach((a) => (by[a.lane] ||= []).push(a));
  $("#board").replaceChildren(...LANES.map(([k, label]) => el("section", { class: "lane", "aria-label": label },
    el("h3", {}, label, el("span", {}, (by[k] || []).length)),
    (by[k] || []).map((a) => el("div", { class: "card", tabindex: "0", role: "button", on: activate(() => openAccount(a.domain)) },
      el("b", {}, a.name), el("span", {}, [a.verdict && `${VERDICT[a.verdict]} ${a.score}`, a.contact && first(a.contact)].filter(Boolean).join(" · ") || a.domain))))));
}

// ---------- drawer ----------
const evd = (t, id) => t.evidence.find((e) => e.id === id);
function evLine(t, id) {
  const e = evd(t, id);
  return e ? el("span", { class: "ev" }, `“${e.quote.slice(0, 150)}” `, el("a", { href: e.source_url, target: "_blank", rel: "noopener noreferrer" }, "source"), e.verified ? " · on their site" : " · web search") : null;
}
function plain(q) {
  const top = q.signals.filter((s) => s.points).sort((x, y) => y.points - x.points).slice(0, 3), unknown = q.signals.filter((s) => s.state === "unknown");
  return [top.length && `Strongest: ${top.map((s) => `${SIGNAL[s.signal_id] || s.signal_id} +${s.points}`).join(", ")}.`,
    unknown.length && `Unknown: ${unknown.map((s) => SIGNAL[s.signal_id] || s.signal_id).join(", ")}.`].filter(Boolean).join(" ");
}
function paneOverview(t) {
  const q = t.steps.qualify, a = STATE.accounts.find((x) => x.domain === t.domain) || {};
  if (!q) return [el("p", { class: "note ember" }, why(a)[0] || "Not scored.")];
  return [
    el("div", { class: "verdicts" },
      el("div", { class: "verdict" }, el("div", { class: "k" }, "Website only"), el("div", { class: "v" }, `${VERDICT[a.fixed] || VERDICT[q.verdict]} ${a.fixed_score ?? q.score}`)), arrow(),
      el("div", { class: "verdict final" }, el("div", { class: "k" }, `After ${q.iterations.length} research step${q.iterations.length === 1 ? "" : "s"}`), el("div", { class: "v" }, `${VERDICT[q.verdict]} ${q.score}`))),
    el("p", { class: "note" }, plain(q)),
    q.disqualifier && el("p", { class: "note ember" }, `${GATE[q.disqualifier.gate_id] || q.disqualifier.gate_id}. `, q.disqualifier.evidence_ids.map((i) => evLine(t, i))),
    el("div", { class: "sec" }, el("h3", {}, "How the score was built"),
      el("div", { class: "sig-wrap" }, el("table", { class: "sig" }, el("thead", {}, el("tr", {}, ["Signal", "Finding", "Points", "Evidence"].map((h) => el("th", {}, h)))),
        el("tbody", {}, q.signals.map((s) => el("tr", {}, el("td", {}, SIGNAL[s.signal_id] || s.signal_id), el("td", {}, s.state === "unknown" ? "Unknown" : s.bucket.replace(/_/g, " ")),
          el("td", {}, `${s.points} / ${s.max}`), el("td", {}, s.evidence_ids.map((i) => evLine(t, i))))))))),
  ];
}
function paneContact(t) {
  const c = t.steps.contact;
  if (!c) return [el("p", { class: "note" }, "Only qualified companies get a contact search.")];
  const w = c.chosen;
  return [
    w ? el("div", { class: "person" }, el("b", {}, `${w.first_name} ${w.last_name}`), el("span", {}, w.position), el("span", {}, `${w.email} · ${w.source}`),
      w.linkedin && el("a", { href: w.linkedin, target: "_blank", rel: "noopener noreferrer" }, "LinkedIn")) : el("p", { class: "note ember" }, "No eligible decision-maker. Add one to contacts.csv and re-run."),
    el("div", { class: "sec" }, el("h3", {}, "Why this person"), el("p", { class: "note" }, c.reason), c.fallback && el("p", { class: "note" }, c.fallback)),
    t.steps.pains && el("div", { class: "sec" }, el("h3", {}, "Likely pain points"), t.steps.pains.map((p) => el("p", { class: "note" }, p.text, p.evidence_ids.map((i) => evLine(t, i))))),
    el("div", { class: "sec" }, el("h3", {}, "Considered"), el("p", { class: "note" }, (c.considered.length ? c.considered : ["Nobody"]).join(" · "))),
  ];
}
function paneEmail(t, gmail) {
  const d = t.steps.draft, s = t.steps.send;
  if (!d) return [el("p", { class: "note" }, "No email: not qualified or no contact.")];
  const rv = d.review;
  return [
    t.status === "held" ? el("p", { class: "note ember" }, "Held, not sent. ", d.validator_errors.map(plainCheck).join(" ")) : s?.id ? el("p", { class: "note accent" }, `Sent to ${s.to} · ${when(s.sent_at)}`) : null,
    rv && el("div", { class: "scores" }, [["Overall", rv.score], ["Specific", rv.specificity], ["Relevant", rv.relevance], ["Would reply", rv.reply_likelihood]].map(([l, v]) => el("div", {}, el("b", {}, v), el("span", {}, l)))),
    rv && el("p", { class: "note" }, rv.critique),
    el("div", { class: "sec" }, el("div", { class: "subj" }, d.subject), el("div", { class: "mail" }, d.text),
      gmail && el("a", { href: gmail, target: "_blank", rel: "noopener noreferrer" }, "Open in Gmail, to yourself")),
  ];
}
function paneActivity(t) {
  const st = t.steps, items = [];
  if (st.scrape) items.push(["Read the website", st.scrape.map((p) => `${p.path} ${p.outcome.toLowerCase()}`).join(" · ")]);
  (st.qualify?.iterations || []).forEach((it) => items.push([`Research: ${TOOL[it.tool] || it.tool}`, `${it.rationale} ${it.score_before} → ${it.score_after ?? "?"}`]));
  if (st.qualify) items.push([`Verdict: ${VERDICT[st.qualify.verdict]}`, st.qualify.stop_reason]);
  if (st.contact) items.push(["Contact", st.contact.chosen ? `${st.contact.chosen.first_name} ${st.contact.chosen.last_name}` : "None found"]);
  (st.draft?.attempts || []).forEach((a, i) => items.push([`Draft ${i + 1}`, a.review ? `Reviewer ${a.review.score} / 10` : a.validator_errors.map(plainCheck).join(" ")]));
  if (st.send) items.push(["Sent", st.send.id ? `${st.send.to} · ${when(st.send.sent_at)}` : st.send.error]);
  items.push([`Done: ${status(t)[0]}`, `${t.seconds ?? "?"}s · ${t.llm_calls.length} model calls`]);
  return [el("ul", { class: "timeline" }, items.map(([h, b]) => el("li", {}, el("b", {}, h), el("div", {}, b))))];
}
function drawPane() {
  const { trace, gmail } = STATE.detail;
  const panes = { overview: paneOverview, contact: paneContact, email: (t) => paneEmail(t, gmail), activity: paneActivity };
  $$(".tabs .tab").forEach((b) => b.classList.toggle("on", b.dataset.pane === STATE.pane));
  $("#d-body").replaceChildren(...panes[STATE.pane](trace).flat(3).filter(Boolean));
  $("#d-body").scrollTop = 0;
  if (motionOK()) gsap.from("#d-body > *", { y: 14, autoAlpha: 0, stagger: 0.05, duration: 0.7, ease: "expo.out" });
}
let lastFocus = null;
async function openAccount(domain, pane = "overview") {
  try { STATE.detail = await api(`/api/account/${encodeURIComponent(domain)}`); } catch (e) { showJob({ running: false, done: [], error: e.message }); return; }
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
  if (motionOK()) { gsap.fromTo("#drawer", { xPercent: 12, autoAlpha: 0 }, { xPercent: 0, autoAlpha: 1, duration: 0.8, ease: "expo.out" }); gsap.fromTo("#scrim", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.5 }); }
  drawPane();
  $("#d-close").focus();
}
function closeDrawer() {
  if ($("#drawer").hidden) return;
  $("#drawer").hidden = $("#scrim").hidden = true; STATE.open = null;
  window.lenis?.start();
  lastFocus?.focus?.();
}
function trapFocus(e) {
  if (e.key !== "Tab" || $("#drawer").hidden) return;
  const f = $$('#drawer a[href], #drawer button, #drawer select, #drawer textarea').filter((n) => n.offsetParent);
  if (!f.length) return;
  const [a, z] = [f[0], f[f.length - 1]];
  if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); } else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
}

// ---------- motion: Lenis + ScrollTrigger pins, SplitText hero, Vanta fog ----------
const motionOK = () => typeof gsap !== "undefined" && !matchMedia("(prefers-reduced-motion: reduce)").matches;
let mm = null, fog = null;
function startFog() {
  if (fog || !window.VANTA || !window.THREE || !matchMedia("(min-width: 901px)").matches || !motionOK()) return;
  try {
    fog = VANTA.FOG({ el: "#fog", THREE: window.THREE, mouseControls: true, touchControls: false, gyroControls: false, minHeight: 200, minWidth: 200,
      highlightColor: 0x3d4bff, midtoneColor: 0x1a1c4a, lowlightColor: 0x0b0b0d, baseColor: 0x0b0b0d, blurFactor: 0.72, speed: 0.7, zoom: 0.75 });
  } catch { fog = null; }   // no WebGL: the hero keeps its plain ground
}
function stopFog() { fog?.destroy(); fog = null; }
new IntersectionObserver(([e]) => (e.isIntersecting && STATE.view === "home" ? startFog() : stopFog())).observe($("#ch-hero"));

function setupMotion() {
  if (!motionOK() || typeof ScrollTrigger === "undefined") return;
  mm?.revert();
  mm = gsap.matchMedia();
  mm.add({ desk: "(min-width: 901px)", phone: "(max-width: 900px)" }, ({ conditions: { desk } }) => {
    const s = Number($("#clock").dataset.end || 0);
    if (!STATE.intro && document.fonts.status === "loaded") {     // hero lines rise out of their masks, once fonts are in
      STATE.intro = true;
      const split = SplitText.create("#headline", { type: "lines", mask: "lines" });
      gsap.timeline({ defaults: { ease: "expo.out" } })
        .from(split.lines, { yPercent: 110, duration: 1.4, stagger: 0.12 })
        .from(".facts li", { y: 24, autoAlpha: 0, stagger: 0.08, duration: 1 }, "-=0.9")
        .from(".bar", { y: -20, autoAlpha: 0, duration: 1 }, "<");
    }
    gsap.to("#progress", { scaleX: 1, ease: "none", scrollTrigger: { trigger: "#view-home", start: "top top", end: "bottom bottom", scrub: true } });
    gsap.to(".hero-in", { yPercent: -18, autoAlpha: 0, ease: "none", scrollTrigger: { trigger: "#ch-hero", start: "top top", end: "bottom 20%", scrub: true } });
    gsap.to("#fog", { scale: 1.15, ease: "none", scrollTrigger: { trigger: "#ch-hero", start: "top top", end: "bottom top", scrub: true } });

    // Time: 17:30 by hand collapses to the autopilot's seconds
    const t = { v: MANUAL };
    const time = gsap.timeline({ scrollTrigger: { trigger: "#ch-time", start: desk ? "top top" : "top 70%", end: desk ? "+=160%" : "+=1", pin: desk, scrub: desk ? 1 : false } });
    time.fromTo(t, { v: MANUAL }, { v: s, ease: "power3.inOut", duration: 1, onUpdate: () => {
        $("#clock").textContent = clock(t.v);
        $("#clock-who").textContent = t.v > s + 1 ? "By hand, per company" : "Autopilot, per company";
      } })
      .fromTo("#clock-bar", { scaleX: 1 }, { scaleX: s / MANUAL, ease: "power3.inOut", duration: 1 }, 0)
      .fromTo("#clock-note", { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.2 }, 0.85);

    // Agent loop: each researched score slides across the 60 line, and its verdict flips
    const loop = gsap.timeline({ scrollTrigger: { trigger: "#ch-loop", start: desk ? "top top" : "top 70%", end: desk ? "+=180%" : "+=1", pin: desk, scrub: desk ? 1 : false } });
    loop.from("#loop-big", { y: 40, autoAlpha: 0, duration: 0.3 });
    $$("#ch-loop .db-row").forEach((row, i) => {
      const dot = $(".db-dot.to", row), at = 0.3 + i * 0.35;
      loop.from(row, { y: 30, autoAlpha: 0, duration: 0.25 }, at - 0.15)
        .from($(".db-line", row), { scaleX: 0, transformOrigin: "left center", duration: 0.5, ease: "power2.inOut" }, at)
        .from(dot, { x: () => (Number(dot.dataset.shift) / 100) * dot.parentElement.clientWidth, duration: 0.5, ease: "power2.inOut" }, at)
        .fromTo($(".v-from", row), { yPercent: 0 }, { yPercent: -100, duration: 0.2 }, at + 0.35)
        .fromTo($(".v-to", row), { yPercent: 100 }, { yPercent: 0, duration: 0.2 }, at + 0.35);
    });

    // Funnel: bars draw out and each count runs up
    const fn = gsap.timeline({ scrollTrigger: { trigger: "#ch-funnel", start: desk ? "top top" : "top 70%", end: desk ? "+=120%" : "+=1", pin: desk, scrub: desk ? 1 : false } });
    fn.from("#funnel-big", { y: 40, autoAlpha: 0, duration: 0.3 })
      .from("#ch-funnel .fn-row", { y: 30, autoAlpha: 0, stagger: 0.12, duration: 0.3 }, 0.15)
      .from("#ch-funnel .fn-bar span", { scaleX: 0, transformOrigin: "left center", stagger: 0.12, duration: 0.5, ease: "power2.out" }, 0.25)
      .from("#ch-funnel .fn-out", { autoAlpha: 0, stagger: 0.12, duration: 0.2 }, 0.5);
    $$("#ch-funnel [data-count]").forEach((n, i) => fn.from(n, { textContent: 0, snap: { textContent: 1 }, duration: 0.5, ease: "power2.out" }, 0.25 + i * 0.12));

    // Emails: letters deal onto a stack, the earlier ones settling back
    const letters = $$("#stack .letter");
    const mail = gsap.timeline({ scrollTrigger: { trigger: "#ch-mail", start: desk ? "top top" : "top 70%", end: desk ? `+=${80 + letters.length * 50}%` : "+=1", pin: desk, scrub: desk ? 1 : false } });
    mail.from("#mail-big", { y: 40, autoAlpha: 0, duration: 0.3 });
    letters.forEach((l, i) => {
      mail.from(l, { yPercent: 60, rotateX: -12, autoAlpha: 0, duration: 0.5, ease: "power3.out" }, 0.3 + i * 0.45);
      if (desk) letters.slice(0, i).forEach((p) => mail.to(p, { scale: `-=${0.025}`, autoAlpha: "-=0.18", duration: 0.4 }, 0.3 + i * 0.45));
    });

    // Needs you: rows slide in, the closing link rises
    gsap.from("#ch-queue .q-row, #ch-queue .empty-line", { x: -40, autoAlpha: 0, stagger: 0.1, duration: 1, ease: "expo.out", scrollTrigger: { trigger: "#ch-queue", start: "top 65%" } });
    gsap.from("#ch-queue .ch-big, #ch-queue .link-cta", { y: 40, autoAlpha: 0, stagger: 0.15, duration: 1.2, ease: "expo.out", scrollTrigger: { trigger: "#ch-queue", start: "top 75%" } });

    // chapter index follows the scroll (pinned chapters sit inside their pin spacer)
    ScrollTrigger.create({ trigger: "#view-home", start: "top top", end: "bottom bottom", onUpdate: markChapter });
    markChapter();
  });
}

function markChapter() {
  const mid = innerHeight / 2;
  const cur = $$(".ch").find((c) => { const r = (c.parentElement.classList.contains("pin-spacer") ? c.parentElement : c).getBoundingClientRect(); return r.top <= mid && r.bottom > mid; });
  if (cur) $$(".index a").forEach((a) => a.classList.toggle("on", a.dataset.ch === cur.id));
}

// ---------- views, data, runs ----------
function go(view) {
  STATE.view = view;
  $$(".nav-link").forEach((b) => b.classList.toggle("on", b.dataset.view === view));
  $$(".view").forEach((v) => (v.hidden = v.id !== `view-${view}`));
  $(".index").classList.toggle("off", view !== "home");
  window.lenis ? window.lenis.scrollTo(0, { immediate: true }) : window.scrollTo(0, 0);
  render();
  if (view === "home") { setupMotion(); startFog(); } else { mm?.revert(); mm = null; stopFog(); }
  if (typeof ScrollTrigger !== "undefined") ScrollTrigger.refresh();
  if (motionOK() && view !== "home") gsap.from(`#view-${view} .page-head > *, #view-${view} .filters, #view-${view} .table-wrap, #view-${view} .board`, { y: 30, autoAlpha: 0, stagger: 0.08, duration: 1, ease: "expo.out" });
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
  if (STATE.view === "home") { await document.fonts.ready; setupMotion(); startFog(); }
}
let polling = null;
function showJob(j) {
  const box = $("#job");
  box.classList.toggle("busy", !!j.running); box.classList.toggle("err", !!j.error);
  $("#run-btn").disabled = j.running;
  box.textContent = j.running ? `Researching ${j.current || "…"}` : j.error ? `Run stopped: ${j.error}` : j.done.length ? `Done: ${j.done.map((d) => `${d.domain} ${status(d)[0].toLowerCase()}`).join(", ")}` : "";
  if (j.running && !polling) polling = setInterval(async () => showJob(await api("/api/job")), 3000);
  if (!j.running && polling) { clearInterval(polling); polling = null; load(); }
}
async function run(domains) { try { showJob(await api("/api/run", { domains })); } catch (e) { showJob({ running: false, done: [], error: e.message }); } }

// ---------- wiring ----------
$$("[data-view]").forEach((b) => b.addEventListener("click", (e) => { e.preventDefault(); go(b.dataset.view); }));
$$(".tabs .tab").forEach((b) => b.addEventListener("click", () => { STATE.pane = b.dataset.pane; drawPane(); }));
$$(".index a").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); const t = $(a.getAttribute("href")); window.lenis ? window.lenis.scrollTo(t, { duration: 1.6 }) : t.scrollIntoView(); }));
$("#search").addEventListener("input", renderAccounts);
$("#d-close").addEventListener("click", closeDrawer);
$("#scrim").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); trapFocus(e); });
$("#run-form").addEventListener("submit", (e) => { e.preventDefault(); const d = $("#run-input").value.split(/[\s,]+/).filter(Boolean); if (d.length) { run(d); $("#run-input").value = ""; } });
$("#review").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target, body = Object.fromEntries(["stage", "lead_agrees", "edit_level", "replied", "notes"].map((k) => [k, f[k].value]));
  if (body.stage === "replied" && !body.replied) body.replied = f.replied.value = "y";
  try { await api(`/api/account/${encodeURIComponent(STATE.open)}/review`, body); $("#saved").textContent = "Saved"; await load(); } catch (err) { $("#saved").textContent = `Not saved: ${err.message}`; }
});
if (typeof gsap !== "undefined") gsap.registerPlugin(...[window.ScrollTrigger, window.SplitText].filter(Boolean));
if (motionOK() && typeof Lenis !== "undefined") {
  window.lenis = new Lenis({ lerp: 0.085, wheelMultiplier: 0.9 });
  if (window.ScrollTrigger) window.lenis.on("scroll", ScrollTrigger.update);
  gsap.ticker.add((t) => window.lenis.raf(t * 1000));
  gsap.ticker.lagSmoothing(0);
}
load().catch((err) => { $("#headline").textContent = "Could not load accounts."; $("#hero-facts").replaceChildren(el("li", {}, el("span", {}, `${err.message}. Is app.py running?`))); });

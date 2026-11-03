// Outbound CRM. All page data comes from scraped websites: render it with textContent only, never innerHTML.
const $ = (s) => document.querySelector(s);
const LANES = [
  ["qualified", "Qualified"], ["needs_review", "Needs review"], ["contacted", "Contacted"], ["replied", "Replied"], ["meeting", "Meeting"],
  ["won", "Won"], ["lost", "Lost"], ["needs_data", "Needs data"], ["not_fit", "Not a fit"],
];
const STATE = { accounts: [], stages: [], view: "board", open: null, pane: "overview", detail: null };

function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k === "on") Object.entries(v).forEach(([e, f]) => n.addEventListener(e, f));
    else if (k === "href") { if (/^https?:\/\//i.test(v)) n.href = v; }   // never javascript: URLs
    else n.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) n.append(c instanceof Node ? c : String(c));
  return n;
}

const pill = (text, tone = "") => el("span", { class: `pill ${tone}` }, text);
const tone = (v) => ({ PRIORITY: "good", QUALIFY: "good", sent: "good", contacted: "acc", replied: "good", meeting: "good",
  won: "good", NURTURE: "warn", INSUFFICIENT_DATA: "warn", no_contact: "warn", insufficient_data: "warn", held: "warn", needs_review: "warn",
  REJECT: "bad", DISQUALIFIED: "bad", failed: "bad", lost: "bad", not_qualified: "bad" })[v] || "";
const scoreTone = (s) => (s >= 7 ? "good" : s >= 5 ? "warn" : "bad");

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body) } : {});
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

// ---------- list views ----------
function visible() {
  const q = $("#search").value.trim().toLowerCase();
  return STATE.accounts.filter((a) => !q || [a.domain, a.name, a.contact, a.one_liner].join(" ").toLowerCase().includes(q));
}

function kpis() {
  const a = STATE.accounts, sent = a.filter((x) => x.sent_at), scores = a.map((x) => x.ai_score).filter((x) => x != null);
  const secs = a.map((x) => x.seconds).filter(Boolean), changed = a.filter((x) => x.fixed && x.fixed !== x.verdict);
  const replied = a.filter((x) => x.review.replied === "y").length;
  const avg = (xs) => xs.reduce((s, x) => s + x, 0) / xs.length;
  const items = [
    [a.length, "Accounts researched"],
    [a.filter((x) => ["QUALIFY", "PRIORITY"].includes(x.verdict)).length, "Qualified"],
    [sent.length, "Emails sent"],
    [replied ? `${replied}/${sent.length}` : "–", "Replies"],
    [scores.length ? `${avg(scores).toFixed(1)}/10` : "–", "Avg email score"],
    [secs.length ? `${Math.round(avg(secs))}s` : "–", "Per account (manual: 15-20 min)"],
    [changed.length, "Verdicts fixed by agent loop"],
  ];
  $("#kpis").replaceChildren(...items.map(([v, l]) => el("div", { class: "kpi" }, el("b", {}, v), el("span", {}, l))));
}

function card(a) {
  return el("div", { class: "card", tabindex: "0", on: { click: () => openAccount(a.domain),
    keydown: (e) => e.key === "Enter" && openAccount(a.domain) } },
    el("div", { class: "t" }, a.name), el("div", { class: "d" }, a.domain),
    a.contact && el("div", { class: "who" }, "👤 ", a.contact),
    el("div", { class: "row" },
      a.verdict && pill(`${a.verdict} ${a.score}`, tone(a.verdict)),
      a.ai_score != null && pill(`email ${a.ai_score}/10`, scoreTone(a.ai_score)),
      a.fixed && a.fixed !== a.verdict && pill("agent loop", "acc")));
}

function board() {
  const by = Object.groupBy ? Object.groupBy(visible(), (a) => a.lane) : visible().reduce((m, a) => ((m[a.lane] ||= []).push(a), m), {});
  $("#board").replaceChildren(...LANES.map(([key, label]) => el("section", { class: "lane" },
    el("h3", {}, label, el("span", {}, (by[key] || []).length)), ...(by[key] || []).map(card))));
}

function table() {
  const head = ["Account", "Status", "Fixed → Agent", "Score", "Contact", "Email score", "Stage", "Time"];
  const rows = visible().map((a) => el("tr", { on: { click: () => openAccount(a.domain) } },
    el("td", {}, el("b", {}, a.name), el("div", { class: "muted" }, a.domain)),
    el("td", {}, pill(a.status, tone(a.status))),
    el("td", {}, a.fixed ? `${a.fixed} → ${a.verdict}` : ""),
    el("td", { class: "num" }, a.score ?? ""),
    el("td", {}, a.contact || ""),
    el("td", { class: "num" }, a.ai_score != null ? `${a.ai_score}/10` : ""),
    el("td", {}, pill(LANES.find(([k]) => k === a.lane)?.[1] || a.lane, tone(a.lane))),
    el("td", { class: "num" }, a.seconds ? `${Math.round(a.seconds)}s` : "")));
  $("#table").replaceChildren(el("table", {}, el("thead", {}, el("tr", {}, head.map((h) => el("th", {}, h)))),
    el("tbody", {}, rows)));
}

function render() {
  kpis();
  $("#board").hidden = STATE.view !== "board";
  $("#table").hidden = STATE.view !== "table";
  STATE.view === "board" ? board() : table();
}

async function load() {
  const data = await api("/api/accounts");
  Object.assign(STATE, { accounts: data.accounts, stages: data.stages });
  showJob(data.job);
  render();
}

// ---------- account drawer ----------
const evidence = (t, id) => t.evidence.find((e) => e.id === id);
function evLine(t, id) {
  const e = evidence(t, id);
  if (!e) return el("div", { class: "ev" }, `${id} (missing)`);
  return el("div", { class: "ev" }, `${id} “${e.quote.slice(0, 160)}” `,
    el("a", { href: e.source_url, target: "_blank", rel: "noopener noreferrer" }, "source"),
    e.verified ? " · verified on page" : " · from web search");
}

function overview(t) {
  const q = t.steps.qualify, a = STATE.accounts.find((x) => x.domain === t.domain);
  if (!q) return [el("p", { class: "muted" }, t.reason || t.error || "Not qualified yet: the site could not be read.")];
  const sig = q.signals.map((s) => el("tr", {},
    el("td", {}, s.signal_id.replace(/_/g, " ")),
    el("td", {}, pill(s.state === "unknown" ? "unknown" : s.bucket.replace(/_/g, " "), s.points ? "good" : s.state === "unknown" ? "warn" : "")),
    el("td", { class: "num" }, `${s.points}/${s.max}`),
    el("td", {}, s.evidence_ids.map((i) => evLine(t, i)))));
  return [
    el("h4", {}, "Why this company"),
    el("div", { class: "compare" },
      el("div", { class: "box" }, el("div", { class: "muted" }, "Fixed pipeline"), el("div", { class: "big" }, a?.fixed || q.verdict),
        el("div", { class: "muted" }, `${a?.fixed_score ?? q.score}/100`)),
      el("div", { class: "arrow" }, "→"),
      el("div", { class: "box" }, el("div", { class: "muted" }, `Agent loop · ${q.iterations.length} tool calls`),
        el("div", { class: "big" }, q.verdict), el("div", { class: "muted" }, `${q.score}/100 (bounds ${q.lo}-${q.hi})`))),
    el("p", {}, q.reason),
    q.disqualifier && el("p", {}, pill(`Disqualified: ${q.disqualifier.gate_id}`, "bad"), q.disqualifier.evidence_ids.map((i) => evLine(t, i))),
    el("h4", {}, "Signals"),
    el("table", { class: "signals" }, el("thead", {}, el("tr", {}, ["Signal", "Bucket", "Pts", "Evidence"].map((h) => el("th", {}, h)))),
      el("tbody", {}, sig)),
  ];
}

function contact(t) {
  const c = t.steps.contact;
  if (!c) return [el("p", { class: "muted" }, "No contact search: only qualified companies spend a Hunter search.")];
  const who = c.chosen;
  return [
    el("h4", {}, "Point of contact"),
    who ? el("div", { class: "box" }, el("div", { class: "big" }, `${who.first_name} ${who.last_name}`),
      el("div", {}, who.position), el("div", { class: "muted" }, who.email, " · ", who.source),
      who.linkedin && el("a", { href: who.linkedin, target: "_blank", rel: "noopener noreferrer" }, "LinkedIn"))
      : el("div", { class: "box" }, "No eligible decision-maker found. Add one to contacts.csv."),
    el("h4", {}, "Why this person"),
    el("p", {}, el("b", {}, "Rule: "), c.rule_fired), el("p", {}, c.reason), c.fallback && el("p", { class: "muted" }, c.fallback),
    el("h4", {}, "Considered"), el("ul", {}, (c.considered.length ? c.considered : ["nobody"]).map((x) => el("li", {}, x))),
    t.steps.pains && [el("h4", {}, "Pain points"),
      el("ul", {}, t.steps.pains.map((p) => el("li", {}, p.text, p.evidence_ids.map((i) => evLine(t, i)))))],
  ];
}

function email(t, gmail) {
  const d = t.steps.draft, s = t.steps.send;
  if (!d) return [el("p", { class: "muted" }, "No email: the company did not qualify or has no contact.")];
  const rv = d.review;
  return [
    rv && [el("h4", {}, "Reviewer"),
      el("div", { class: "scores" }, [["Overall", rv.score], ["Specific", rv.specificity], ["Relevant", rv.relevance],
        ["Reply", rv.reply_likelihood]].map(([l, v]) => el("div", { class: "box" }, el("div", { class: "big" }, v),
        pill(l, scoreTone(v))))),
      el("p", { class: "muted" }, "Critique: ", rv.critique)],
    el("h4", {}, "Email as sent"),
    el("div", { class: "box" }, el("b", {}, "Subject: "), d.subject),
    el("div", { class: "box mail" }, d.text),
    el("p", {}, d.hook && ["Hook: ", pill(d.hook.signal_id, "acc"), evLine(t, d.hook.evidence_id)]),
    el("p", { class: "muted" }, `${d.word_count} words · validator ${d.validator_errors.length ? d.validator_errors.join("; ") : "passed"}`,
      d.attempts ? ` · ${d.attempts.length} draft(s)` : ""),
    t.status === "held" && el("p", {}, pill("Held, not sent", "warn"), " It failed the checks above after every rewrite. Fix it by hand or re-run."),
    s && el("p", {}, s.id ? pill("Sent", "good") : pill("Send failed", "bad"), " ", s.id ? `to ${s.to} · ${s.sent_at}` : s.error),
    gmail && el("a", { href: gmail, target: "_blank", rel: "noopener noreferrer" }, "Open in Gmail (to yourself)"),
  ];
}

function activity(t) {
  const items = [["Started", t.started]];
  const st = t.steps;
  if (st.scrape) items.push(["Scraped site", st.scrape.map((p) => `${p.path} ${p.outcome}`).join(" · ")]);
  if (st.extract) items.push(["Extracted profile", `${st.extract.name}: ${st.extract.one_liner}`]);
  (st.qualify?.iterations || []).forEach((it) => items.push([`Agent: ${it.tool}(${it.arg})`,
    `${it.rationale} → ${it.result} (score ${it.score_before} → ${it.score_after ?? "?"})`]));
  if (st.qualify) items.push([`Qualified: ${st.qualify.verdict}`, `stopped: ${st.qualify.stop_reason}`]);
  if (st.contact) items.push(["Contact", st.contact.chosen ? `${st.contact.chosen.first_name} ${st.contact.chosen.last_name}` : "none found"]);
  (st.draft?.attempts || []).forEach((a, i) => items.push([`Draft ${i + 1}`,
    a.review ? `reviewer ${a.review.score}/10` : `failed checks: ${a.validator_errors.join("; ")}`]));
  if (st.send) items.push(["Email sent", st.send.id ? `${st.send.to} · ${st.send.sent_at}` : st.send.error]);
  items.push([`Finished: ${t.status}`, `${t.seconds ?? "?"}s · ${t.llm_calls.length} model calls`]);
  return [el("ul", { class: "timeline" }, items.map(([h, b]) => el("li", {}, el("b", {}, h), el("div", { class: "when" }, b))))];
}

function drawPane() {
  const { trace, gmail } = STATE.detail;
  const panes = { overview, contact, email: (t) => email(t, gmail), activity };
  document.querySelectorAll(".d-tabs .tab").forEach((b) => b.classList.toggle("active", b.dataset.pane === STATE.pane));
  $("#d-body").replaceChildren(...panes[STATE.pane](trace).flat(2).filter(Boolean));
}

async function openAccount(domain) {
  STATE.detail = await api(`/api/account/${encodeURIComponent(domain)}`);
  STATE.open = domain;
  const t = STATE.detail.trace, ext = t.steps.extract || {};
  $("#d-name").textContent = ext.name || domain;
  $("#d-domain").textContent = domain;
  $("#d-domain").href = `https://${domain}`;
  $("#d-liner").textContent = ext.one_liner || "";
  const f = $("#review"), rv = STATE.detail.review;
  f.stage.replaceChildren(el("option", { value: "" }, "auto (from pipeline)"), ...STATE.stages.map((s) => el("option", { value: s }, s)));
  for (const k of ["stage", "lead_agrees", "edit_level", "replied", "notes"]) f[k].value = rv[k] || "";
  $("#saved").textContent = "";
  $("#drawer").hidden = $("#scrim").hidden = false;
  drawPane();
}

function closeDrawer() { $("#drawer").hidden = $("#scrim").hidden = true; STATE.open = null; }

// ---------- runs ----------
let polling = null;
function showJob(j) {
  const box = $("#job");
  box.classList.toggle("busy", j.running);
  $("#run-btn").disabled = j.running;
  box.textContent = j.running ? `Researching ${j.current || "…"} · ${j.queue.length} queued · ${j.done.length} done`
    : j.error ? `Run failed: ${j.error}` : j.done.length ? `Last run: ${j.done.map((d) => `${d.domain} ${d.status}`).join(", ")}` : "";
  if (j.running && !polling) polling = setInterval(poll, 3000);
  if (!j.running && polling) { clearInterval(polling); polling = null; load(); }
}
async function poll() { showJob(await api("/api/job")); }

$("#run-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const domains = $("#run-input").value.split(/[\s,]+/).filter(Boolean);
  if (!domains.length) return;
  try { showJob(await api("/api/run", { domains })); $("#run-input").value = ""; }
  catch (err) { $("#job").textContent = err.message; }
});

$("#review").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target, body = Object.fromEntries(["stage", "lead_agrees", "edit_level", "replied", "notes"].map((k) => [k, f[k].value]));
  if (body.stage === "replied" && !body.replied) body.replied = f.replied.value = "y";
  try { await api(`/api/account/${encodeURIComponent(STATE.open)}/review`, body); $("#saved").textContent = "Saved"; await load(); }
  catch (err) { $("#saved").textContent = err.message; }
});

document.querySelectorAll(".toolbar .tab").forEach((b) => b.addEventListener("click", () => {
  STATE.view = b.dataset.view;
  document.querySelectorAll(".toolbar .tab").forEach((x) => x.classList.toggle("active", x === b));
  render();
}));
document.querySelectorAll(".d-tabs .tab").forEach((b) => b.addEventListener("click", () => { STATE.pane = b.dataset.pane; drawPane(); }));
$("#search").addEventListener("input", render);
$("#d-close").addEventListener("click", closeDrawer);
$("#scrim").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => e.key === "Escape" && closeDrawer());
load().catch((err) => { $("#job").textContent = `Could not load: ${err.message}`; });

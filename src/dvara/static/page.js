// Dvara's owner page: draws what /api says, and nothing else. Every value
// goes in as text (textContent), never as markup: what a person typed is
// shown, it is never run. The key arrives after "#" in the address, is
// kept in this browser, and leaves the address bar at once.
"use strict";

const KEY = "dvara.page.token";
const EVERY = 15000;

function keep(token) {
  try { localStorage.setItem(KEY, token); } catch (_) { /* private window */ }
}
function kept() {
  try { return localStorage.getItem(KEY) || ""; } catch (_) { return ""; }
}

function takeToken() {
  const fresh = new URLSearchParams(location.hash.slice(1)).get("token");
  if (fresh) {
    keep(fresh);
    history.replaceState(null, "", location.pathname + location.search);
    return fresh;
  }
  return kept();
}

const token = takeToken();

function h(spec, attrs, ...kids) {
  const [tag, ...classes] = spec.split(".");
  const el = document.createElement(tag || "div");
  if (classes.length) el.className = classes.join(" ");
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v !== undefined && v !== null && v !== false) el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

class Unauthorized extends Error {}

async function api(path) {
  let res;
  try {
    res = await fetch(path, { headers: { Authorization: `Bearer ${token}` },
                              cache: "no-store" });
  } catch (_) {
    throw new Error("the browser couldn't reach the page's server. Is dvara page " +
                    "still running? An ad blocker can also stop its requests.");
  }
  if (res.status === 401) throw new Unauthorized();
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `${res.status}`);
  return body;
}

const usd = (n) => (n < 0.01 && n > 0 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`);

function ago(iso) {
  if (!iso) return "";
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return iso;
  const s = Math.max(0, (Date.now() - then) / 1000);
  if (s < 90) return "just now";
  if (s < 5400) return `${Math.round(s / 60)} minutes ago`;
  if (s < 129600) return `${Math.round(s / 3600)} hours ago`;
  if (s < 86400 * 45) return `${Math.round(s / 86400)} days ago`;
  return new Date(then).toLocaleDateString();
}

function turns(n, unpriced) {
  const t = `${n} turn${n === 1 ? "" : "s"}`;
  if (!unpriced) return t;
  return unpriced === n ? `${t}, no price (local model)` : `${t}, ${unpriced} with no price`;
}

// -- header ---------------------------------------------------------------------

function drawStatus(st) {
  const badge = st.serving
    ? h("span.badge.serving", { title: st.url || "" },
        st.since ? `door open · since ${ago(st.since)}` : "door open")
    : h("span.badge.down", { title: "start it: dvara serve" }, "door not running");
  document.getElementById("facts").replaceChildren(
    badge, h("span", {}, `you: ${st.owner}`),
    h("span", {}, `${st.people} ${st.people === 1 ? "person" : "people"} · ` +
      `${st.agents} agent${st.agents === 1 ? "" : "s"}`),
    h("span", {}, `dvara ${st.version}`));
  const box = document.getElementById("problems");
  box.hidden = !(st.problems && st.problems.length);
  if (!box.hidden) box.replaceChildren(h("ul", {}, st.problems.map((p) => h("li", {}, p))));
}

// -- people ---------------------------------------------------------------------

function personCard(p) {
  const today = p.today;
  const limit = p.allowance.per_day;
  let money;
  if (limit !== null && limit !== undefined) {
    const used = limit > 0 ? Math.min(1, today.spent / limit) : 1;
    money = [
      h("div.money", {}, h("span", {}, `${usd(today.spent)} of ${usd(limit)} today`),
        h("span", {}, `${usd(today.left)} left`)),
      h("div.meter" + (used >= 1 ? ".full" : ""), { role: "img",
        "aria-label": `${Math.round(used * 100)}% of today's allowance used` },
        bar(used)),
    ];
  } else {
    money = [h("div.money", {}, h("span", {}, `${usd(today.spent)} today`),
               h("span", {}, "no daily limit"))];
  }
  const agents = p.agents === null ? "every agent" : (p.agents.join(", ") || "no agents");
  return h("article.card", {},
    h("div.card-head", {}, h("h3", {}, p.id, p.owner ? h("span.you", {}, "you") : null),
      p.permissions ? h("span.chip", { title: "how far their agents may go" },
                        p.permissions) : null),
    ...money,
    h("div.meta", {}, `${turns(today.turns, today.unpriced)} today · ` +
      `${usd(p.week.spent)} over 7 days (${turns(p.week.turns, p.week.unpriced)})`),
    h("div.facts-row", {},
      h("span", {}, `agents: ${agents}`),
      h("span", {}, p.channels.length ? `reached on ${p.channels.join(", ")}`
                                      : "no channel"),
      p.accounts ? h("span", {}, `accounts: ${p.accounts}`) : null,
      p.allowance.per_turn != null ? h("span", {}, `${usd(p.allowance.per_turn)} a turn`)
                                   : null));
}

// a width set through the DOM: the policy allows no style="" attributes
function bar(used) {
  const fill = h("span");
  fill.style.width = `${Math.round(used * 100)}%`;
  return fill;
}

function drawPeople(people) {
  document.getElementById("n-people").textContent = `${people.length}`;
  const box = document.getElementById("people");
  box.replaceChildren(...(people.length ? people.map(personCard)
    : [h("p.empty", {}, "Nobody in the actors file yet.")]));
  fill("who", people.map((p) => p.id), "everyone");
}

function drawAgents(agents) {
  document.getElementById("n-agents").textContent = `${agents.length}`;
  document.getElementById("agents").replaceChildren(...(agents.length
    ? agents.map((a) => h("article.card", {}, h("h3", {}, a.name),
        h("div.meta", {}, a.people.length ? `for ${a.people.join(", ")}`
                                          : "nobody may use it")))
    : [h("p.empty", {}, "No agents in the root folder.")]));
  fill("which", agents.map((a) => a.name), "every agent");
}

function fill(id, values, all) {
  const sel = document.getElementById(id);
  const was = sel.value;
  sel.replaceChildren(h("option", { value: "" }, all),
                      ...values.map((v) => h("option", { value: v }, v)));
  sel.value = values.includes(was) ? was : "";
}

// -- runs -----------------------------------------------------------------------

const HOW = { end_turn: "finished", held: "waiting for an answer", error: "failed",
              refused: "turned away", cancelled: "cancelled", max_tokens: "ran out of room",
              files: "/files", new: "/new", accounts: "/accounts" };
const FINE = new Set(["end_turn", "held", "files", "new", "accounts", "cancelled"]);

function runCard(r) {
  const cost = r.cost_usd === null ? "no price" : usd(r.cost_usd);
  const how = HOW[r.stop_reason] || r.stop_reason;
  const card = h("article.run" + (FINE.has(r.stop_reason) ? "" : ".bad"), {},
    h("div.run-head", {},
      h("span.run-who", {}, `${r.actor} → ${r.agent}`),
      h("span.run-meta", { title: r.started_at }, `${ago(r.started_at)} · ${how} · ${cost}`
        + (r.unattended ? " · scheduled" : ""))),
    r.tools.length ? h("div.steps", {}, r.tools.map((t) => h(
      "span.step" + (t.refusal && t.refusal !== "held" ? ".refused" : ""),
      { title: t.refusal ? `refused: ${t.refusal}` : "ran" }, t.name))) : null);
  if (r.message !== null) {
    // a scheduled turn's message is the schedule's prompt: nobody typed it
    card.append(h("div.words", {}, h("b", {}, r.unattended ? "Schedule: " : "You: "),
                  r.message,
                  r.reply ? ["\n", h("b", {}, "Agent: "), r.reply] : null));
  } else {
    card.append(h("span.private", {}, "What was said stays theirs."));
  }
  return card;
}

async function drawRuns() {
  const who = document.getElementById("who").value;
  const which = document.getElementById("which").value;
  const q = new URLSearchParams({ limit: "60" });
  if (who) q.set("actor", who);
  if (which) q.set("agent", which);
  const data = await api(`/api/runs?${q}`);
  document.getElementById("runs").replaceChildren(...(data.runs.length
    ? data.runs.map(runCard) : [h("p.empty", {}, "No turns recorded yet.")]));
}

// -- the loop -------------------------------------------------------------------

async function refresh() {
  const gate = document.getElementById("gate");
  if (!token) { gate.hidden = false; return; }
  try {
    const [st, people, agents] = await Promise.all([
      api("/api/status"), api("/api/people"), api("/api/agents")]);
    gate.hidden = true;
    drawStatus(st);
    drawPeople(people.people);
    drawAgents(agents.agents);
    await drawRuns();
    document.getElementById("updated").textContent =
      `Updated ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    if (err instanceof Unauthorized) { gate.hidden = false; return; }
    document.getElementById("updated").textContent = `Couldn't read it: ${err.message}`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  for (const id of ["who", "which"]) {
    document.getElementById(id).addEventListener("change", () => drawRuns().catch(() => {}));
  }
  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, EVERY);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
});

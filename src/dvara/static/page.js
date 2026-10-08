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

async function api(path, payload) {
  let res;
  const init = { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" };
  if (payload !== undefined) {
    init.method = "POST";
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(payload);
  }
  try {
    res = await fetch(path, init);
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

// -- waiting for you ----------------------------------------------------------
//
// Redrawn only when what is waiting changes: a choice half made on a held
// turn must survive the next refresh.

let waitingKey = null;

function askCard(a) {
  const say = h("div.meta", {});
  const yes = h("button.btn.go", { type: "button" }, "Allow");
  const no = h("button.btn", { type: "button" }, "Refuse");
  const decide = async (approve) => {
    yes.disabled = no.disabled = true;
    say.textContent = approve ? "Allowing…" : "Refusing…";
    try {
      await api(`/api/asks/${encodeURIComponent(a.id)}`, { approve });
      say.textContent = approve ? "Allowed. The turn carries on." : "Refused.";
    } catch (err) {
      say.textContent = `Couldn't: ${err.message}`;
      yes.disabled = no.disabled = false;
    }
    waitingKey = null;
  };
  yes.addEventListener("click", () => decide(true));
  no.addEventListener("click", () => decide(false));
  return h("article.run.ask", {},
    h("div.run-head", {}, h("span.run-who", {}, `${a.agent} asks to use ${a.tool}`),
      h("span.run-meta", { title: a.asked_at }, ago(a.asked_at))),
    a.picture && /^[A-Za-z0-9+/=]+$/.test(a.picture)
      ? h("img.ask-picture", { src: `data:image/png;base64,${a.picture}`,
                               alt: "the phone's screen; a tap lands where it is ringed" })
      : null,
    h("div.cmd", {}, a.summary),
    h("div.actions", {}, yes, no), say);
}

function holdCard(hd) {
  const choice = {};
  const say = h("div.meta", {});
  const go = h("button.btn.go", { type: "button" }, "Carry on");
  const rows = hd.calls.map((c) => {
    const name = `hold-${hd.id}-${c.id}`;
    const allow = h("input", { type: "radio", name, value: "allow" });
    const refuse = h("input", { type: "radio", name, value: "refuse" });
    const why = h("input.reason", { type: "text", placeholder: "why not (optional)",
                                     "aria-label": `why not ${c.tool}`, hidden: "" });
    allow.addEventListener("change", () => { choice[c.id] = true; why.hidden = true; });
    refuse.addEventListener("change", () => { choice[c.id] = false; why.hidden = false; });
    why.addEventListener("input", () => { choice[c.id] = why.value.trim() || false; });
    return h("div.call", {},
      h("div.cmd", {}, `${c.tool}: ${c.summary}`),
      h("div.choices", {}, h("label", {}, allow, " Allow"), h("label", {}, refuse, " Refuse"),
        why));
  });
  go.addEventListener("click", async () => {
    const missing = hd.calls.filter((c) => !(c.id in choice));
    if (missing.length) { say.textContent = "Choose Allow or Refuse for each one first."; return; }
    go.disabled = true;
    say.textContent = "Carrying on… (this runs the rest of the turn)";
    try {
      const r = await api(`/api/holds/${encodeURIComponent(hd.id)}`, { answers: choice });
      say.replaceChildren(h("b", {}, "Agent: "), r.text || "(no reply)");
    } catch (err) {
      say.textContent = `Couldn't: ${err.message}`;
      go.disabled = false;
    }
    waitingKey = null;
  });
  return h("article.run.ask", {},
    h("div.run-head", {}, h("span.run-who", {}, `${hd.agent} stopped to ask you`),
      h("span.run-meta", { title: hd.held_at }, `held ${ago(hd.held_at)}`)),
    ...rows, h("div.actions", {}, go), say);
}

async function drawWaiting() {
  const data = await api("/api/waiting");
  const items = [...data.asks.map((a) => `a${a.id}`), ...data.holds.map((x) => `h${x.id}`)];
  const key = JSON.stringify([data.door.reachable, data.door.why, items]);
  const count = items.length;
  document.getElementById("n-waiting").textContent = count ? `${count}` : "";
  if (key === waitingKey) return;
  waitingKey = key;
  const box = document.getElementById("waiting");
  if (!data.door.reachable) {
    box.replaceChildren(h("p.empty", {}, `Nothing to answer here: ${data.door.why}.`));
    return;
  }
  box.replaceChildren(...(count
    ? [...data.asks.map(askCard), ...data.holds.map(holdCard)]
    : [h("p.empty", {}, "Nothing is waiting for you.")]));
}

// -- schedules and files -------------------------------------------------------------

function size(n) {
  if (n < 1024) return `${n} bytes`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function soon(iso) {
  if (!iso) return "";
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return iso;
  const s = (then - Date.now()) / 1000;
  if (s < 0) return "due now";
  if (s < 5400) return `in ${Math.max(1, Math.round(s / 60))} minutes`;
  if (s < 129600) return `in ${Math.round(s / 3600)} hours`;
  return new Date(then).toLocaleString();
}

function scheduleCard(sc) {
  const last = sc.last ? `last ${sc.last.outcome || "?"}` +
    (sc.last.at ? ` ${ago(sc.last.at)}` : "") : "not run yet";
  return h("article.run", {},
    h("div.run-head", {},
      h("span.run-who", {}, `${sc.person} · ${sc.agent || "?"}`),
      h("span.run-meta", {}, sc.state === "active"
        ? `next ${soon(sc.next_at)}` : sc.state)),
    h("div.who", {}, sc.sentence),
    sc.paused_because ? h("div.warn", {}, `Paused: ${sc.paused_because}`) : null,
    h("div.meta", {}, last),
    sc.prompt !== null && sc.prompt !== undefined
      ? h("div.words", {}, sc.prompt)
      : h("div.private", {}, "What it asks is theirs."));
}

async function drawSchedules() {
  const data = await api("/api/schedules");
  const box = document.getElementById("schedules");
  document.getElementById("n-schedules").textContent =
    data.schedules.length ? `${data.schedules.length}` : "";
  const rows = [];
  if (!data.samay.found) {
    rows.push(h("p.empty", {}, data.samay.why));
  } else if (!data.schedules.length) {
    rows.push(h("p.empty", {}, "Nobody here has a schedule."));
  }
  rows.push(...data.schedules.map(scheduleCard));
  if (data.samay.page) {
    rows.push(h("p.meta", {}, "Change them on ",
      h("a", { href: data.samay.page, target: "_blank", rel: "noopener noreferrer" },
        "Samay's page"), "."));
  }
  box.replaceChildren(...rows);
}

let filesSeen = "";

async function drawFiles() {
  const data = await api("/api/files");
  const key = JSON.stringify(data.folders);
  if (key === filesSeen) return;          // a file open below stays open
  filesSeen = key;
  const box = document.getElementById("files");
  const total = data.folders.reduce((n, f) => n + f.count, 0);
  document.getElementById("n-files").textContent = total ? `${total}` : "";
  if (!data.folders.length) {
    box.replaceChildren(h("p.empty", {}, "No agent has a folder for anyone yet."));
    return;
  }
  box.replaceChildren(...data.folders.map(folderCard));
}

function folderCard(f) {
  const list = h("ul.file-list", {}, f.files.map((file) => {
    const name = f.owner
      ? h("button.name", { type: "button", title: "open it here" }, file.path)
      : h("span.name", {}, file.path);
    if (f.owner) name.addEventListener("click", () => openFile(f.agent, file.path));
    return h("li", {}, name,
      h("span.when", { title: file.modified }, `${size(file.size)} · ${ago(file.modified)}`));
  }));
  return h("article.card", {},
    h("div.card-head", {},
      h("h3", {}, f.person, f.owner ? h("span.you", {}, "you") : null),
      h("span.chip", {}, f.agent)),
    h("div.meta", {}, f.count
      ? `${f.count} file${f.count === 1 ? "" : "s"}, ${size(f.bytes)}`
      : "empty"),
    f.count ? list : null,
    f.count > f.files.length
      ? h("div.meta", {}, `The newest ${f.files.length} of ${f.count}.`) : null);
}

async function openFile(agent, path) {
  const view = document.getElementById("file-view");
  view.hidden = false;
  const close = h("button.btn", { type: "button" }, "Close");
  close.addEventListener("click", () => { view.hidden = true; });
  const head = h("div.card-head", {}, h("h3", {}, `${agent} / ${path}`), close);
  try {
    const q = `agent=${encodeURIComponent(agent)}&path=${encodeURIComponent(path)}`;
    const f = await api(`/api/file?${q}`);
    view.replaceChildren(head,
      h("div.meta", {}, size(f.size) + (f.truncated ? " — the first 256 KB" : "")),
      f.binary ? h("p.empty", {}, "Not text, so it isn't shown here. Send /file " +
                   `${path} in your chat to get it.`)
               : h("pre", {}, f.text));
  } catch (err) {
    view.replaceChildren(head, h("p.warn", {}, `Couldn't open it: ${err.message}`));
  }
  view.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
    await drawWaiting();
    await Promise.all([drawSchedules(), drawFiles()]);
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
  // a question gives up after two minutes (by default): look more often
  setInterval(() => { if (!document.hidden && token) drawWaiting().catch(() => {}); }, 5000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
});

"""Demo Store — supports the S3 milestone (2026-11-16).

A tiny store completely separated from the main project: it only shares the venv,
runs in its own terminal on a different port (9000), and its job is to test the
integration with the project's public API (contract §8.3):

  POST /api/v1/data                          (X-API-Key) — upload the catalog
  POST /api/v1/chat                          (X-API-Key) — customer message → AI Employee reply
  GET  /api/v1/conversations/{id}/history    (X-API-Key) — read the conversation
  GET  /api/health                           (no key) — health probe

Run (from the project root — same venv as the backend):
  .venv/runtime/venv/backend/bin/python store/server.py

Key: from Dashboard → API Keys — either env DEMO_STORE_API_KEY or paste it in the page.
Deliberate security note: the key is a server-to-server secret — the page never talks to
the main API directly; every call goes through the store server (the same pattern as a
real integration).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

def _default_api_url() -> str:
    """Main API URL — in order: DEMO_STORE_API_URL from the env ← API_PORT from the main
    project's .env (the Launcher writes the port you chose at launch there) ← 8000 default."""
    env = os.environ.get("DEMO_STORE_API_URL", "").strip()
    if env:
        return env.rstrip("/")
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.strip().partition("=")
            if key.strip() == "API_PORT" and value.strip().isdigit():
                return f"http://127.0.0.1:{value.strip()}"
    return "http://127.0.0.1:8000"


API_URL = _default_api_url()
PORT = int(os.environ.get("DEMO_STORE_PORT", "9000"))
KEY_FILE = Path(__file__).resolve().parent / ".store_key"  # remembers the last locally pasted key

app = FastAPI(title="Demo Store", docs_url=None, redoc_url=None, openapi_url=None)

# The key starts from the env (when present), and can be replaced/set from the page.
_state: dict[str, Any] = {"api_key": (os.environ.get("DEMO_STORE_API_KEY", "") or "").strip()}
if not _state["api_key"] and KEY_FILE.exists():
    _state["api_key"] = KEY_FILE.read_text(encoding="utf-8").strip()


# ============== Store data (the catalog) ==============
# All data lives in store/catalog.txt — one line = one item uploaded to the AI Employee.
# Format: plain line → auto id (line-N) · "ID|text" → an id of your choice · leading # = comment.
# The file is read live at upload/display time — edit it and see the change without restarting.
CATALOG_FILE = Path(__file__).resolve().parent / "catalog.txt"


def load_catalog() -> list[dict]:
    """Reads the store data from catalog.txt at call time (one line = one item, or ID|text)."""
    items: list[dict] = []
    if CATALOG_FILE.exists():
        for lineno, raw in enumerate(CATALOG_FILE.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                item_id, content = line.split("|", 1)
                items.append({"id": item_id.strip() or f"line-{lineno}", "content": content.strip()})
            else:
                items.append({"id": f"line-{lineno}", "content": line})
    return items


# ============== Calls to the main API (server-to-server) ==============

def _call_saas(*, method: str, path: str, body: Optional[dict] = None, use_key: bool = False,
               timeout: float = 30.0) -> dict:
    """One call to the main API. Returns {status, body, latency_ms, error?} — never raises."""
    headers = {"Content-Type": "application/json"}
    if use_key and _state["api_key"]:
        headers["X-API-Key"] = _state["api_key"]
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{API_URL}{path}", data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return {"status": resp.status, "body": payload,
                    "latency_ms": round((time.perf_counter() - started) * 1000)}
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 — non-JSON body
            payload = {"raw": str(exc)}
        return {"status": exc.code, "body": payload,
                "latency_ms": round((time.perf_counter() - started) * 1000)}
    except Exception as exc:  # noqa: BLE001 — the connection itself failed (project not running?)
        return {"status": 0, "body": None, "error": f"{type(exc).__name__}: {exc}",
                "latency_ms": round((time.perf_counter() - started) * 1000)}


# ============== Store endpoints (the ones the page calls) ==============

class KeyIn(BaseModel):
    api_key: str = Field(min_length=10, max_length=200)


class ChatIn(BaseModel):
    customer_id: str = Field(default="cust-1", min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[int] = None


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """The store's single page (inline HTML/JS — no build step)."""
    return PAGE


@app.get("/store/api/catalog")
def catalog() -> dict:
    """A live sample of the store data (the exact items that will be uploaded to the AI Employee)."""
    items = load_catalog()
    return {"count": len(items), "items": items}


@app.get("/store/api/status")
def status() -> dict:
    """Connectivity probe: is the project running? Is a key set? Is the key valid?

    Key test with zero side effects: a history call on a non-existent conversation —
    403/200 = the key is valid and connected, 401 = the key was rejected, 0 = project down.
    """
    health = _call_saas(method="GET", path="/api/health", timeout=8.0)
    result: dict[str, Any] = {
        "api_url": API_URL,
        "api_reachable": health["status"] == 200,
        "key_set": bool(_state["api_key"]),
    }
    if result["api_reachable"] and _state["api_key"]:
        probe = _call_saas(method="GET", path="/api/v1/conversations/99999999/history",
                           use_key=True, timeout=8.0)
        result["key_valid"] = probe["status"] in (200, 403)  # 403 = not our conversation but the key was accepted
        result["probe_status"] = probe["status"]
    elif not _state["api_key"]:
        result["key_valid"] = False
        result["probe_status"] = None
    else:
        result["key_valid"] = False
        result["probe_status"] = None
    return result


@app.post("/store/api/key")
def set_key(payload: KeyIn) -> dict:
    """Sets the API key from the page (saved locally in store/.store_key for easy testing)."""
    _state["api_key"] = payload.api_key.strip()
    try:
        KEY_FILE.write_text(_state["api_key"], encoding="utf-8")
    except OSError:
        pass  # testing continues from memory if the write fails
    return {"ok": True, "key_set": True, "key_preview": _state["api_key"][:12] + "…"}


@app.post("/store/api/setup")
def setup_catalog() -> dict:
    """Uploads the store data to the AI Employee via POST /api/v1/data (X-API-Key).

    The data is read from store/catalog.txt when the button is pressed —
    edit the file and re-upload without restarting.
    """
    items = load_catalog()
    out = _call_saas(method="POST", path="/api/v1/data",
                     body={"items": items, "source": "api"}, use_key=True, timeout=60.0)
    return {"saas": out, "items_sent": len(items)}


@app.post("/store/api/chat")
def send_chat(payload: ChatIn) -> dict:
    """A customer message to the AI Employee via POST /api/v1/chat (X-API-Key)."""
    body: dict[str, Any] = {
        "customer_external_id": payload.customer_id,
        "message": payload.message,
        "request_human": False,
    }
    if payload.conversation_id:
        body["conversation_id"] = payload.conversation_id
    out = _call_saas(method="POST", path="/api/v1/chat", body=body, use_key=True, timeout=90.0)
    data = (out["body"] or {}).get("data") if out["body"] else None
    return {"saas": out,
            "reply": (data or {}).get("reply"),
            "analysis": (data or {}).get("analysis"),
            "case_status": (data or {}).get("case_status"),
            "transfer_request": (data or {}).get("transfer_request"),
            "conversation_id": (data or {}).get("conversation_id")}


@app.get("/store/api/history/{conversation_id}")
def history(conversation_id: int) -> dict:
    """Reads a full conversation via GET /api/v1/conversations/{id}/history (X-API-Key)."""
    out = _call_saas(method="GET", path=f"/api/v1/conversations/{conversation_id}/history",
                     use_key=True, timeout=30.0)
    return {"saas": out}


# ============== The page (inline HTML/JS — English, LTR) ==============

PAGE = """<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>My Store — Demo Store integrated with the AI Employee</title>
<style>
  :root { --bg:#0b0d11; --card:#151820; --line:#262b36; --txt:#e8eaf0; --mut:#8b93a5;
          --acc:#5b8cff; --acc2:#7aa5ff; --ok:#2ecc71; --bad:#e74c3c; --warn:#f39c12; }
  * { box-sizing:border-box; }
  body { margin:0; color:var(--txt); font-family:"Segoe UI",Tahoma,Arial,sans-serif;
         background:radial-gradient(1100px 500px at 80% -10%, #16202f 0%, var(--bg) 55%) fixed var(--bg); }
  .wrap { max-width:1050px; margin:0 auto; padding:18px 16px 60px; }
  header { display:flex; align-items:center; justify-content:space-between; gap:12px;
           border-bottom:1px solid var(--line); padding-bottom:14px; margin-bottom:18px;
           background:linear-gradient(90deg, rgba(91,140,255,.08), transparent 60%); }
  h1 { font-size:20px; margin:0; background:linear-gradient(90deg,#dfe7ff,#9db9ff);
       -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; }
  .sub { color:var(--mut); font-size:12.5px; margin-top:4px; }
  .badge { padding:6px 14px; border-radius:99px; font-size:12.5px; border:1px solid var(--line);
           background:var(--card); white-space:nowrap; transition:color .3s, border-color .3s; }
  .badge.ok { color:var(--ok); border-color:var(--ok); } .badge.bad { color:var(--bad); border-color:var(--bad); }
  .badge.warn { color:var(--warn); border-color:var(--warn); }
  .card { background:var(--card); border:1px solid var(--line); border-radius:14px;
          padding:16px; margin-bottom:16px; box-shadow:0 2px 10px rgba(0,0,0,.25);
          transition:border-color .2s; }
  .card:hover { border-color:#323a4d; }
  .card h2 { font-size:15px; margin:0 0 10px; }
  .row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  input[type=text], input[type=password] { background:#0d0f13; color:var(--txt); border:1px solid var(--line);
          border-radius:9px; padding:9px 12px; font-size:13.5px; transition:border-color .15s, box-shadow .15s; }
  input[type=text]:focus, input[type=password]:focus { outline:0; border-color:var(--acc);
          box-shadow:0 0 0 3px rgba(91,140,255,.18); }
  input#key { flex:1; min-width:220px; direction:ltr; text-align:left; font-family:monospace; }
  button { background:linear-gradient(180deg,var(--acc2),var(--acc)); color:#fff; border:0; border-radius:9px;
           padding:9px 16px; font-size:13.5px; cursor:pointer; font-family:inherit;
           transition:filter .15s, transform .06s; }
  button:hover { filter:brightness(1.12); } button:active { transform:scale(.98); }
  button:focus-visible { outline:2px solid var(--acc2); outline-offset:2px; }
  button.ghost { background:transparent; border:1px solid var(--line); color:var(--txt); }
  button:disabled { opacity:.45; cursor:default; transform:none; }
  .catbar { display:flex; gap:8px; align-items:center; justify-content:space-between; margin-bottom:8px; }
  .chip { font-size:11.5px; color:var(--mut); border:1px dashed var(--line); border-radius:99px; padding:4px 10px; }
  .chip b { color:var(--acc2); }
  .catlist { max-height:240px; overflow-y:auto; display:flex; flex-direction:column; gap:6px; padding:2px; }
  .catitem { display:flex; gap:8px; align-items:baseline; background:#0d0f13; border:1px solid var(--line);
             border-radius:8px; padding:7px 10px; }
  .cid { font-family:monospace; font-size:11px; color:var(--acc2); border:1px solid #2c3a55;
         border-radius:6px; padding:1px 7px; direction:ltr; white-space:nowrap; }
  .ctxt { color:var(--mut); font-size:12.5px; line-height:1.6; overflow:hidden;
          text-overflow:ellipsis; white-space:nowrap; min-width:0; }
  #chat { display:flex; flex-direction:column; height:460px; }
  #msgs { flex:1; overflow-y:auto; display:flex; flex-direction:column; gap:10px; padding:4px 2px; }
  .msg { max-width:78%; border-radius:14px; padding:9px 13px; font-size:13.5px; line-height:1.7;
         border:1px solid var(--line); white-space:pre-wrap; word-break:break-word;
         animation:pop .18s ease-out; }
  @keyframes pop { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:none; } }
  .msg.cust { align-self:flex-start; background:#1d2530; border-radius:14px 14px 5px 14px; }
  .msg.ai { align-self:flex-end; background:linear-gradient(135deg,#153a5f,#102c4a);
            border-color:#2c3a55; border-radius:14px 14px 14px 5px; }
  .msg.sys { align-self:center; color:var(--mut); font-size:12px; background:transparent; border:0; animation:none; }
  .msg.typing { color:var(--mut); background:#12202e; }
  .dots i { display:inline-block; width:6px; height:6px; margin:0 2px; border-radius:99px;
            background:var(--acc2); animation:blink 1.2s infinite; }
  .dots i:nth-child(2) { animation-delay:.2s; } .dots i:nth-child(3) { animation-delay:.4s; }
  @keyframes blink { 0%, 80%, 100% { opacity:.25; } 40% { opacity:1; } }
  .meta { font-size:11px; color:var(--mut); margin-top:6px; display:flex; gap:6px; flex-wrap:wrap; align-items:center; }
  .tag { border-radius:99px; padding:2px 8px; border:1px solid var(--line); }
  .tag.neg { color:var(--bad); } .tag.pos { color:var(--ok); } .tag.neu { color:var(--mut); }
  .tag.warn { color:var(--warn); }
  .raw { direction:ltr; text-align:left; font-family:monospace; font-size:11px; color:var(--mut);
         background:#0d0f13; border:1px solid var(--line); border-radius:8px; padding:8px;
         margin-top:8px; max-height:180px; overflow:auto; white-space:pre-wrap; }
  .composer { display:flex; gap:8px; margin-top:12px; }
  .composer input { flex:1; }
  a { color:var(--acc); text-decoration:none; }
  ::-webkit-scrollbar { width:9px; height:9px; }
  ::-webkit-scrollbar-thumb { background:#242b3a; border-radius:99px; }
  ::-webkit-scrollbar-track { background:transparent; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>🛍️ My Store — Demo Store</h1>
      <div class="sub">Integration test page for the AI Employee · every call goes from the store server (port 9000) to the main API via X-API-Key</div>
    </div>
    <div class="badge" id="status">⏳ Checking…</div>
  </header>

  <div class="card">
    <h2>1) Connection: API key &amp; status</h2>
    <div class="row">
      <input type="password" id="key" placeholder="Paste the key here (ak_live_… from Dashboard → API Keys)">
      <button id="btnKey">Save key</button>
      <button class="ghost" id="btnTest">Test connection</button>
      <button class="ghost" id="btnSetup">2) Upload the catalog to the AI Employee</button>
    </div>
    <div class="sub" style="margin-top:8px">
      No key yet? Open the project Dashboard → API Keys → create a new key and copy it (it is shown once).
      Data is read from <b>store/catalog.txt</b> — one line = one item (or ID|text) — edit the file and re-upload without restarting.
      <span id="setupResult" style="display:block"></span>
      <div class="raw" id="setupRaw" style="display:none"></div>
    </div>
  </div>

  <div class="card">
    <h2>3) Store data (store/catalog.txt)</h2>
    <div class="catbar">
      <span class="chip" id="catCount">… reading</span>
      <button class="ghost" onclick="loadCatalog()">Refresh list</button>
    </div>
    <div class="catlist" id="catList"></div>
    <div class="sub" style="margin-top:8px">One line in the file = one item — edit store/catalog.txt and press "Refresh list" or the upload button above.</div>
  </div>

  <div class="card" id="chat">
    <h2>4) Chat: a customer asks the AI Employee (the same path your real store will use)</h2>
    <div id="msgs"><div class="msg sys">Type a question as a customer — e.g. "How much is the cotton T-shirt?" or "Do you deliver to Alexandria?" or "I want to talk to a human"</div></div>
    <div class="composer">
      <input type="text" id="cust" value="cust-1" style="max-width:120px" title="Customer ID at the store">
      <input type="text" id="text" placeholder="Type the customer's message here…" onkeydown="if(event.key==='Enter')send()">
      <button id="btnSend" onclick="send()">Send</button>
    </div>
  </div>

  <div class="card">
    <h2>5) Read the conversation from the API (optional)</h2>
    <div class="row">
      <input type="text" id="histId" placeholder="Conversation number (conversation_id)" style="max-width:220px">
      <button class="ghost" onclick="loadHistory()">Read conversation</button>
    </div>
    <div class="raw" id="histRaw" style="display:none;margin-top:10px"></div>
  </div>
</div>

<script>
const $ = (id) => document.getElementById(id);
let convId = null;

function badge(text, cls) { const b = $("status"); b.textContent = text; b.className = "badge " + cls; }

async function pollStatus() {
  try {
    const r = await (await fetch("/store/api/status")).json();
    if (!r.api_reachable) { badge("● Main project is not running (" + r.api_url + ")", "bad"); return r; }
    if (!r.key_set) { badge("● Project is running — but no API key is set", "warn"); return r; }
    if (r.key_valid) { badge("● Connected — the integration works ✔", "ok"); return r; }
    badge("● Project is running — but the key was rejected (401)", "bad"); return r;
  } catch (e) { badge("● The store server itself is not responding", "bad"); return null; }
}
setInterval(pollStatus, 8000); pollStatus();

async function saveKey() {
  const k = $("key").value.trim();
  if (!k) { alert("Write/paste the key first"); return; }
  await (await fetch("/store/api/key", {method:"POST", headers:{"Content-Type":"application/json"},
          body: JSON.stringify({api_key:k})})).json();
  $("key").value = ""; pollStatus();
}

async function testConn() {
  const r = await pollStatus();
  if (r) addSys("Check result: project=" + (r.api_reachable ? "running" : "not running")
    + " · key=" + (r.key_set ? (r.key_valid ? "accepted ✔" : "rejected (401)") : "not set")
    + (r.probe_status != null ? " · probe=" + r.probe_status : ""));
}

async function uploadCatalog() {
  $("setupResult").textContent = "… uploading";
  try {
    const r = await (await fetch("/store/api/setup", {method:"POST"})).json();
    const s = r.saas;
    $("setupRaw").style.display = "block";
    $("setupRaw").textContent = "POST " + "http://…/api/v1/data\\nHTTP " + s.status
      + "  (" + s.latency_ms + " ms)\\n" + JSON.stringify(s.body, null, 2);
    $("setupResult").textContent = s.status === 200
      ? `✔ Catalog uploaded (${r.items_sent} items) in ${s.latency_ms} ms — the AI Employee now knows your products`
      : `✗ Upload failed (HTTP ${s.status}) — see the response below`;
    if (s.status === 401) $("setupResult").textContent += " ← wrong or missing key";
  } catch (e) { $("setupResult").textContent = "✗ Could not reach the store server: " + e; }
}

function esc(s) { return (s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function escAttr(s) { return esc(s).replace(/"/g,"&quot;"); }

// Auto-scroll to the latest message (S5) — called after every new message/update
function scrollChat() {
  const m = $("msgs");
  requestAnimationFrame(() => m.scrollTo({top: m.scrollHeight, behavior: "smooth"}));
}

// Live view of the store data (exactly what will be uploaded to the AI Employee) — from /store/api/catalog
async function loadCatalog() {
  try {
    const r = await (await fetch("/store/api/catalog")).json();
    $("catCount").innerHTML = `<b>${r.count}</b> items in catalog.txt — exactly what will be uploaded to the AI Employee`;
    $("catList").innerHTML = r.items.length
      ? r.items.map(it =>
          `<div class="catitem"><span class="cid">${esc(it.id)}</span><span class="ctxt" title="${escAttr(it.content)}">${esc(it.content)}</span></div>`).join("")
      : '<div class="catitem"><span class="ctxt">The file is empty — add items in store/catalog.txt (one line = one item)</span></div>';
  } catch (e) { $("catCount").textContent = "✗ Could not read catalog.txt"; }
}
loadCatalog();

function addSys(t) {
  const d = document.createElement("div"); d.className = "msg sys"; d.textContent = t;
  $("msgs").appendChild(d); scrollChat();
}

function analysisTags(a, caseStatus) {
  if (!a) return "";
  const s = a.sentiment || "neutral";
  const cls = s === "negative" ? "neg" : (s === "positive" ? "pos" : "neu");
  let t = `<span class="tag ${cls}">sentiment: ${s}</span>`;
  if (a.is_complaint) t += `<span class="tag warn">complaint</span>`;
  if (a.is_violation) t += `<span class="tag warn">violation${a.violation_type ? ": " + a.violation_type : ""}</span>`;
  if (caseStatus) t += `<span class="tag neu">case: ${caseStatus}</span>`;
  return t;
}

async function send(requestHuman = false) {
  const text = requestHuman ? "" : $("text").value.trim();
  if (!requestHuman && !text) return;
  const btn = $("btnSend"); btn.disabled = true;
  if (!requestHuman) {
    $("text").value = "";
    const d = document.createElement("div"); d.className = "msg cust"; d.textContent = text;
    $("msgs").appendChild(d); scrollChat();
  } else {
    addSys("The customer accepted the transfer to a human agent (request_human=true)…");
  }
  // "Preparing the reply" bubble (S5): appears instantly with a live seconds counter,
  // and is removed the moment the reply arrives.
  const typing = document.createElement("div"); typing.className = "msg ai typing";
  typing.innerHTML = 'Preparing the reply <span class="dots"><i></i><i></i><i></i></span> <span class="tsec">0.0 s</span>';
  $("msgs").appendChild(typing); scrollChat();
  const t0 = performance.now();
  const tick = setInterval(() => {
    const el = typing.querySelector(".tsec");
    if (el) el.textContent = ((performance.now() - t0) / 1000).toFixed(1) + " s";
  }, 100);
  const body = {customer_id: $("cust").value.trim() || "cust-1", message: text || "I need a human agent"};
  if (requestHuman) body.request_human = true;
  if (convId) body.conversation_id = convId;
  try {
    const r = await (await fetch("/store/api/chat", {method:"POST", headers:{"Content-Type":"application/json"},
                     body: JSON.stringify(body)})).json();
    const s = r.saas;
    const waited = ((performance.now() - t0) / 1000).toFixed(1);
    typing.remove();
    const m = document.createElement("div"); m.className = "msg ai";
    m.innerHTML = s.status === 200
      ? esc(r.reply || "(empty reply — check the raw)")
      : `✗ HTTP error ${s.status}: ${esc((s.body && s.body.error && s.body.error.message) || s.error || "")}`;
    if (s.status === 200) {
      convId = r.conversation_id || convId;
      m.innerHTML += `<div class="meta"><span class="tag neu">⏱ replied in ${waited} s</span>${analysisTags(r.analysis, r.case_status)}
        <span class="tag neu">conv #${convId}</span><span class="tag neu">${s.latency_ms} ms server</span>
        <button class="ghost" style="padding:2px 8px;font-size:11px" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">raw</button>
        <div class="raw" style="display:none">${esc(JSON.stringify(s.body, null, 2))}</div></div>`;
      if (r.transfer_request && r.transfer_request.status && r.transfer_request.status !== "resolved") {
        m.innerHTML += `<div class="meta"><button style="padding:4px 10px;font-size:12px" onclick="send(true)">I am the customer — accept the transfer to a human agent</button></div>`;
      }
    }
    $("msgs").appendChild(m); scrollChat();
  } catch (e) { typing.remove(); addSys("✗ Could not reach the store server: " + e); }
  finally { clearInterval(tick); btn.disabled = false; }
}

async function loadHistory() {
  const id = parseInt($("histId").value.trim(), 10);
  if (!id) { alert("Type the conversation number (shown as conv # in the chat)"); return; }
  const r = await (await fetch("/store/api/history/" + id)).json();
  $("histRaw").style.display = "block";
  $("histRaw").textContent = "GET /api/v1/conversations/" + id + "/history\\nHTTP " + r.saas.status
    + "  (" + r.saas.latency_ms + " ms)\\n" + JSON.stringify(r.saas.body, null, 2);
}

$("btnKey").onclick = saveKey;
$("btnTest").onclick = testConn;
$("btnSetup").onclick = uploadCatalog;
</script>
</body>
</html>
"""


# ============== Direct run: python store/server.py ==============

if __name__ == "__main__":
    import uvicorn

    print("=" * 62)
    print("  Demo Store")
    print(f"  Page       : http://127.0.0.1:{PORT}")
    print(f"  Main API   : {API_URL}")
    key_preview = (_state["api_key"][:8] + "…") if _state["api_key"] else "(not set — paste it in the page)"
    print(f"  API key    : {key_preview}")
    print("=" * 62)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")

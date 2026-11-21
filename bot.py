from __future__ import annotations

import asyncio
import html
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

from app import run
from config import Settings
from services.inbox_store import InboxStore


_SETTINGS: Settings | None = None
_INBOX: InboxStore | None = None


def _get_store() -> tuple[Settings, InboxStore]:
    global _SETTINGS, _INBOX
    if _SETTINGS is None:
        _SETTINGS = Settings.from_env()
        _SETTINGS.ensure_directories()
    if _INBOX is None:
        _INBOX = InboxStore(_SETTINGS.download_location / "inbox.sqlite3")
    return _SETTINGS, _INBOX


def _send_telegram_message(bot_token: str, chat_id: int, text: str) -> tuple[bool, str]:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("ok"):
                return True, "Yuborildi"
            return False, str(body.get("description") or "Xato")
    except Exception as exc:
        return False, str(exc)


_PANEL_HTML = """<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bot Chat Panel</title>
<style>
  * { box-sizing: border-box; font-family: system-ui, -apple-system, sans-serif; }
  body { margin: 0; background: #0e1621; color: #f5f7fa; height: 100vh; display: flex; flex-direction: column; }
  header { background: #17212b; padding: 10px 16px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #242f3d; flex-wrap: wrap; }
  header h2 { margin: 0; font-size: 16px; }
  .tabs { display: flex; gap: 6px; }
  .tab { background: #23303d; color: #cbd5e1; border: none; padding: 7px 12px; border-radius: 8px; cursor: pointer; font-size: 13px; }
  .tab.active { background: #2b5278; color: #fff; font-weight: 600; }
  .main { display: flex; flex: 1; min-height: 0; }
  .sidebar { width: 310px; background: #17212b; border-right: 1px solid #242f3d; overflow-y: auto; }
  .item { padding: 11px 14px; border-bottom: 1px solid #1f2b38; cursor: pointer; }
  .item:hover { background: #202b36; }
  .item.active { background: #2b5278; }
  .item-title { font-weight: 600; font-size: 14px; }
  .item-sub { font-size: 12px; color: #94a3b8; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .chat-area { flex: 1; display: flex; flex-direction: column; background: #0e1621; min-width: 0; }
  .chat-top { padding: 10px 16px; background: #17212b; border-bottom: 1px solid #242f3d; font-size: 14px; font-weight: 600; }
  .messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 8px; }
  .msg { max-width: 72%; padding: 9px 12px; border-radius: 12px; font-size: 14px; line-height: 1.4; word-break: break-word; }
  .msg.in { background: #182533; align-self: flex-start; }
  .msg.out { background: #2b5278; align-self: flex-end; }
  .msg-meta { font-size: 11px; color: #94a3b8; margin-bottom: 3px; }
  .composer { display: flex; gap: 8px; padding: 10px 14px; background: #17212b; border-top: 1px solid #242f3d; }
  .composer input { flex: 1; padding: 10px 12px; border-radius: 8px; border: 1px solid #2b394a; background: #0e1621; color: #fff; font-size: 14px; }
  .composer button { padding: 10px 16px; border-radius: 8px; border: none; background: #3390ec; color: #fff; font-weight: 600; cursor: pointer; }
  @media (max-width: 768px) {
    .main { flex-direction: column; }
    .sidebar { width: 100%; max-height: 36vh; border-right: none; border-bottom: 1px solid #242f3d; }
  }
</style>
</head>
<body>
<header>
  <h2>Bot Panel</h2>
  <div class="tabs">
    <button class="tab active" data-kind="private" onclick="switchTab('private')">Lichkalar</button>
    <button class="tab" data-kind="groups" onclick="switchTab('groups')">Guruh / Kanallar</button>
    <button class="tab" data-kind="contacts" onclick="switchTab('contacts')">Kontaktlar</button>
  </div>
</header>
<div class="main">
  <div class="sidebar" id="sidebar"></div>
  <div class="chat-area">
    <div class="chat-top" id="chatTop">Chat tanlang</div>
    <div class="messages" id="messages"></div>
    <form class="composer" onsubmit="sendMsg(event)">
      <input id="msgInput" placeholder="Bot nomidan xabar yozing..." autocomplete="off">
      <button type="submit">Yuborish</button>
    </form>
  </div>
</div>
<script>
const KEY = new URLSearchParams(location.search).get("key") || "";
let currentKind = "private";
let activeChatId = null;

function switchTab(kind) {
  currentKind = kind;
  document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.kind === kind));
  activeChatId = null;
  loadState();
}

async function loadState(selectId = null) {
  const idParam = selectId !== null ? selectId : (activeChatId !== null ? activeChatId : "");
  const res = await fetch(`/api/state?key=${encodeURIComponent(KEY)}&kind=${currentKind}&chat_id=${idParam}`);
  if (!res.ok) {
    document.getElementById("chatTop").textContent = "Kirish kaliti noto'g'ri (?key=BOT_TOKEN)";
    return;
  }
  const data = await res.json();
  activeChatId = data.active_chat_id;
  renderSidebar(data);
  renderMessages(data);
}

function renderSidebar(data) {
  const sb = document.getElementById("sidebar");
  sb.innerHTML = "";
  if (currentKind === "contacts") {
    data.contacts.forEach(c => {
      const id = c.user_id;
      const div = document.createElement("div");
      div.className = "item" + (id === activeChatId ? " active" : "");
      div.innerHTML = `<div class="item-title">${esc(c.full_name)}</div><div class="item-sub">${c.username ? "@" + esc(c.username) + " · " : ""}ID: ${id}</div>`;
      div.onclick = () => { activeChatId = id; loadState(id); };
      sb.appendChild(div);
    });
    return;
  }
  data.chats.forEach(ch => {
    const div = document.createElement("div");
    div.className = "item" + (ch.chat_id === activeChatId ? " active" : "");
    div.innerHTML = `<div class="item-title">${esc(ch.title)}</div><div class="item-sub">${esc(ch.last_message || "")}</div>`;
    div.onclick = () => { activeChatId = ch.chat_id; loadState(ch.chat_id); };
    sb.appendChild(div);
  });
}

function renderMessages(data) {
  const box = document.getElementById("messages");
  const top = document.getElementById("chatTop");
  top.textContent = activeChatId ? `Chat ID: ${activeChatId}` : "Chat tanlang";
  box.innerHTML = "";
  (data.messages || []).forEach(m => {
    const div = document.createElement("div");
    div.className = "msg " + (m.direction === "out" ? "out" : "in");
    div.innerHTML = `<div class="msg-meta">${esc(m.sender_name)} · ${esc(m.created_at)}</div><div>${esc(m.text)}</div>`;
    box.appendChild(div);
  });
  box.scrollTop = box.scrollHeight;
}

async function sendMsg(e) {
  e.preventDefault();
  const inp = document.getElementById("msgInput");
  const text = inp.value.trim();
  if (!text || !activeChatId) return;
  const res = await fetch(`/api/send?key=${encodeURIComponent(KEY)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: activeChatId, text })
  });
  const out = await res.json();
  if (out.ok) {
    inp.value = "";
    loadState(activeChatId);
  } else {
    alert("Xato: " + out.error);
  }
}

function esc(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}[c]));
}

loadState();
setInterval(() => loadState(), 4000);
</script>
</body>
</html>
"""


class _HealthHandler(BaseHTTPRequestHandler):
    def _authorized(self, query: dict[str, list[str]]) -> bool:
        settings, _ = _get_store()
        provided = (query.get("key") or [""])[0]
        return bool(provided) and provided == settings.bot_token

    def _send_json(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/panel":
            body = _PANEL_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/state":
            if not self._authorized(query):
                self._send_json(401, {"ok": False, "error": "Unauthorized"})
                return
            _, store = _get_store()
            kind = (query.get("kind") or ["private"])[0]
            raw_id = (query.get("chat_id") or [""])[0]
            chat_id = int(raw_id) if raw_id.lstrip("-").isdigit() else None
            payload = json.loads(store.export_state_json(kind=kind, chat_id=chat_id))
            payload["ok"] = True
            self._send_json(200, payload)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path != "/api/send":
            self.send_response(404)
            self.end_headers()
            return
        if not self._authorized(query):
            self._send_json(401, {"ok": False, "error": "Unauthorized"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        data = json.loads(raw or "{}")
        chat_id = int(data.get("chat_id", 0))
        text = str(data.get("text", "")).strip()
        if not chat_id or not text:
            self._send_json(400, {"ok": False, "error": "chat_id va text kerak"})
            return

        settings, store = _get_store()
        ok, info = _send_telegram_message(settings.bot_token, chat_id, text)
        if ok:
            store.record_outgoing(chat_id=chat_id, text=text)
            self._send_json(200, {"ok": True})
        else:
            self._send_json(400, {"ok": False, "error": info})

    def log_message(self, format: str, *args) -> None:
        return


def _start_port_server() -> None:
    _get_store()
    port = int(os.environ.get("PORT", "10000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()


if __name__ == "__main__":
    _start_port_server()
    asyncio.run(run())

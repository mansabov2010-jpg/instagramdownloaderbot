from __future__ import annotations

import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

from app import run
from config import Settings
from services.inbox_store import InboxStore


_SETTINGS: Settings | None = None
_INBOX: InboxStore | None = None
_BG_FILE = Path(__file__).resolve().parent / "assets" / "Без названия.jpg"


def _get_store() -> tuple[Settings, InboxStore]:
    global _SETTINGS, _INBOX
    if _SETTINGS is None:
        _SETTINGS = Settings.from_env()
        _SETTINGS.ensure_directories()
    if _INBOX is None:
        _INBOX = InboxStore(_SETTINGS.download_location / "inbox.sqlite3")
    return _SETTINGS, _INBOX


def _tg_api(bot_token: str, method: str, payload: dict) -> tuple[bool, dict | str]:
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    raw = json.dumps(payload).encode("utf-8")
    req = Request(url, data=raw, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("ok"):
                return True, body.get("result") or {}
            return False, str(body.get("description") or "Telegram API xatosi")
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
  body {
    margin: 0;
    background: #07111c;
    color: #f5f7fa;
    height: 100vh;
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden;
  }
  body::before {
    content: "";
    position: fixed;
    inset: 0;
    background-image: var(--panel-bg, url("/assets/bg.jpg"));
    background-size: cover;
    background-position: center;
    opacity: 0.24;
    filter: saturate(1.15) contrast(1.05);
    pointer-events: none;
    z-index: 0;
  }
  header, .main { position: relative; z-index: 1; }
  header {
    background: rgba(15, 27, 40, 0.88);
    backdrop-filter: blur(10px);
    padding: 10px 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    border-bottom: 1px solid rgba(56, 189, 248, 0.2);
    flex-wrap: wrap;
  }
  header h2 { margin: 0; font-size: 16px; color: #e0f2fe; }
  .tabs { display: flex; gap: 6px; }
  .tab {
    background: rgba(30, 48, 68, 0.85);
    color: #cbd5e1;
    border: 1px solid rgba(148, 163, 184, 0.18);
    padding: 7px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
  }
  .tab.active { background: #0284c7; color: #fff; font-weight: 600; border-color: #38bdf8; }
  .search-box {
    margin-left: auto;
    padding: 6px 10px;
    border-radius: 8px;
    border: 1px solid rgba(148, 163, 184, 0.25);
    background: rgba(9, 18, 30, 0.85);
    color: #fff;
    font-size: 13px;
    min-width: 180px;
  }
  .main { display: flex; flex: 1; min-height: 0; }
  .sidebar {
    width: 310px;
    background: rgba(15, 27, 40, 0.82);
    backdrop-filter: blur(8px);
    border-right: 1px solid rgba(56, 189, 248, 0.18);
    overflow-y: auto;
  }
  .item { padding: 11px 14px; border-bottom: 1px solid rgba(148, 163, 184, 0.12); cursor: pointer; }
  .item:hover { background: rgba(30, 52, 75, 0.7); }
  .item.active { background: rgba(2, 132, 199, 0.45); border-left: 3px solid #38bdf8; }
  .item-title { font-weight: 600; font-size: 14px; }
  .item-sub { font-size: 12px; color: #cbd5e1; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .chat-area { flex: 1; display: flex; flex-direction: column; background: rgba(8, 17, 28, 0.52); min-width: 0; }
  .chat-top {
    padding: 10px 16px;
    background: rgba(15, 27, 40, 0.88);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid rgba(56, 189, 248, 0.18);
    font-size: 14px;
    font-weight: 600;
  }
  .messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 8px; }
  .msg {
    max-width: 74%;
    padding: 9px 12px;
    border-radius: 12px;
    font-size: 14px;
    line-height: 1.4;
    word-break: break-word;
    backdrop-filter: blur(6px);
  }
  .msg.in { background: rgba(23, 39, 58, 0.88); align-self: flex-start; border: 1px solid rgba(148, 163, 184, 0.16); }
  .msg.out { background: rgba(14, 116, 144, 0.88); align-self: flex-end; border: 1px solid rgba(56, 189, 248, 0.35); }
  .msg-meta { font-size: 11px; color: #bae6fd; margin-bottom: 4px; display: flex; justify-content: space-between; gap: 10px; align-items: center; }
  .reply-quote {
    background: rgba(0, 0, 0, 0.28);
    border-left: 3px solid #38bdf8;
    padding: 5px 8px;
    border-radius: 6px;
    margin-bottom: 6px;
    font-size: 12px;
    color: #e2e8f0;
  }
  .reply-who { font-weight: 600; color: #7dd3fc; font-size: 11px; }
  .msg-actions { display: flex; gap: 6px; margin-top: 6px; justify-content: flex-end; }
  .mini-btn {
    background: rgba(15, 23, 42, 0.65);
    color: #e2e8f0;
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 6px;
    padding: 2px 7px;
    font-size: 11px;
    cursor: pointer;
  }
  .mini-btn:hover { background: rgba(56, 189, 248, 0.25); }
  .mini-btn.del:hover { background: rgba(239, 68, 68, 0.35); }
  .reply-bar {
    display: none;
    padding: 7px 14px;
    background: rgba(15, 27, 40, 0.94);
    border-top: 1px solid rgba(56, 189, 248, 0.25);
    font-size: 12px;
    color: #bae6fd;
    align-items: center;
    justify-content: space-between;
  }
  .composer {
    display: flex;
    gap: 8px;
    padding: 10px 14px;
    background: rgba(15, 27, 40, 0.9);
    backdrop-filter: blur(10px);
    border-top: 1px solid rgba(56, 189, 248, 0.2);
  }
  .composer input {
    flex: 1;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid rgba(148, 163, 184, 0.3);
    background: rgba(9, 18, 30, 0.88);
    color: #fff;
    font-size: 14px;
  }
  .composer button {
    padding: 10px 16px;
    border-radius: 8px;
    border: none;
    background: #0284c7;
    color: #fff;
    font-weight: 600;
    cursor: pointer;
  }
  @media (max-width: 768px) {
    .main { flex-direction: column; }
    .sidebar { width: 100%; max-height: 36vh; border-right: none; border-bottom: 1px solid rgba(56, 189, 248, 0.2); }
    .search-box { margin-left: 0; width: 100%; }
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
  <input class="search-box" id="searchInput" placeholder="Xabar qidirish..." oninput="renderMessages(lastData)">
</header>
<div class="main">
  <div class="sidebar" id="sidebar"></div>
  <div class="chat-area">
    <div class="chat-top" id="chatTop">Chat tanlang</div>
    <div class="messages" id="messages"></div>
    <div class="reply-bar" id="replyBar">
      <span id="replyPreview"></span>
      <button type="button" class="mini-btn" onclick="clearReply()">✕</button>
    </div>
    <form class="composer" onsubmit="sendMsg(event)">
      <input id="msgInput" placeholder="Bot nomidan xabar yozing..." autocomplete="off">
      <button type="submit">Yuborish</button>
    </form>
  </div>
</div>
<script>
const params = new URLSearchParams(location.search);
const KEY = params.get("key") || "";
const bgUrl = params.get("bg");
if (bgUrl) {
  document.documentElement.style.setProperty("--panel-bg", `url("${bgUrl}")`);
}
let currentKind = "private";
let activeChatId = null;
let replyTarget = null;
let lastData = { messages: [] };

function switchTab(kind) {
  currentKind = kind;
  document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.kind === kind));
  activeChatId = null;
  clearReply();
  loadState();
}

function setReply(m) {
  if (!m.tg_message_id) {
    alert("Bu xabarda Telegram message_id yo'q, reply qilib bo'lmaydi.");
    return;
  }
  replyTarget = {
    tg_message_id: m.tg_message_id,
    sender_name: m.sender_name,
    text: m.text
  };
  document.getElementById("replyPreview").textContent = `Reply → ${m.sender_name}: ${m.text}`;
  document.getElementById("replyBar").style.display = "flex";
  document.getElementById("msgInput").focus();
}

function clearReply() {
  replyTarget = null;
  document.getElementById("replyBar").style.display = "none";
  document.getElementById("replyPreview").textContent = "";
}

async function editOutMsg(m) {
  if (!m.tg_message_id) {
    alert("Bu xabar Telegram ID'siz saqlangan.");
    return;
  }
  const updated = prompt("Yangi matnni kiriting:", m.text);
  if (updated === null || !updated.trim() || updated.trim() === m.text) return;
  const res = await fetch(`/api/edit?key=${encodeURIComponent(KEY)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      row_id: m.id,
      chat_id: activeChatId,
      message_id: m.tg_message_id,
      text: updated.trim()
    })
  });
  const out = await res.json();
  if (out.ok) loadState(activeChatId);
  else alert("Tahrirlash xatosi: " + out.error);
}

async function deleteOutMsg(m) {
  if (!confirm("Xabarni o'chirasizmi?")) return;
  const res = await fetch(`/api/delete?key=${encodeURIComponent(KEY)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      row_id: m.id,
      chat_id: activeChatId,
      message_id: m.tg_message_id || null
    })
  });
  const out = await res.json();
  if (out.ok) loadState(activeChatId);
  else alert("O'chirish xatosi: " + out.error);
}

async function loadState(selectId = null) {
  const idParam = selectId !== null ? selectId : (activeChatId !== null ? activeChatId : "");
  const res = await fetch(`/api/state?key=${encodeURIComponent(KEY)}&kind=${currentKind}&chat_id=${idParam}`);
  if (!res.ok) {
    document.getElementById("chatTop").textContent = "Kirish kaliti noto'g'ri (?key=BOT_TOKEN)";
    return;
  }
  const data = await res.json();
  lastData = data;
  activeChatId = data.active_chat_id;
  renderSidebar(data);
  renderMessages(data);
}

function renderSidebar(data) {
  const sb = document.getElementById("sidebar");
  sb.innerHTML = "";
  if (currentKind === "contacts") {
    data.contacts.forEach(c => {
      const targetId = c.last_chat_id || c.user_id;
      const div = document.createElement("div");
      div.className = "item" + (targetId === activeChatId ? " active" : "");
      div.innerHTML = `<div class="item-title">${esc(c.full_name)}</div><div class="item-sub">${c.username ? "@" + esc(c.username) + " · " : ""}ID: ${c.user_id}</div>`;
      div.onclick = () => { activeChatId = targetId; loadState(targetId); };
      sb.appendChild(div);
    });
    return;
  }
  (data.chats || []).forEach(ch => {
    const div = document.createElement("div");
    div.className = "item" + (ch.chat_id === activeChatId ? " active" : "");
    div.innerHTML = `<div class="item-title">${esc(ch.title)}</div><div class="item-sub">${esc(ch.last_message || "")}</div>`;
    div.onclick = () => { activeChatId = ch.chat_id; clearReply(); loadState(ch.chat_id); };
    sb.appendChild(div);
  });
}

function renderMessages(data) {
  const box = document.getElementById("messages");
  const top = document.getElementById("chatTop");
  const q = (document.getElementById("searchInput").value || "").trim().toLowerCase();
  top.textContent = activeChatId ? `Chat ID: ${activeChatId}` : "Chat tanlang";
  box.innerHTML = "";
  const list = (data.messages || []).filter(m => !q || String(m.text || "").toLowerCase().includes(q) || String(m.sender_name || "").toLowerCase().includes(q));
  list.forEach(m => {
    const div = document.createElement("div");
    const isOut = m.direction === "out";
    div.className = "msg " + (isOut ? "out" : "in");
    const quoteHtml = m.reply_to_text
      ? `<div class="reply-quote"><div class="reply-who">↩ ${esc(m.reply_to_sender || "Xabar")}</div><div>${esc(m.reply_to_text)}</div></div>`
      : "";
    const actionsHtml = isOut
      ? `<div class="msg-actions">
           <button type="button" class="mini-btn" onclick='setReply(${JSON.stringify(m).replace(/'/g, "&#39;")})'>Reply</button>
           <button type="button" class="mini-btn" onclick='editOutMsg(${JSON.stringify(m).replace(/'/g, "&#39;")})'>Tahrirlash</button>
           <button type="button" class="mini-btn del" onclick='deleteOutMsg(${JSON.stringify(m).replace(/'/g, "&#39;")})'>O'chirish</button>
         </div>`
      : `<div class="msg-actions">
           <button type="button" class="mini-btn" onclick='setReply(${JSON.stringify(m).replace(/'/g, "&#39;")})'>Reply</button>
         </div>`;
    div.innerHTML = `<div class="msg-meta"><span>${esc(m.sender_name)}</span><span>${esc(m.created_at)}</span></div>${quoteHtml}<div>${esc(m.text)}</div>${actionsHtml}`;
    box.appendChild(div);
  });
  box.scrollTop = box.scrollHeight;
}

async function sendMsg(e) {
  e.preventDefault();
  const inp = document.getElementById("msgInput");
  const text = inp.value.trim();
  if (!text || !activeChatId) return;
  const payload = {
    chat_id: activeChatId,
    text,
    reply_to_message_id: replyTarget ? replyTarget.tg_message_id : null,
    reply_to_sender: replyTarget ? replyTarget.sender_name : "",
    reply_to_text: replyTarget ? replyTarget.text : ""
  };
  const res = await fetch(`/api/send?key=${encodeURIComponent(KEY)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const out = await res.json();
  if (out.ok) {
    inp.value = "";
    clearReply();
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

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path in ("/assets/bg.jpg", f"/assets/{quote('Без названия.jpg')}") and _BG_FILE.is_file():
            img_bytes = _BG_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(img_bytes)))
            self.end_headers()
            self.wfile.write(img_bytes)
            return

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
        if not self._authorized(query):
            self._send_json(401, {"ok": False, "error": "Unauthorized"})
            return

        settings, store = _get_store()
        data = self._read_json_body()

        if parsed.path == "/api/send":
            chat_id = int(data.get("chat_id", 0))
            text = str(data.get("text", "")).strip()
            reply_to_id = data.get("reply_to_message_id")
            reply_sender = str(data.get("reply_to_sender", "")).strip()
            reply_text = str(data.get("reply_to_text", "")).strip()
            if not chat_id or not text:
                self._send_json(400, {"ok": False, "error": "chat_id va text kerak"})
                return

            payload: dict = {"chat_id": chat_id, "text": text}
            if reply_to_id:
                payload["reply_parameters"] = {"message_id": int(reply_to_id)}

            ok, res = _tg_api(settings.bot_token, "sendMessage", payload)
            if ok and isinstance(res, dict):
                store.record_outgoing(
                    chat_id=chat_id,
                    text=text,
                    tg_message_id=res.get("message_id"),
                    reply_to_tg_id=int(reply_to_id) if reply_to_id else None,
                    reply_to_sender=reply_sender,
                    reply_to_text=reply_text,
                )
                self._send_json(200, {"ok": True})
            else:
                self._send_json(400, {"ok": False, "error": str(res)})
            return

        if parsed.path == "/api/edit":
            row_id = int(data.get("row_id", 0))
            chat_id = int(data.get("chat_id", 0))
            message_id = int(data.get("message_id", 0))
            text = str(data.get("text", "")).strip()
            if not chat_id or not message_id or not text:
                self._send_json(400, {"ok": False, "error": "Ma'lumotlar yetarli emas"})
                return

            ok, res = _tg_api(
                settings.bot_token,
                "editMessageText",
                {"chat_id": chat_id, "message_id": message_id, "text": text},
            )
            if ok:
                store.update_outgoing_message(row_id=row_id, new_text=text)
                self._send_json(200, {"ok": True})
            else:
                self._send_json(400, {"ok": False, "error": str(res)})
            return

        if parsed.path == "/api/delete":
            row_id = int(data.get("row_id", 0))
            chat_id = int(data.get("chat_id", 0))
            message_id = data.get("message_id")
            if message_id and chat_id:
                _tg_api(
                    settings.bot_token,
                    "deleteMessage",
                    {"chat_id": chat_id, "message_id": int(message_id)},
                )
            store.delete_outgoing_message(row_id=row_id)
            self._send_json(200, {"ok": True})
            return

        self.send_response(404)
        self.end_headers()

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

from __future__ import annotations

import asyncio
import json
import os
import re
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


def _normalize_sub_target(raw_link: str) -> tuple[str, str]:
    val = raw_link.strip()
    if not val:
        return "", ""
    if val.lstrip("-").isdigit():
        return val, ""
    m = re.search(r"(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z0-9_]+)/?", val)
    if m:
        username = m.group(1)
        return f"@{username}", f"https://t.me/{username}"
    clean = val.lstrip("@")
    return f"@{clean}", f"https://t.me/{clean}"


def _is_admin_key(provided: str, settings: Settings) -> bool:
    token = (provided or "").strip()
    if not token:
        return False
    if token == settings.bot_token:
        return True
    admins = {int(uid) for uid in (settings.auth_users or ())}
    if admins and token.isdigit():
        return int(token) in admins
    return False


_PANEL_HTML = """<!doctype html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Admin Chat Panel</title>
<style>
  * { box-sizing: border-box; font-family: system-ui, -apple-system, sans-serif; }
  html, body {
    margin: 0;
    padding: 0;
    background: #081524;
    color: #f8fafc;
    height: 100dvh;
    width: 100%;
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
    background-position: center top;
    opacity: 0.52;
    filter: brightness(1.12) saturate(1.22);
    pointer-events: none;
    z-index: 0;
  }
  header, .main, .locked-screen { position: relative; z-index: 1; }
  .locked-screen {
    flex: 1;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 20px;
    text-align: center;
  }
  .locked-card {
    background: rgba(12, 24, 38, 0.9);
    border: 1px solid rgba(248, 113, 113, 0.45);
    border-radius: 14px;
    padding: 24px;
    max-width: 420px;
  }
  header {
    flex-shrink: 0;
    background: rgba(12, 24, 38, 0.84);
    backdrop-filter: blur(8px);
    padding: 8px 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    border-bottom: 1px solid rgba(56, 189, 248, 0.28);
    flex-wrap: wrap;
  }
  header h2 { margin: 0; font-size: 15px; color: #e0f2fe; margin-right: 4px; }
  .tabs { display: flex; gap: 6px; flex-wrap: wrap; }
  .tab {
    background: rgba(24, 42, 62, 0.85);
    color: #e2e8f0;
    border: 1px solid rgba(148, 163, 184, 0.25);
    padding: 6px 10px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 12px;
  }
  .tab.active { background: #0284c7; color: #fff; font-weight: 600; border-color: #7dd3fc; }
  .search-box {
    margin-left: auto;
    padding: 6px 10px;
    border-radius: 8px;
    border: 1px solid rgba(148, 163, 184, 0.35);
    background: rgba(9, 18, 30, 0.82);
    color: #fff;
    font-size: 13px;
    min-width: 160px;
  }
  .main {
    display: flex;
    flex: 1;
    min-height: 0;
    width: 100%;
    overflow: hidden;
  }
  .sidebar {
    width: 300px;
    flex-shrink: 0;
    background: rgba(12, 24, 38, 0.76);
    backdrop-filter: blur(6px);
    border-right: 1px solid rgba(56, 189, 248, 0.22);
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
  }
  .item { padding: 10px 14px; border-bottom: 1px solid rgba(255, 255, 255, 0.09); cursor: pointer; }
  .item:hover { background: rgba(30, 58, 86, 0.72); }
  .item.active { background: rgba(2, 132, 199, 0.55); border-left: 3px solid #7dd3fc; }
  .item-title { font-weight: 600; font-size: 14px; }
  .item-sub { font-size: 12px; color: #cbd5e1; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .chat-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: rgba(8, 17, 28, 0.28);
    min-width: 0;
    min-height: 0;
    height: 100%;
    overflow: hidden;
  }
  .chat-top {
    flex-shrink: 0;
    padding: 8px 14px;
    background: rgba(12, 24, 38, 0.84);
    backdrop-filter: blur(8px);
    border-bottom: 1px solid rgba(56, 189, 248, 0.22);
    font-size: 13.5px;
    font-weight: 600;
  }
  .messages {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .msg {
    max-width: 82%;
    padding: 9px 12px;
    border-radius: 12px;
    font-size: 14px;
    line-height: 1.4;
    word-break: break-word;
    backdrop-filter: blur(6px);
    flex-shrink: 0;
  }
  .msg.in { background: rgba(18, 33, 51, 0.86); align-self: flex-start; border: 1px solid rgba(148, 163, 184, 0.22); }
  .msg.out { background: rgba(2, 132, 199, 0.88); align-self: flex-end; border: 1px solid rgba(125, 211, 252, 0.45); }
  .msg-meta { font-size: 11px; color: #e0f2fe; margin-bottom: 4px; display: flex; justify-content: space-between; gap: 10px; }
  .reply-quote {
    background: rgba(0, 0, 0, 0.3);
    border-left: 3px solid #7dd3fc;
    padding: 5px 8px;
    border-radius: 6px;
    margin-bottom: 6px;
    font-size: 12px;
  }
  .reply-who { font-weight: 600; color: #bae6fd; font-size: 11px; }
  .msg-actions { display: flex; gap: 6px; margin-top: 6px; justify-content: flex-end; flex-wrap: wrap; }
  .mini-btn {
    background: rgba(15, 23, 42, 0.75);
    color: #f8fafc;
    border: 1px solid rgba(148, 163, 184, 0.3);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    cursor: pointer;
  }
  .mini-btn.del { background: rgba(185, 28, 28, 0.78); }
  .reply-bar {
    display: none;
    flex-shrink: 0;
    padding: 6px 12px;
    background: rgba(12, 24, 38, 0.92);
    border-top: 1px solid rgba(56, 189, 248, 0.3);
    font-size: 12px;
    color: #bae6fd;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .composer {
    display: flex;
    flex-shrink: 0;
    gap: 8px;
    padding: 8px 12px;
    background: rgba(12, 24, 38, 0.9);
    backdrop-filter: blur(8px);
    border-top: 1px solid rgba(56, 189, 248, 0.28);
    width: 100%;
  }
  .composer input {
    flex: 1;
    min-width: 0;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid rgba(148, 163, 184, 0.35);
    background: rgba(9, 18, 30, 0.9);
    color: #fff;
    font-size: 14px;
  }
  .composer button, .primary-btn {
    flex-shrink: 0;
    padding: 10px 14px;
    border-radius: 8px;
    border: none;
    background: #0284c7;
    color: #fff;
    font-weight: 600;
    cursor: pointer;
  }
  .tool-panel {
    display: none;
    padding: 14px;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    flex: 1;
    min-height: 0;
    gap: 14px;
    flex-direction: column;
  }
  .card {
    background: rgba(12, 24, 38, 0.84);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(56, 189, 248, 0.25);
    border-radius: 12px;
    padding: 14px;
    max-width: 720px;
  }
  .card h3 { margin: 0 0 10px 0; font-size: 15px; color: #e0f2fe; }
  .card textarea, .card input[type="text"] {
    width: 100%;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid rgba(148, 163, 184, 0.35);
    background: rgba(9, 18, 30, 0.88);
    color: #fff;
    font-size: 13.5px;
    margin-bottom: 10px;
  }
  .checks { display: flex; gap: 14px; margin-bottom: 10px; font-size: 13px; flex-wrap: wrap; }
  .sub-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 10px;
    border-radius: 8px;
    background: rgba(15, 28, 44, 0.82);
    border: 1px solid rgba(148, 163, 184, 0.2);
    margin-bottom: 8px;
    gap: 8px;
  }
  @media (max-width: 768px) {
    header { padding: 7px 10px; gap: 6px; }
    .main { flex-direction: column; flex: 1; min-height: 0; height: 100%; }
    .sidebar {
      width: 100%;
      height: 115px;
      max-height: 115px;
      flex-shrink: 0;
      border-right: none;
      border-bottom: 1px solid rgba(56, 189, 248, 0.25);
    }
    .chat-area {
      flex: 1;
      min-height: 0;
      height: auto;
    }
    .messages {
      flex: 1;
      min-height: 0;
      overflow-y: auto;
      padding: 10px;
    }
    .composer {
      padding: 8px 10px;
    }
    .search-box { margin-left: 0; width: 100%; min-width: 0; }
  }
</style>
</head>
<body>
<div class="locked-screen" id="lockedScreen">
  <div class="locked-card">
    <h3 style="margin:0 0 8px 0;color:#fca5a5;">Kirish taqiqlangan</h3>
    <p style="margin:0;font-size:13.5px;color:#cbd5e1;">Bu panel faqat adminlar uchun mo‘ljallangan. To‘g‘ri admin kaliti (?key=...) bilan kiring.</p>
  </div>
</div>
<div id="appShell" style="display:none;flex:1;min-height:0;flex-direction:column;">
<header>
  <h2>Admin Panel</h2>
  <div class="tabs">
    <button class="tab active" data-kind="private" onclick="switchTab('private')">Lichkalar</button>
    <button class="tab" data-kind="groups" onclick="switchTab('groups')">Guruh / Kanallar</button>
    <button class="tab" data-kind="contacts" onclick="switchTab('contacts')">Kontaktlar</button>
    <button class="tab" data-kind="broadcast" onclick="switchTab('broadcast')">Barchaga xabar</button>
    <button class="tab" data-kind="forcesub" onclick="switchTab('forcesub')">Majburiy obuna</button>
  </div>
  <input class="search-box" id="searchInput" placeholder="Xabar qidirish..." oninput="renderMessages(lastData)">
</header>
<div class="main">
  <div class="sidebar" id="sidebar"></div>

  <div class="chat-area" id="chatArea">
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

  <div class="tool-panel" id="broadcastPanel">
    <div class="card">
      <h3>Barchaga xabar yuborish</h3>
      <div class="checks">
        <label><input type="checkbox" id="bcContacts" checked> Kontaktlar (lichkalar)</label>
        <label><input type="checkbox" id="bcGroups" checked> Guruh va kanallar</label>
      </div>
      <textarea id="bcText" rows="4" placeholder="Yuboriladigan xabar matnini yozing..."></textarea>
      <button class="primary-btn" onclick="runBroadcast()">Yuborishni boshlash</button>
      <div id="bcResult" style="margin-top:10px;font-size:13px;color:#bae6fd;"></div>
    </div>
  </div>

  <div class="tool-panel" id="forcesubPanel">
    <div class="card">
      <h3>Majburiy obuna qo‘shish</h3>
      <div style="font-size:12.5px;color:#cbd5e1;margin-bottom:10px;">
        Kanal yoki guruh havolasini (`https://t.me/...` yoki `@username`) kiriting. Bot o‘sha kanal/guruhga admin bo‘lishi kerak. Qo‘shilmasa bot odatdagidek ishlayveradi.
      </div>
      <input type="text" id="subLink" placeholder="Kanal yoki guruh havolasi / @username (masalan: https://t.me/kanal_nomi)">
      <input type="text" id="subTitle" placeholder="Tugma nomi (ixtiyoriy, masalan: Rasmiy kanal)">
      <button class="primary-btn" onclick="addForceSub()">Majburiy obuna qo‘shish</button>
      <div id="subMsg" style="margin-top:10px;font-size:13px;color:#bae6fd;"></div>
    </div>
    <div class="card">
      <h3>Faol majburiy obunalar</h3>
      <div id="subList"></div>
    </div>
  </div>
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
let lastData = { messages: [], force_subs: [] };
let shouldStickBottom = true;
let pollTimer = null;

function showLocked() {
  document.getElementById("lockedScreen").style.display = "flex";
  document.getElementById("appShell").style.display = "none";
  if (pollTimer) clearInterval(pollTimer);
}

function showUnlocked() {
  document.getElementById("lockedScreen").style.display = "none";
  document.getElementById("appShell").style.display = "flex";
}

function switchTab(kind) {
  currentKind = kind;
  document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.kind === kind));
  const isTool = (kind === "broadcast" || kind === "forcesub");
  document.getElementById("chatArea").style.display = isTool ? "none" : "flex";
  document.getElementById("broadcastPanel").style.display = kind === "broadcast" ? "flex" : "none";
  document.getElementById("forcesubPanel").style.display = kind === "forcesub" ? "flex" : "none";
  if (!isTool) {
    activeChatId = null;
    shouldStickBottom = true;
    clearReply();
  }
  loadState();
}

function setReply(m) {
  if (!m.tg_message_id) {
    alert("Bu xabarda Telegram message_id yo'q.");
    return;
  }
  replyTarget = { tg_message_id: m.tg_message_id, sender_name: m.sender_name, text: m.text };
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
  if (!m.tg_message_id) return alert("Telegram message_id topilmadi.");
  const updated = prompt("Yangi matnni kiriting:", m.text);
  if (updated === null || !updated.trim() || updated.trim() === m.text) return;
  const res = await fetch(`/api/edit?key=${encodeURIComponent(KEY)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ row_id: m.id, chat_id: activeChatId, message_id: m.tg_message_id, text: updated.trim() })
  });
  const out = await res.json();
  if (out.ok) loadState(activeChatId, true);
  else alert("Tahrirlash xatosi: " + out.error);
}

async function deleteOutMsg(m) {
  if (!confirm("Xabarni o'chirasizmi?")) return;
  const res = await fetch(`/api/delete?key=${encodeURIComponent(KEY)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ row_id: m.id, chat_id: activeChatId, message_id: m.tg_message_id || null })
  });
  const out = await res.json();
  if (out.ok) loadState(activeChatId, true);
  else alert("O'chirish xatosi: " + out.error);
}

async function runBroadcast() {
  const txt = document.getElementById("bcText").value.trim();
  const incContacts = document.getElementById("bcContacts").checked;
  const incGroups = document.getElementById("bcGroups").checked;
  if (!txt) return alert("Xabar matnini kiriting.");
  const res = await fetch(`/api/broadcast?key=${encodeURIComponent(KEY)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: txt, include_contacts: incContacts, include_groups: incGroups })
  });
  const out = await res.json();
  if (out.ok) {
    document.getElementById("bcResult").textContent = `Yuborildi: ${out.sent} ta chatga, xato: ${out.failed} ta.`;
    document.getElementById("bcText").value = "";
  } else {
    document.getElementById("bcResult").textContent = "Xato: " + out.error;
  }
}

async function addForceSub() {
  const link = document.getElementById("subLink").value.trim();
  const title = document.getElementById("subTitle").value.trim();
  if (!link) return alert("Kanal yoki guruh havolasini kiriting.");
  const res = await fetch(`/api/forcesub/add?key=${encodeURIComponent(KEY)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ link, title })
  });
  const out = await res.json();
  if (out.ok) {
    document.getElementById("subLink").value = "";
    document.getElementById("subTitle").value = "";
    document.getElementById("subMsg").textContent = "Majburiy obuna qo‘shildi!";
    loadState();
  } else {
    document.getElementById("subMsg").textContent = "Xato: " + out.error;
  }
}

async function removeForceSub(id) {
  const res = await fetch(`/api/forcesub/delete?key=${encodeURIComponent(KEY)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id })
  });
  const out = await res.json();
  if (out.ok) loadState();
}

function renderForceSubs(subs) {
  const box = document.getElementById("subList");
  if (!subs || !subs.length) {
    box.innerHTML = `<div style="font-size:13px;color:#94a3b8;">Majburiy obuna qo‘shilmagan — bot odatdagidek ishlaydi.</div>`;
    return;
  }
  box.innerHTML = subs.map(s => `
    <div class="sub-row">
      <div>
        <div style="font-weight:600;font-size:13.5px;">${esc(s.title || s.target)}</div>
        <div style="font-size:12px;color:#bae6fd;">${esc(s.target)} · ${esc(s.invite_url)}</div>
      </div>
      <button class="mini-btn del" onclick="removeForceSub(${s.id})">O‘chirish</button>
    </div>
  `).join("");
}

async function loadState(selectId = null, forceScroll = false) {
  const box = document.getElementById("messages");
  if (box && !forceScroll) {
    shouldStickBottom = (box.scrollHeight - box.scrollTop - box.clientHeight) < 80;
  } else if (forceScroll) {
    shouldStickBottom = true;
  }
  const idParam = selectId !== null ? selectId : (activeChatId !== null ? activeChatId : "");
  const kindParam = (currentKind === "broadcast" || currentKind === "forcesub") ? "groups" : currentKind;
  const res = await fetch(`/api/state?key=${encodeURIComponent(KEY)}&kind=${kindParam}&chat_id=${idParam}`);
  if (!res.ok) {
    showLocked();
    return;
  }
  showUnlocked();
  const data = await res.json();
  const chatChanged = data.active_chat_id !== activeChatId;
  lastData = data;
  activeChatId = data.active_chat_id;
  if (chatChanged) shouldStickBottom = true;
  renderSidebar(data);
  renderMessages(data);
  renderForceSubs(data.force_subs || []);
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
      div.onclick = () => { activeChatId = targetId; loadState(targetId, true); };
      sb.appendChild(div);
    });
    return;
  }
  const list = data.chats || [];
  if (!list.length) {
    sb.innerHTML = `<div class="item"><div class="item-sub">Hozircha ro‘yxat bo‘sh</div></div>`;
    return;
  }
  list.forEach(ch => {
    const div = document.createElement("div");
    div.className = "item" + (ch.chat_id === activeChatId ? " active" : "");
    div.innerHTML = `<div class="item-title">${esc(ch.title)}</div><div class="item-sub">${esc(ch.last_message || "")}</div>`;
    div.onclick = () => { activeChatId = ch.chat_id; clearReply(); loadState(ch.chat_id, true); };
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
  if (shouldStickBottom) {
    box.scrollTop = box.scrollHeight;
  }
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
    loadState(activeChatId, true);
  } else {
    alert("Xato: " + out.error);
  }
}

function esc(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}[c]));
}

loadState(null, true).then(() => {
  pollTimer = setInterval(() => loadState(), 5000);
});
</script>
</body>
</html>
"""


class _HealthHandler(BaseHTTPRequestHandler):
    def _authorized(self, query: dict[str, list[str]]) -> bool:
        settings, _ = _get_store()
        provided = (query.get("key") or [""])[0]
        return _is_admin_key(provided, settings)

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
            if not self._authorized(query):
                self._send_json(403, {"ok": False, "error": "Faqat adminlar uchun"})
                return
            body = _PANEL_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/state":
            if not self._authorized(query):
                self._send_json(403, {"ok": False, "error": "Faqat adminlar uchun"})
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
            self._send_json(403, {"ok": False, "error": "Faqat adminlar uchun"})
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

        if parsed.path == "/api/broadcast":
            text = str(data.get("text", "")).strip()
            inc_contacts = bool(data.get("include_contacts", True))
            inc_groups = bool(data.get("include_groups", True))
            if not text:
                self._send_json(400, {"ok": False, "error": "Matn bo'sh"})
                return
            targets = store.get_broadcast_targets(
                include_contacts=inc_contacts,
                include_groups=inc_groups,
            )
            sent = 0
            failed = 0
            for tid in targets:
                ok, res = _tg_api(settings.bot_token, "sendMessage", {"chat_id": tid, "text": text})
                if ok:
                    sent += 1
                    store.record_outgoing(
                        chat_id=tid,
                        text=text,
                        tg_message_id=res.get("message_id") if isinstance(res, dict) else None,
                    )
                else:
                    failed += 1
            self._send_json(200, {"ok": True, "sent": sent, "failed": failed})
            return

        if parsed.path == "/api/forcesub/add":
            raw_link = str(data.get("link", "")).strip()
            custom_title = str(data.get("title", "")).strip()
            target, invite_url = _normalize_sub_target(raw_link)
            if not target:
                self._send_json(400, {"ok": False, "error": "Havola yoki username noto'g'ri"})
                return
            title = custom_title
            ok, chat_info = _tg_api(settings.bot_token, "getChat", {"chat_id": target})
            if ok and isinstance(chat_info, dict):
                if not title:
                    title = str(chat_info.get("title") or target)
                if not invite_url:
                    invite_url = str(chat_info.get("invite_link") or f"https://t.me/{target.lstrip('@')}")
            if not invite_url:
                self._send_json(400, {"ok": False, "error": "Guruh/kanal uchun t.me havola kiriting"})
                return
            store.add_force_sub(target=target, title=title or target, invite_url=invite_url)
            self._send_json(200, {"ok": True})
            return

        if parsed.path == "/api/forcesub/delete":
            sub_id = int(data.get("id", 0))
            if sub_id:
                store.remove_force_sub(sub_id)
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

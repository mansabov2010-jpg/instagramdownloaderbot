from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class InboxStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chats (
                    chat_id INTEGER PRIMARY KEY,
                    chat_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    username TEXT DEFAULT '',
                    last_message TEXT DEFAULT '',
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS contacts (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    username TEXT DEFAULT '',
                    last_chat_id INTEGER,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    sender_name TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def record_incoming(
        self,
        chat_id: int,
        chat_type: str,
        chat_title: str,
        chat_username: str | None,
        user_id: int | None,
        full_name: str | None,
        user_username: str | None,
        text: str,
    ) -> None:
        now = _now_iso()
        clean_title = (chat_title or "Noma'lum chat").strip()
        c_user = (chat_username or "").lstrip("@")
        u_name = (full_name or "Foydalanuvchi").strip()
        u_user = (user_username or "").lstrip("@")
        preview = (text or "[Media / Fayl]").strip()

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chats (chat_id, chat_type, title, username, last_message, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    chat_type = excluded.chat_type,
                    title = CASE WHEN excluded.title != '' THEN excluded.title ELSE chats.title END,
                    username = CASE WHEN excluded.username != '' THEN excluded.username ELSE chats.username END,
                    last_message = excluded.last_message,
                    updated_at = excluded.updated_at
                """,
                (chat_id, chat_type, clean_title, c_user, preview[:160], now),
            )

            if user_id:
                conn.execute(
                    """
                    INSERT INTO contacts (user_id, full_name, username, last_chat_id, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        full_name = CASE WHEN excluded.full_name != '' THEN excluded.full_name ELSE contacts.full_name END,
                        username = CASE WHEN excluded.username != '' THEN excluded.username ELSE contacts.username END,
                        last_chat_id = excluded.last_chat_id,
                        updated_at = excluded.updated_at
                    """,
                    (user_id, u_name, u_user, chat_id, now),
                )

            conn.execute(
                """
                INSERT INTO messages (chat_id, sender_name, direction, text, created_at)
                VALUES (?, ?, 'in', ?, ?)
                """,
                (chat_id, u_name, preview, now),
            )
            conn.commit()

    def record_outgoing(self, chat_id: int, text: str, chat_type: str = "private", title: str | None = None) -> None:
        now = _now_iso()
        preview = text.strip()[:160]
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chats (chat_id, chat_type, title, username, last_message, updated_at)
                VALUES (?, ?, ?, '', ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    last_message = excluded.last_message,
                    updated_at = excluded.updated_at,
                    title = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE chats.title END
                """,
                (chat_id, chat_type, title or f"Chat {chat_id}", preview, now, title, title, title),
            )
            conn.execute(
                """
                INSERT INTO messages (chat_id, sender_name, direction, text, created_at)
                VALUES (?, 'Bot', 'out', ?, ?)
                """,
                (chat_id, text.strip(), now),
            )
            conn.commit()

    def get_chats(self, kind: str) -> list[dict]:
        with self._lock, self._connect() as conn:
            if kind == "private":
                rows = conn.execute(
                    "SELECT * FROM chats WHERE chat_type = 'private' ORDER BY updated_at DESC"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM chats WHERE chat_type != 'private' ORDER BY updated_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_contacts(self) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM contacts ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_messages(self, chat_id: int, limit: int = 80) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (chat_id, limit),
            ).fetchall()
            items = [dict(r) for r in rows]
            items.reverse()
            return items

    def export_state_json(self, kind: str = "private", chat_id: int | None = None) -> str:
        chats = self.get_chats(kind if kind in ("private", "groups") else "private")
        contacts = self.get_contacts()
        active_id = chat_id
        if active_id is None:
            if kind == "contacts" and contacts:
                active_id = contacts[0]["user_id"]
            elif chats:
                active_id = chats[0]["chat_id"]
        messages = self.get_messages(active_id) if active_id is not None else []
        return json.dumps(
            {
                "kind": kind,
                "active_chat_id": active_id,
                "chats": chats,
                "contacts": contacts,
                "messages": messages,
            },
            ensure_ascii=False,
        )

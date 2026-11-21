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
                    tg_message_id INTEGER,
                    reply_to_tg_id INTEGER,
                    reply_to_sender TEXT DEFAULT '',
                    reply_to_text TEXT DEFAULT '',
                    sender_name TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_columns(conn)
            conn.commit()

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(messages)").fetchall()}
        additions = {
            "tg_message_id": "INTEGER",
            "reply_to_tg_id": "INTEGER",
            "reply_to_sender": "TEXT DEFAULT ''",
            "reply_to_text": "TEXT DEFAULT ''",
        }
        for col, col_type in additions.items():
            if col not in cols:
                conn.execute(f"ALTER TABLE messages ADD COLUMN {col} {col_type}")

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
        tg_message_id: int | None = None,
        reply_to_tg_id: int | None = None,
        save_contact: bool = False,
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

            # Faqat lichkada yozgan foydalanuvchilar kontaktda saqlanadi
            if save_contact and chat_type == "private" and user_id:
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

            reply_sender = ""
            reply_text = ""
            if reply_to_tg_id:
                ref = conn.execute(
                    """
                    SELECT sender_name, text FROM messages
                    WHERE chat_id = ? AND tg_message_id = ?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (chat_id, reply_to_tg_id),
                ).fetchone()
                if ref:
                    reply_sender = ref["sender_name"] or ""
                    reply_text = (ref["text"] or "")[:100]

            conn.execute(
                """
                INSERT INTO messages (
                    chat_id, tg_message_id, reply_to_tg_id, reply_to_sender, reply_to_text,
                    sender_name, direction, text, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'in', ?, ?)
                """,
                (
                    chat_id,
                    tg_message_id,
                    reply_to_tg_id,
                    reply_sender,
                    reply_text,
                    u_name,
                    preview,
                    now,
                ),
            )
            conn.commit()

    def record_outgoing(
        self,
        chat_id: int,
        text: str,
        tg_message_id: int | None = None,
        reply_to_tg_id: int | None = None,
        reply_to_sender: str = "",
        reply_to_text: str = "",
        chat_type: str | None = None,
        title: str | None = None,
    ) -> int:
        now = _now_iso()
        clean_text = text.strip()
        preview = clean_text[:160]
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT chat_type, title FROM chats WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
            resolved_type = chat_type or (existing["chat_type"] if existing else "private")
            resolved_title = title or (existing["title"] if existing else f"Chat {chat_id}")

            conn.execute(
                """
                INSERT INTO chats (chat_id, chat_type, title, username, last_message, updated_at)
                VALUES (?, ?, ?, '', ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    last_message = excluded.last_message,
                    updated_at = excluded.updated_at,
                    title = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE chats.title END
                """,
                (
                    chat_id,
                    resolved_type,
                    resolved_title,
                    preview,
                    now,
                    title,
                    title,
                    title,
                ),
            )
            cur = conn.execute(
                """
                INSERT INTO messages (
                    chat_id, tg_message_id, reply_to_tg_id, reply_to_sender, reply_to_text,
                    sender_name, direction, text, created_at
                )
                VALUES (?, ?, ?, ?, ?, 'Bot', 'out', ?, ?)
                """,
                (
                    chat_id,
                    tg_message_id,
                    reply_to_tg_id,
                    reply_to_sender,
                    reply_to_text[:100],
                    clean_text,
                    now,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def update_outgoing_message(self, row_id: int, new_text: str) -> None:
        clean_text = new_text.strip()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE messages SET text = ? WHERE id = ? AND direction = 'out'",
                (clean_text, row_id),
            )
            conn.commit()

    def delete_outgoing_message(self, row_id: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM messages WHERE id = ? AND direction = 'out'",
                (row_id,),
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
                    "SELECT * FROM chats WHERE chat_type IN ('group', 'supergroup', 'channel') ORDER BY updated_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_contacts(self) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM contacts ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_messages(self, chat_id: int, limit: int = 100) -> list[dict]:
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
        if kind == "contacts":
            if active_id is not None:
                c_row = next((c for c in contacts if c["user_id"] == active_id), None)
                if c_row and c_row.get("last_chat_id"):
                    active_id = c_row["last_chat_id"]
            if active_id is None and contacts:
                active_id = contacts[0].get("last_chat_id") or contacts[0]["user_id"]
        else:
            valid_ids = {c["chat_id"] for c in chats}
            if active_id not in valid_ids:
                active_id = chats[0]["chat_id"] if chats else None

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

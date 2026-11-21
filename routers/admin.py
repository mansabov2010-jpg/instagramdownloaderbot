from __future__ import annotations

import html
import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Settings
from services.inbox_store import InboxStore

router = Router(name="admin_menu")
logger = logging.getLogger(__name__)

_ADMIN_SESSIONS: dict[int, dict[str, str]] = {}


def _is_admin(user_id: int | None, settings: Settings) -> bool:
    if not user_id:
        return False
    admins = {int(uid) for uid in (settings.auth_users or ())}
    return user_id in admins


def _admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 A'zolar", callback_data="adm:users"),
                InlineKeyboardButton(text="💬 Guruhlar", callback_data="adm:groups"),
            ],
            [
                InlineKeyboardButton(text="📢 Barchaga xabar", callback_data="adm:bc_menu"),
                InlineKeyboardButton(text="🔒 Majburiy obuna", callback_data="adm:fsub_menu"),
            ],
            [InlineKeyboardButton(text="✖️ Yopish", callback_data="adm:close")],
        ]
    )


def _normalize_target(raw: str) -> tuple[str, str]:
    val = raw.strip()
    if not val:
        return "", ""
    if val.lstrip("-").isdigit():
        return val, ""
    m = re.search(r"(?:https?://)?(?:t\.me|telegram\.me)/([A-Za-z0-9_]+)/?", val)
    if m:
        uname = m.group(1)
        return f"@{uname}", f"https://t.me/{uname}"
    clean = val.lstrip("@")
    return f"@{clean}", f"https://t.me/{clean}"


async def _refresh_group_counts(bot: Bot, inbox_store: InboxStore) -> list[dict]:
    groups = inbox_store.get_chats("groups")
    for g in groups:
        cid = int(g["chat_id"])
        try:
            cnt = await bot.get_chat_member_count(chat_id=cid)
            if isinstance(cnt, int) and cnt > 0:
                inbox_store.set_chat_member_count(cid, cnt)
                g["member_count"] = cnt
        except Exception:
            pass
    return inbox_store.get_chats("groups")


@router.message(Command("admin"))
async def cmd_admin(message: Message, settings: Settings, inbox_store: InboxStore) -> None:
    if not message.from_user or not _is_admin(message.from_user.id, settings):
        return
    _ADMIN_SESSIONS.pop(message.from_user.id, None)
    stats = inbox_store.get_stats_summary()
    await message.answer(
        "🛠 <b>Admin Boshqaruv Menyusi</b>\n\n"
        f"👥 <b>A’zolar:</b> {stats['users_count']} ta\n"
        f"💬 <b>Guruh / Kanallar:</b> {stats['groups_count']} ta\n"
        f"👤 <b>Guruhlardagi jami odamlar:</b> ~{stats['total_group_members']} ta\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=_admin_keyboard(),
    )


@router.callback_query(F.data.startswith("adm:"))
async def on_admin_callback(
    callback: CallbackQuery,
    bot: Bot,
    settings: Settings,
    inbox_store: InboxStore,
) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id, settings):
        await callback.answer("Faqat adminlar uchun!", show_alert=True)
        return

    uid = callback.from_user.id
    action = (callback.data or "").split(":", 1)[1]

    if action == "close":
        _ADMIN_SESSIONS.pop(uid, None)
        if callback.message:
            await callback.message.delete()
        await callback.answer()
        return

    if action == "back":
        _ADMIN_SESSIONS.pop(uid, None)
        stats = inbox_store.get_stats_summary()
        if callback.message:
            await callback.message.edit_text(
                "🛠 <b>Admin Boshqaruv Menyusi</b>\n\n"
                f"👥 <b>A’zolar:</b> {stats['users_count']} ta\n"
                f"💬 <b>Guruh / Kanallar:</b> {stats['groups_count']} ta\n"
                f"👤 <b>Guruhlardagi jami odamlar:</b> ~{stats['total_group_members']} ta\n\n"
                "Kerakli bo‘limni tanlang:",
                reply_markup=_admin_keyboard(),
            )
        await callback.answer()
        return

    if action == "users":
        stats = inbox_store.get_stats_summary()
        contacts = inbox_store.get_contacts()[:15]
        lines = [
            "👥 <b>A’zolar Statistikasi</b>\n",
            f"• <b>Umumiy a’zolar:</b> {stats['users_count']} ta",
            f"• <b>Lichka chatlar:</b> {stats['private_chats_count']} ta\n",
        ]
        if contacts:
            lines.append("<b>So‘nggi faol a’zolar:</b>")
            for idx, c in enumerate(contacts, start=1):
                uname = f" (@{html.escape(c['username'])})" if c.get("username") else ""
                lines.append(f"{idx}. {html.escape(c['full_name'])}{uname} — <code>{c['user_id']}</code>")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:back")]]
        )
        if callback.message:
            await callback.message.edit_text("\n".join(lines), reply_markup=kb)
        await callback.answer()
        return

    if action == "groups":
        groups = await _refresh_group_counts(bot, inbox_store)
        total_members = sum(int(g.get("member_count") or 0) for g in groups)
        lines = [
            "💬 <b>Guruh va Kanallar Statistikasi</b>\n",
            f"• <b>Umumiy guruh/kanallar:</b> {len(groups)} ta",
            f"• <b>Guruhlardagi jami odamlar:</b> ~{total_members} ta\n",
        ]
        if not groups:
            lines.append("Hozircha guruh yoki kanal topilmadi.")
        else:
            for idx, g in enumerate(groups, start=1):
                title = html.escape(g.get("title") or f"Chat {g['chat_id']}")
                cnt = int(g.get("member_count") or 0)
                cnt_text = f"~{cnt} ta odam" if cnt > 0 else "aniqlanmagan"
                lines.append(f"{idx}. <b>{title}</b> — <b>{cnt_text}</b> (<code>{g['chat_id']}</code>)")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Yangilash", callback_data="adm:groups")],
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:back")],
            ]
        )
        if callback.message:
            await callback.message.edit_text("\n".join(lines), reply_markup=kb)
        await callback.answer("Yangilandi")
        return

    if action == "bc_menu":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📨 Barchaga (A'zolar + Guruhlar)", callback_data="adm:bc_all")],
                [InlineKeyboardButton(text="👥 Faqat A'zolarga", callback_data="adm:bc_users")],
                [InlineKeyboardButton(text="💬 Faqat Guruhlarga", callback_data="adm:bc_groups")],
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:back")],
            ]
        )
        if callback.message:
            await callback.message.edit_text(
                "📢 <b>Barchaga xabar yuborish</b>\n\nKimga yubormoqchisiz?",
                reply_markup=kb,
            )
        await callback.answer()
        return

    if action in ("bc_all", "bc_users", "bc_groups"):
        _ADMIN_SESSIONS[uid] = {"mode": "broadcast", "scope": action}
        scope_label = {
            "bc_all": "barcha a'zolar va guruhlarga",
            "bc_users": "faqat a'zolarga",
            "bc_groups": "faqat guruh/kanallarga",
        }[action]
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm:back")]]
        )
        if callback.message:
            await callback.message.edit_text(
                f"✍️ <b>{scope_label}</b> yuboriladigan xabar matnini yozib yuboring:",
                reply_markup=kb,
            )
        await callback.answer()
        return

    if action == "fsub_menu":
        subs = inbox_store.list_force_subs()
        lines = ["🔒 <b>Majburiy Obuna Boshqaruvi</b>\n"]
        if not subs:
            lines.append("Majburiy obuna qo‘shilmagan — bot odatdagidek ishlaydi.")
        else:
            for s in subs:
                lines.append(
                    f"• <b>{html.escape(s.get('title') or s['target'])}</b> — {html.escape(s['target'])}"
                )
        rows: list[list[InlineKeyboardButton]] = [
            [InlineKeyboardButton(text="➕ Majburiy obuna qo'shish", callback_data="adm:fsub_add")]
        ]
        for s in subs:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"🗑 O'chirish: {s.get('title') or s['target']}",
                        callback_data=f"adm:fsub_del:{s['id']}",
                    )
                ]
            )
        rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm:back")])
        if callback.message:
            await callback.message.edit_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            )
        await callback.answer()
        return

    if action == "fsub_add":
        _ADMIN_SESSIONS[uid] = {"mode": "add_forcesub"}
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm:fsub_menu")]]
        )
        if callback.message:
            await callback.message.edit_text(
                "🔗 <b>Majburiy obuna uchun kanal yoki guruh havolasini yuboring!</b>\n\n"
                "Masalan: <code>https://t.me/kanal_nomi</code> yoki <code>@kanal_nomi</code>\n"
                "<i>Bot o‘sha kanal yoki guruhda admin bo‘lishi kerak.</i>",
                reply_markup=kb,
            )
        await callback.answer()
        return

    if action.startswith("fsub_del:"):
        sub_id_str = action.split(":", 1)[1]
        if sub_id_str.isdigit():
            inbox_store.remove_force_sub(int(sub_id_str))
        await callback.answer("O'chirildi")
        callback.data = "adm:fsub_menu"
        await on_admin_callback(callback, bot, settings, inbox_store)


@router.message(F.chat.type == "private", F.text, ~F.text.startswith("/"))
async def handle_admin_session_input(
    message: Message,
    bot: Bot,
    settings: Settings,
    inbox_store: InboxStore,
) -> None:
    if not message.from_user or not _is_admin(message.from_user.id, settings):
        return
    uid = message.from_user.id
    session = _ADMIN_SESSIONS.get(uid)
    if not session:
        return

    mode = session.get("mode")
    txt = (message.text or "").strip()
    if not txt:
        return

    if mode == "broadcast":
        _ADMIN_SESSIONS.pop(uid, None)
        scope = session.get("scope", "bc_all")
        inc_contacts = scope in ("bc_all", "bc_users")
        inc_groups = scope in ("bc_all", "bc_groups")
        targets = inbox_store.get_broadcast_targets(
            include_contacts=inc_contacts,
            include_groups=inc_groups,
        )
        sent = 0
        failed = 0
        for tid in targets:
            try:
                msg = await bot.send_message(chat_id=tid, text=txt)
                inbox_store.record_outgoing(
                    chat_id=tid,
                    text=txt,
                    tg_message_id=msg.message_id,
                )
                sent += 1
            except Exception:
                failed += 1

        await message.answer(
            f"✅ <b>Xabar tarqatish yakunlandi!</b>\n\n"
            f"• Yuborildi: <b>{sent}</b> ta chatga\n"
            f"• Xato / yetib bormadi: <b>{failed}</b> ta",
            reply_markup=_admin_keyboard(),
        )
        return

    if mode == "add_forcesub":
        _ADMIN_SESSIONS.pop(uid, None)
        target, invite_url = _normalize_target(txt)
        if not target:
            await message.answer(
                "⚠️ Havola yoki username noto‘g‘ri. Qaytadan <code>/admin</code> → <b>Majburiy obuna</b> orqali urinib ko‘ring.",
                reply_markup=_admin_keyboard(),
            )
            return

        title = target
        try:
            chat_info = await bot.get_chat(target)
            if chat_info.title:
                title = chat_info.title
            if not invite_url:
                invite_url = chat_info.invite_link or (
                    f"https://t.me/{target.lstrip('@')}" if target.startswith("@") else ""
                )
        except Exception as exc:
            logger.warning("get_chat failed for force_sub %s: %s", target, exc)

        if not invite_url:
            await message.answer(
                "⚠️ Ushbu kanal/guruh uchun <code>https://t.me/...</code> havola aniqlanmadi. Havolani to‘liq yuboring.",
                reply_markup=_admin_keyboard(),
            )
            return

        inbox_store.add_force_sub(target=target, title=title, invite_url=invite_url)
        await message.answer(
            f"✅ <b>Majburiy obuna qo‘shildi!</b>\n\n"
            f"• Kanal/Guruh: <b>{html.escape(title)}</b>\n"
            f"• Manzil: <code>{html.escape(target)}</code>\n"
            f"• Havola: {html.escape(invite_url)}",
            reply_markup=_admin_keyboard(),
        )

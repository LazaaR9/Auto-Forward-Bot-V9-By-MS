"""
Project flow:
1. User clicks "Add Forwarding Project"
2. Choose mode: With Bot / Without Bot
3. Name the project
4. Set Source Channel (ID or forward)
5. Add Destination Channel(s)
6. Configure Filters
7. Set Forward Mode (with/without tag)
8. Save or Clear
"""
import asyncio
from bson import ObjectId
from database import db
from config import Config
from translation import Translation
from plugins.helpers import (
    is_premium_or_owner, get_channel_id_from_input,
    MAX_PROJECTS_FREE, MAX_DESTINATIONS_FREE
)
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
)

MAX_KEYWORDS = 10  # Max keywords allowed for Keyword Filter / Keyword Replace / Keyword Unfilter (for all users)
MAX_FILE_EXTENSIONS = 3  # Max extensions allowed for F Keywords Filter (unchanged)

# ─── Temporary in-memory state per user during project creation ──────────────
_draft: dict = {}   # user_id -> draft project dict

def _get_draft(user_id: int) -> dict:
    if user_id not in _draft:
        _draft[user_id] = {
            "name": "",
            "mode": "with_bot",     # with_bot / without_bot
            "source_id": None,
            "source_title": "",
            "destinations": [],     # list of {"id": ..., "title": ...}
            "filters": None,        # will be filled with db defaults
            "forward_tag": False,   # True = send with "Forwarded from" tag
        }
    return _draft[user_id]

def _clear_draft(user_id: int):
    _draft.pop(user_id, None)


# ─── Filters keyboard ────────────────────────────────────────────────────────
def _filters_markup(project_filters: dict, project_id: str = "draft"):
    keys = ["text", "photo", "video", "audio", "document", "voice", "animation", "sticker", "poll"]
    labels = {
        "text": "🖍️ Text", "photo": "📷 Photo", "video": "🎞️ Video",
        "audio": "🎧 Audio", "document": "📁 Document", "voice": "🎤 Voice",
        "animation": "🎭 Animation", "sticker": "🃏 Sticker", "poll": "📊 Poll",
    }
    buttons = []
    for k in keys:
        val = project_filters.get(k, True)
        icon = "✅" if val else "❌"
        buttons.append([
            InlineKeyboardButton(labels[k], callback_data=f"pf_label_{k}_{project_id}"),
            InlineKeyboardButton(icon, callback_data=f"pf_toggle_{k}_{project_id}"),
        ])
    buttons.append([InlineKeyboardButton("↩️ Back", callback_data=f"proj_edit_menu_{project_id}")])
    return InlineKeyboardMarkup(buttons)


def _fwd_mode_markup(forward_tag: bool, project_id: str = "draft"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{'✅' if not forward_tag else '🔘'} Without Tag (Copy)", callback_data=f"pf_tag_False_{project_id}"),
        ],
        [
            InlineKeyboardButton(f"{'✅' if forward_tag else '🔘'} With Forward Tag", callback_data=f"pf_tag_True_{project_id}"),
        ],
        [InlineKeyboardButton("↩️ Back", callback_data=f"proj_edit_menu_{project_id}")],
    ])


def _project_edit_markup(project_id: str, p: dict):
    source = p.get("source_title") or p.get("source_id") or "Not set"
    dests = p.get("destinations", [])
    dest_str = f"{len(dests)} set" if dests else "None"
    fwd = "With Tag ✅" if p.get("forward_tag") else "Without Tag ✅"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📌 Source: {source}", callback_data=f"proj_set_source_{project_id}")],
        [InlineKeyboardButton(f"📩 Destinations: {dest_str}", callback_data=f"proj_list_dests_{project_id}")],
        [
            InlineKeyboardButton("🔍 Filter Type", callback_data=f"proj_filters_{project_id}"),
            InlineKeyboardButton(f"📤 Forward Mode", callback_data=f"proj_fwd_mode_{project_id}"),
        ],
        [InlineKeyboardButton("⚙️ Additional Options", callback_data=f"proj_additional_{project_id}")],
        [InlineKeyboardButton("✅ Save Project", callback_data=f"proj_save_{project_id}")],
        [
            InlineKeyboardButton("🗑️ Clear Project", callback_data=f"proj_clear_{project_id}"),
            InlineKeyboardButton("↩️ Back", callback_data="my_projects"),
        ],
    ])


async def _project_summary(p: dict) -> str:
    source = p.get("source_title") or p.get("source_id") or "Not set"
    dests = p.get("destinations", [])
    dest_names = ", ".join(d.get("title", str(d.get("id", ""))) for d in dests) or "None"
    fwd = "With Forward Tag" if p.get("forward_tag") else "Without Forward Tag (Copy)"
    mode = "With Bot" if p.get("mode") == "with_bot" else "Without Bot (Userbot)"
    return (
        f"<b>📋 Project: {p.get('name', 'Unnamed')}</b>\n\n"
        f"• Mode: {mode}\n"
        f"• Source: <code>{source}</code>\n"
        f"• Destinations: {dest_names}\n"
        f"• Forward Mode: {fwd}\n"
    )


# ─── My Projects ─────────────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex("^my_projects$"))
async def my_projects_cb(bot: Client, query: CallbackQuery):
    user_id = query.from_user.id
    projects = await db.get_projects(user_id)
    if not projects:
        await query.message.edit_text(
            "<b>📋 My Forwarding Projects</b>\n\nYou have no projects yet.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Project", callback_data="project_add_start")],
                [InlineKeyboardButton("↩️ Back", callback_data="back_main")],
            ])
        )
        return
    buttons = []
    for p in projects:
        pid = str(p["_id"])
        name = p.get("name", "Unnamed")
        buttons.append([InlineKeyboardButton(f"📁 {name}", callback_data=f"proj_view_{pid}")])
    buttons.append([InlineKeyboardButton("➕ Add New Project", callback_data="project_add_start")])
    buttons.append([InlineKeyboardButton("↩️ Back", callback_data="back_main")])
    await query.message.edit_text(
        f"<b>📋 My Forwarding Projects</b>\n\n{len(projects)} project(s):",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@Client.on_callback_query(filters.regex(r"^proj_view_(.+)$"))
async def proj_view_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    if not p:
        await query.answer("Project not found!", show_alert=True)
        return
    summary = await _project_summary(p)
    await query.message.edit_text(
        summary,
        reply_markup=_project_edit_markup(project_id, p)
    )


# ─── Add New Project ─────────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex("^project_add_start$"))
async def project_add_start(bot: Client, query: CallbackQuery):
    user_id = query.from_user.id
    premium = await is_premium_or_owner(user_id)
    count = await db.count_projects(user_id)
    if not premium and count >= MAX_PROJECTS_FREE:
        await query.message.edit_text(
            Translation.PROJECT_LIMIT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ Upgrade", callback_data="premium_info")],
                [InlineKeyboardButton("↩️ Back", callback_data="back_main")],
            ])
        )
        return
    _clear_draft(user_id)
    _get_draft(user_id)  # init
    await query.message.edit_text(
        "<b>➕ Add Forwarding Project</b>\n\nChoose forwarding mode:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🤖 With Bot", callback_data="proj_mode_with_bot")],
            [InlineKeyboardButton("🚫 Without Bot (Userbot)", callback_data="proj_mode_without_bot")],
            [InlineKeyboardButton("↩️ Back", callback_data="back_main")],
        ])
    )


@Client.on_callback_query(filters.regex(r"^proj_mode_(with_bot|without_bot)$"))
async def proj_mode_cb(bot: Client, query: CallbackQuery):
    user_id = query.from_user.id
    mode = query.matches[0].group(1)
    _get_draft(user_id)["mode"] = mode

    _bot = await db.get_bot(user_id)
    if not _bot:
        kind = "bot token" if mode == "with_bot" else "userbot session"
        await query.message.edit_text(
            f"⚠️ You haven't added a {kind} yet. Please go to <b>My Bot / Userbot</b> to add one first.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🤖 Add Bot/Userbot", callback_data="my_bot")],
                [InlineKeyboardButton("↩️ Back", callback_data="project_add_start")],
            ])
        )
        return

    # Ask for project name
    await query.message.delete()
    prompt = await bot.send_message(user_id, Translation.PROJECT_NAME_PROMPT)
    try:
        msg = await bot.listen(chat_id=user_id, timeout=120)
    except asyncio.TimeoutError:
        await prompt.edit_text("⏰ Timed out.")
        return
    if not msg or (msg.text and msg.text == "/cancel"):
        await prompt.edit_text(Translation.CANCEL)
        return
    name = msg.text.strip() if msg.text else "My Project"
    await msg.delete()
    _get_draft(user_id)["name"] = name
    _get_draft(user_id)["filters"] = db.default_filters()

    # Create a temp project in DB so we have an ID to work with
    draft = _get_draft(user_id)
    project = {
        "user_id": user_id,
        "name": draft["name"],
        "mode": draft["mode"],
        "source_id": None,
        "source_title": "",
        "destinations": [],
        "filters": draft["filters"],
        "forward_tag": False,
        "active": False,
        "keyword_replace": db.default_keyword_replace(),
        "keyword_filter": db.default_keyword_filter(),
    }
    await db.add_project(project)
    # Retrieve newly created project
    projects = await db.get_projects(user_id)
    p = projects[-1]
    pid = str(p["_id"])
    _clear_draft(user_id)

    summary = await _project_summary(p)
    await prompt.edit_text(
        f"{summary}\n<i>Now configure your project using the buttons below:</i>",
        reply_markup=_project_edit_markup(pid, p)
    )


# ─── Edit menu (for existing projects) ───────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^proj_edit_menu_(.+)$"))
async def proj_edit_menu_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    if not p:
        await query.answer("Project not found!", show_alert=True)
        return
    summary = await _project_summary(p)
    await query.message.edit_text(summary, reply_markup=_project_edit_markup(project_id, p))


# ─── Set Source Channel ───────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^proj_set_source_(.+)$"))
async def proj_set_source_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    user_id = query.from_user.id
    await query.message.delete()
    prompt = await bot.send_message(user_id, Translation.SOURCE_PROMPT)
    try:
        msg = await bot.listen(chat_id=user_id, timeout=300)
    except asyncio.TimeoutError:
        await prompt.edit_text("⏰ Timed out.")
        return
    if not msg or msg.text == "/cancel":
        await prompt.edit_text(Translation.CANCEL)
        _show_project_after_edit(bot, user_id, project_id, prompt)
        return

    chat_id, title = await get_channel_id_from_input(bot, msg.text or "", fwd_msg=msg)
    if not chat_id:
        await prompt.edit_text("❌ Could not resolve channel. Send a valid channel ID or forward a message from it.")
        return
    await msg.delete()
    await db.update_project(project_id, {"source_id": chat_id, "source_title": title or str(chat_id)})
    p = await db.get_project(project_id)
    summary = await _project_summary(p)
    await prompt.edit_text(
        f"✅ Source set to: <code>{title or chat_id}</code>\n\n{summary}",
        reply_markup=_project_edit_markup(project_id, p)
    )


# ─── Destinations ─────────────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^proj_list_dests_(.+)$"))
async def proj_list_dests_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    if not p:
        await query.answer("Project not found!", show_alert=True)
        return
    dests = p.get("destinations", [])
    buttons = []
    for i, d in enumerate(dests):
        buttons.append([
            InlineKeyboardButton(
                f"📩 {d.get('title', d.get('id'))}",
                callback_data=f"proj_dest_info_{project_id}_{i}"
            ),
            InlineKeyboardButton("🗑️", callback_data=f"proj_dest_del_{project_id}_{i}")
        ])
    buttons.append([InlineKeyboardButton("➕ Add Destination", callback_data=f"proj_add_dest_{project_id}")])
    buttons.append([InlineKeyboardButton("↩️ Back", callback_data=f"proj_edit_menu_{project_id}")])
    await query.message.edit_text(
        f"<b>📩 Destinations for: {p.get('name', 'Project')}</b>\n\n{len(dests)} destination(s):",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@Client.on_callback_query(filters.regex(r"^proj_add_dest_(.+)$"))
async def proj_add_dest_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    user_id = query.from_user.id
    premium = await is_premium_or_owner(user_id)
    p = await db.get_project(project_id)
    if not premium and len(p.get("destinations", [])) >= MAX_DESTINATIONS_FREE:
        await query.answer(Translation.DEST_LIMIT, show_alert=True)
        return
    await query.message.delete()
    prompt = await bot.send_message(user_id, Translation.DEST_PROMPT)
    try:
        msg = await bot.listen(chat_id=user_id, timeout=300)
    except asyncio.TimeoutError:
        await prompt.edit_text("⏰ Timed out.")
        return
    if not msg or msg.text == "/cancel":
        await prompt.edit_text(Translation.CANCEL)
        return
    chat_id, title = await get_channel_id_from_input(bot, msg.text or "", fwd_msg=msg)
    if not chat_id:
        await prompt.edit_text("❌ Could not resolve channel.")
        return
    await msg.delete()
    p = await db.get_project(project_id)
    dests = p.get("destinations", [])
    if any(d["id"] == chat_id for d in dests):
        await prompt.edit_text(Translation.DEST_EXISTS)
        return
    dests.append({"id": chat_id, "title": title or str(chat_id)})
    await db.update_project(project_id, {"destinations": dests})
    p = await db.get_project(project_id)
    summary = await _project_summary(p)
    await prompt.edit_text(
        f"✅ Destination added: <code>{title or chat_id}</code>\n\n{summary}",
        reply_markup=_project_edit_markup(project_id, p)
    )


@Client.on_callback_query(filters.regex(r"^proj_dest_del_(.+)_(\d+)$"))
async def proj_dest_del_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    idx = int(query.matches[0].group(2))
    p = await db.get_project(project_id)
    dests = p.get("destinations", [])
    if 0 <= idx < len(dests):
        dests.pop(idx)
        await db.update_project(project_id, {"destinations": dests})
    await query.answer("Destination removed!", show_alert=False)
    p = await db.get_project(project_id)
    # Refresh destinations list
    buttons = []
    for i, d in enumerate(p.get("destinations", [])):
        buttons.append([
            InlineKeyboardButton(f"📩 {d.get('title', d.get('id'))}", callback_data=f"proj_dest_info_{project_id}_{i}"),
            InlineKeyboardButton("🗑️", callback_data=f"proj_dest_del_{project_id}_{i}")
        ])
    buttons.append([InlineKeyboardButton("➕ Add Destination", callback_data=f"proj_add_dest_{project_id}")])
    buttons.append([InlineKeyboardButton("↩️ Back", callback_data=f"proj_edit_menu_{project_id}")])
    await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))


# ─── Filters ─────────────────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^proj_filters_(.+)$"))
async def proj_filters_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    f = p.get("filters") or db.default_filters()
    await query.message.edit_text(
        "<b>🔍 Filter Type</b>\n\nChoose which message types to forward (✅ = forward, ❌ = skip):",
        reply_markup=_filters_markup(f, project_id)
    )


@Client.on_callback_query(filters.regex(r"^pf_toggle_(\w+)_(.+)$"))
async def pf_toggle_cb(bot: Client, query: CallbackQuery):
    key = query.matches[0].group(1)
    project_id = query.matches[0].group(2)
    p = await db.get_project(project_id)
    f = p.get("filters") or db.default_filters()
    f[key] = not f.get(key, True)
    await db.update_project(project_id, {"filters": f})
    await query.message.edit_reply_markup(_filters_markup(f, project_id))


@Client.on_callback_query(filters.regex(r"^pf_label_"))
async def pf_label_noop(bot: Client, query: CallbackQuery):
    await query.answer()


# ─── Forward Mode ─────────────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^proj_fwd_mode_(.+)$"))
async def proj_fwd_mode_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    await query.message.edit_text(
        "<b>📤 Forward Mode</b>\n\nChoose how messages are sent to destination:",
        reply_markup=_fwd_mode_markup(p.get("forward_tag", False), project_id)
    )


@Client.on_callback_query(filters.regex(r"^pf_tag_(True|False)_(.+)$"))
async def pf_tag_cb(bot: Client, query: CallbackQuery):
    val = query.matches[0].group(1) == "True"
    project_id = query.matches[0].group(2)
    await db.update_project(project_id, {"forward_tag": val})
    p = await db.get_project(project_id)
    await query.message.edit_reply_markup(_fwd_mode_markup(val, project_id))


# ═══════════════════════════════════════════════════════════════════════════════
# ─── Additional Options ────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def _additional_markup(project_id: str, p: dict):
    """Main Additional Options menu."""
    kr = p.get("keyword_replace") or db.default_keyword_replace()
    kf = p.get("keyword_filter") or db.default_keyword_filter()
    ff = p.get("file_filter") or db.default_file_filter()
    ku = p.get("keyword_unfilter") or db.default_keyword_unfilter()

    kr_status = "✅ ON" if kr.get("enabled") else "❌ OFF"
    kf_status = "✅ ON" if kf.get("enabled") else "❌ OFF"
    ff_status = "✅ ON" if ff.get("enabled") else "❌ OFF"
    ku_status = "✅ ON" if ku.get("enabled") else "❌ OFF"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔄 Keyword Replace  [{kr_status}]", callback_data=f"proj_kr_menu_{project_id}")],
        [InlineKeyboardButton(f"🔎 Keyword Filter  [{kf_status}]", callback_data=f"proj_kf_menu_{project_id}")],
        [InlineKeyboardButton(f"📂 F Keywords Filter  [{ff_status}]", callback_data=f"proj_ff_menu_{project_id}")],
        [InlineKeyboardButton(f"🚫 Keyword Unfilter  [{ku_status}]", callback_data=f"proj_ku_menu_{project_id}")],
        [InlineKeyboardButton("↩️ Back", callback_data=f"proj_edit_menu_{project_id}")],
    ])


@Client.on_callback_query(filters.regex(r"^proj_additional_(.+)$"))
async def proj_additional_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    if not p:
        await query.answer("Project not found!", show_alert=True)
        return
    await query.message.edit_text(
        "<b>⚙️ Additional Options</b>\n\nChoose a feature to configure:",
        reply_markup=_additional_markup(project_id, p)
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ─── KEYWORD REPLACE ───────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def _kr_menu_markup(project_id: str, kr: dict):
    """Keyword Replace settings menu."""
    enabled = kr.get("enabled", False)
    pairs = kr.get("pairs", [])

    toggle_label = "🔴 Turn OFF" if enabled else "🟢 Turn ON"
    buttons = [
        [InlineKeyboardButton(toggle_label, callback_data=f"proj_kr_toggle_{project_id}")],
    ]

    # Show current pairs
    if pairs:
        buttons.append([InlineKeyboardButton("─── Current Keywords ───", callback_data="noop")])
        for i, pair in enumerate(pairs):
            buttons.append([
                InlineKeyboardButton(
                    f"🔁 {pair['old']} → {pair['new']}",
                    callback_data="noop"
                ),
                InlineKeyboardButton("🗑️", callback_data=f"proj_kr_del_{project_id}_{i}"),
            ])

    if len(pairs) < MAX_KEYWORDS:
        buttons.append([InlineKeyboardButton("➕ Add Keyword Pair", callback_data=f"proj_kr_add_{project_id}")])

    buttons.append([InlineKeyboardButton("↩️ Back", callback_data=f"proj_additional_{project_id}")])
    return InlineKeyboardMarkup(buttons)


def _kr_info_text(kr: dict) -> str:
    enabled = kr.get("enabled", False)
    pairs = kr.get("pairs", [])
    status = "✅ ON" if enabled else "❌ OFF"
    pair_lines = "\n".join(f"  • <code>{p['old']}</code> → <code>{p['new']}</code>" for p in pairs) or "  (none)"
    return (
        f"<b>🔄 Keyword Replace</b>  [{status}]\n\n"
        f"Replaces old keywords with new ones in caption (exact match, case-sensitive).\n\n"
        f"<b>Format to add:</b> <code>OldWord&NewWord</code>\n"
        f"<b>Multiple:</b> <code>Old1&New1,Old2&New2</code>\n\n"
        f"<b>Current pairs ({len(pairs)}/{MAX_KEYWORDS}):</b>\n{pair_lines}"
    )


@Client.on_callback_query(filters.regex(r"^proj_kr_menu_(.+)$"))
async def proj_kr_menu_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    if not p:
        await query.answer("Project not found!", show_alert=True)
        return
    kr = p.get("keyword_replace") or db.default_keyword_replace()
    await query.message.edit_text(
        _kr_info_text(kr),
        reply_markup=_kr_menu_markup(project_id, kr)
    )


@Client.on_callback_query(filters.regex(r"^proj_kr_toggle_(.+)$"))
async def proj_kr_toggle_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    kr = p.get("keyword_replace") or db.default_keyword_replace()
    kr["enabled"] = not kr.get("enabled", False)
    await db.update_project(project_id, {"keyword_replace": kr})
    await query.message.edit_text(
        _kr_info_text(kr),
        reply_markup=_kr_menu_markup(project_id, kr)
    )


@Client.on_callback_query(filters.regex(r"^proj_kr_add_(.+)$"))
async def proj_kr_add_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    user_id = query.from_user.id
    p = await db.get_project(project_id)
    kr = p.get("keyword_replace") or db.default_keyword_replace()
    pairs = kr.get("pairs", [])

    if len(pairs) >= MAX_KEYWORDS:
        await query.answer(f"Maximum {MAX_KEYWORDS} keyword pairs allowed!", show_alert=True)
        return

    await query.message.delete()
    prompt = await bot.send_message(
        user_id,
        f"<b>➕ Add Keyword Replace Pair(s)</b>\n\n"
        f"Send in format:\n"
        f"• Single: <code>OldKeyword&NewKeyword</code>\n"
        f"• Multiple: <code>Old1&New1,Old2&New2</code>\n\n"
        f"⚠️ Case-sensitive | Max {MAX_KEYWORDS} total pairs\n"
        f"Current: {len(pairs)}/{MAX_KEYWORDS}\n\n"
        f"/cancel to cancel"
    )
    try:
        msg = await bot.listen(chat_id=user_id, timeout=120)
    except asyncio.TimeoutError:
        await prompt.edit_text("⏰ Timed out.")
        return
    if not msg or (msg.text and msg.text.strip() == "/cancel"):
        await prompt.edit_text(Translation.CANCEL)
        return

    text = msg.text.strip() if msg.text else ""
    await msg.delete()

    # Parse pairs: "Old1&New1,Old2&New2"
    new_pairs = []
    errors = []
    entries = [e.strip() for e in text.split(",") if e.strip()]
    for entry in entries:
        if "&" not in entry:
            errors.append(f"❌ Invalid format: <code>{entry}</code> (missing &)")
            continue
        parts = entry.split("&", 1)
        old_kw = parts[0].strip()
        new_kw = parts[1].strip()
        if not old_kw or not new_kw:
            errors.append(f"❌ Empty keyword in: <code>{entry}</code>")
            continue
        new_pairs.append({"old": old_kw, "new": new_kw})

    # Check total limit
    can_add = MAX_KEYWORDS - len(pairs)
    if len(new_pairs) > can_add:
        new_pairs = new_pairs[:can_add]

    pairs.extend(new_pairs)
    kr["pairs"] = pairs
    await db.update_project(project_id, {"keyword_replace": kr})

    result_lines = [f"✅ Added: <code>{np['old']}</code> → <code>{np['new']}</code>" for np in new_pairs]
    if errors:
        result_lines.extend(errors)

    await prompt.edit_text(
        "\n".join(result_lines) + f"\n\n" + _kr_info_text(kr),
        reply_markup=_kr_menu_markup(project_id, kr)
    )


@Client.on_callback_query(filters.regex(r"^proj_kr_del_(.+)_(\d+)$"))
async def proj_kr_del_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    idx = int(query.matches[0].group(2))
    p = await db.get_project(project_id)
    kr = p.get("keyword_replace") or db.default_keyword_replace()
    pairs = kr.get("pairs", [])
    if 0 <= idx < len(pairs):
        removed = pairs.pop(idx)
        kr["pairs"] = pairs
        await db.update_project(project_id, {"keyword_replace": kr})
        await query.answer(f"Removed: {removed['old']} → {removed['new']}", show_alert=False)
    await query.message.edit_text(
        _kr_info_text(kr),
        reply_markup=_kr_menu_markup(project_id, kr)
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ─── KEYWORD FILTER ────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def _kf_menu_markup(project_id: str, kf: dict):
    """Keyword Filter settings menu."""
    enabled = kf.get("enabled", False)
    keywords = kf.get("keywords", [])

    toggle_label = "🔴 Turn OFF" if enabled else "🟢 Turn ON"
    buttons = [
        [InlineKeyboardButton(toggle_label, callback_data=f"proj_kf_toggle_{project_id}")],
    ]

    if keywords:
        buttons.append([InlineKeyboardButton("─── Current Keywords ───", callback_data="noop")])
        for i, kw in enumerate(keywords):
            buttons.append([
                InlineKeyboardButton(f"🔑 {kw}", callback_data="noop"),
                InlineKeyboardButton("🗑️", callback_data=f"proj_kf_del_{project_id}_{i}"),
            ])

    if len(keywords) < MAX_KEYWORDS:
        buttons.append([InlineKeyboardButton("➕ Add Keyword", callback_data=f"proj_kf_add_{project_id}")])

    buttons.append([InlineKeyboardButton("↩️ Back", callback_data=f"proj_additional_{project_id}")])
    return InlineKeyboardMarkup(buttons)


def _kf_info_text(kf: dict) -> str:
    enabled = kf.get("enabled", False)
    keywords = kf.get("keywords", [])
    status = "✅ ON" if enabled else "❌ OFF"
    kw_lines = "\n".join(f"  • <code>{kw}</code>" for kw in keywords) or "  (none)"
    return (
        f"<b>🔎 Keyword Filter</b>  [{status}]\n\n"
        f"Only forwards messages whose caption contains one of the set keywords (exact, case-sensitive).\n"
        f"If OFF or no keywords set → all messages forwarded.\n\n"
        f"<b>Format to add:</b> <code>keyword</code>\n"
        f"<b>Multiple:</b> <code>keyword1,keyword2</code>\n\n"
        f"<b>Current keywords ({len(keywords)}/{MAX_KEYWORDS}):</b>\n{kw_lines}"
    )


@Client.on_callback_query(filters.regex(r"^proj_kf_menu_(.+)$"))
async def proj_kf_menu_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    if not p:
        await query.answer("Project not found!", show_alert=True)
        return
    kf = p.get("keyword_filter") or db.default_keyword_filter()
    await query.message.edit_text(
        _kf_info_text(kf),
        reply_markup=_kf_menu_markup(project_id, kf)
    )


@Client.on_callback_query(filters.regex(r"^proj_kf_toggle_(.+)$"))
async def proj_kf_toggle_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    kf = p.get("keyword_filter") or db.default_keyword_filter()
    kf["enabled"] = not kf.get("enabled", False)
    await db.update_project(project_id, {"keyword_filter": kf})
    await query.message.edit_text(
        _kf_info_text(kf),
        reply_markup=_kf_menu_markup(project_id, kf)
    )


@Client.on_callback_query(filters.regex(r"^proj_kf_add_(.+)$"))
async def proj_kf_add_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    user_id = query.from_user.id
    p = await db.get_project(project_id)
    kf = p.get("keyword_filter") or db.default_keyword_filter()
    keywords = kf.get("keywords", [])

    if len(keywords) >= MAX_KEYWORDS:
        await query.answer(f"Maximum {MAX_KEYWORDS} keywords allowed!", show_alert=True)
        return

    await query.message.delete()
    prompt = await bot.send_message(
        user_id,
        f"<b>➕ Add Filter Keyword(s)</b>\n\n"
        f"Send keyword(s) to match in caption:\n"
        f"• Single: <code>keyword</code>\n"
        f"• Multiple: <code>keyword1,keyword2</code>\n\n"
        f"⚠️ Case-sensitive | Max {MAX_KEYWORDS} total\n"
        f"Current: {len(keywords)}/{MAX_KEYWORDS}\n\n"
        f"/cancel to cancel"
    )
    try:
        msg = await bot.listen(chat_id=user_id, timeout=120)
    except asyncio.TimeoutError:
        await prompt.edit_text("⏰ Timed out.")
        return
    if not msg or (msg.text and msg.text.strip() == "/cancel"):
        await prompt.edit_text(Translation.CANCEL)
        return

    text = msg.text.strip() if msg.text else ""
    await msg.delete()

    new_kws = [k.strip() for k in text.split(",") if k.strip()]
    can_add = MAX_KEYWORDS - len(keywords)
    new_kws = new_kws[:can_add]

    keywords.extend(new_kws)
    kf["keywords"] = keywords
    await db.update_project(project_id, {"keyword_filter": kf})

    added_lines = [f"✅ Added: <code>{kw}</code>" for kw in new_kws]
    await prompt.edit_text(
        "\n".join(added_lines) + "\n\n" + _kf_info_text(kf),
        reply_markup=_kf_menu_markup(project_id, kf)
    )


@Client.on_callback_query(filters.regex(r"^proj_kf_del_(.+)_(\d+)$"))
async def proj_kf_del_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    idx = int(query.matches[0].group(2))
    p = await db.get_project(project_id)
    kf = p.get("keyword_filter") or db.default_keyword_filter()
    keywords = kf.get("keywords", [])
    if 0 <= idx < len(keywords):
        removed = keywords.pop(idx)
        kf["keywords"] = keywords
        await db.update_project(project_id, {"keyword_filter": kf})
        await query.answer(f"Removed: {removed}", show_alert=False)
    await query.message.edit_text(
        _kf_info_text(kf),
        reply_markup=_kf_menu_markup(project_id, kf)
    )


@Client.on_callback_query(filters.regex("^noop$"))
async def noop_cb(bot: Client, query: CallbackQuery):
    await query.answer()


# ═══════════════════════════════════════════════════════════════════════════════
# ─── F KEYWORDS FILTER (FILE EXTENSION FILTER) ─────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def _ff_menu_markup(project_id: str, ff: dict):
    """F Keywords Filter (file extension) settings menu."""
    enabled = ff.get("enabled", False)
    extensions = ff.get("extensions", [])

    toggle_label = "🔴 Turn OFF" if enabled else "🟢 Turn ON"
    buttons = [
        [InlineKeyboardButton(toggle_label, callback_data=f"proj_ff_toggle_{project_id}")],
    ]

    if extensions:
        buttons.append([InlineKeyboardButton("─── Current Extensions ───", callback_data="noop")])
        for i, ext in enumerate(extensions):
            buttons.append([
                InlineKeyboardButton(f"📄 .{ext}", callback_data="noop"),
                InlineKeyboardButton("🗑️", callback_data=f"proj_ff_del_{project_id}_{i}"),
            ])

    if len(extensions) < MAX_FILE_EXTENSIONS:
        buttons.append([InlineKeyboardButton("➕ Add Extension", callback_data=f"proj_ff_add_{project_id}")])

    buttons.append([InlineKeyboardButton("↩️ Back", callback_data=f"proj_additional_{project_id}")])
    return InlineKeyboardMarkup(buttons)


def _ff_info_text(ff: dict) -> str:
    enabled = ff.get("enabled", False)
    extensions = ff.get("extensions", [])
    status = "✅ ON" if enabled else "❌ OFF"
    ext_lines = "\n".join(f"  • <code>.{ext}</code>" for ext in extensions) or "  (none)"
    return (
        f"<b>📂 F Keywords Filter (File Extension)</b>  [{status}]\n\n"
        f"Only forwards files whose extension matches one of the set extensions.\n"
        f"Messages without any file (text, etc.) are not affected by this filter.\n"
        f"If OFF or no extensions set → all files forwarded.\n\n"
        f"<b>Format to add:</b> <code>pdf</code>\n"
        f"<b>Multiple:</b> <code>pdf,zip,txt</code>\n\n"
        f"<b>Current extensions ({len(extensions)}/{MAX_FILE_EXTENSIONS}):</b>\n{ext_lines}"
    )


@Client.on_callback_query(filters.regex(r"^proj_ff_menu_(.+)$"))
async def proj_ff_menu_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    if not p:
        await query.answer("Project not found!", show_alert=True)
        return
    ff = p.get("file_filter") or db.default_file_filter()
    await query.message.edit_text(
        _ff_info_text(ff),
        reply_markup=_ff_menu_markup(project_id, ff)
    )


@Client.on_callback_query(filters.regex(r"^proj_ff_toggle_(.+)$"))
async def proj_ff_toggle_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    ff = p.get("file_filter") or db.default_file_filter()
    ff["enabled"] = not ff.get("enabled", False)
    await db.update_project(project_id, {"file_filter": ff})
    await query.message.edit_text(
        _ff_info_text(ff),
        reply_markup=_ff_menu_markup(project_id, ff)
    )


@Client.on_callback_query(filters.regex(r"^proj_ff_add_(.+)$"))
async def proj_ff_add_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    user_id = query.from_user.id
    p = await db.get_project(project_id)
    ff = p.get("file_filter") or db.default_file_filter()
    extensions = ff.get("extensions", [])

    if len(extensions) >= MAX_FILE_EXTENSIONS:
        await query.answer(f"Maximum {MAX_FILE_EXTENSIONS} extensions allowed!", show_alert=True)
        return

    await query.message.delete()
    prompt = await bot.send_message(
        user_id,
        f"<b>➕ Add File Extension(s)</b>\n\n"
        f"Send file extension(s) to allow (without dot):\n"
        f"• Single: <code>pdf</code>\n"
        f"• Multiple: <code>pdf,zip,txt</code>\n\n"
        f"⚠️ Max {MAX_FILE_EXTENSIONS} total\n"
        f"Current: {len(extensions)}/{MAX_FILE_EXTENSIONS}\n\n"
        f"/cancel to cancel"
    )
    try:
        msg = await bot.listen(chat_id=user_id, timeout=120)
    except asyncio.TimeoutError:
        await prompt.edit_text("⏰ Timed out.")
        return
    if not msg or (msg.text and msg.text.strip() == "/cancel"):
        await prompt.edit_text(Translation.CANCEL)
        return

    text = msg.text.strip() if msg.text else ""
    await msg.delete()

    new_exts = [e.strip().lower().lstrip(".") for e in text.split(",") if e.strip().strip(".")]
    can_add = MAX_FILE_EXTENSIONS - len(extensions)
    new_exts = new_exts[:can_add]

    extensions.extend(new_exts)
    ff["extensions"] = extensions
    await db.update_project(project_id, {"file_filter": ff})

    added_lines = [f"✅ Added: <code>.{ext}</code>" for ext in new_exts]
    await prompt.edit_text(
        "\n".join(added_lines) + "\n\n" + _ff_info_text(ff),
        reply_markup=_ff_menu_markup(project_id, ff)
    )


@Client.on_callback_query(filters.regex(r"^proj_ff_del_(.+)_(\d+)$"))
async def proj_ff_del_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    idx = int(query.matches[0].group(2))
    p = await db.get_project(project_id)
    ff = p.get("file_filter") or db.default_file_filter()
    extensions = ff.get("extensions", [])
    if 0 <= idx < len(extensions):
        removed = extensions.pop(idx)
        ff["extensions"] = extensions
        await db.update_project(project_id, {"file_filter": ff})
        await query.answer(f"Removed: .{removed}", show_alert=False)
    await query.message.edit_text(
        _ff_info_text(ff),
        reply_markup=_ff_menu_markup(project_id, ff)
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ─── KEYWORD UNFILTER (PROHIBITED KEYWORDS) ────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def _ku_menu_markup(project_id: str, ku: dict):
    """Keyword Unfilter settings menu."""
    enabled = ku.get("enabled", False)
    keywords = ku.get("keywords", [])

    toggle_label = "🔴 Turn OFF" if enabled else "🟢 Turn ON"
    buttons = [
        [InlineKeyboardButton(toggle_label, callback_data=f"proj_ku_toggle_{project_id}")],
    ]

    if keywords:
        buttons.append([InlineKeyboardButton("─── Current Keywords ───", callback_data="noop")])
        for i, kw in enumerate(keywords):
            buttons.append([
                InlineKeyboardButton(f"🚫 {kw}", callback_data="noop"),
                InlineKeyboardButton("🗑️", callback_data=f"proj_ku_del_{project_id}_{i}"),
            ])

    if len(keywords) < MAX_KEYWORDS:
        buttons.append([InlineKeyboardButton("➕ Add Keyword", callback_data=f"proj_ku_add_{project_id}")])

    buttons.append([InlineKeyboardButton("↩️ Back", callback_data=f"proj_additional_{project_id}")])
    return InlineKeyboardMarkup(buttons)


def _ku_info_text(ku: dict) -> str:
    enabled = ku.get("enabled", False)
    keywords = ku.get("keywords", [])
    status = "✅ ON" if enabled else "❌ OFF"
    kw_lines = "\n".join(f"  • <code>{kw}</code>" for kw in keywords) or "  (none)"
    return (
        f"<b>🚫 Keyword Unfilter</b>  [{status}]\n\n"
        f"Blocks (skips) messages whose caption/text contains any of these prohibited keywords (exact, case-sensitive).\n"
        f"If OFF or no keywords set → no message is blocked by this feature.\n\n"
        f"<b>Format to add:</b> <code>keyword</code>\n"
        f"<b>Multiple:</b> <code>keyword1,keyword2</code>\n\n"
        f"<b>Current keywords ({len(keywords)}/{MAX_KEYWORDS}):</b>\n{kw_lines}"
    )


@Client.on_callback_query(filters.regex(r"^proj_ku_menu_(.+)$"))
async def proj_ku_menu_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    if not p:
        await query.answer("Project not found!", show_alert=True)
        return
    ku = p.get("keyword_unfilter") or db.default_keyword_unfilter()
    await query.message.edit_text(
        _ku_info_text(ku),
        reply_markup=_ku_menu_markup(project_id, ku)
    )


@Client.on_callback_query(filters.regex(r"^proj_ku_toggle_(.+)$"))
async def proj_ku_toggle_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    ku = p.get("keyword_unfilter") or db.default_keyword_unfilter()
    ku["enabled"] = not ku.get("enabled", False)
    await db.update_project(project_id, {"keyword_unfilter": ku})
    await query.message.edit_text(
        _ku_info_text(ku),
        reply_markup=_ku_menu_markup(project_id, ku)
    )


@Client.on_callback_query(filters.regex(r"^proj_ku_add_(.+)$"))
async def proj_ku_add_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    user_id = query.from_user.id
    p = await db.get_project(project_id)
    ku = p.get("keyword_unfilter") or db.default_keyword_unfilter()
    keywords = ku.get("keywords", [])

    if len(keywords) >= MAX_KEYWORDS:
        await query.answer(f"Maximum {MAX_KEYWORDS} keywords allowed!", show_alert=True)
        return

    await query.message.delete()
    prompt = await bot.send_message(
        user_id,
        f"<b>➕ Add Prohibited Keyword(s)</b>\n\n"
        f"Send keyword(s); messages containing any of them will be skipped:\n"
        f"• Single: <code>keyword</code>\n"
        f"• Multiple: <code>keyword1,keyword2</code>\n\n"
        f"⚠️ Case-sensitive | Max {MAX_KEYWORDS} total\n"
        f"Current: {len(keywords)}/{MAX_KEYWORDS}\n\n"
        f"/cancel to cancel"
    )
    try:
        msg = await bot.listen(chat_id=user_id, timeout=120)
    except asyncio.TimeoutError:
        await prompt.edit_text("⏰ Timed out.")
        return
    if not msg or (msg.text and msg.text.strip() == "/cancel"):
        await prompt.edit_text(Translation.CANCEL)
        return

    text = msg.text.strip() if msg.text else ""
    await msg.delete()

    new_kws = [k.strip() for k in text.split(",") if k.strip()]
    can_add = MAX_KEYWORDS - len(keywords)
    new_kws = new_kws[:can_add]

    keywords.extend(new_kws)
    ku["keywords"] = keywords
    await db.update_project(project_id, {"keyword_unfilter": ku})

    added_lines = [f"✅ Added: <code>{kw}</code>" for kw in new_kws]
    await prompt.edit_text(
        "\n".join(added_lines) + "\n\n" + _ku_info_text(ku),
        reply_markup=_ku_menu_markup(project_id, ku)
    )


@Client.on_callback_query(filters.regex(r"^proj_ku_del_(.+)_(\d+)$"))
async def proj_ku_del_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    idx = int(query.matches[0].group(2))
    p = await db.get_project(project_id)
    ku = p.get("keyword_unfilter") or db.default_keyword_unfilter()
    keywords = ku.get("keywords", [])
    if 0 <= idx < len(keywords):
        removed = keywords.pop(idx)
        ku["keywords"] = keywords
        await db.update_project(project_id, {"keyword_unfilter": ku})
        await query.answer(f"Removed: {removed}", show_alert=False)
    await query.message.edit_text(
        _ku_info_text(ku),
        reply_markup=_ku_menu_markup(project_id, ku)
    )


# ─── Save Project ─────────────────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^proj_save_(.+)$"))
async def proj_save_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    p = await db.get_project(project_id)
    if not p:
        await query.answer("Project not found!", show_alert=True)
        return
    if not p.get("source_id"):
        await query.answer("⚠️ Please set a source channel first!", show_alert=True)
        return
    if not p.get("destinations"):
        await query.answer("⚠️ Please add at least one destination channel!", show_alert=True)
        return
    await db.update_project(project_id, {"active": True})
    await query.message.edit_text(
        Translation.SAVED_OK,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 My Projects", callback_data="my_projects")],
            [InlineKeyboardButton("↩️ Main Menu", callback_data="back_main")],
        ])
    )


# ─── Clear / Delete Project ───────────────────────────────────────────────────
@Client.on_callback_query(filters.regex(r"^proj_clear_(.+)$"))
async def proj_clear_cb(bot: Client, query: CallbackQuery):
    project_id = query.matches[0].group(1)
    await db.delete_project(project_id)
    await query.message.edit_text(
        Translation.CLEARED,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 My Projects", callback_data="my_projects")],
            [InlineKeyboardButton("↩️ Main Menu", callback_data="back_main")],
        ])
    )


def _show_project_after_edit(bot, user_id, project_id, msg):
    """Helper to show project menu in a non-async context (fire and forget)."""
    import asyncio
    async def _inner():
        p = await db.get_project(project_id)
        if p:
            summary = await _project_summary(p)
            await msg.edit_text(summary, reply_markup=_project_edit_markup(project_id, p))
    asyncio.create_task(_inner())

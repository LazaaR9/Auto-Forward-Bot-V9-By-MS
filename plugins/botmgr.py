import re
import asyncio
from database import db
from config import Config
from translation import Translation
from plugins.helpers import is_premium_or_owner
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
)
from pyrogram.errors import AccessTokenInvalid, AccessTokenExpired

SESSION_STRING_MIN_LEN = 300


@Client.on_callback_query(filters.regex("^my_bot$"))
async def my_bot_cb(bot: Client, query: CallbackQuery):
    user_id = query.from_user.id
    _bot = await db.get_bot(user_id)
    if _bot:
        kind = "🤖 Bot" if _bot.get("is_bot") else "👤 Userbot"
        name = _bot.get("name", "Unknown")
        username = _bot.get("username", "")
        text = (
            f"<b>{kind} Details</b>\n\n"
            f"• <b>Name:</b> {name}\n"
            f"• <b>ID:</b> <code>{_bot.get('id', 'N/A')}</code>\n"
            f"• <b>Username:</b> @{username}\n"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Remove", callback_data="bot_remove")],
            [InlineKeyboardButton("↩️ Back", callback_data="back_main")],
        ])
    else:
        text = "<b>🤖 My Bot / Userbot</b>\n\nYou haven't added a bot or userbot yet."
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Bot (Bot Token)", callback_data="bot_add_bot")],
            [InlineKeyboardButton("➕ Add Userbot (Session)", callback_data="bot_add_userbot")],
            [InlineKeyboardButton("↩️ Back", callback_data="back_main")],
        ])
    await query.message.edit_text(text, reply_markup=markup)


@Client.on_callback_query(filters.regex("^bot_remove$"))
async def bot_remove_cb(bot: Client, query: CallbackQuery):
    await db.remove_bot(query.from_user.id)
    await query.message.edit_text(
        Translation.BOT_REMOVED,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Back", callback_data="my_bot")]
        ])
    )


@Client.on_callback_query(filters.regex("^bot_add_bot$"))
async def bot_add_bot_cb(bot: Client, query: CallbackQuery):
    user_id = query.from_user.id
    await query.message.delete()
    prompt = await bot.send_message(user_id, Translation.BOT_TOKEN_PROMPT)
    try:
        msg = await bot.listen(chat_id=user_id, timeout=300)
    except asyncio.TimeoutError:
        await prompt.edit_text("⏰ Timed out. Please try again.")
        return
    if not msg or msg.text == "/cancel":
        await prompt.edit_text(Translation.CANCEL)
        return

    token = None
    # Try extracting from forwarded message from BotFather
    text_to_check = msg.text or ""
    origin = msg.forward_origin if msg.forward_origin else None
    origin_user = getattr(origin, "sender_user", None)
    if origin_user and str(origin_user.id) == "93372553":
        match = re.search(r'\d{8,10}:[0-9A-Za-z_-]{35}', text_to_check)
        if match:
            token = match.group()
    elif re.match(r'^\d{8,10}:[0-9A-Za-z_-]{35}$', text_to_check.strip()):
        token = text_to_check.strip()

    if not token:
        await prompt.edit_text("❌ Could not find a valid bot token. Please try again.")
        return

    await msg.delete()
    verifying = await prompt.edit_text("🔍 Verifying bot token...")
    try:
        test_client = Client("_verify", api_id=Config.API_ID, api_hash=Config.API_HASH,
                             bot_token=token, in_memory=True)
        await test_client.start()
        me = await test_client.get_me()
        await test_client.stop()
        details = {
            "user_id": user_id,
            "is_bot": True,
            "id": me.id,
            "name": me.first_name,
            "username": me.username or "",
            "token": token,
        }
        await db.add_bot(details)
        await verifying.edit_text(
            f"✅ Bot <b>{me.first_name}</b> (@{me.username}) added successfully!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Back", callback_data="my_bot")]
            ])
        )
    except (AccessTokenInvalid, AccessTokenExpired):
        await verifying.edit_text("❌ Invalid or expired bot token.")
    except Exception as e:
        await verifying.edit_text(f"❌ Error: <code>{e}</code>")


@Client.on_callback_query(filters.regex("^bot_add_userbot$"))
async def bot_add_userbot_cb(bot: Client, query: CallbackQuery):
    user_id = query.from_user.id
    await query.message.delete()
    prompt = await bot.send_message(user_id, Translation.SESSION_PROMPT)
    try:
        msg = await bot.listen(chat_id=user_id, timeout=300)
    except asyncio.TimeoutError:
        await prompt.edit_text("⏰ Timed out.")
        return
    if not msg or msg.text == "/cancel":
        await prompt.edit_text(Translation.CANCEL)
        return

    session = (msg.text or "").strip()
    if len(session) < SESSION_STRING_MIN_LEN:
        await prompt.edit_text("❌ Invalid session string (too short). Please try again.")
        return

    await msg.delete()
    verifying = await prompt.edit_text("🔍 Verifying session...")
    try:
        test_client = Client("_verify_user", api_id=Config.API_ID, api_hash=Config.API_HASH,
                             session_string=session, in_memory=True)
        await test_client.start()
        me = await test_client.get_me()
        await test_client.stop()
        details = {
            "user_id": user_id,
            "is_bot": False,
            "id": me.id,
            "name": me.first_name,
            "username": me.username or "",
            "session": session,
        }
        await db.add_bot(details)
        await verifying.edit_text(
            f"✅ Userbot <b>{me.first_name}</b> (@{me.username or 'N/A'}) added!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Back", callback_data="my_bot")]
            ])
        )
    except Exception as e:
        await verifying.edit_text(f"❌ Error: <code>{e}</code>")

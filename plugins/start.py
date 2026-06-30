import asyncio
from database import db
from config import Config
from translation import Translation
from plugins.helpers import check_fsub, fsub_markup, is_premium_or_owner
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
)

def main_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Upgrade to Pro/Premium", callback_data="premium_info")],
        [InlineKeyboardButton("➕ Add Forwarding Project", callback_data="project_add_start")],
        [InlineKeyboardButton("📋 My Forwarding Projects", callback_data="my_projects")],
        [InlineKeyboardButton("🤖 My Bot / Userbot", callback_data="my_bot")],
        [InlineKeyboardButton("👤 My Account", callback_data="my_account")],
        [InlineKeyboardButton("🆘 Help", callback_data="help")],
    ])


@Client.on_message(filters.private & filters.command("start"))
async def start_cmd(bot: Client, message: Message):
    user = message.from_user
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)

    # Force subscribe check
    if Config.FSUB_CHANNELS:
        not_joined = await check_fsub(bot, user.id)
        if not_joined:
            await message.reply_text(
                "📢 <b>Join the Channels Below to Use the Bot</b>",
                reply_markup=fsub_markup(not_joined)
            )
            return

    await message.reply_text(
        Translation.START_TXT.format(name=user.first_name),
        reply_markup=main_menu_markup(),
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex("^fsub_check$"))
async def fsub_verify(bot: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if Config.FSUB_CHANNELS:
        not_joined = await check_fsub(bot, user_id)
        if not_joined:
            await query.answer("❌ You haven't joined all channels yet!", show_alert=True)
            return

    await query.message.edit_text(
        Translation.START_TXT.format(name=query.from_user.first_name),
        reply_markup=main_menu_markup(),
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex("^fsub_noop$"))
async def fsub_noop(bot: Client, query: CallbackQuery):
    await query.answer("Click the channel name to join!", show_alert=True)


@Client.on_callback_query(filters.regex("^back_main$"))
async def back_main(bot: Client, query: CallbackQuery):
    await query.message.edit_text(
        Translation.START_TXT.format(name=query.from_user.first_name),
        reply_markup=main_menu_markup(),
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex("^help$"))
async def help_cb(bot: Client, query: CallbackQuery):
    await query.message.edit_text(
        Translation.HELP_TXT,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Back", callback_data="back_main")]
        ])
    )


@Client.on_callback_query(filters.regex("^my_account$"))
async def my_account_cb(bot: Client, query: CallbackQuery):
    user_id = query.from_user.id
    is_owner = user_id in Config.BOT_OWNER_ID
    is_auth = await db.is_auth(user_id)
    total_projects = await db.count_projects(user_id)
    plan = "👑 Owner" if is_owner else ("⭐ Premium" if is_auth else "🆓 Free")
    project_limit = "Unlimited" if (is_owner or is_auth) else f"{total_projects}/3"
    dest_limit = "Unlimited" if (is_owner or is_auth) else "3 per project"

    text = (
        f"<b>👤 My Account</b>\n\n"
        f"• <b>Name:</b> {query.from_user.first_name}\n"
        f"• <b>User ID:</b> <code>{user_id}</code>\n"
        f"• <b>Plan:</b> {plan}\n"
        f"• <b>Projects:</b> {project_limit}\n"
        f"• <b>Destinations/project:</b> {dest_limit}\n"
    )
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Back", callback_data="back_main")]
        ])
    )


@Client.on_callback_query(filters.regex("^premium_info$"))
async def premium_info_cb(bot: Client, query: CallbackQuery):
    user_id = query.from_user.id
    if await is_premium_or_owner(user_id):
        await query.message.edit_text(
            Translation.ALREADY_PREMIUM,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Back", callback_data="back_main")]
            ])
        )
    else:
        await query.message.edit_text(
            Translation.PREMIUM_MSG,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Back", callback_data="back_main")]
            ])
        )

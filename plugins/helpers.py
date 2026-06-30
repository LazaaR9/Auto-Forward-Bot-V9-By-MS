import re
import logging
from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import Config

logger = logging.getLogger(__name__)

MAX_PROJECTS_FREE = 3
MAX_DESTINATIONS_FREE = 3

async def is_premium_or_owner(user_id: int) -> bool:
    """Check if user is owner, hardcoded auth, or DB auth (premium)."""
    from database import db
    if user_id in Config.BOT_OWNER_ID:
        return True
    if user_id in Config.HARDCODED_AUTH_USERS:
        return True
    return await db.is_auth(user_id)

async def get_channel_id_from_input(bot: Client, text: str, fwd_msg=None):
    """
    Try to extract channel ID from:
    1. Forward message
    2. Raw ID like -1001234567890
    3. @username
    Returns (chat_id, title) or (None, None)
    """
    # From forwarded message
    if fwd_msg and fwd_msg.forward_origin:
        origin = fwd_msg.forward_origin
        # Channel forward: origin.chat holds the source channel
        chat = getattr(origin, "chat", None)
        if chat:
            return chat.id, chat.title or str(chat.id)

    if not text:
        return None, None

    text = text.strip()

    # Numeric ID
    if re.match(r'^-?\d+$', text):
        cid = int(text)
        try:
            chat = await bot.get_chat(cid)
            return chat.id, chat.title or str(cid)
        except Exception:
            return cid, str(cid)

    # @username
    if text.startswith("@") or not text.startswith("-"):
        try:
            chat = await bot.get_chat(text)
            return chat.id, chat.title or text
        except Exception:
            return None, None

    return None, None

def back_btn(data: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data=data)]])

async def check_fsub(bot: Client, user_id: int) -> list:
    """
    Returns list of channels user hasn't joined yet.
    Uses hardcoded title and URL from Config - no API call needed for channel info.
    Each item: {"id": ..., "title": ..., "invite": ...}
    """
    from pyrogram.enums import ChatMemberStatus
    not_joined = []
    for ch in Config.FSUB_CHANNELS_INFO:
        try:
            member = await bot.get_chat_member(ch["id"], user_id)
            if member.status in [ChatMemberStatus.BANNED, ChatMemberStatus.LEFT]:
                not_joined.append({
                    "id": ch["id"],
                    "title": ch["title"],
                    "invite": ch["url"]
                })
        except Exception:
            not_joined.append({
                "id": ch["id"],
                "title": ch["title"],
                "invite": ch["url"]
            })
    return not_joined

def fsub_markup(not_joined: list):
    """Build inline keyboard with join buttons + verified check."""
    buttons = []
    for ch in not_joined:
        row = []
        if ch.get("invite"):
            row.append(InlineKeyboardButton(ch["title"], url=ch["invite"]))
        else:
            row.append(InlineKeyboardButton(ch["title"], callback_data="fsub_noop"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✅ Joined / Verify", callback_data="fsub_check")])
    return InlineKeyboardMarkup(buttons)

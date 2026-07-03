"""
Core forwarding engine.
Bot itself (admin in both channels) copies messages from source to destination.
No secondary client needed — uses the main bot directly.
"""
import logging
import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatWriteForbidden, ChannelInvalid, MessageIdInvalid
from database import db
from config import temp

logger = logging.getLogger(__name__)

# Duplicate tracking: set of (project_id_str, message_id)
_forwarded_ids: set = set()
_MAX_CACHE = 10000


def _message_type(message: Message) -> str:
    if message.video:     return "video"
    if message.document:  return "document"
    if message.photo:     return "photo"
    if message.audio:     return "audio"
    if message.voice:     return "voice"
    if message.animation: return "animation"
    if message.sticker:   return "sticker"
    if message.poll:      return "poll"
    if message.text or message.caption:
        return "text"
    return "unknown"


def _passes_filter(message: Message, f: dict) -> bool:
    mtype = _message_type(message)
    return f.get(mtype, True)


def _apply_keyword_replace(text: str, pairs: list) -> str:
    """
    Replace old keywords with new keywords in text.
    Word-by-word, exact, case-sensitive.
    Replaces full words only (splits by spaces, replaces matching tokens).
    """
    if not text or not pairs:
        return text
    # Split preserving spaces: we do word-by-word replacement
    # to avoid partial matches inside words we split on word boundaries
    words = text.split(" ")
    for pair in pairs:
        old = pair.get("old", "")
        new = pair.get("new", "")
        if not old:
            continue
        words = [new if w == old else w for w in words]
    return " ".join(words)


def _passes_keyword_filter(caption: str, kf: dict) -> bool:
    """
    Returns True if:
    - keyword filter is disabled, OR
    - no keywords set, OR
    - caption contains at least one keyword (exact, case-sensitive, word match)
    Returns False if filter is enabled, keywords set, but none match.
    """
    if not kf or not kf.get("enabled", False):
        return True
    keywords = kf.get("keywords", [])
    if not keywords:
        return True
    if not caption:
        return False
    # Word-by-word exact match (split on any whitespace: space, tab, newline, etc.)
    words = re.split(r"\s+", caption.strip())
    for kw in keywords:
        if kw in words:
            return True
    return False


def _get_file_extension(message: Message):
    """
    Returns the lowercase file extension (without the dot) of the media in
    the message, based on its file_name, or None if the message has no
    named file (e.g. plain text, photo without filename, etc.).
    """
    for attr in ("document", "video", "audio", "animation", "voice"):
        obj = getattr(message, attr, None)
        file_name = getattr(obj, "file_name", None) if obj else None
        if file_name and "." in file_name:
            return file_name.rsplit(".", 1)[-1].strip().lower()
    return None


def _passes_file_filter(message: Message, ff: dict) -> bool:
    """
    File Keywords Filter (extension based):
    Returns True if:
    - filter is disabled, OR
    - no extensions set, OR
    - message has no named file (filter only applies to actual files), OR
    - the message's file extension matches one of the set extensions.
    Returns False if filter is enabled, extensions set, message has a file,
    but its extension does not match any of them.
    """
    if not ff or not ff.get("enabled", False):
        return True
    extensions = ff.get("extensions", [])
    if not extensions:
        return True
    ext = _get_file_extension(message)
    if ext is None:
        return True
    allowed = [e.strip().lower().lstrip(".") for e in extensions]
    return ext in allowed


def _blocked_by_keyword_unfilter(caption: str, ku: dict) -> bool:
    """
    Keyword Unfilter (prohibited keywords):
    Returns True (i.e. message should be BLOCKED/skipped) if:
    - unfilter is enabled, AND
    - keywords are set, AND
    - caption contains at least one of the prohibited keywords (exact, case-sensitive, word match)
    Otherwise returns False (message is allowed to pass).
    """
    if not ku or not ku.get("enabled", False):
        return False
    keywords = ku.get("keywords", [])
    if not keywords:
        return False
    if not caption:
        return False
    words = re.split(r"\s+", caption.strip())
    for kw in keywords:
        if kw in words:
            return True
    return False


async def _send_message(bot: Client, message: Message, dest_id: int, forward_tag: bool,
                        keyword_replace_pairs: list = None, caption_override: str = None):
    """
    Copy or forward a single message to dest_id using the main bot.
    If caption_override is set, use it as the new caption.
    """
    try:
        if forward_tag:
            await bot.forward_messages(
                chat_id=dest_id,
                from_chat_id=message.chat.id,
                message_ids=message.id,
            )
        else:
            # copy_message: sends without "Forwarded from" tag
            if caption_override is not None:
                await bot.copy_message(
                    chat_id=dest_id,
                    from_chat_id=message.chat.id,
                    message_id=message.id,
                    caption=caption_override,
                )
            else:
                await bot.copy_message(
                    chat_id=dest_id,
                    from_chat_id=message.chat.id,
                    message_id=message.id,
                )
    except FloodWait as e:
        wait = e.value + 1
        logger.warning(f"FloodWait {wait}s, sleeping...")
        await asyncio.sleep(wait)
        await _send_message(bot, message, dest_id, forward_tag, keyword_replace_pairs, caption_override)
    except (ChatWriteForbidden, ChannelInvalid) as e:
        logger.error(f"Cannot write to {dest_id}: {e}")
    except MessageIdInvalid:
        logger.warning(f"MessageIdInvalid for msg {message.id} -> {dest_id}, skipping")
    except Exception as e:
        logger.exception(f"Error copying to {dest_id}: {e}")


@Client.on_message(filters.channel & filters.incoming)
async def channel_message_handler(bot: Client, message: Message):
    """Handle new messages from any channel the bot is admin in."""
    source_id = message.chat.id

    # Find all active projects with this source
    from bson import ObjectId
    cursor = db.projects.find({"source_id": source_id, "active": True})
    projects = [p async for p in cursor]

    if not projects:
        return

    for project in projects:
        project_id_str = str(project["_id"])
        dup_key = (project_id_str, message.id)

        # Duplicate check
        if dup_key in _forwarded_ids:
            logger.debug(f"Duplicate msg {message.id} for project {project_id_str}, skipping")
            continue

        destinations = project.get("destinations", [])
        if not destinations:
            continue

        project_filters = project.get("filters") or db.default_filters()
        forward_tag = project.get("forward_tag", False)

        if not _passes_filter(message, project_filters):
            logger.debug(f"Message filtered out for project {project_id_str}")
            continue

        # ── Build searchable text (Caption + Text + Document Filename) ─────────
        search_text = " ".join(filter(None, [
            message.caption,
            message.text,
            message.document.file_name if message.document else None,
        ]))

        # ── Keyword Filter check ──────────────────────────────────────────────
        kf = project.get("keyword_filter") or db.default_keyword_filter()
        if not _passes_keyword_filter(search_text, kf):
            logger.debug(f"Keyword filter blocked msg {message.id} for project {project_id_str}")
            continue

        # ── File Keywords Filter check (file extension based) ──────────────────
        ff = project.get("file_filter") or db.default_file_filter()
        if not _passes_file_filter(message, ff):
            logger.debug(f"File filter blocked msg {message.id} for project {project_id_str}")
            continue

        # ── Keyword Unfilter check (prohibited keywords) ────────────────────────
        ku = project.get("keyword_unfilter") or db.default_keyword_unfilter()
        if _blocked_by_keyword_unfilter(search_text, ku):
            logger.debug(f"Keyword unfilter blocked msg {message.id} for project {project_id_str}")
            continue

        # ── Keyword Replace — build modified caption ──────────────────────────
        kr = project.get("keyword_replace") or db.default_keyword_replace()
        caption_override = None
        if kr.get("enabled") and kr.get("pairs") and not forward_tag:
            # Only apply replace on caption (not on pure text messages without caption)
            original_caption = message.caption
            if original_caption is not None:
                new_caption = _apply_keyword_replace(original_caption, kr["pairs"])
                if new_caption != original_caption:
                    caption_override = new_caption

        mtype = _message_type(message)
        logger.info(f"Copying [{mtype}] msg {message.id} from {source_id} for project {project_id_str}")

        # Mark before sending to prevent race duplicates
        _forwarded_ids.add(dup_key)
        if len(_forwarded_ids) > _MAX_CACHE:
            old = list(_forwarded_ids)[:_MAX_CACHE // 2]
            for k in old:
                _forwarded_ids.discard(k)

        # Send to all destinations with small delay
        for dest in destinations:
            dest_id = dest["id"]
            await _send_message(bot, message, dest_id, forward_tag,
                                keyword_replace_pairs=kr.get("pairs") if kr.get("enabled") else None,
                                caption_override=caption_override)
            await asyncio.sleep(1)

        temp.forwardings += 1
        logger.info(f"Done. Total forwardings: {temp.forwardings}")

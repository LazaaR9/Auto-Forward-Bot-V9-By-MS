import os
import asyncio
import logging
import threading
from flask import Flask
from pyrogram import idle
from bot import Bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ─── Flask keep-alive server for Render ───────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return 'Bot is running!'

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    flask_app.run(host="0.0.0.0", port=port)

# Start Flask in background thread so Render detects open port
threading.Thread(target=run_flask, daemon=True).start()
# ─────────────────────────────────────────────────────────────────────────────


async def main():
    bot = Bot()
    await bot.start()
    logging.info("Bot is running. Press Ctrl+C to stop.")
    await idle()
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())

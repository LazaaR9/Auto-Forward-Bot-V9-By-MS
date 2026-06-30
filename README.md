# DoneForward Bot 🤖

Auto forward new posts from source channels to destination channels — **without forward tag** (or with, your choice).

---

## ✨ Features

- ✅ Forward new channel posts in real time
- ✅ Copy mode (no "Forwarded from" tag) or forward mode
- ✅ Multiple destination channels per project
- ✅ Filter by message type (text, photo, video, audio, document, etc.)
- ✅ Force subscribe (users must join your channels before using bot)
- ✅ Owner & Premium system (unlimited projects/destinations)
- ✅ Free users: max 3 projects, max 3 destinations each
- ✅ Broadcast to all users (owner only)
- ✅ Ban/unban users
- ✅ Auth/unauth premium users
- ✅ Deploy-ready for Render (Docker + Flask keep-alive)

---

## 🚀 Deploy on Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service → Connect your repo
3. Choose **Docker** environment
4. Set environment variables (see below)
5. Deploy!

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `API_ID` | ✅ | Telegram API ID from my.telegram.org |
| `API_HASH` | ✅ | Telegram API Hash from my.telegram.org |
| `BOT_TOKEN` | ✅ | Your bot token from @BotFather |
| `DATABASE_URI` | ✅ | MongoDB connection URI |
| `DATABASE_NAME` | ❌ | Database name (default: `doneforward`) |
| `BOT_OWNER_ID` | ✅ | Your Telegram user ID (space-separated for multiple) |
| `FSUB_CHANNELS` | ❌ | Comma-separated channel IDs/usernames for force subscribe |
| `PORT` | ❌ | Port for Flask server (default: 8000) |

---

## 🤖 Owner Commands

| Command | Description |
|---------|-------------|
| `/broadcast` | Broadcast to all users (reply to a message) |
| `/auth <user_id>` | Grant premium to a user |
| `/unauth <user_id>` | Remove premium from a user |
| `/ban <user_id>` | Ban a user |
| `/unban <user_id>` | Unban a user |
| `/stats` | Show bot statistics |
| `/users` | List all users |

---

## 📋 How It Works

1. User adds their **Bot** (via token) or **Userbot** (via session string)
2. User creates a **Forwarding Project** with:
   - Source channel (the channel to watch)
   - Destination channel(s) (where to send)
   - Filter type (what message types to forward)
   - Forward mode (with/without tag)
3. Bot listens to source channel — when a new post arrives, it's automatically copied to all destination channels

---

## 📁 Project Structure

```
DoneForward/
├── main.py           # Entry point (Flask + Bot)
├── bot.py            # Pyrogram Bot client
├── config.py         # Configuration from env vars
├── database.py       # MongoDB operations
├── translation.py    # All text strings
├── requirements.txt
├── Dockerfile
├── Procfile
├── render.yaml
└── plugins/
    ├── __init__.py
    ├── start.py      # Start, help, main menu, force-subscribe
    ├── botmgr.py     # Add/remove bot/userbot
    ├── projects.py   # Create/manage forwarding projects
    ├── forward.py    # Core forwarding engine
    ├── owner.py      # Owner commands (broadcast, auth, ban, stats)
    └── helpers.py    # Shared utility functions
```

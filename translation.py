class Translation:

    START_TXT = """🤖 <b>Hello {name}!</b>

I am <b>DoneForward Bot</b> — Auto Forward messages from source channels to destination channels in <b>real time</b>, without forward tag!

<b>✨ Features:</b>
• Forward new posts without "Forwarded from" tag
• Multiple destination channels per project
• Filter by message type (text, photo, video, etc.)
• Forward mode: with tag / without tag
• Premium & Owner unlimited projects

Use the buttons below to get started 👇"""

    HELP_TXT = """<b>📖 HOW TO USE</b>

1️⃣ Go to <b>Add Forwarding Project</b>
2️⃣ Choose mode: <b>With Bot</b> (bot token) or <b>Without Bot</b> (userbot session)
3️⃣ Set <b>Source Channel</b> (the channel to watch)
4️⃣ Set <b>Destination Channel(s)</b> (where to send)
5️⃣ Configure <b>Filters</b> (what types to forward)
6️⃣ Choose <b>Forward Mode</b> (with/without tag)
7️⃣ Click <b>✅ Save Project</b>

<b>⚠️ Important:</b>
• Your bot/userbot must be <b>admin</b> in source & destination channels
• Non-premium users can create max <b>3 projects</b> and <b>3 destination channels</b> per project"""

    ABOUT_TXT = """<b>╭──────❰ 🤖 Bot Info ❱──────╮
│
│ 🤖 Name : DoneForward Bot
│ 🗣️ Language : Python 3.12
│ 📚 Library : Pyrogram
│ 💾 Database : MongoDB
│ 🚀 Host : Render
│
╰────────────────────────╯</b>"""

    PREMIUM_MSG = """⭐ <b>Upgrade to Premium</b>

Unlock unlimited projects and channels!

📩 Contact: <b>@JapaneseFury</b> to purchase Premium."""

    ALREADY_PREMIUM = "✅ <b>Congrats! You already have a Premium Plan!</b>"

    NO_BOT_ERR = "❌ You haven't added a bot/userbot. Go to your project settings to add one."
    NO_SOURCE_ERR = "❌ Source channel not set. Please set source channel first."
    NO_DEST_ERR = "❌ No destination channel set. Please add at least one destination."
    CANCEL = "🚫 Process cancelled."
    PROJECT_LIMIT = "⚠️ <b>Free users can only create up to 3 projects.</b>\n\nUpgrade to ⭐ Premium for unlimited projects!"
    DEST_LIMIT = "⚠️ <b>Free users can only add up to 3 destination channels per project.</b>\n\nUpgrade to ⭐ Premium!"
    SAVED_OK = "✅ <b>Project saved successfully!</b>\n\nNew posts in your source channel will now be forwarded automatically."
    CLEARED = "🗑️ Project cleared."
    BOT_ADDED = "✅ Bot token saved successfully!"
    SESSION_ADDED = "✅ Userbot session saved successfully!"
    BOT_REMOVED = "✅ Bot/Userbot removed."
    SOURCE_SET = "✅ Source channel set: <code>{}</code>"
    DEST_ADDED = "✅ Destination added: <code>{}</code>"
    DEST_EXISTS = "ℹ️ This destination is already added."
    DEST_REMOVED = "✅ Destination removed."
    BOT_TOKEN_PROMPT = """<b>📌 How to add your Bot:</b>
1) Create a bot via @BotFather
2) You'll get a message with the bot token
3) Forward that BotFather message here

/cancel to cancel"""
    SESSION_PROMPT = """<b>📌 Send your Pyrogram session string.</b>

⚠️ <i>Use at your own risk. Add your bot/userbot as admin to both source and destination channels.</i>

/cancel to cancel"""
    SOURCE_PROMPT = """<b>📌 Set Source Channel</b>

Send the <b>channel ID</b> (e.g. <code>-1001234567890</code>) or forward any message from that channel.

/cancel to cancel"""
    DEST_PROMPT = """<b>📌 Add Destination Channel</b>

Send the <b>channel ID</b> (e.g. <code>-1001234567890</code>) or forward any message from that channel.

/cancel to cancel"""
    PROJECT_NAME_PROMPT = "📝 Send a <b>name</b> for this project (e.g. <code>My Channel Forward</code>):\n\n/cancel to cancel"
    BROADCAST_PROMPT = "📢 Reply to a message to broadcast it to all users."

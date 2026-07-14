from os import environ

class Config:
    API_ID = int(environ.get("API_ID", "25662550"))
    API_HASH = environ.get("API_HASH", "3d2663ae1493ece93fab45f83b659acc")
    BOT_TOKEN = environ.get("BOT_TOKEN", "8646605422:AAEQVzjhp1fVLhmgbcRCHMXRqbulKdcAAQQ")
    BOT_SESSION = environ.get("BOT_SESSION", "DoneForwardBot")
    DATABASE_URI = environ.get("DATABASE_URI", "mongodb+srv://zee:zee@cluster0.s5dgb.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    DATABASE_NAME = environ.get("DATABASE_NAME", "doneforward")
    BOT_OWNER_ID = [int(x) for x in environ.get("BOT_OWNER_ID", "5179011789").split()]

    # ─── Hardcoded Auth Users (Premium) ───────────────────────────────────────
    # Add user IDs here to grant permanent premium access via config
    # These are in addition to DB-based auth users
    HARDCODED_AUTH_USERS = [int(x) for x in environ.get("HARDCODED_AUTH_USERS", "").split() if x]

    # Force subscribe channels - hardcoded with title and URL
    FSUB_CHANNEL1_ID = int(environ.get("FSUB_CHANNEL1_ID", "")
    FSUB_CHANNEL1_TITLE = ""
    FSUB_CHANNEL1_URL = ""

    FSUB_CHANNEL2_ID = int(environ.get("FSUB_CHANNEL2_ID", ""))
    FSUB_CHANNEL2_TITLE = ""
    FSUB_CHANNEL2_URL = ""

    FSUB_CHANNEL3_ID = int(environ.get("FSUB_CHANNEL3_ID", ""))
    FSUB_CHANNEL3_TITLE = ""
    FSUB_CHANNEL3_URL = ""

    FSUB_CHANNELS_INFO = [
        {"id": FSUB_CHANNEL1_ID, "title": FSUB_CHANNEL1_TITLE, "url": FSUB_CHANNEL1_URL},
        {"id": FSUB_CHANNEL2_ID, "title": FSUB_CHANNEL2_TITLE, "url": FSUB_CHANNEL2_URL},
        {"id": FSUB_CHANNEL3_ID, "title": FSUB_CHANNEL3_TITLE, "url": FSUB_CHANNEL3_URL},
    ]
    # Keep FSUB_CHANNELS as list of IDs for backward compat
    FSUB_CHANNELS = [FSUB_CHANNEL1_ID, FSUB_CHANNEL2_ID, FSUB_CHANNEL3_ID]

class temp:
    BANNED_USERS = []
    forwardings = 0

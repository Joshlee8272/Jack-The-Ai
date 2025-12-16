import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from gtts import gTTS
from deep_translator import GoogleTranslator
import tempfile, re, time, json, os
from flask import Flask, request

TOKEN = "8369185267:AAGV7CPcWM0UBR7xiEGIpz4btLr4QGlmXyU"
OWNER_ID = 7301067810

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=20)
app = Flask(__name__)
START_TIME = time.time()

DATA_FILE = "data.json"
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"ban_words": {}, "warnings": {}, "users": [], "groups": [], "channel": None}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def is_admin(chat_id, user_id):
    try:
        admins = bot.get_chat_administrators(chat_id)
        return any(a.user.id == user_id for a in admins)
    except:
        return False

def get_target_user(message):
    parts = message.text.split()
    if message.reply_to_message:
        return message.reply_to_message.from_user.id
    elif len(parts) > 1:
        if parts[1].isdigit():
            return int(parts[1])
        try:
            user = bot.get_chat_member(message.chat.id, parts[1])
            return user.user.id
        except:
            return None
    return None

@app.route("/" + TOKEN, methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Bot is running!", 200

# ====================== START / HELP ===========================
@bot.message_handler(commands=["start"])
def start(message):
    if message.chat.type == "private" and message.from_user.id not in data["users"]:
        data["users"].append(message.from_user.id)
        save_data()
    if message.chat.type in ["group", "supergroup"] and message.chat.id not in data["groups"]:
        data["groups"].append(message.chat.id)
        save_data()

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🗣 Text → Voice", callback_data="text_to_voice"))
    markup.add(InlineKeyboardButton("📖 Help", callback_data="show_help"))

    bot.send_message(
        message.chat.id,
        f"👋 *Welcome {message.from_user.first_name}!* 🎉\n\n"
        "🤖 I am *Jack The AI Bot*.\n"
        "🗣 Text-to-Voice • 👮 Admin Tools • 📊 Stats • 📢 Announcements",
        reply_markup=markup,
        parse_mode="Markdown",
    )

@bot.callback_query_handler(func=lambda c: c.data == "show_help")
def show_help_callback(call):
    send_help(call.message.chat.id)

@bot.message_handler(commands=["help"])
def help_cmd(message):
    send_help(message.chat.id)

def send_help(chat_id):
    bot.send_message(
        chat_id,
        "🤖 *Commands List*\n\n"
        "🗣 /start – Start the bot\n"
        "🗒 /help – Show commands\n"
        "📊 /botstats – Bot stats\n"
        "🏓 /ping – Check ping\n"
        "👤 /userinfo – Your info\n"
        "💌 /feedback <msg>\n"
        "🐞 /report <msg>\n\n"
        "👮 *Admin Only:*\n"
        "/kick (reply/@id)\n"
        "/mute <1m|1h|1d> (reply/@id)\n"
        "/promote (reply/@id)\n"
        "/demote (reply/@id)\n"
        "/warn (reply/@id)\n"
        "/unwarn (reply/@id)\n"
        "/warnlist\n"
        "/banwords word1, word2\n\n"
        "👑 *Owner Only:*\n"
        "/announcement <msg>\n"
        "/setchannel @username\n"
        "/post <msg>",
        parse_mode="Markdown",
    )

# ====================== WELCOME / LEAVE ===========================
@bot.message_handler(content_types=["new_chat_members"])
def welcome_new_member(message):
    for m in message.new_chat_members:
        bot.send_message(message.chat.id, f"👋 Welcome {m.first_name}! 🎉")

@bot.message_handler(content_types=["left_chat_member"])
def goodbye_member(message):
    bot.send_message(message.chat.id, f"👋 {message.left_chat_member.first_name} left.")

# ====================== TEXT TO VOICE ===========================
@bot.callback_query_handler(func=lambda c: c.data == "text_to_voice")
def callback_handler(call):
    markup = InlineKeyboardMarkup(row_width=2)
    langs = [("🇺🇸 English", "en"), ("🇵🇭 Tagalog", "tl"), ("🇪🇸 Spanish", "es"),
             ("🇯🇵 Japanese", "ja"), ("🇰🇷 Korean", "ko"), ("🇨🇳 Chinese", "zh-cn"),
             ("🇫🇷 French", "fr"), ("🇩🇪 German", "de"), ("🇮🇳 Hindi", "hi"), ("🇷🇺 Russian", "ru")]
    for n, c in langs:
        markup.add(InlineKeyboardButton(n, callback_data=f"lang_{c}"))
    bot.send_message(call.message.chat.id, "🌐 Choose language:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("lang_"))
def select_language(call):
    lang = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, "✏ Send me text:")
    bot.register_next_step_handler(msg, lambda m: translate_and_convert(m, lang))

def translate_and_convert(message, lang):
    translated = GoogleTranslator(source="auto", target=lang).translate(message.text)
    tts = gTTS(text=translated, lang=lang)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tts.save(tmp.name)
        bot.send_voice(message.chat.id, open(tmp.name, "rb"))
    bot.send_message(message.chat.id, f"✅ Translated to {lang.upper()}:\n_{translated}_", parse_mode="Markdown")

# ====================== INFO COMMANDS ===========================
@bot.message_handler(commands=["botstats"])
def botstats_cmd(message):
    uptime = int(time.time() - START_TIME)
    h, m = uptime // 3600, (uptime % 3600) // 60
    bot.send_message(message.chat.id,
        f"📊 *Bot Stats*\n👥 Users: {len(data['users'])}\n💬 Groups: {len(data['groups'])}\n"
        f"⚠ Warnings: {len(data['warnings'])}\n⏳ Uptime: {h}h {m}m", parse_mode="Markdown")

@bot.message_handler(commands=["ping"])
def ping_cmd(message):
    start = time.time()
    sent = bot.send_message(message.chat.id, "🏓 Pinging...")
    bot.edit_message_text(f"🏓 Pong! {round((time.time()-start)*1000)}ms", message.chat.id, sent.message_id)

@bot.message_handler(commands=["userinfo"])
def userinfo_cmd(message):
    u = message.from_user
    bot.send_message(message.chat.id,
        f"👤 *User Info*\n🆔 {u.id}\n📛 {u.first_name}\n🔗 @{u.username or 'None'}",
        parse_mode="Markdown")

# ====================== FEEDBACK / REPORT ===========================
@bot.message_handler(commands=["feedback"])
def feedback_cmd(message):
    msg = message.text.replace("/feedback", "").strip()
    if msg:
        bot.send_message(OWNER_ID, f"💌 Feedback from {message.from_user.id}:\n{msg}")
        bot.reply_to(message, "✅ Feedback sent!")

@bot.message_handler(commands=["report"])
def report_cmd(message):
    msg = message.text.replace("/report", "").strip()
    if msg:
        bot.send_message(OWNER_ID, f"🐞 Report from {message.from_user.id}:\n{msg}")
        bot.reply_to(message, "✅ Report sent!")

# ====================== OWNER COMMANDS ===========================
@bot.message_handler(commands=["announcement"])
def announcement_cmd(message):
    if message.from_user.id != OWNER_ID: return
    text = message.text.replace("/announcement", "").strip()
    for uid in data["users"]:
        try: bot.send_message(uid, f"📢 Announcement:\n{text}")
        except: pass
    bot.reply_to(message, "✅ Sent!")

@bot.message_handler(commands=["setchannel"])
def setchannel_cmd(message):
    if message.from_user.id != OWNER_ID: return
    parts = message.text.split()
    if len(parts) < 2: return bot.reply_to(message, "Usage: /setchannel @username")
    data["channel"] = parts[1]; save_data()
    bot.reply_to(message, f"✅ Channel set to {parts[1]}")

@bot.message_handler(commands=["post"])
def post_cmd(message):
    if not data.get("channel"): return bot.reply_to(message, "❌ No channel set.")
    msg = message.text.replace("/post", "").strip()
    if msg: bot.send_message(data["channel"], msg); bot.reply_to(message, "✅ Posted!")

# ====================== ADMIN COMMANDS ===========================
@bot.message_handler(commands=["kick"])
def kick_cmd(message):
    uid = get_target_user(message)
    if uid and is_admin(message.chat.id, message.from_user.id):
        bot.kick_chat_member(message.chat.id, uid)
        bot.send_message(message.chat.id, "✅ User kicked.")

@bot.message_handler(commands=["mute"])
def mute_cmd(message):
    uid = get_target_user(message)
    parts = message.text.split()
    times = {"1m":60,"1h":3600,"1d":86400}
    if uid and len(parts)>1 and parts[1] in times:
        bot.restrict_chat_member(message.chat.id, uid, until_date=int(time.time())+times[parts[1]])
        bot.send_message(message.chat.id, f"✅ Muted {parts[1]}")

@bot.message_handler(commands=["promote"])
def promote_cmd(message):
    uid = get_target_user(message)
    if uid and is_admin(message.chat.id, message.from_user.id):
        bot.promote_chat_member(message.chat.id, uid, can_manage_chat=True,
                                can_delete_messages=True, can_invite_users=True, can_restrict_members=True)
        bot.send_message(message.chat.id, "✅ Promoted.")

@bot.message_handler(commands=["demote"])
def demote_cmd(message):
    uid = get_target_user(message)
    if uid and is_admin(message.chat.id, message.from_user.id):
        bot.promote_chat_member(message.chat.id, uid, can_manage_chat=False,
                                can_delete_messages=False, can_invite_users=False, can_restrict_members=False)
        bot.send_message(message.chat.id, "✅ Demoted.")

# ====================== WARN SYSTEM ===========================
@bot.message_handler(commands=["warn"])
def warn_cmd(message):
    uid = get_target_user(message)
    if uid:
        key = f"{message.chat.id}:{uid}"
        data["warnings"][key] = data["warnings"].get(key, 0) + 1
        save_data()
        bot.send_message(message.chat.id, f"⚠ User warned ({data['warnings'][key]} warnings)")

@bot.message_handler(commands=["unwarn"])
def unwarn_cmd(message):
    uid = get_target_user(message)
    key = f"{message.chat.id}:{uid}"
    if uid and key in data["warnings"]:
        data["warnings"][key] = max(0, data["warnings"][key]-1)
        save_data()
        bot.send_message(message.chat.id, "✅ Warning removed")

@bot.message_handler(commands=["warnlist"])
def warnlist_cmd(message):
    warns = [f"{k}: {v}" for k,v in data["warnings"].items() if k.startswith(str(message.chat.id))]
    bot.send_message(message.chat.id, "⚠ Warn List:\n"+"\n".join(warns) if warns else "✅ No warnings")

# ====================== BAN WORDS ===========================
@bot.message_handler(commands=["banwords"])
def set_ban_words(message):
    if not is_admin(message.chat.id, message.from_user.id): return
    words = message.text.replace("/banwords", "").strip().split(",")
    data["ban_words"][str(message.chat.id)] = [w.strip().lower() for w in words if w.strip()]
    save_data()
    bot.reply_to(message, f"✅ Ban words: {', '.join(data['ban_words'][str(message.chat.id)])}")

@bot.message_handler(func=lambda m: True)
def check_ban_words(message):
    chat_words = data["ban_words"].get(str(message.chat.id), [])
    for w in chat_words:
        if message.text and re.search(rf"\b{re.escape(w)}\b", message.text.lower()):
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except: pass

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url="https://jack-the-ai.onrender.com/" + TOKEN)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)    send_help(call.message.chat.id)

@bot.message_handler(commands=["help"])
def help_cmd(message):
    send_help(message.chat.id)

def send_help(chat_id):
    bot.send_message(
        chat_id,
        "🤖 *Commands List*\n\n"
        "🗣 /start – Start the bot\n"
        "🗒 /help – Show commands\n"
        "📊 /botstats – Bot stats\n"
        "🏓 /ping – Check ping\n"
        "👤 /userinfo – Your info\n"
        "💌 /feedback <msg>\n"
        "🐞 /report <msg>\n\n"
        "👮 *Admin Only:*\n"
        "/kick (reply/@id)\n"
        "/mute <1m|1h|1d> (reply/@id)\n"
        "/promote (reply/@id)\n"
        "/demote (reply/@id)\n"
        "/warn (reply/@id)\n"
        "/unwarn (reply/@id)\n"
        "/warnlist\n"
        "/banwords word1, word2\n\n"
        "👑 *Owner Only:*\n"
        "/announcement <msg>\n"
        "/setchannel @username\n"
        "/post <msg>",
        parse_mode="Markdown",
    )

# ====================== WELCOME / LEAVE ===========================
@bot.message_handler(content_types=["new_chat_members"])
def welcome_new_member(message):
    for m in message.new_chat_members:
        bot.send_message(message.chat.id, f"👋 Welcome {m.first_name}! 🎉")

@bot.message_handler(content_types=["left_chat_member"])
def goodbye_member(message):
    bot.send_message(message.chat.id, f"👋 {message.left_chat_member.first_name} left.")

# ====================== TEXT TO VOICE ===========================
@bot.callback_query_handler(func=lambda c: c.data == "text_to_voice")
def callback_handler(call):
    markup = InlineKeyboardMarkup(row_width=2)
    langs = [("🇺🇸 English", "en"), ("🇵🇭 Tagalog", "tl"), ("🇪🇸 Spanish", "es"),
             ("🇯🇵 Japanese", "ja"), ("🇰🇷 Korean", "ko"), ("🇨🇳 Chinese", "zh-cn"),
             ("🇫🇷 French", "fr"), ("🇩🇪 German", "de"), ("🇮🇳 Hindi", "hi"), ("🇷🇺 Russian", "ru")]
    for n, c in langs:
        markup.add(InlineKeyboardButton(n, callback_data=f"lang_{c}"))
    bot.send_message(call.message.chat.id, "🌐 Choose language:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("lang_"))
def select_language(call):
    lang = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, "✏ Send me text:")
    bot.register_next_step_handler(msg, lambda m: translate_and_convert(m, lang))

def translate_and_convert(message, lang):
    translated = GoogleTranslator(source="auto", target=lang).translate(message.text)
    tts = gTTS(text=translated, lang=lang)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tts.save(tmp.name)
        bot.send_voice(message.chat.id, open(tmp.name, "rb"))
    bot.send_message(message.chat.id, f"✅ Translated to {lang.upper()}:\n_{translated}_", parse_mode="Markdown")

# ====================== INFO COMMANDS ===========================
@bot.message_handler(commands=["botstats"])
def botstats_cmd(message):
    uptime = int(time.time() - START_TIME)
    h, m = uptime // 3600, (uptime % 3600) // 60
    bot.send_message(message.chat.id,
        f"📊 *Bot Stats*\n👥 Users: {len(data['users'])}\n💬 Groups: {len(data['groups'])}\n"
        f"⚠ Warnings: {len(data['warnings'])}\n⏳ Uptime: {h}h {m}m", parse_mode="Markdown")

@bot.message_handler(commands=["ping"])
def ping_cmd(message):
    start = time.time()
    sent = bot.send_message(message.chat.id, "🏓 Pinging...")
    bot.edit_message_text(f"🏓 Pong! {round((time.time()-start)*1000)}ms", message.chat.id, sent.message_id)

@bot.message_handler(commands=["userinfo"])
def userinfo_cmd(message):
    u = message.from_user
    bot.send_message(message.chat.id,
        f"👤 *User Info*\n🆔 {u.id}\n📛 {u.first_name}\n🔗 @{u.username or 'None'}",
        parse_mode="Markdown")

# ====================== FEEDBACK / REPORT ===========================
@bot.message_handler(commands=["feedback"])
def feedback_cmd(message):
    msg = message.text.replace("/feedback", "").strip()
    if msg:
        bot.send_message(OWNER_ID, f"💌 Feedback from {message.from_user.id}:\n{msg}")
        bot.reply_to(message, "✅ Feedback sent!")

@bot.message_handler(commands=["report"])
def report_cmd(message):
    msg = message.text.replace("/report", "").strip()
    if msg:
        bot.send_message(OWNER_ID, f"🐞 Report from {message.from_user.id}:\n{msg}")
        bot.reply_to(message, "✅ Report sent!")

# ====================== OWNER COMMANDS ===========================
@bot.message_handler(commands=["announcement"])
def announcement_cmd(message):
    if message.from_user.id != OWNER_ID: return
    text = message.text.replace("/announcement", "").strip()
    for uid in data["users"]:
        try: bot.send_message(uid, f"📢 Announcement:\n{text}")
        except: pass
    bot.reply_to(message, "✅ Sent!")

@bot.message_handler(commands=["setchannel"])
def setchannel_cmd(message):
    if message.from_user.id != OWNER_ID: return
    parts = message.text.split()
    if len(parts) < 2: return bot.reply_to(message, "Usage: /setchannel @username")
    data["channel"] = parts[1]; save_data()
    bot.reply_to(message, f"✅ Channel set to {parts[1]}")

@bot.message_handler(commands=["post"])
def post_cmd(message):
    if not data.get("channel"): return bot.reply_to(message, "❌ No channel set.")
    msg = message.text.replace("/post", "").strip()
    if msg: bot.send_message(data["channel"], msg); bot.reply_to(message, "✅ Posted!")

# ====================== ADMIN COMMANDS ===========================
@bot.message_handler(commands=["kick"])
def kick_cmd(message):
    uid = get_target_user(message)
    if uid and is_admin(message.chat.id, message.from_user.id):
        bot.kick_chat_member(message.chat.id, uid)
        bot.send_message(message.chat.id, "✅ User kicked.")

@bot.message_handler(commands=["mute"])
def mute_cmd(message):
    uid = get_target_user(message)
    parts = message.text.split()
    times = {"1m":60,"1h":3600,"1d":86400}
    if uid and len(parts)>1 and parts[1] in times:
        bot.restrict_chat_member(message.chat.id, uid, until_date=int(time.time())+times[parts[1]])
        bot.send_message(message.chat.id, f"✅ Muted {parts[1]}")

@bot.message_handler(commands=["promote"])
def promote_cmd(message):
    uid = get_target_user(message)
    if uid and is_admin(message.chat.id, message.from_user.id):
        bot.promote_chat_member(message.chat.id, uid, can_manage_chat=True,
                                can_delete_messages=True, can_invite_users=True, can_restrict_members=True)
        bot.send_message(message.chat.id, "✅ Promoted.")

@bot.message_handler(commands=["demote"])
def demote_cmd(message):
    uid = get_target_user(message)
    if uid and is_admin(message.chat.id, message.from_user.id):
        bot.promote_chat_member(message.chat.id, uid, can_manage_chat=False,
                                can_delete_messages=False, can_invite_users=False, can_restrict_members=False)
        bot.send_message(message.chat.id, "✅ Demoted.")

# ====================== WARN SYSTEM ===========================
@bot.message_handler(commands=["warn"])
def warn_cmd(message):
    uid = get_target_user(message)
    if uid:
        key = f"{message.chat.id}:{uid}"
        data["warnings"][key] = data["warnings"].get(key, 0) + 1
        save_data()
        bot.send_message(message.chat.id, f"⚠ User warned ({data['warnings'][key]} warnings)")

@bot.message_handler(commands=["unwarn"])
def unwarn_cmd(message):
    uid = get_target_user(message)
    key = f"{message.chat.id}:{uid}"
    if uid and key in data["warnings"]:
        data["warnings"][key] = max(0, data["warnings"][key]-1)
        save_data()
        bot.send_message(message.chat.id, "✅ Warning removed")

@bot.message_handler(commands=["warnlist"])
def warnlist_cmd(message):
    warns = [f"{k}: {v}" for k,v in data["warnings"].items() if k.startswith(str(message.chat.id))]
    bot.send_message(message.chat.id, "⚠ Warn List:\n"+"\n".join(warns) if warns else "✅ No warnings")

# ====================== BAN WORDS ===========================
@bot.message_handler(commands=["banwords"])
def set_ban_words(message):
    if not is_admin(message.chat.id, message.from_user.id): return
    words = message.text.replace("/banwords", "").strip().split(",")
    data["ban_words"][str(message.chat.id)] = [w.strip().lower() for w in words if w.strip()]
    save_data()
    bot.reply_to(message, f"✅ Ban words: {', '.join(data['ban_words'][str(message.chat.id)])}")

@bot.message_handler(func=lambda m: True)
def check_ban_words(message):
    chat_words = data["ban_words"].get(str(message.chat.id), [])
    for w in chat_words:
        if message.text and re.search(rf"\b{re.escape(w)}\b", message.text.lower()):
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except: pass

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url="https://jack-the-ai.onrender.com/" + TOKEN)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Fail fast if token not set
if not BOT_TOKEN or BOT_TOKEN == "PASTE_YOUR_TOKEN_HERE":
    raise RuntimeError("BOT_TOKEN not set. Export BOT_TOKEN environment variable or edit the file.")

# ----------------------
# Logging & Bot setup
# ----------------------
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s",
                    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=16)
app = Flask(__name__)
START_TIME = time.time()

# ----------------------
# Thread-safe persistence
# ----------------------
_data_lock = threading.Lock()
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        logger.exception("Failed to read data file; starting with empty data")
        data = {}
else:
    data = {}

# default structure
_defaults = {
    "users": [],         # private users who've started bot
    "groups": [],        # groups where bot was used
    "settings": {},      # per-group settings
    "warnings": {},      # "chatid:userid" -> count
    "ban_words": {},     # chat_id -> [words]
    "banned": {},        # chat_id -> [user_ids]
    "reports": [],       # stored reports
    "channel": None,     # broadcast channel username/id
    "accepted": {},      # chat_id -> [user_ids] who clicked I agree
}
for k, v in _defaults.items():
    if k not in data:
        data[k] = v

def save_data():
    with _data_lock:
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            logger.exception("Error saving data")

atexit.register(lambda: save_data())

# ----------------------
# Utilities & decorators
# ----------------------
def is_group_admin(chat_id, user_id):
    try:
        admins = bot.get_chat_administrators(chat_id)
        return any(a.user.id == user_id for a in admins)
    except Exception:
        return False

def admin_only(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        if message.chat.type in ["group", "supergroup"]:
            if is_group_admin(message.chat.id, message.from_user.id) or message.from_user.id == OWNER_ID:
                return func(message, *args, **kwargs)
            else:
                return bot.reply_to(message, "❌ You must be an admin to use this.")
        else:
            return bot.reply_to(message, "❌ This command is for groups only.")
    return wrapper

def owner_only(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        if message.from_user.id != OWNER_ID:
            return bot.reply_to(message, "❌ Owner only.")
        return func(message, *args, **kwargs)
    return wrapper

def chat_settings(chat_id):
    cs = data["settings"].setdefault(str(chat_id), {
        "welcome_enabled": True,
        "welcome_text": "👋 Welcome {first_name} to {title}!\nPlease read the rules and press *I agree* to participate.",
        "welcome_photo": None,            # file_id
        "welcome_buttons": True,
        "welcome_pin": False,
        "warn_limit": 3,
        "anti_link": False,
        "anti_spam": False,
        "spam_threshold": 7,
        "spam_seconds": 10,
        "auto_kick_on_warn": True,
    })
    return cs

def add_user_record(uid):
    if uid and uid not in data["users"]:
        data["users"].append(uid)
        save_data()

def add_group_record(gid):
    if gid and gid not in data["groups"]:
        data["groups"].append(gid)
        save_data()

def format_welcome_text(template, user, chat):
    return template.format(
        first_name=getattr(user, "first_name", "") or getattr(user, "username", "") or "there",
        username=("@"+user.username) if getattr(user, "username", None) else "",
        title=getattr(chat, "title", "this chat")
    )

# ephemeral spam counters for anti-spam
_spam_counters = {}  # key (chat_id, user_id) -> [timestamps]

LINK_RE = re.compile(r"https?://\S+|t.me/\S+|telegram.me/\S+", re.IGNORECASE)

# ----------------------
# Flask webhook endpoints (optional)
# ----------------------
@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
        bot.process_new_updates([update])
    except Exception:
        logger.exception("Webhook processing error")
    return "OK", 200

@app.route("/")
def index():
    return "Bot is running!", 200

# ----------------------
# START / HELP / INFO
# ----------------------
@bot.message_handler(commands=["start"])
def cmd_start(message):
    if message.chat.type == "private":
        add_user_record(message.from_user.id)
    elif message.chat.type in ["group", "supergroup"]:
        add_group_record(message.chat.id)
    mk = InlineKeyboardMarkup()
    mk.add(InlineKeyboardButton("🗣 Text → Voice", callback_data="text_to_voice"))
    mk.add(InlineKeyboardButton("📖 Help", callback_data="show_help"))
    bot.send_message(message.chat.id,
                     f"👋 Hello {message.from_user.first_name}!\nI am *Jack The AI Bot* — admin tools + enhanced welcome.",
                     parse_mode="Markdown", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data == "show_help")
def cb_show_help(call):
    send_help(call.message.chat.id)

@bot.message_handler(commands=["help"])
def cmd_help(message):
    send_help(message.chat.id)

def send_help(chat_id):
    bot.send_message(chat_id,
        "🤖 *Commands*\n"
        "/start /help\n"
        "/botstats — stats\n"
        "/ping — ping\n"
        "/userinfo — your info\n\n"
        "Welcome & rules (admin):\n"
        "/setwelcome <text>\n"
        "/setwelcomephoto (reply to photo)\n"
        "/unsetwelcomephoto\n"
        "/togglewelcomebuttons\n"
        "/togglewelcomepin\n"
        "/welcome_preview\n"
        "/acceptedlist\n\n"
        "Admin:\n"
        "/kick /ban /unban /mute /promote /demote\n"
        "/warn /unwarn /warnlist\n"
        "/banwords word1, word2\n\n"
        "Owner:\n"
        "/announcement <msg>\n"
        "/broadcast <msg> (to all users)\n"
        "/setchannel @channel\n"
        "/post <msg>",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["botstats"])
def cmd_botstats(message):
    uptime = int(time.time() - START_TIME)
    h, m = uptime // 3600, (uptime % 3600) // 60
    bot.send_message(message.chat.id,
        f"📊 *Bot Stats*\nUsers: {len(data['users'])}\nGroups: {len(data['groups'])}\n"
        f"Uptime: {h}h {m}m", parse_mode="Markdown")

@bot.message_handler(commands=["ping"])
def cmd_ping(message):
    start = time.time()
    sent = bot.send_message(message.chat.id, "🏓 Pinging...")
    elapsed = round((time.time() - start) * 1000)
    bot.edit_message_text(f"🏓 Pong! {elapsed}ms", message.chat.id, sent.message_id)

@bot.message_handler(commands=["userinfo"])
def cmd_userinfo(message):
    u = message.from_user
    bot.send_message(message.chat.id,
                     f"👤 *User Info*\nID: `{u.id}`\nName: {u.first_name} {u.last_name or ''}\nUsername: @{u.username or 'None'}",
                     parse_mode="Markdown")

# ----------------------
# Feedback / Report
# ----------------------
@bot.message_handler(commands=["feedback"])
def cmd_feedback(message):
    text = message.text.replace("/feedback", "").strip()
    if text:
        try:
            bot.send_message(OWNER_ID, f"💌 Feedback from {message.from_user.id}:\n{text}")
            bot.reply_to(message, "✅ Feedback sent to owner.")
        except Exception:
            bot.reply_to(message, "❌ Failed to send feedback.")

@bot.message_handler(commands=["report"])
def cmd_report(message):
    text = message.text.replace("/report", "").strip()
    if text:
        r = {"from": message.from_user.id, "chat": getattr(message.chat, "id", None), "text": text, "time": time.time()}
        data["reports"].append(r)
        save_data()
        bot.reply_to(message, "✅ Report stored. Owner notified.")
        try:
            bot.send_message(OWNER_ID, f"🐞 Report: from {message.from_user.id} in chat {message.chat.id}\n{text}")
        except:
            pass

@bot.message_handler(commands=["reports"])
@owner_only
def cmd_reports(message):
    rows = data.get("reports", [])
    if not rows:
        return bot.reply_to(message, "✅ No reports.")
    out = []
    for r in rows[-30:]:
        t = datetime.fromtimestamp(r["time"]).isoformat()
        out.append(f"{t} — from {r['from']} in chat {r.get('chat')}: {r['text']}")
    bot.send_message(message.chat.id, "📋 Recent reports:\n\n" + "\n\n".join(out))

# ----------------------
# Owner commands: announcements, broadcast, channel
# ----------------------
@bot.message_handler(commands=["announcement"])
def cmd_announcement(message):
    if message.from_user.id != OWNER_ID:
        return
    text = message.text.replace("/announcement", "").strip()
    if not text:
        return bot.reply_to(message, "Usage: /announcement <msg>")
    for uid in list(data.get("users", [])):
        try:
            bot.send_message(uid, f"📢 Announcement:\n{text}")
        except:
            pass
    bot.reply_to(message, "✅ Sent announcement to users.")

@bot.message_handler(commands=["broadcast"])
@owner_only
def cmd_broadcast(message):
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        return bot.reply_to(message, "Usage: /broadcast <msg>")
    sent = 0
    for uid in list(data.get("users", [])):
        try:
            bot.send_message(uid, text)
            sent += 1
        except:
            pass
    bot.reply_to(message, f"✅ Broadcast sent to {sent} users.")

@bot.message_handler(commands=["setchannel"])
@owner_only
def cmd_setchannel(message):
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "Usage: /setchannel @channelusername")
    data["channel"] = parts[1]
    save_data()
    bot.reply_to(message, f"✅ Channel set to {parts[1]}")

@bot.message_handler(commands=["post"])
@owner_only
def cmd_post(message):
    if not data.get("channel"):
        return bot.reply_to(message, "❌ No channel set.")
    text = message.text.replace("/post", "").strip()
    if text:
        try:
            bot.send_message(data["channel"], text)
            bot.reply_to(message, "✅ Posted to channel.")
        except Exception:
            bot.reply_to(message, "❌ Failed to post (check channel username and bot permissions).")

# ----------------------
# Admin helpers: get target user
# ----------------------
def get_target_user(message):
    # reply -> target, otherwise parse username/id
    if message.reply_to_message:
        return message.reply_to_message.from_user.id
    parts = message.text.split() if message.text else []
    if len(parts) > 1:
        maybe = parts[1]
        if maybe.isdigit():
            return int(maybe)
        try:
            member = bot.get_chat_member(message.chat.id, maybe)
            return member.user.id
        except:
            return None
    return None

# ----------------------
# Admin actions: kick/ban/unban/mute/promote/demote
# ----------------------
@bot.message_handler(commands=["kick"])
@admin_only
def cmd_kick(message):
    uid = get_target_user(message)
    if not uid:
        return bot.reply_to(message, "Usage: reply or /kick <id|@username>")
    try:
        bot.kick_chat_member(message.chat.id, uid)
        bot.reply_to(message, "✅ User kicked.")
    except Exception:
        bot.reply_to(message, "❌ Failed to kick (insufficient rights or invalid user).")

@bot.message_handler(commands=["ban"])
@admin_only
def cmd_ban(message):
    uid = get_target_user(message)
    if not uid:
        return bot.reply_to(message, "Usage: reply or /ban <id|@username>")
    key = str(message.chat.id)
    data["banned"].setdefault(key, [])
    if uid not in data["banned"][key]:
        data["banned"][key].append(uid)
        save_data()
    try:
        bot.kick_chat_member(message.chat.id, uid)
    except:
        pass
    bot.reply_to(message, "✅ User banned (and kicked if possible).")

@bot.message_handler(commands=["unban"])
@admin_only
def cmd_unban(message):
    uid = get_target_user(message)
    if not uid:
        return bot.reply_to(message, "Usage: reply or /unban <id|@username>")
    key = str(message.chat.id)
    lst = data.get("banned", {}).get(key, [])
    if uid in lst:
        lst.remove(uid)
        data["banned"][key] = lst
        save_data()
        bot.reply_to(message, "✅ User unbanned.")
    else:
        bot.reply_to(message, "User not in banned list.")

@bot.message_handler(commands=["mute"])
@admin_only
def cmd_mute(message):
    uid = get_target_user(message)
    parts = message.text.split()
    times = {"1m":60,"1h":3600,"1d":86400}
    if uid and len(parts) > 1 and parts[1] in times:
        try:
            bot.restrict_chat_member(message.chat.id, uid, until_date=int(time.time())+times[parts[1]])
            bot.reply_to(message, f"✅ Muted for {parts[1]}.")
        except Exception:
            bot.reply_to(message, "❌ Failed to mute.")
    else:
        bot.reply_to(message, "Usage: /mute <1m|1h|1d> (reply/id)")

@bot.message_handler(commands=["promote"])
@admin_only
def cmd_promote(message):
    uid = get_target_user(message)
    if not uid:
        return bot.reply_to(message, "Usage: reply or /promote <id|@username>")
    try:
        bot.promote_chat_member(message.chat.id, uid,
                                can_change_info=True, can_delete_messages=True,
                                can_invite_users=True, can_restrict_members=True,
                                can_pin_messages=True)
        bot.reply_to(message, "✅ Promoted.")
    except Exception:
        bot.reply_to(message, "❌ Failed to promote.")

@bot.message_handler(commands=["demote"])
@admin_only
def cmd_demote(message):
    uid = get_target_user(message)
    if not uid:
        return bot.reply_to(message, "Usage: reply or /demote <id|@username>")
    try:
        bot.promote_chat_member(message.chat.id, uid,
                                can_change_info=False, can_delete_messages=False,
                                can_invite_users=False, can_restrict_members=False,
                                can_pin_messages=False)
        bot.reply_to(message, "✅ Demoted.")
    except Exception:
        bot.reply_to(message, "❌ Failed to demote.")

# ----------------------
# Warn system
# ----------------------
@bot.message_handler(commands=["warn"])
@admin_only
def cmd_warn(message):
    uid = get_target_user(message)
    if not uid:
        return bot.reply_to(message, "Usage: reply or /warn <id|@username>")
    key = f"{message.chat.id}:{uid}"
    data["warnings"][key] = data["warnings"].get(key, 0) + 1
    save_data()
    cur = data["warnings"][key]
    s = chat_settings(message.chat.id)
    bot.send_message(message.chat.id, f"⚠ User warned ({cur}/{s.get('warn_limit',3)})")
    if cur >= s.get("warn_limit", 3):
        try:
            if s.get("auto_kick_on_warn", True):
                bot.kick_chat_member(message.chat.id, uid)
                bot.send_message(message.chat.id, f"🔨 User auto-kicked after {cur} warnings.")
        except Exception:
            logger.exception("Auto-action failed")

@bot.message_handler(commands=["unwarn"])
@admin_only
def cmd_unwarn(message):
    uid = get_target_user(message)
    if not uid:
        return bot.reply_to(message, "Usage: reply or /unwarn <id|@username>")
    key = f"{message.chat.id}:{uid}"
    if key in data["warnings"]:
        data["warnings"][key] = max(0, data["warnings"][key]-1)
        save_data()
        bot.reply_to(message, "✅ Warning removed.")
    else:
        bot.reply_to(message, "No warnings for that user.")

@bot.message_handler(commands=["warnlist"])
def cmd_warnlist(message):
    warns = [f"{k.split(':',1)[1]}: {v}" for k,v in data["warnings"].items() if k.startswith(str(message.chat.id)+":")]
    bot.send_message(message.chat.id, "⚠ Warn List:\n" + ("\n".join(warns) if warns else "No warnings."))

# ----------------------
# Ban words, settings for group
# ----------------------
@bot.message_handler(commands=["banwords"])
@admin_only
def cmd_banwords(message):
    text = message.text.replace("/banwords", "").strip()
    if not text:
        return bot.reply_to(message, "Usage: /banwords word1, word2")
    words = [w.strip().lower() for w in text.split(",") if w.strip()]
    data["ban_words"][str(message.chat.id)] = words
    save_data()
    bot.reply_to(message, f"✅ Ban words set: {', '.join(words)}")

@bot.message_handler(commands=["setsafe"])
@admin_only
def cmd_setsafe(message):
    args = message.text.replace("/setsafe", "").strip().split()
    if not args:
        return bot.reply_to(message, "Usage: /setsafe anti_link:on anti_spam:off warn_limit:2 spam_threshold:5 spam_seconds:6")
    s = chat_settings(message.chat.id)
    for a in args:
        if ":" in a:
            k, v = a.split(":",1)
            if k in ("anti_link","anti_spam"):
                s[k] = v.lower() in ("1","on","true","yes")
            elif k in ("warn_limit","spam_threshold","spam_seconds","spam_seconds"):
                try:
                    s[k] = int(v)
                except:
                    pass
    save_data()
    bot.reply_to(message, f"✅ Settings updated: {s}")

@bot.message_handler(commands=["settings"])
def cmd_settings(message):
    s = chat_settings(message.chat.id)
    bot.reply_to(message, f"Settings: {json.dumps(s, ensure_ascii=False)}")

# ----------------------
# Enhanced Welcome features
# ----------------------
@bot.message_handler(content_types=["new_chat_members"])
def on_new_members(message):
    add_group_record(message.chat.id)
    s = chat_settings(message.chat.id)
    if not s.get("welcome_enabled", True):
        return
    for new_user in message.new_chat_members:
        caption = format_welcome_text(s.get("welcome_text", ""), new_user, message.chat)
        markup = None
        if s.get("welcome_buttons", True):
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("✅ I agree", callback_data=f"welcome_agree:{message.chat.id}"))
        try:
            if s.get("welcome_photo"):
                sent = bot.send_photo(message.chat.id, s["welcome_photo"], caption=caption, reply_markup=markup, parse_mode="Markdown")
            else:
                sent = bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode="Markdown")
            if s.get("welcome_pin", False):
                try:
                    bot.pin_chat_message(message.chat.id, sent.message_id, disable_notification=True)
                except Exception:
                    logger.debug("Pin failed (missing rights?)")
        except Exception:
            logger.exception("Failed to send welcome message")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("welcome_agree:"))
def cb_welcome_agree(call):
    try:
        _, chat_id_str = call.data.split(":", 1)
        chat_id = int(chat_id_str)
    except:
        return bot.answer_callback_query(call.id, "Invalid data.")
    if not call.message or not call.message.chat:
        return bot.answer_callback_query(call.id, "Invalid context.")
    if call.message.chat.id != chat_id:
        return bot.answer_callback_query(call.id, "This button isn't for this chat.")
    uid = call.from_user.id
    accepted = data.setdefault("accepted", {}).setdefault(str(chat_id), [])
    if uid in accepted:
        return bot.answer_callback_query(call.id, "✅ You already accepted.")
    accepted.append(uid)
    save_data()
    bot.answer_callback_query(call.id, "Thanks — you've accepted the rules!")
    try:
        bot.send_message(chat_id, f"✅ {call.from_user.first_name} accepted the rules.")
    except:
        pass

# Welcome management commands
@bot.message_handler(commands=["setwelcome"])
@admin_only
def cmd_setwelcome(message):
    text = message.text.replace("/setwelcome", "").strip()
    if not text:
        return bot.reply_to(message, "Usage: /setwelcome <text> (use {first_name} {title} {username})")
    s = chat_settings(message.chat.id)
    s["welcome_text"] = text
    save_data()
    bot.reply_to(message, "✅ Welcome text updated.")

@bot.message_handler(commands=["setwelcomephoto"])
@admin_only
def cmd_setwelcomephoto(message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return bot.reply_to(message, "Reply to a photo with /setwelcomephoto to set it.")
    photo = message.reply_to_message.photo[-1]
    file_id = photo.file_id
    s = chat_settings(message.chat.id)
    s["welcome_photo"] = file_id
    save_data()
    bot.reply_to(message, "✅ Welcome photo saved (file_id stored).")

@bot.message_handler(commands=["unsetwelcomephoto"])
@admin_only
def cmd_unsetwelcomephoto(message):
    s = chat_settings(message.chat.id)
    if s.get("welcome_photo"):
        s["welcome_photo"] = None
        save_data()
        bot.reply_to(message, "✅ Welcome photo removed.")
    else:
        bot.reply_to(message, "No welcome photo set.")

@bot.message_handler(commands=["togglewelcomebuttons"])
@admin_only
def cmd_togglewelcomebuttons(message):
    s = chat_settings(message.chat.id)
    s["welcome_buttons"] = not s.get("welcome_buttons", True)
    save_data()
    bot.reply_to(message, f"✅ Welcome buttons {'enabled' if s['welcome_buttons'] else 'disabled'}.")

@bot.message_handler(commands=["togglewelcomepin"])
@admin_only
def cmd_togglewelcomepin(message):
    s = chat_settings(message.chat.id)
    s["welcome_pin"] = not s.get("welcome_pin", False)
    save_data()
    bot.reply_to(message, f"✅ Welcome pin {'enabled' if s['welcome_pin'] else 'disabled'}.")

@bot.message_handler(commands=["welcome_preview"])
@admin_only
def cmd_welcome_preview(message):
    s = chat_settings(message.chat.id)
    preview_text = format_welcome_text(s.get("welcome_text", ""), message.from_user, message.chat)
    markup = None
    if s.get("welcome_buttons", True):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ I agree", callback_data=f"welcome_agree:{message.chat.id}"))
    try:
        if s.get("welcome_photo"):
            bot.send_photo(message.chat.id, s["welcome_photo"], caption=preview_text, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, preview_text, reply_markup=markup, parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ Failed to send preview (check bot permissions).")

@bot.message_handler(commands=["acceptedlist"])
@admin_only
def cmd_acceptedlist(message):
    al = data.get("accepted", {}).get(str(message.chat.id), [])
    if not al:
        return bot.reply_to(message, "✅ No accepted users yet.")
    rows = []
    for uid in al[-200:]:
        try:
            cm = bot.get_chat_member(message.chat.id, uid)
            rows.append(f"{cm.user.first_name} ({uid})")
        except:
            rows.append(str(uid))
    bot.send_message(message.chat.id, "✅ Accepted users:\n" + "\n".join(rows))

# ----------------------
# TTS: choose language then send translated TTS immediately (safer than encoding text into callback)
# ----------------------
@bot.callback_query_handler(func=lambda c: c.data == "text_to_voice")
def cb_text_to_voice(call):
    markup = InlineKeyboardMarkup(row_width=3)
    langs = [("English","en"),("Tagalog","tl"),("Spanish","es"),("Japanese","ja"),("Korean","ko"),
             ("Chinese","zh-cn"),("French","fr"),("German","de"),("Hindi","hi"),("Russian","ru")]
    for name, code in langs:
        markup.add(InlineKeyboardButton(name, callback_data=f"tts_lang:{code}"))
    bot.send_message(call.message.chat.id, "🌐 Choose language for TTS:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("tts_lang:"))
def cb_tts_lang(call):
    lang = call.data.split(":",1)[1]
    msg = bot.send_message(call.message.chat.id, f"✏ Send the text to convert to {lang} voice:")
    bot.register_next_step_handler(msg, lambda m, l=lang: tts_translate_and_send(m, l))

def tts_translate_and_send(message, lang):
    text = message.text or ""
    try:
        translated = GoogleTranslator(source="auto", target=lang).translate(text)
    except Exception:
        translated = text
    # generate tts and send
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            gTTS(text=translated, lang=lang).save(tmp.name)
            with open(tmp.name, "rb") as f:
                bot.send_voice(message.chat.id, f)
    except Exception:
        logger.exception("TTS failed")
        bot.send_message(message.chat.id, "❌ Failed to generate TTS.")
    finally:
        try:
            os.remove(tmp.name)
        except:
            pass
    bot.send_message(message.chat.id, f"✅ Sent voice (translated text: {translated[:800]})")

# ----------------------
# Global message handler: ban words, anti-link, anti-spam, banned users
# ----------------------
@bot.message_handler(func=lambda m: True, content_types=["text","video","photo","audio","sticker"])
def global_message_handler(message):
    # ignore bots
    if message.from_user and message.from_user.is_bot:
        return

    # record user/group
    if message.chat.type == "private":
        add_user_record(message.from_user.id)
    else:
        add_group_record(message.chat.id)

    # if user is banned in this chat -> delete message
    if is_user_banned_in_chat(message.chat.id, message.from_user.id):
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        return

    # ban words
    if message.text:
        banned_words = data.get("ban_words", {}).get(str(message.chat.id), [])
        for w in banned_words:
            if re.search(rf"\b{re.escape(w)}\b", message.text.lower()):
                try:
                    bot.delete_message(message.chat.id, message.message_id)
                    bot.send_message(message.chat.id, "⚠ Message deleted: banned word detected.")
                except:
                    pass
                return

    # anti-link
    s = chat_settings(message.chat.id)
    if s.get("anti_link", False) and message.text and LINK_RE.search(message.text):
        try:
            bot.delete_message(message.chat.id, message.message_id)
            bot.send_message(message.chat.id, "⚠ Link removed (anti-link enabled).")
        except:
            pass
        return

    # anti-spam
    if s.get("anti_spam", False) and message.text:
        now = time.time()
        key = (str(message.chat.id), message.from_user.id)
        window = s.get("spam_seconds", 10)
        threshold = s.get("spam_threshold", 7)
        times = _spam_counters.get(key, [])
        times = [t for t in times if now - t <= window]
        times.append(now)
        _spam_counters[key] = times
        if len(times) >= threshold:
            try:
                bot.restrict_chat_member(message.chat.id, message.from_user.id, until_date=int(now + 60))
                bot.send_message(message.chat.id, f"🔇 {message.from_user.first_name} muted for spamming.")
            except:
                pass
            _spam_counters[key] = []
            return

# helper
def is_user_banned_in_chat(chat_id, user_id):
    return user_id in data.get("banned", {}).get(str(chat_id), [])

# ----------------------
# Run mode: webhook if WEBHOOK_URL set otherwise polling
# ----------------------
def start_bot():
    if WEBHOOK_URL:
        try:
            bot.remove_webhook()
            logger.info("Setting webhook to %s", WEBHOOK_URL + BOT_TOKEN)
            bot.set_webhook(url=WEBHOOK_URL + BOT_TOKEN)
            app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
        except Exception:
            logger.exception("Webhook failed; falling back to polling")
            bot.remove_webhook()
            bot.polling(none_stop=True, interval=2)
    else:
        bot.remove_webhook()
        bot.polling(none_stop=True, interval=2)

if __name__ == "__main__":
    logger.info("Starting Jack The AI Bot...")
    save_data()
    start_bot()

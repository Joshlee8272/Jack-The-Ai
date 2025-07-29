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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from gtts import gTTS
from deep_translator import GoogleTranslator
import tempfile, re, time, json, os
from flask import Flask, request

# ---------------- CONFIG ----------------
TOKEN = "8369185267:AAGV7CPcWM0UBR7xiEGIpz4btLr4QGlmXyU"
OWNER_ID = 7301067810
# default required channel (can be updated by owner with /setrequiredchannel)
DEFAULT_REQUIRED_CHANNEL = "@txtfilegenerator"
# ----------------------------------------

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=20)
app = Flask(__name__)
START_TIME = time.time()

DATA_FILE = "data.json"
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {
        "ban_words": {},
        "warnings": {},
        "users": [],
        "groups": [],
        "channel": None,                # used by /post command in original script
        "required_channel": DEFAULT_REQUIRED_CHANNEL  # channel user must join
    }

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def is_admin(chat_id, user_id):
    try:
        admins = bot.get_chat_administrators(chat_id)
        return any(a.user.id == user_id for a in admins)
    except Exception:
        return False

def get_target_user(message):
    """Return target user id from a reply or @username/id argument."""
    parts = message.text.split() if message.text else []
    if message.reply_to_message:
        return message.reply_to_message.from_user.id
    elif len(parts) > 1:
        # if argument is a digit -> id
        if parts[1].isdigit():
            return int(parts[1])
        # try to resolve username in current chat
        try:
            member = bot.get_chat_member(message.chat.id, parts[1])
            return member.user.id
        except Exception:
            return None
    return None

def required_channel_username():
    """Return the required channel username (string starting with @)."""
    return data.get("required_channel") or DEFAULT_REQUIRED_CHANNEL

def is_member_channel(user_id):
    """
    Returns True if user_id is a member/administrator/creator/restricted of the required channel.
    If the check fails (bot not added, private channel issues), returns False.
    """
    chan = required_channel_username()
    if not chan:
        return True  # no requirement set
    try:
        # telebot allows passing username like "@channel"
        member = bot.get_chat_member(chan, user_id)
        return member.status in ("member", "creator", "administrator", "restricted")
    except Exception:
        # if error (private channel, bot not in channel, etc.) treat as not member
        return False

def send_join_prompt(chat_id):
    chan = required_channel_username()
    url = f"https://t.me/{chan.lstrip('@')}" if chan else None
    markup = InlineKeyboardMarkup()
    if url:
        markup.add(InlineKeyboardButton("🔗 Join Channel", url=url))
    markup.add(InlineKeyboardButton("I've Joined ✅", callback_data="check_join"))
    bot.send_message(
        chat_id,
        f"🔒 *Join This Channel First*\n\nTo use this bot you must join {chan}.\n\n"
        "Press *Join Channel* then come back and tap *I've Joined ✅*.",
        reply_markup=markup,
        parse_mode="Markdown",
    )

# ---------------- Flask webhook ----------------
@app.route("/" + TOKEN, methods=["POST"])
def webhook():
    raw = request.stream.read().decode("utf-8")
    update = telebot.types.Update.de_json(raw)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/")
def index():
    return "Bot is running!", 200

# ====================== START / HELP ===========================
@bot.message_handler(commands=["start"])
def start(message):
    # check required channel membership for private chats and commands
    user_id = getattr(message.from_user, "id", None)
    if user_id and not is_member_channel(user_id):
        send_join_prompt(message.chat.id)
        return

    # record user/group
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
    # require channel membership before showing help
    if message.from_user and not is_member_channel(message.from_user.id):
        send_join_prompt(message.chat.id)
        return
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
        "/setchannel @username  - set posting channel\n"
        "/setrequiredchannel @username - require users to join this channel\n"
        "/post <msg>",
        parse_mode="Markdown",
    )

# -------------------- Callbacks for join check --------------------
@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def check_join_callback(call):
    user_id = call.from_user.id
    if is_member_channel(user_id):
        try:
            bot.answer_callback_query(call.id, "Thanks — access granted ✅", show_alert=False)
        except Exception:
            pass
        # show normal start flow in this chat
        start(call.message)
    else:
        try:
            bot.answer_callback_query(call.id, "Still not a member. Please join the channel first.", show_alert=True)
        except Exception:
            pass
        send_join_prompt(call.message.chat.id)

# ====================== TEXT TO VOICE ===========================
@bot.callback_query_handler(func=lambda c: c.data == "text_to_voice")
def callback_handler(call):
    # check membership again for safety
    if not is_member_channel(call.from_user.id):
        send_join_prompt(call.message.chat.id)
        return

    markup = InlineKeyboardMarkup(row_width=2)
    langs = [
        ("🇺🇸 English", "en"), ("🇵🇭 Tagalog", "tl"), ("🇪🇸 Spanish", "es"),
        ("🇯🇵 Japanese", "ja"), ("🇰🇷 Korean", "ko"), ("🇨🇳 Chinese", "zh-cn"),
        ("🇫🇷 French", "fr"), ("🇩🇪 German", "de"), ("🇮🇳 Hindi", "hi"), ("🇷🇺 Russian", "ru")
    ]
    for n, code in langs:
        markup.add(InlineKeyboardButton(n, callback_data=f"lang_{code}"))
    bot.send_message(call.message.chat.id, "🌐 Choose language:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("lang_"))
def select_language(call):
    lang = call.data.split("_", 1)[1]
    msg = bot.send_message(call.message.chat.id, "✏ Send me text:")
    bot.register_next_step_handler(msg, lambda m: translate_and_convert(m, lang))

def translate_and_convert(message, lang):
    try:
        translated = GoogleTranslator(source="auto", target=lang).translate(message.text)
    except Exception:
        translated = message.text  # fall back to original text if translator fails
    tts = gTTS(text=translated, lang=lang)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tf:
            tmp = tf.name
            tts.save(tmp)
        with open(tmp, "rb") as f:
            bot.send_voice(message.chat.id, f)
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Failed to generate/send voice.")
    finally:
        # cleanup temp file
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass
    bot.send_message(message.chat.id, f"✅ Translated to {lang.upper()}:\n_{translated}_", parse_mode="Markdown")

# ====================== INFO COMMANDS ===========================
@bot.message_handler(commands=["botstats"])
def botstats_cmd(message):
    if message.from_user and not is_member_channel(message.from_user.id):
        send_join_prompt(message.chat.id)
        return
    uptime = int(time.time() - START_TIME)
    h, m = uptime // 3600, (uptime % 3600) // 60
    bot.send_message(
        message.chat.id,
        f"📊 *Bot Stats*\n👥 Users: {len(data['users'])}\n💬 Groups: {len(data['groups'])}\n"
        f"⚠ Warnings: {len(data['warnings'])}\n⏳ Uptime: {h}h {m}m",
        parse_mode="Markdown",
    )

@bot.message_handler(commands=["ping"])
def ping_cmd(message):
    if message.from_user and not is_member_channel(message.from_user.id):
        send_join_prompt(message.chat.id)
        return
    start = time.time()
    sent = bot.send_message(message.chat.id, "🏓 Pinging...")
    bot.edit_message_text(f"🏓 Pong! {round((time.time()-start)*1000)}ms", message.chat.id, sent.message_id)

@bot.message_handler(commands=["userinfo"])
def userinfo_cmd(message):
    if message.from_user and not is_member_channel(message.from_user.id):
        send_join_prompt(message.chat.id)
        return
    u = message.from_user
    bot.send_message(
        message.chat.id,
        f"👤 *User Info*\n🆔 {u.id}\n📛 {u.first_name}\n🔗 @{u.username or 'None'}",
        parse_mode="Markdown",
    )

# ====================== FEEDBACK / REPORT ===========================
@bot.message_handler(commands=["feedback"])
def feedback_cmd(message):
    if message.from_user and not is_member_channel(message.from_user.id):
        send_join_prompt(message.chat.id)
        return
    msg = message.text.replace("/feedback", "").strip()
    if msg:
        bot.send_message(OWNER_ID, f"💌 Feedback from {message.from_user.id}:\n{msg}")
        bot.reply_to(message, "✅ Feedback sent!")

@bot.message_handler(commands=["report"])
def report_cmd(message):
    if message.from_user and not is_member_channel(message.from_user.id):
        send_join_prompt(message.chat.id)
        return
    msg = message.text.replace("/report", "").strip()
    if msg:
        bot.send_message(OWNER_ID, f"🐞 Report from {message.from_user.id}:\n{msg}")
        bot.reply_to(message, "✅ Report sent!")

# ====================== OWNER COMMANDS ===========================
@bot.message_handler(commands=["announcement"])
def announcement_cmd(message):
    if message.from_user.id != OWNER_ID:
        return
    text = message.text.replace("/announcement", "").strip()
    for uid in data["users"]:
        try:
            bot.send_message(uid, f"📢 Announcement:\n{text}")
        except Exception:
            pass
    bot.reply_to(message, "✅ Sent!")

@bot.message_handler(commands=["setchannel"])
def setchannel_cmd(message):
    if message.from_user.id != OWNER_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "Usage: /setchannel @username")
    data["channel"] = parts[1]
    save_data()
    bot.reply_to(message, f"✅ Channel set to {parts[1]}")

@bot.message_handler(commands=["setrequiredchannel"])
def set_required_channel_cmd(message):
    """Owner can change which channel users must join to access the bot."""
    if message.from_user.id != OWNER_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "Usage: /setrequiredchannel @channelusername")
    data["required_channel"] = parts[1]
    save_data()
    bot.reply_to(message, f"✅ Required channel set to {parts[1]}")

@bot.message_handler(commands=["post"])
def post_cmd(message):
    if message.from_user.id != OWNER_ID:
        return
    if not data.get("channel"):
        return bot.reply_to(message, "❌ No channel set. Use /setchannel @username")
    msg = message.text.replace("/post", "").strip()
    if msg:
        bot.send_message(data["channel"], msg)
        bot.reply_to(message, "✅ Posted!")

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
    times = {"1m":60, "1h":3600, "1d":86400}
    if uid and len(parts) > 1 and parts[1] in times:
        bot.restrict_chat_member(message.chat.id, uid, until_date=int(time.time())+times[parts[1]])
        bot.send_message(message.chat.id, f"✅ Muted {parts[1]}")

@bot.message_handler(commands=["promote"])
def promote_cmd(message):
    uid = get_target_user(message)
    if uid and is_admin(message.chat.id, message.from_user.id):
        bot.promote_chat_member(
            message.chat.id, uid,
            can_manage_chat=True,
            can_delete_messages=True,
            can_invite_users=True,
            can_restrict_members=True
        )
        bot.send_message(message.chat.id, "✅ Promoted.")

@bot.message_handler(commands=["demote"])
def demote_cmd(message):
    uid = get_target_user(message)
    if uid and is_admin(message.chat.id, message.from_user.id):
        bot.promote_chat_member(
            message.chat.id, uid,
            can_manage_chat=False,
            can_delete_messages=False,
            can_invite_users=False,
            can_restrict_members=False
        )
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
        data["warnings"][key] = max(0, data["warnings"][key] - 1)
        save_data()
        bot.send_message(message.chat.id, "✅ Warning removed")

@bot.message_handler(commands=["warnlist"])
def warnlist_cmd(message):
    warns = [f"{k}: {v}" for k, v in data["warnings"].items() if k.startswith(str(message.chat.id))]
    bot.send_message(message.chat.id, "⚠ Warn List:\n" + "\n".join(warns) if warns else "✅ No warnings")

# ====================== BAN WORDS ===========================
@bot.message_handler(commands=["banwords"])
def set_ban_words(message):
    if not is_admin(message.chat.id, message.from_user.id):
        return
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
            except Exception:
                pass

# -------------------- main --------------------
if __name__ == "__main__":
    bot.remove_webhook()
    # update the webhook url to your render/host URL + TOKEN
    bot.set_webhook(url="https://jack-the-ai.onrender.com/" + TOKEN)
    # run flask app (Render will set PORT in env)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from gtts import gTTS
import tempfile, re, time, json, os
from flask import Flask, request

TOKEN = "8369185267:AAGV7CPcWM0UBR7xiEGIpz4btLr4QGlmXyU"
OWNER_ID = 7301067810  # ✅ Your Telegram ID

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=10)
app = Flask(__name__)

DATA_FILE = "data.json"

# ✅ Load or create data.json
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"ban_words": {}, "warnings": {}, "users": []}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def is_admin(chat_id, user_id):
    try:
        admins = bot.get_chat_administrators(chat_id)
        return any(a.user.id == user_id for a in admins)
    except:
        return False

@app.route("/" + TOKEN, methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    try:
        bot.process_new_updates([update])
    except Exception as e:
        print("Error:", e)
    return "OK", 200

@app.route("/")
def index():
    return "Bot is running!", 200

# ✅ Start command
@bot.message_handler(commands=["start"])
def start(message):
    if message.chat.type == "private" and message.from_user.id not in data["users"]:
        data["users"].append(message.from_user.id)
        save_data()

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🗣 Text To Voice", callback_data="text_to_voice"))
    markup.add(InlineKeyboardButton("⚙ Customize Channel", callback_data="customize_channel"))
    bot.send_message(message.chat.id, "Welcome! Choose an option:", reply_markup=markup)

# ✅ Help command
@bot.message_handler(commands=["help"])
def help_cmd(message):
    text = (
        "📜 *Bot Commands*\n"
        "/kick (reply) – Kick a user\n"
        "/mute <time> (reply) – Mute user (1m,1h,1d)\n"
        "/banwords word1,word2 – Set banned words\n"
        "/stats – Show group stats\n"
        "/promote (reply) – Promote user to admin\n"
        "/demote (reply) – Demote admin\n"
        "/announcement <msg> – (Owner Only)"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ✅ Handle buttons
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "text_to_voice":
        msg = bot.send_message(call.message.chat.id, "Send me text to convert to voice:")
        bot.register_next_step_handler(msg, convert_text_to_voice)
    elif call.data == "customize_channel":
        bot.send_message(call.message.chat.id, "Please add me to your discussion group as admin.")

def convert_text_to_voice(message):
    try:
        if not message.text:
            bot.reply_to(message, "❌ Please send text only.")
            return
        tts = gTTS(text=message.text, lang="en")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tts.save(tmp.name)
            bot.send_voice(message.chat.id, open(tmp.name, "rb"))
    except Exception as e:
        bot.reply_to(message, f"⚠ Error: {e}")

# ✅ Warning system
def warn_user(chat_id, user_id, username):
    key = f"{chat_id}:{user_id}"
    data["warnings"][key] = data["warnings"].get(key, 0) + 1
    save_data()

    count = data["warnings"][key]
    penalties = {1: 60, 2: 3600, 3: 86400}

    if count <= 3:
        try:
            bot.restrict_chat_member(chat_id, user_id, until_date=int(time.time()) + penalties[count])
            bot.send_message(chat_id, f"⚠ Warning {count}/4 for {username}. Muted {penalties[count]}s.")
        except:
            pass
    else:
        try:
            bot.kick_chat_member(chat_id, user_id)
            bot.send_message(chat_id, f"🚫 {username} has been kicked for repeated ban words.")
        except:
            pass

# ✅ Ban words
@bot.message_handler(commands=["banwords"])
def set_ban_words(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Admins only.")
        return
    words = message.text.replace("/banwords", "").strip().split(",")
    data["ban_words"][str(message.chat.id)] = [w.strip().lower() for w in words if w.strip()]
    save_data()
    bot.reply_to(message, f"✅ Ban words set: {', '.join(data['ban_words'][str(message.chat.id)])}")

# ✅ Stats command
@bot.message_handler(commands=["stats"])
def stats_cmd(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Admins only.")
        return
    total_warned = sum(1 for k in data["warnings"] if k.startswith(str(message.chat.id)))
    banned_words = len(data["ban_words"].get(str(message.chat.id), []))
    bot.send_message(message.chat.id, f"📊 Stats:\n👥 Warned Users: {total_warned}\n🚫 Banned Words: {banned_words}")

# ✅ Kick / Mute
@bot.message_handler(commands=["kick"])
def kick_cmd(message):
    if not message.reply_to_message or not is_admin(message.chat.id, message.from_user.id):
        return
    try:
        bot.kick_chat_member(message.chat.id, message.reply_to_message.from_user.id)
        bot.send_message(message.chat.id, "✅ User kicked.")
    except:
        bot.send_message(message.chat.id, "⚠ Failed to kick user.")

@bot.message_handler(commands=["mute"])
def mute_cmd(message):
    if not message.reply_to_message or not is_admin(message.chat.id, message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /mute <1m|1h|1d>")
        return
    times = {"1m": 60, "1h": 3600, "1d": 86400}
    duration = times.get(parts[1], 60)
    bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, until_date=int(time.time()) + duration)
    bot.send_message(message.chat.id, f"✅ User muted for {parts[1]}")

# ✅ Promote / Demote
@bot.message_handler(commands=["promote"])
def promote_cmd(message):
    if not message.reply_to_message or not is_admin(message.chat.id, message.from_user.id):
        return
    try:
        bot.promote_chat_member(message.chat.id, message.reply_to_message.from_user.id,
                                can_manage_chat=True, can_delete_messages=True,
                                can_invite_users=True, can_restrict_members=True)
        bot.send_message(message.chat.id, "✅ User promoted to admin.")
    except:
        bot.send_message(message.chat.id, "⚠ Failed to promote user.")

@bot.message_handler(commands=["demote"])
def demote_cmd(message):
    if not message.reply_to_message or not is_admin(message.chat.id, message.from_user.id):
        return
    try:
        bot.promote_chat_member(message.chat.id, message.reply_to_message.from_user.id,
                                can_manage_chat=False, can_delete_messages=False,
                                can_invite_users=False, can_restrict_members=False)
        bot.send_message(message.chat.id, "✅ User demoted.")
    except:
        bot.send_message(message.chat.id, "⚠ Failed to demote user.")

# ✅ Announcement (Owner only)
@bot.message_handler(commands=["announcement"])
def announcement_cmd(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Only bot owner can use this.")
        return
    text = message.text.replace("/announcement", "").strip()
    if not text:
        bot.reply_to(message, "Usage: /announcement <message>")
        return
    for user_id in data["users"]:
        try:
            bot.send_message(user_id, f"📢 Announcement:\n{text}")
        except:
            pass

# ✅ Check messages for ban words
@bot.message_handler(func=lambda m: True)
def check_ban_words(message):
    chat_ban_words = data["ban_words"].get(str(message.chat.id), [])
    for w in chat_ban_words:
        if re.search(rf"\b{re.escape(w)}\b", message.text.lower()):
            try:
                bot.delete_message(message.chat.id, message.message_id)
                warn_user(message.chat.id, message.from_user.id, message.from_user.first_name)
            except:
                pass
            return

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url="https://jack-the-ai.onrender.com/" + TOKEN)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

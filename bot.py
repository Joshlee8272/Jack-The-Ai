import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from gtts import gTTS
import tempfile, re, time, json, os
from flask import Flask, request

TOKEN = "8369185267:AAGV7CPcWM0UBR7xiEGIpz4btLr4QGlmXyU"
OWNER_ID = 7301067810

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=10)
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

# ✅ /start with better design
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

    welcome_text = (
        f"👋 *Welcome {message.from_user.first_name}!* 🎉\n\n"
        "🤖 I am *Jack The AI Bot*, your smart Telegram assistant!\n\n"
        "✨ *Features:*\n"
        "🗣 Convert Text to Voice\n"
        "👮 Powerful Admin Tools\n"
        "📊 Group & Bot Stats\n"
        "📢 Announcements & Reports\n\n"
        "🔽 *Choose an option below to get started!*"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="Markdown")

# ✅ Help callback
@bot.callback_query_handler(func=lambda c: c.data == "show_help")
def show_help_callback(call):
    send_help(call.message.chat.id)

@bot.message_handler(commands=["help"])
def help_cmd(message):
    send_help(message.chat.id)

def send_help(chat_id):
    help_text = (
        "🤖 *Jack The AI Bot Commands:*\n\n"
        "🗣 /start - Start the bot\n"
        "🗒 /help - Show this help message\n"
        "📊 /botstats - Show bot stats\n"
        "🏓 /ping - Check bot speed\n"
        "👤 /userinfo - Get your info\n"
        "💌 /feedback <msg> - Send feedback to owner\n"
        "🐞 /report <msg> - Report a bug\n\n"
        "👮 *Admin Commands:*\n"
        "/kick (reply) - Kick user\n"
        "/mute <1m|1h|1d> (reply) - Mute user\n"
        "/promote (reply) - Promote to admin\n"
        "/demote (reply) - Remove admin rights\n"
        "/banwords word1, word2 - Ban words in group\n"
        "/leave - Bot leaves the group\n\n"
        "📢 *Owner Only:*\n"
        "/announcement <msg> - DM to all users\n"
        "/setchannel @username - Link a channel\n"
        "/post <msg> - Post to linked channel"
    )
    bot.send_message(chat_id, help_text, parse_mode="Markdown")

# ✅ Welcome / Goodbye messages
@bot.message_handler(content_types=["new_chat_members"])
def welcome_new_member(message):
    for member in message.new_chat_members:
        bot.send_message(
            message.chat.id,
            f"👋 Welcome {member.first_name}! 🎉 Have a great time here!"
        )

@bot.message_handler(content_types=["left_chat_member"])
def goodbye_member(message):
    bot.send_message(
        message.chat.id,
        f"👋 {message.left_chat_member.first_name} has left the group. Goodbye!"
    )

# ✅ Leave command
@bot.message_handler(commands=["leave"])
def leave_cmd(message):
    if not is_admin(message.chat.id, message.from_user.id) and message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "❌ Only admins or owner can make me leave.")
    bot.send_message(message.chat.id, "👋 Goodbye everyone!")
    bot.leave_chat(message.chat.id)

# ✅ Text → Voice
@bot.callback_query_handler(func=lambda c: c.data == "text_to_voice")
def callback_handler(call):
    msg = bot.send_message(call.message.chat.id, "Send me text to convert to voice:")
    bot.register_next_step_handler(msg, convert_text_to_voice)

def convert_text_to_voice(message):
    if not message.text:
        bot.reply_to(message, "❌ Please send text only.")
        return
    tts = gTTS(text=message.text, lang="en")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tts.save(tmp.name)
        bot.send_voice(message.chat.id, open(tmp.name, "rb"))

# ✅ Bot Stats
@bot.message_handler(commands=["botstats"])
def botstats_cmd(message):
    uptime = int(time.time() - START_TIME)
    hours, mins = uptime // 3600, (uptime % 3600) // 60
    text = (
        "📊 *Bot Stats*\n"
        f"👥 Users: {len(data['users'])}\n"
        f"💬 Groups: {len(data['groups'])}\n"
        f"⚠ Warnings: {len(data['warnings'])}\n"
        f"🚫 Ban Words: {sum(len(v) for v in data['ban_words'].values())}\n"
        f"⏳ Uptime: {hours}h {mins}m"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ✅ Ping
@bot.message_handler(commands=["ping"])
def ping_cmd(message):
    start = time.time()
    sent = bot.send_message(message.chat.id, "🏓 Pinging...")
    bot.edit_message_text(f"🏓 Pong! {round((time.time()-start)*1000)}ms", message.chat.id, sent.message_id)

# ✅ User Info
@bot.message_handler(commands=["userinfo"])
def userinfo_cmd(message):
    user = message.from_user
    bot.send_message(
        message.chat.id,
        f"👤 *User Info*\n🆔 ID: {user.id}\n📛 Name: {user.first_name}\n🔗 Username: @{user.username or 'None'}",
        parse_mode="Markdown"
    )

# ✅ Feedback & Report
@bot.message_handler(commands=["feedback"])
def feedback_cmd(message):
    msg = message.text.replace("/feedback", "").strip()
    if msg:
        bot.send_message(OWNER_ID, f"💌 Feedback from {message.from_user.id}:\n{msg}")
        bot.reply_to(message, "✅ Feedback sent!")
    else:
        bot.reply_to(message, "Usage: /feedback <message>")

@bot.message_handler(commands=["report"])
def report_cmd(message):
    msg = message.text.replace("/report", "").strip()
    if msg:
        bot.send_message(OWNER_ID, f"🐞 Bug report from {message.from_user.id}:\n{msg}")
        bot.reply_to(message, "✅ Report sent!")
    else:
        bot.reply_to(message, "Usage: /report <message>")

# ✅ Announcement (Owner Only)
@bot.message_handler(commands=["announcement"])
def announcement_cmd(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "❌ Owner only.")
    text = message.text.replace("/announcement", "").strip()
    if not text:
        return bot.reply_to(message, "Usage: /announcement <message>")
    for user_id in data["users"]:
        try:
            bot.send_message(user_id, f"📢 Announcement:\n{text}")
        except:
            pass
    bot.reply_to(message, "✅ Announcement sent to all users!")

# ✅ Channel Commands
@bot.message_handler(commands=["setchannel"])
def setchannel_cmd(message):
    if message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "❌ Only owner can set channel.")
    parts = message.text.split()
    if len(parts) < 2:
        return bot.reply_to(message, "Usage: /setchannel @channelusername")
    data["channel"] = parts[1]
    save_data()
    bot.reply_to(message, f"✅ Channel set to {parts[1]}")

@bot.message_handler(commands=["post"])
def post_cmd(message):
    if not data.get("channel"):
        return bot.reply_to(message, "❌ No channel linked. Use /setchannel first.")
    if not is_admin(message.chat.id, message.from_user.id) and message.from_user.id != OWNER_ID:
        return bot.reply_to(message, "❌ Only admins or owner can post.")
    msg = message.text.replace("/post", "").strip()
    if msg:
        bot.send_message(data["channel"], msg)
        bot.reply_to(message, "✅ Posted to channel!")
    else:
        bot.reply_to(message, "Usage: /post <message>")

# ✅ Kick / Mute / Promote / Demote
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
    times = {"1m": 60, "1h": 3600, "1d": 86400}
    if len(parts) < 2 or parts[1] not in times:
        return bot.reply_to(message, "Usage: /mute <1m|1h|1d>")
    bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, until_date=int(time.time())+times[parts[1]])
    bot.send_message(message.chat.id, f"✅ User muted for {parts[1]}")

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

# ✅ Ban Words
@bot.message_handler(commands=["banwords"])
def set_ban_words(message):
    if not is_admin(message.chat.id, message.from_user.id):
        return bot.reply_to(message, "❌ Admins only.")
    words = message.text.replace("/banwords", "").strip().split(",")
    data["ban_words"][str(message.chat.id)] = [w.strip().lower() for w in words if w.strip()]
    save_data()
    bot.reply_to(message, f"✅ Ban words set: {', '.join(data['ban_words'][str(message.chat.id)])}")

@bot.message_handler(func=lambda m: True)
def check_ban_words(message):
    chat_ban_words = data["ban_words"].get(str(message.chat.id), [])
    for w in chat_ban_words:
        if message.text and re.search(rf"\b{re.escape(w)}\b", message.text.lower()):
            try:
                bot.delete_message(message.chat.id, message.message_id)
                key = f"{message.chat.id}:{message.from_user.id}"
                data["warnings"][key] = data["warnings"].get(key, 0) + 1
                save_data()
            except:
                pass
            return

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url="https://jack-the-ai.onrender.com/" + TOKEN)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

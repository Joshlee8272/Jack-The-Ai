import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from gtts import gTTS
import tempfile, re, time
from flask import Flask, request
import os

# ✅ Your bot token
TOKEN = "8369185267:AAGV7CPcWM0UBR7xiEGIpz4btLr4QGlmXyU"
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=10)
app = Flask(__name__)

ban_words = {}  # Stores banned words per chat
warnings = {}   # Stores warning count per user

def is_admin(chat_id, user_id):
    """Check if user is an admin in the chat"""
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

# ✅ Start command with buttons
@bot.message_handler(commands=["start"])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🗣 Text To Voice", callback_data="text_to_voice"))
    markup.add(InlineKeyboardButton("⚙ Customize Channel", callback_data="customize_channel"))
    bot.send_message(message.chat.id, "Welcome! Choose an option:", reply_markup=markup)

# ✅ Handle button clicks
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "text_to_voice":
        msg = bot.send_message(call.message.chat.id, "Send me text to convert to voice:")
        bot.register_next_step_handler(msg, convert_text_to_voice)
    elif call.data == "customize_channel":
        bot.send_message(call.message.chat.id, "Please add me to your discussion group as admin.")

# ✅ Convert text to voice
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

# ✅ Warning system for ban words
def warn_user(chat_id, user_id, username):
    key = f"{chat_id}:{user_id}"
    warnings[key] = warnings.get(key, 0) + 1
    count = warnings[key]

    penalties = {1: 60, 2: 3600, 3: 86400}  # mute times
    if count <= 3:
        duration = penalties[count]
        try:
            bot.restrict_chat_member(chat_id, user_id, until_date=int(time.time()) + duration)
            bot.send_message(chat_id, f"⚠ Warning {count}/4 for {username}. Muted for {duration}s.")
        except:
            bot.send_message(chat_id, f"⚠ Warning {count}/4 for {username}.")
    else:
        try:
            bot.kick_chat_member(chat_id, user_id)
            bot.send_message(chat_id, f"🚫 {username} has been kicked for repeated ban words.")
        except:
            bot.send_message(chat_id, f"⚠ Could not kick {username}.")

# ✅ Command to set ban words
@bot.message_handler(commands=["banwords"])
def set_ban_words(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Only admins can set ban words.")
        return
    words = message.text.replace("/banwords", "").strip().split(",")
    ban_words[message.chat.id] = [w.strip().lower() for w in words if w.strip()]
    bot.reply_to(message, f"✅ Ban words set: {', '.join(ban_words[message.chat.id])}")

# ✅ Check messages for ban words
@bot.message_handler(func=lambda m: True)
def check_ban_words(message):
    if message.chat.id in ban_words:
        for w in ban_words[message.chat.id]:
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

import logging
import sqlite3
from dotenv import load_dotenv
import os

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton
)

from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext
)

# --------------------
# LOAD ENV
# --------------------

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# --------------------
# LOGGING
# --------------------

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# --------------------
# DATABASE
# --------------------

conn = sqlite3.connect('database.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT
)
''')

conn.commit()

# --------------------
# MEMORY FOR REPLY MODE
# --------------------

reply_targets = {}

# --------------------
# MENU
# --------------------

main_menu = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📋 Menu")],
        [KeyboardButton("📞 Contact Admin")],
        [KeyboardButton("ℹ️ Help")]
    ],
    resize_keyboard=True
)

# --------------------
# SAVE USER
# --------------------

def save_user(user):
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
        (
            user.id,
            user.username,
            user.full_name
        )
    )
    conn.commit()

# --------------------
# START
# --------------------

def start(update: Update, context: CallbackContext):
    user = update.effective_user

    save_user(user)

    text = f"""
🔥 Welcome {user.first_name}

This is your advanced menu bot.

Use the buttons below.
"""

    update.message.reply_text(text, reply_markup=main_menu)

# --------------------
# HELP
# --------------------

def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Use the menu buttons to interact with the bot."
    )

# --------------------
# MENU BUTTONS
# --------------------

def menu_handler(update: Update, context: CallbackContext):
    text = update.message.text
    user = update.effective_user

    save_user(user)

    if text == "📋 Menu":
        update.message.reply_text(
            "📌 Available Options:\n\n"
            "1. Contact Admin\n"
            "2. Get Help\n"
            "3. Broadcast System\n"
        )

    elif text == "📞 Contact Admin":
        update.message.reply_text(
            "✍️ Send your message now. Admin will reply soon."
        )

    elif text == "ℹ️ Help":
        update.message.reply_text(
            "This bot supports menus, broadcasts and admin replies."
        )

# --------------------
# USER MESSAGE -> ADMIN
# --------------------

def forward_to_admin(update: Update, context: CallbackContext):
    user = update.effective_user
    message = update.message.text

    save_user(user)

    # Skip admin commands
    if message.startswith('/'):
        return

    # Ignore menu buttons
    if message in ["📋 Menu", "📞 Contact Admin", "ℹ️ Help"]:
        return

    admin_message = (
        f"📩 New Message\n\n"
        f"👤 Name: {user.full_name}\n"
        f"🆔 ID: {user.id}\n"
        f"📛 Username: @{user.username}\n\n"
        f"💬 Message:\n{message}"
    )

    keyboard_text = f"/reply {user.id}"

    context.bot.send_message(
        chat_id=ADMIN_ID,
        text=admin_message + f"\n\nReply using:\n{keyboard_text}"
    )

    update.message.reply_text(
        "✅ Your message was sent to admin."
    )

# --------------------
# BROADCAST
# --------------------

def broadcast(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        update.message.reply_text("❌ Unauthorized")
        return

    if len(context.args) == 0:
        update.message.reply_text(
            "Usage:\n/broadcast Your message"
        )
        return

    message = ' '.join(context.args)

    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    success = 0
    failed = 0

    for user in users:
        try:
            context.bot.send_message(chat_id=user[0], text=message)
            success += 1
        except:
            failed += 1

    update.message.reply_text(
        f"✅ Broadcast Complete\n\n"
        f"Success: {success}\n"
        f"Failed: {failed}"
    )

# --------------------
# REPLY SYSTEM
# --------------------

def reply_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        update.message.reply_text("❌ Unauthorized")
        return

    if len(context.args) < 2:
        update.message.reply_text(
            "Usage:\n/reply USER_ID message"
        )
        return

    target_id = int(context.args[0])
    message = ' '.join(context.args[1:])

    try:
        context.bot.send_message(
            chat_id=target_id,
            text=f"📨 Admin Reply:\n\n{message}"
        )

        update.message.reply_text("✅ Reply sent")

    except Exception as e:
        update.message.reply_text(f"❌ Failed: {e}")

# --------------------
# USERS COUNT
# --------------------

def users(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        update.message.reply_text("❌ Unauthorized")
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]

    update.message.reply_text(
        f"👥 Total Users: {total}"
    )

# --------------------
# ADMIN PANEL
# --------------------

def admin(update: Update, context: CallbackContext):
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        update.message.reply_text("❌ Unauthorized")
        return

    text = """
🛠 Admin Commands

/users - Total users
/broadcast MESSAGE - Send broadcast
/reply USER_ID MESSAGE - Reply user
"""

    update.message.reply_text(text)

# --------------------
# MAIN
# --------------------

def main():
    updater = Updater(BOT_TOKEN, use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("broadcast", broadcast))
    dp.add_handler(CommandHandler("reply", reply_command))
    dp.add_handler(CommandHandler("users", users))
    dp.add_handler(CommandHandler("admin", admin))

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, menu_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, forward_to_admin))

    updater.start_polling()

    print("Bot started...")

    updater.idle()

if __name__ == '__main__':
    main()

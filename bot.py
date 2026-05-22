import logging
import sqlite3
import os

from dotenv import load_dotenv

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# -----------------------
# LOAD ENV
# -----------------------

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# -----------------------
# LOGGING
# -----------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# -----------------------
# DATABASE
# -----------------------

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT
)
""")

conn.commit()

# -----------------------
# SAVE USER
# -----------------------

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

# -----------------------
# MENU
# -----------------------

main_menu = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📋 Menu")],
        [KeyboardButton("📞 Contact Admin")],
        [KeyboardButton("ℹ️ Help")]
    ],
    resize_keyboard=True
)

# -----------------------
# START COMMAND
# -----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    save_user(user)

    text = f"""
🔥 Welcome {user.first_name}

This is your advanced Telegram menu bot.

Use the buttons below.
"""

    await update.message.reply_text(
        text,
        reply_markup=main_menu
    )

# -----------------------
# HELP
# -----------------------

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Use the menu buttons to interact with the bot."
    )

# -----------------------
# ADMIN PANEL
# -----------------------

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return

    text = """
🛠 Admin Panel

/users - Total users
/broadcast MESSAGE - Broadcast to users
/reply USER_ID MESSAGE - Reply to user
"""

    await update.message.reply_text(text)

# -----------------------
# USERS COUNT
# -----------------------

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]

    await update.message.reply_text(
        f"👥 Total Users: {total}"
    )

# -----------------------
# BROADCAST
# -----------------------

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return

    if len(context.args) == 0:
        await update.message.reply_text(
            "Usage:\n/broadcast your message"
        )
        return

    message = " ".join(context.args)

    cursor.execute("SELECT user_id FROM users")
    all_users = cursor.fetchall()

    success = 0
    failed = 0

    for user in all_users:
        try:
            await context.bot.send_message(
                chat_id=user[0],
                text=message
            )
            success += 1

        except:
            failed += 1

    await update.message.reply_text(
        f"""
✅ Broadcast Complete

Success: {success}
Failed: {failed}
"""
    )

# -----------------------
# REPLY COMMAND
# -----------------------

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage:\n/reply USER_ID message"
        )
        return

    target_id = int(context.args[0])

    message = " ".join(context.args[1:])

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"📨 Admin Reply:\n\n{message}"
        )

        await update.message.reply_text("✅ Reply sent")

    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed: {e}"
        )

# -----------------------
# MENU HANDLER
# -----------------------

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📋 Menu":
        await update.message.reply_text(
            """
📌 Available Options

1. Contact Admin
2. Help
3. Broadcast System
"""
        )

    elif text == "📞 Contact Admin":
        await update.message.reply_text(
            "✍️ Send your message now."
        )

    elif text == "ℹ️ Help":
        await update.message.reply_text(
            "This bot supports menus, broadcasts and admin replies."
        )

# -----------------------
# USER MESSAGE TO ADMIN
# -----------------------

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message.text

    save_user(user)

    if message.startswith("/"):
        return

    if message in [
        "📋 Menu",
        "📞 Contact Admin",
        "ℹ️ Help"
    ]:
        return

    admin_text = f"""
📩 New Message

👤 Name: {user.full_name}
🆔 ID: {user.id}
📛 Username: @{user.username}

💬 Message:
{message}

Reply:
 /reply {user.id} your_message
"""

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text
        )

        await update.message.reply_text(
            "✅ Message sent to admin."
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {e}"
        )

# -----------------------
# MAIN
# -----------------------

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # COMMANDS
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("reply", reply))

    # TEXT HANDLERS
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            menu_handler
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            forward_to_admin
        )
    )

    print("Bot is running...")

    app.run_polling()

# -----------------------
# START APP
# -----------------------

if __name__ == "__main__":
    main()

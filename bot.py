"""
Menu Builder Bot - Fixed for Render Deployment
Features: Custom menus, Broadcast, Two-way Admin Chat, User Management
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from threading import Lock
from flask import Flask, request, jsonify

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode

# ==================== CONFIGURATION ====================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8952928835:AAHgMEV7Bbma2sEAqYZ_yUS8M3XClmh8O18")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "157828443") or "0")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://confrontergains.onrender.com")
PORT = int(os.environ.get("PORT", "10000"))

USERS_FILE = "users.json"
MENUS_FILE = "menus.json"
MESSAGES_FILE = "messages.json"
SETTINGS_FILE = "settings.json"

# ==================== DATA STORE ====================

class DataStore:
    def __init__(self):
        self.lock = Lock()
        self.users = self._load(USERS_FILE, {})
        self.menus = self._load(MENUS_FILE, {
            "main": {
                "name": "Main Menu",
                "buttons": [
                    [{"text": "📋 Services", "callback": "menu_services"},
                     {"text": "💰 Pricing", "callback": "menu_pricing"}],
                    [{"text": "📞 Contact", "callback": "menu_contact"},
                     {"text": "❓ Help", "callback": "menu_help"}]
                ],
                "responses": {
                    "menu_services": "🛠 Our Services:\n\n1. Web Development\n2. Bot Development\n3. App Design",
                    "menu_pricing": "💰 Pricing:\n\nBasic: $99/month\nPro: $199/month\nEnterprise: Custom",
                    "menu_contact": "📞 Contact us:\n\n@YourUsername\nEmail: contact@example.com",
                    "menu_help": "❓ Help:\n\nUse the buttons below to navigate. For support, click Chat with Admin"
                }
            }
        })
        self.messages = self._load(MESSAGES_FILE, [])
        self.settings = self._load(SETTINGS_FILE, {
            "start_message": "👋 Welcome! Use the menu below to navigate.",
            "admin_chat_enabled": True,
            "broadcast_enabled": True
        })

    def _load(self, filename, default):
        try:
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
        return default

    def _save(self, filename, data):
        with self.lock:
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Error saving {filename}: {e}")

    def add_user(self, user_id, username, first_name, last_name):
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                "id": user_id,
                "username": username or "",
                "first_name": first_name or "",
                "last_name": last_name or "",
                "joined_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "message_count": 0,
                "blocked": False
            }
            self._save(USERS_FILE, self.users)
            return True
        else:
            self.users[user_id]["last_active"] = datetime.now().isoformat()
            self.users[user_id]["message_count"] = self.users[user_id].get("message_count", 0) + 1
            self._save(USERS_FILE, self.users)
            return False

    def get_user(self, user_id):
        return self.users.get(str(user_id))

    def get_all_users(self):
        return list(self.users.values())

    def get_active_users(self):
        return [u for u in self.users.values() if not u.get("blocked", False)]

    def block_user(self, user_id):
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id]["blocked"] = True
            self._save(USERS_FILE, self.users)

    def unblock_user(self, user_id):
        user_id = str(user_id)
        if user_id in self.users:
            self.users[user_id]["blocked"] = False
            self._save(USERS_FILE, self.users)

    def save_message(self, from_id, to_id, message_text, message_type="text"):
        msg = {
            "id": len(self.messages) + 1,
            "from_id": from_id,
            "to_id": to_id,
            "text": message_text,
            "type": message_type,
            "timestamp": datetime.now().isoformat(),
            "read": False
        }
        self.messages.append(msg)
        self._save(MESSAGES_FILE, self.messages)
        return msg["id"]

    def get_unread_messages(self, user_id):
        return [m for m in self.messages if str(m["to_id"]) == str(user_id) and not m.get("read", False)]

    def mark_read(self, message_id):
        for m in self.messages:
            if m["id"] == message_id:
                m["read"] = True
        self._save(MESSAGES_FILE, self.messages)

db = DataStore()

# ==================== KEYBOARDS ====================

def build_menu_keyboard(menu_id="main", is_admin=False):
    menu = db.menus.get(menu_id, db.menus["main"])
    keyboard = []
    for row in menu.get("buttons", []):
        button_row = []
        for btn in row:
            if btn.get("callback"):
                button_row.append(InlineKeyboardButton(btn["text"], callback_data=btn["callback"]))
            elif btn.get("url"):
                button_row.append(InlineKeyboardButton(btn["text"], url=btn["url"]))
            elif btn.get("web_app"):
                button_row.append(InlineKeyboardButton(btn["text"], web_app=WebAppInfo(url=btn["web_app"])))
        if button_row:
            keyboard.append(button_row)
    if db.settings.get("admin_chat_enabled", True) and not is_admin:
        keyboard.append([InlineKeyboardButton("💬 Chat with Admin", callback_data="start_chat")])
    return InlineKeyboardMarkup(keyboard)

def build_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💬 User Messages", callback_data="admin_messages")],
        [InlineKeyboardButton("👥 Users List", callback_data="admin_users")],
        [InlineKeyboardButton("📝 Edit Menus", callback_data="admin_menus")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")],
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
    ]
    return InlineKeyboardMarkup(keyboard)

def build_back_keyboard(callback="admin_panel"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data=callback)]])

# ==================== HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_new = db.add_user(user.id, user.username, user.first_name, user.last_name)

    if user.id == ADMIN_ID:
        await update.message.reply_text(
            f"👑 *Admin Panel*\n\nWelcome, {user.first_name}!\n\n"
            f"Total users: {len(db.get_all_users())}\n"
            f"New today: {sum(1 for u in db.get_all_users() if u.get('joined_at', '').startswith(datetime.now().strftime('%Y-%m-%d')))}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_admin_keyboard()
        )
        return

    welcome_text = db.settings.get("start_message", "👋 Welcome! Use the menu below to navigate.")
    if is_new:
        welcome_text += "\n\n🎉 You are now subscribed to updates!"

    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_menu_keyboard()
    )

    if is_new and ADMIN_ID:
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🆕 *New User!*\n\n"
                f"Name: {user.first_name} {user.last_name or ''}\n"
                f"Username: @{user.username or 'N/A'}\n"
                f"ID: `{user.id}`",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *Bot Help*\n\n"
        "This bot provides an interactive menu system.\n\n"
        "*User Commands:*\n"
        "/start - Start the bot\n"
        "/help - Show this help\n"
        "💬 Chat with Admin - Send messages to admin\n\n"
        "*Admin Commands:*\n"
        "/admin - Open admin panel\n"
        "/stats - Show bot statistics\n"
        "/users - List all users"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ You are not authorized.")
        return
    await update.message.reply_text("👑 *Admin Panel*", parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_keyboard())

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = db.get_all_users()
    total = len(users)
    today = datetime.now().strftime("%Y-%m-%d")
    new_today = sum(1 for u in users if u.get("joined_at", "").startswith(today))
    active = len(db.get_active_users())
    blocked = total - active
    stats_text = (
        f"📊 *Bot Statistics*\n\n"
        f"👥 Total Users: {total}\n"
        f"✅ Active: {active}\n"
        f"🚫 Blocked: {blocked}\n"
        f"🆕 New Today: {new_today}\n"
        f"📨 Total Messages: {len(db.messages)}"
    )
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    users = db.get_all_users()
    if not users:
        await update.message.reply_text("No users yet.")
        return
    text = "👥 *Users List* (showing last 50):\n\n"
    for user in users[-50:]:
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        username = f"@{user.get('username')}" if user.get("username") else "No username"
        status = "🚫" if user.get("blocked") else "✅"
        text += f"{status} `{user['id']}` - {name} ({username})\n"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("✅ Cancelled. Use /start to see the menu.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "admin_panel":
        await query.edit_message_text("👑 *Admin Panel*", parse_mode=ParseMode.MARKDOWN, reply_markup=build_admin_keyboard())
        return

    if data == "admin_broadcast":
        if not db.settings.get("broadcast_enabled", True):
            await query.answer("Broadcast is disabled!", show_alert=True)
            return
        await query.edit_message_text(
            "📢 *Broadcast Message*\n\nSend me the message you want to broadcast to all users.\nYou can use text, photos, videos, or documents.\n\nType /cancel to abort.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_back_keyboard()
        )
        context.user_data["awaiting_broadcast"] = True
        return

    if data == "admin_messages":
        unread = db.get_unread_messages(ADMIN_ID)
        if not unread:
            await query.edit_message_text("📭 No new messages from users.", reply_markup=build_back_keyboard())
            return
        text = "💬 *Recent Messages:*\n\n"
        for msg in unread[-10:]:
            user = db.get_user(msg["from_id"])
            name = user["first_name"] if user else f"User {msg['from_id']}"
            text += f"From: {name} (`{msg['from_id']}`)\n📝 {msg['text'][:100]}...\n[Reply](tg://user?id={msg['from_id']})\n\n"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data == "admin_users":
        users = db.get_all_users()
        text = f"👥 *Total Users: {len(users)}*\n\n"
        for user in users[-20:]:
            name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            text += f"• `{user['id']}` - {name}\n"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data == "admin_menus":
        text = "📝 *Menu Editor*\n\nCurrent menus:\n"
        for menu_id, menu in db.menus.items():
            text += f"• {menu['name']} (`{menu_id}`)\n"
        keyboard = [
            [InlineKeyboardButton("➕ Add Menu", callback_data="menu_add")],
            [InlineKeyboardButton("◀️ Back", callback_data="admin_panel")]
        ]
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "admin_settings":
        settings_text = (
            "⚙️ *Bot Settings*\n\n"
            f"Admin Chat: {'✅' if db.settings.get('admin_chat_enabled') else '❌'}\n"
            f"Broadcast: {'✅' if db.settings.get('broadcast_enabled') else '❌'}\n\n"
            "Toggle settings below:"
        )
        keyboard = [
            [InlineKeyboardButton("Toggle Admin Chat", callback_data="toggle_chat")],
            [InlineKeyboardButton("Toggle Broadcast", callback_data="toggle_broadcast")],
            [InlineKeyboardButton("Set Start Message", callback_data="set_start")],
            [InlineKeyboardButton("◀️ Back", callback_data="admin_panel")]
        ]
        await query.edit_message_text(settings_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "admin_stats":
        users = db.get_all_users()
        total = len(users)
        today = datetime.now().strftime("%Y-%m-%d")
        new_today = sum(1 for u in users if u.get("joined_at", "").startswith(today))
        stats_text = f"📊 *Statistics*\n\n👥 Total Users: {total}\n🆕 New Today: {new_today}\n📨 Messages: {len(db.messages)}"
        await query.edit_message_text(stats_text, parse_mode=ParseMode.MARKDOWN, reply_markup=build_back_keyboard())
        return

    if data == "toggle_chat":
        db.settings["admin_chat_enabled"] = not db.settings.get("admin_chat_enabled", True)
        db._save(SETTINGS_FILE, db.settings)
        await query.answer("Admin chat toggled!")
        await query.edit_message_text(
            "⚙️ *Bot Settings*\n\n"
            f"Admin Chat: {'✅' if db.settings.get('admin_chat_enabled') else '❌'}\n"
            f"Broadcast: {'✅' if db.settings.get('broadcast_enabled') else '❌'}\n\n"
            "Toggle settings below:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Toggle Admin Chat", callback_data="toggle_chat")],
                [InlineKeyboardButton("Toggle Broadcast", callback_data="toggle_broadcast")],
                [InlineKeyboardButton("Set Start Message", callback_data="set_start")],
                [InlineKeyboardButton("◀️ Back", callback_data="admin_panel")]
            ])
        )
        return

    if data == "toggle_broadcast":
        db.settings["broadcast_enabled"] = not db.settings.get("broadcast_enabled", True)
        db._save(SETTINGS_FILE, db.settings)
        await query.answer("Broadcast toggled!")
        await query.edit_message_text(
            "⚙️ *Bot Settings*\n\n"
            f"Admin Chat: {'✅' if db.settings.get('admin_chat_enabled') else '❌'}\n"
            f"Broadcast: {'✅' if db.settings.get('broadcast_enabled') else '❌'}\n\n"
            "Toggle settings below:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Toggle Admin Chat", callback_data="toggle_chat")],
                [InlineKeyboardButton("Toggle Broadcast", callback_data="toggle_broadcast")],
                [InlineKeyboardButton("Set Start Message", callback_data="set_start")],
                [InlineKeyboardButton("◀️ Back", callback_data="admin_panel")]
            ])
        )
        return

    if data == "set_start":
        await query.edit_message_text(
            "📝 Send me the new start message. Use {first_name} for user's name.\nType /cancel to abort.",
            reply_markup=build_back_keyboard()
        )
        context.user_data["awaiting_start_msg"] = True
        return

    if data == "start_chat":
        if not db.settings.get("admin_chat_enabled", True):
            await query.answer("Chat is currently unavailable.", show_alert=True)
            return
        await query.edit_message_text(
            "💬 *Chat with Admin*\n\nSend your message now. The admin will reply shortly.\nType /cancel to end the chat.",
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["in_chat"] = True
        return

    menu = db.menus.get("main")
    if menu and data in menu.get("responses", {}):
        response_text = menu["responses"][data]
        await query.edit_message_text(
            response_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back to Menu", callback_data="back_to_menu")]])
        )
        return

    if data == "back_to_menu":
        await query.edit_message_text(
            db.settings.get("start_message", "👋 Welcome! Use the menu below to navigate."),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_menu_keyboard()
        )
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message
    db.add_user(user.id, user.username, user.first_name, user.last_name)

    if context.user_data.get("awaiting_broadcast") and user.id == ADMIN_ID:
        context.user_data["awaiting_broadcast"] = False
        context.user_data["broadcast_content"] = {
            "text": message.text,
            "photo": message.photo[-1].file_id if message.photo else None,
            "video": message.video.file_id if message.video else None,
            "document": message.document.file_id if message.document else None,
            "caption": message.caption
        }
        preview_text = "📢 *Broadcast Preview:*\n\n"
        if message.text:
            preview_text += message.text[:500]
        elif message.caption:
            preview_text += message.caption[:500]
        keyboard = [
            [InlineKeyboardButton("✅ Send to All", callback_data="confirm_broadcast")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")]
        ]
        await message.reply_text(preview_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if context.user_data.get("awaiting_start_msg") and user.id == ADMIN_ID:
        context.user_data["awaiting_start_msg"] = False
        db.settings["start_message"] = message.text
        db._save(SETTINGS_FILE, db.settings)
        await message.reply_text("✅ Start message updated!")
        return

    if context.user_data.get("in_chat") and user.id != ADMIN_ID:
        msg_id = db.save_message(user.id, ADMIN_ID, message.text or message.caption or "[Media]")
        try:
            forward_text = (
                f"💬 *New Message from User*\n\n"
                f"From: {user.first_name} {user.last_name or ''}\n"
                f"ID: `{user.id}`\n"
                f"Username: @{user.username or 'N/A'}\n\n"
                f"📝 {message.text or message.caption or '[Media]'}"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Reply", callback_data=f"reply_{user.id}")],
                [InlineKeyboardButton("🚫 Block", callback_data=f"block_{user.id}")]
            ])
            if message.photo:
                await context.bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=forward_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            elif message.video:
                await context.bot.send_video(ADMIN_ID, message.video.file_id, caption=forward_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            elif message.document:
                await context.bot.send_document(ADMIN_ID, message.document.file_id, caption=forward_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            else:
                await context.bot.send_message(ADMIN_ID, forward_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
            await message.reply_text("✅ Message sent to admin! They will reply soon.")
        except Exception as e:
            logger.error(f"Failed to forward message: {e}")
            await message.reply_text("❌ Failed to send message. Please try again later.")
        return

    if context.user_data.get("replying_to") and user.id == ADMIN_ID:
        target_id = context.user_data["replying_to"]
        context.user_data["replying_to"] = None
        try:
            if message.text:
                await context.bot.send_message(target_id, f"📨 *Admin Reply:*\n\n{message.text}", parse_mode=ParseMode.MARKDOWN)
            elif message.photo:
                await context.bot.send_photo(target_id, message.photo[-1].file_id, caption=message.caption)
            elif message.video:
                await context.bot.send_video(target_id, message.video.file_id, caption=message.caption)
            elif message.document:
                await context.bot.send_document(target_id, message.document.file_id, caption=message.caption)
            db.save_message(ADMIN_ID, target_id, message.text or message.caption or "[Media]")
            await message.reply_text(f"✅ Reply sent to user `{target_id}`", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Failed to reply: {e}")
            await message.reply_text("❌ Failed to send reply. User may have blocked the bot.")
        return

    await message.reply_text(
        db.settings.get("start_message", "👋 Welcome! Use the menu below to navigate."),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=build_menu_keyboard()
    )

async def handle_broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel_broadcast":
        context.user_data["broadcast_content"] = None
        await query.edit_message_text("❌ Broadcast cancelled.")
        return

    if data == "confirm_broadcast":
        content = context.user_data.get("broadcast_content", {})
        if not content:
            await query.edit_message_text("❌ No broadcast content found.")
            return
        users = db.get_active_users()
        sent = 0
        failed = 0
        status_msg = await query.edit_message_text(f"📢 Broadcasting to {len(users)} users...")
        for user in users:
            try:
                user_id = int(user["id"])
                if content.get("photo"):
                    await context.bot.send_photo(user_id, content["photo"], caption=content.get("caption"))
                elif content.get("video"):
                    await context.bot.send_video(user_id, content["video"], caption=content.get("caption"))
                elif content.get("document"):
                    await context.bot.send_document(user_id, content["document"], caption=content.get("caption"))
                elif content.get("text"):
                    await context.bot.send_message(user_id, content["text"])
                sent += 1
                if sent % 20 == 0:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Failed to send to {user['id']}: {e}")
                failed += 1
                if "blocked" in str(e).lower():
                    db.block_user(user["id"])
        await status_msg.edit_text(f"✅ *Broadcast Complete!*\n\n📤 Sent: {sent}\n❌ Failed: {failed}", parse_mode=ParseMode.MARKDOWN)
        context.user_data["broadcast_content"] = None

async def handle_admin_reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("reply_"):
        target_id = int(data.split("_")[1])
        context.user_data["replying_to"] = target_id
        await query.edit_message_text(f"✏️ Replying to user `{target_id}`.\nSend your message now. Type /cancel to abort.", parse_mode=ParseMode.MARKDOWN)
        return

    if data.startswith("block_"):
        target_id = data.split("_")[1]
        db.block_user(target_id)
        await query.edit_message_text(f"🚫 User `{target_id}` has been blocked.", parse_mode=ParseMode.MARKDOWN)
        return

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("❌ An error occurred. Please try again.")

# ==================== FLASK + WEBHOOK ====================

flask_app = Flask(__name__)

application = Application.builder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("admin", admin_command))
application.add_handler(CommandHandler("stats", stats_command))
application.add_handler(CommandHandler("users", users_command))
application.add_handler(CommandHandler("cancel", cancel_command))

application.add_handler(CallbackQueryHandler(button_callback, pattern="^(?!reply_|block_|confirm_broadcast|cancel_broadcast).*"))
application.add_handler(CallbackQueryHandler(handle_broadcast_confirm, pattern="^(confirm_broadcast|cancel_broadcast)$"))
application.add_handler(CallbackQueryHandler(handle_admin_reply_callback, pattern="^(reply_|block_).*"))

application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_message))

application.add_error_handler(error_handler)

@flask_app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "running",
        "bot": "Menu Builder Bot",
        "users": len(db.get_all_users()),
        "timestamp": datetime.now().isoformat()
    })

@flask_app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), application.update_queue._loop)
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Error", 500

async def setup_webhook():
    webhook_url = f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}"
    await application.bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook set to: {webhook_url}")

# ==================== MAIN ====================

if __name__ == "__main__":
    import sys

    if "--polling" in sys.argv:
        print("Starting in polling mode...")
        application.run_polling()
    else:
        print("Starting in webhook mode...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(application.initialize())
        loop.run_until_complete(application.start())
        loop.run_until_complete(setup_webhook())

        flask_app.run(host="0.0.0.0", port=PORT)

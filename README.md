# Menu Builder Bot

A full-featured Telegram bot with custom menus, broadcasting, and two-way admin chat.

## Features

- **Custom Menus**: Create interactive button menus with custom responses
- **Broadcast**: Send messages to all users who started the bot
- **Two-Way Chat**: Users can chat with admin, admin can reply directly
- **User Management**: Track users, block/unblock, view statistics
- **Admin Panel**: Web-based admin controls via Telegram

## Setup on Render

### 1. Create a Telegram Bot
- Message [@BotFather](https://t.me/BotFather) on Telegram
- Create a new bot and copy the API token

### 2. Get Your User ID
- Message [@userinfobot](https://t.me/userinfobot) on Telegram
- Copy your numeric User ID

### 3. Deploy on Render

#### Option A: Using Render Dashboard
1. Fork this repo or create a new one with these files
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click "New Web Service"
4. Connect your GitHub repo
5. Set environment variables:
   - `BOT_TOKEN`: Your bot token from BotFather
   - `ADMIN_ID`: Your Telegram user ID
   - `WEBHOOK_URL`: Your Render service URL (e.g., `https://menu-bot.onrender.com`)
6. Deploy!

#### Option B: Using render.yaml (Blueprint)
1. Push code to GitHub with `render.yaml`
2. Go to [Render Blueprints](https://dashboard.render.com/blueprints)
3. Connect your repo and deploy

### 4. Set Webhook
After deployment, visit:

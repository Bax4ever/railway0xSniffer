import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder
from bot.handlers import set_bot_commands, register_handlers
from db import init_db
from hypercorn.asyncio import serve
from hypercorn.config import Config
from bot.config import TRACKADEMYBOT

app = Flask(__name__)

# Create Telegram app
application = ApplicationBuilder().token(TRACKADEMYBOT).build()

# Setup database and handlers
init_db()
register_handlers(application)

# Webhook endpoint for Telegram
@app.route('/webhook', methods=['POST'])
async def webhook():
    try:
        data = request.get_json(force=True)
        print("📩 Incoming Telegram data:", data)
        
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return 'OK'
        
    except Exception as e:
        print("❌ Error in webhook:", str(e))
        return 'ERROR', 500

async def main():
    public_url = os.getenv("RAILWAY_PUBLIC_URL")  # Set this in Railway env vars
    await application.initialize()
    await application.bot.set_webhook(f"{public_url}/webhook")
    await set_bot_commands(application)
    await application.start()

    config = Config()
    config.bind = ["0.0.0.0:8080"]  # Railway requires 0.0.0.0
    await serve(app, config)

if __name__ == "__main__":
    asyncio.run(main())

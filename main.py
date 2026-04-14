import os
import logging
import threading
from http.server import HTTPServer

from telegram import BotCommand
from telegram.ext import ApplicationBuilder

from db import init_db
from bot_handlers import register_handlers
from dashboard import handler as dashboard_handler

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
PORT = int(os.environ.get("PORT", 5000))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.WARNING,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def run_dashboard():
    server = HTTPServer(("0.0.0.0", PORT), dashboard_handler)
    print(f"Dashboard running on port {PORT}")
    server.serve_forever()


async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("start", "📋 បើកម៉ឺនុយចម្បង"),
        BotCommand("language", "🌐 ជ្រើសរើសភាសាបកប្រែ"),
    ])


def main():
    init_db()

    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()

    print("Starting Telegram bot with long polling...")
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    register_handlers(app)
    app.run_polling(allowed_updates=[
        "message",
        "edited_message",
        "callback_query",
        "business_connection",
        "business_message",
        "edited_business_message",
        "deleted_business_messages",
    ])


if __name__ == "__main__":
    main()

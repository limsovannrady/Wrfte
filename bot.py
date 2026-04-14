import logging
import os

from telegram import Update, constants
from telegram.ext import (
    ApplicationBuilder,
    BusinessConnectionHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return

    await context.bot.send_chat_action(message.chat_id, constants.ChatAction.TYPING)
    await context.bot.send_message(
        chat_id=message.chat_id,
        text=f"សួស្តី {update.effective_user.first_name}",
        business_connection_id=getattr(message, "business_connection_id", None),
    )


async def business_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    connection = update.business_connection
    if not connection:
        return

    logger.info(
        "Business connection %s for user_chat_id=%s enabled=%s",
        connection.id,
        connection.user_chat_id,
        connection.is_enabled,
    )

    if connection.is_enabled:
        await context.bot.send_message(
            chat_id=connection.user_chat_id,
            text="Bot connected to your Telegram Business account.",
            business_connection_id=connection.id,
        )


async def business_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.business_message or update.edited_business_message
    if not message or not message.text:
        return

    await context.bot.send_chat_action(
        chat_id=message.chat_id,
        action=constants.ChatAction.TYPING,
        business_connection_id=message.business_connection_id,
    )

    if message.text.startswith("/start"):
        reply = "សួស្តី! Bot is ready for this Telegram Business chat."
    else:
        reply = "សួស្តី! ខ្ញុំបានទទួលសាររបស់អ្នកហើយ។ Our team will reply soon."

    await context.bot.send_message(
        chat_id=message.chat_id,
        text=reply,
        business_connection_id=message.business_connection_id,
    )

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(BusinessConnectionHandler(business_connection))
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.UpdateType.BUSINESS_MESSAGE & filters.TEXT, business_message))
app.add_handler(MessageHandler(filters.UpdateType.EDITED_BUSINESS_MESSAGE & filters.TEXT, business_message))
app.run_polling(allowed_updates=Update.ALL_TYPES)

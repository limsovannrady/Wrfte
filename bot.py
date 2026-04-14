import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import (
    ApplicationBuilder,
    BusinessConnectionHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    TypeHandler,
)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
BUSINESS_OWNER_USER_IDS = {}


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📦 ផលិតផល", callback_data="menu_products"),
            InlineKeyboardButton("💰 តម្លៃ", callback_data="menu_price"),
        ],
        [
            InlineKeyboardButton("📞 ទំនាក់ទំនង", callback_data="menu_contact"),
            InlineKeyboardButton("🕐 ម៉ោងបម្រើ", callback_data="menu_hours"),
        ],
        [
            InlineKeyboardButton("📍 ទីតាំង", callback_data="menu_location"),
            InlineKeyboardButton("❓ ជំនួយ", callback_data="menu_help"),
        ],
    ])


def direct_messages_topic_id(message):
    topic = getattr(message, "direct_messages_topic", None)
    return getattr(topic, "topic_id", None)


async def get_business_owner_user_id(business_connection_id, context: ContextTypes.DEFAULT_TYPE):
    if not business_connection_id:
        return None

    if business_connection_id not in BUSINESS_OWNER_USER_IDS:
        connection = await context.bot.get_business_connection(business_connection_id)
        BUSINESS_OWNER_USER_IDS[business_connection_id] = connection.user.id

    return BUSINESS_OWNER_USER_IDS[business_connection_id]


async def is_business_owner_message(message, context: ContextTypes.DEFAULT_TYPE):
    business_connection_id = getattr(message, "business_connection_id", None)
    sender = getattr(message, "from_user", None)
    if not business_connection_id or not sender:
        return False

    if getattr(sender, "is_bot", False):
        logger.info("Skipping business message from a bot sender user_id=%s", sender.id)
        return True

    try:
        owner_user_id = await get_business_owner_user_id(business_connection_id, context)
    except Exception:
        logger.exception("Could not check business connection owner")
        return False

    if sender.id == owner_user_id:
        logger.info(
            "Skipping business owner message user_id=%s business_connection_id=%s",
            sender.id,
            business_connection_id,
        )
        return True

    return False


async def log_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_type = "unknown"
    message = None

    if update.business_connection:
        update_type = "business_connection"
    elif update.business_message:
        update_type = "business_message"
        message = update.business_message
    elif update.edited_business_message:
        update_type = "edited_business_message"
        message = update.edited_business_message
    elif update.deleted_business_messages:
        update_type = "deleted_business_messages"
    elif update.message:
        update_type = "message"
        message = update.message

    logger.info(
        "Received update type=%s chat_id=%s from_user_id=%s business_connection_id=%s direct_topic_id=%s",
        update_type,
        getattr(message, "chat_id", None),
        getattr(getattr(message, "from_user", None), "id", None),
        getattr(message, "business_connection_id", None),
        direct_messages_topic_id(message) if message else None,
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Telegram handler failed", exc_info=context.error)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return

    if await is_business_owner_message(message, context):
        return

    first_name = update.effective_user.first_name if update.effective_user else "បង"
    await context.bot.send_chat_action(message.chat_id, constants.ChatAction.TYPING)
    await context.bot.send_message(
        chat_id=message.chat_id,
        text=(
            f"សួស្តី {first_name}! 👋\n\n"
            "ស្វាគមន៍មកកាន់សេវាកម្មរបស់យើង។\n"
            "សូមជ្រើសរើសពីម៉ឺនុយខាងក្រោម៖"
        ),
        business_connection_id=getattr(message, "business_connection_id", None),
        direct_messages_topic_id=direct_messages_topic_id(message),
        reply_markup=main_menu_keyboard(),
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    responses = {
        "menu_products": (
            "📦 *ផលិតផលរបស់យើង*\n\n"
            "យើងមានផលិតផលជាច្រើនប្រភេទ។\n"
            "សូមទំនាក់ទំនងមកកាន់ក្រុមការងាររបស់យើង ដើម្បីទទួលបានព័ត៌មានលម្អិត។"
        ),
        "menu_price": (
            "💰 *តម្លៃ*\n\n"
            "តម្លៃអាស្រ័យលើប្រភេទផលិតផល និងបរិមាណ។\n"
            "សូមទំនាក់ទំនងដើម្បីទទួលបានតម្លៃត្រឹមត្រូវ។"
        ),
        "menu_contact": (
            "📞 *ទំនាក់ទំនង*\n\n"
            "📱 លេខទូរស័ព្ទ: +855 XX XXX XXX\n"
            "📧 អ៊ីម៉ែល: info@example.com\n"
            "🌐 វេបសាយ: www.example.com"
        ),
        "menu_hours": (
            "🕐 *ម៉ោងបម្រើការ*\n\n"
            "ច័ន្ទ - សុក្រ: 8:00 - 17:00\n"
            "សៅរ៍: 8:00 - 12:00\n"
            "អាទិត្យ: បិទ"
        ),
        "menu_location": (
            "📍 *ទីតាំង*\n\n"
            "រាជធានីភ្នំពេញ, កម្ពុជា\n\n"
            "សូមទំនាក់ទំនងដើម្បីទទួលបានទីតាំងត្រឹមត្រូវ។"
        ),
        "menu_help": (
            "❓ *ជំនួយ*\n\n"
            "ប្រសិនបើអ្នកមានសំណួរ សូមផ្ញើសាររបស់អ្នក "
            "ហើយក្រុមការងាររបស់យើងនឹងឆ្លើយតបឱ្យបានឆាប់រហ័ស។"
        ),
    }

    data = query.data
    reply_text = responses.get(data, "សូមជ្រើសរើសពីម៉ឺនុយ។")

    await query.edit_message_text(
        text=reply_text,
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 ត្រឡប់ក្រោយ", callback_data="menu_back")]
        ]),
    )


async def button_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    first_name = query.from_user.first_name if query.from_user else "បង"
    await query.edit_message_text(
        text=(
            f"សួស្តី {first_name}! 👋\n\n"
            "ស្វាគមន៍មកកាន់សេវាកម្មរបស់យើង។\n"
            "សូមជ្រើសរើសពីម៉ឺនុយខាងក្រោម៖"
        ),
        reply_markup=main_menu_keyboard(),
    )


async def business_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    connection = update.business_connection
    if not connection:
        return

    logger.info(
        "Business connection %s for user_id=%s user_chat_id=%s enabled=%s",
        connection.id,
        connection.user.id,
        connection.user_chat_id,
        connection.is_enabled,
    )
    BUSINESS_OWNER_USER_IDS[connection.id] = connection.user.id

    if connection.is_enabled:
        logger.info("Business connection is enabled and ready to receive customer messages")


async def business_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.business_message or update.edited_business_message
    if not message:
        return

    text = message.text or message.caption or ""
    topic_id = direct_messages_topic_id(message)

    if await is_business_owner_message(message, context):
        return

    await context.bot.send_chat_action(
        chat_id=message.chat_id,
        action=constants.ChatAction.TYPING,
        business_connection_id=message.business_connection_id,
    )

    first_name = getattr(message.from_user, "first_name", "") or ""
    last_name = getattr(message.from_user, "last_name", "") or ""
    full_name = f"{first_name} {last_name}".strip() or "បង"

    if text.startswith("/start"):
        reply = f"សួស្តី {full_name}! Bot កំពុងដំណើរការ។"
    elif text:
        reply = (
            f"សួស្តីបង {last_name or first_name}! 👋\n\n"
            "សូមជ្រើសរើសពីម៉ឺនុយខាងក្រោម ដើម្បីទទួលបានជំនួយ៖"
        )
    else:
        reply = "សួស្តី! ខ្ញុំបានទទួល message របស់អ្នកហើយ។ Our team will reply soon."

    await context.bot.send_message(
        chat_id=message.chat_id,
        text=reply,
        business_connection_id=message.business_connection_id,
        direct_messages_topic_id=topic_id,
        reply_markup=main_menu_keyboard(),
    )


async def business_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.business_message or update.edited_business_message:
        await business_message(update, context)
    elif update.deleted_business_messages:
        deleted = update.deleted_business_messages
        logger.info(
            "Business messages deleted business_connection_id=%s chat_id=%s message_ids=%s",
            deleted.business_connection_id,
            deleted.chat.id,
            list(deleted.message_ids),
        )


app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(TypeHandler(Update, log_update), group=-1)
app.add_handler(BusinessConnectionHandler(business_connection))
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_back_callback, pattern="^menu_back$"))
app.add_handler(CallbackQueryHandler(button_callback, pattern="^menu_"))
app.add_handler(TypeHandler(Update, business_update), group=1)
app.add_error_handler(error_handler)
app.run_polling(allowed_updates=Update.ALL_TYPES)

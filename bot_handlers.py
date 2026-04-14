import logging
import qrcode
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from db import log_activity

try:
    import zxingcpp
    from PIL import Image as PILImage
    ZXING_AVAILABLE = True
except ImportError:
    ZXING_AVAILABLE = False

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    user = update.effective_user
    last_name = user.last_name or ""
    log_activity(user, "បើក Bot", "/start")
    text = (
        f"👋 សួស្តី {last_name}\n\n"
        "<b>ខ្ញុំជា QR Code Bot</b>\n\n"
        "<blockquote>"
        "👉 មុខងារ\n"
        "• ផ្ញើ Text / Link → បង្កើត QR Code\n\n"
        "• ផ្ញើរូបភាព QR → Bot នឹងស្កេនកូដ QR"
        "</blockquote>"
    )
    await update.message.reply_text(text, parse_mode="HTML", do_quote=True)


async def generate_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)
    user = update.effective_user
    text = update.message.text
    log_activity(user, "បង្កើត QR Code", text[:80] if text else "")

    img = qrcode.make(text)
    file_path = "/tmp/qr.png"
    img.save(file_path)

    with open(file_path, "rb") as f:
        await update.message.reply_photo(photo=f, do_quote=True)


async def decode_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    user = update.effective_user
    photo = await update.message.photo[-1].get_file()

    file_path = "/tmp/qr_input.png"
    await photo.download_to_drive(file_path)

    if not ZXING_AVAILABLE:
        log_activity(user, "ស្កេន QR Code", "Library unavailable")
        await update.message.reply_text(
            "❌ មុខងារស្កេន QR មិនទាន់ដំណើរការនៅ server នេះទេ",
            do_quote=True,
        )
        return

    try:
        img = PILImage.open(file_path)
        results = zxingcpp.read_barcodes(img)
        if results:
            data = results[0].text
            log_activity(user, "ស្កេន QR Code", data[:80])
            await update.message.reply_text(data, do_quote=True)
        else:
            log_activity(user, "ស្កេន QR Code", "មិនអាចអាន QR")
            await update.message.reply_text("❌ មិនអាចអាន QR បានទេ", do_quote=True)
    except Exception as e:
        logger.error(f"Decode error: {e}")
        log_activity(user, "ស្កេន QR Code", "Error")
        await update.message.reply_text("❌ មិនអាចអាន QR បានទេ", do_quote=True)


def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_qr))
    app.add_handler(MessageHandler(filters.PHOTO, decode_qr))

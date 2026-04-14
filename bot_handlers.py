import json
import logging
import os
import asyncio
import qrcode
from deep_translator import GoogleTranslator
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyParameters, Update, constants
from telegram.ext import (
    Application,
    BusinessConnectionHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    TypeHandler,
)
from db import log_activity
import tts as TTS

try:
    import zxingcpp
    from PIL import Image as PILImage
    ZXING_AVAILABLE = True
except ImportError:
    ZXING_AVAILABLE = False

logger = logging.getLogger(__name__)
BUSINESS_OWNER_USER_IDS = {}

# ── Translation languages ───────────────────────────────────────────────────────
LANGUAGES = {
    "km": "🇰🇭 ខ្មែរ",
    "en": "🇺🇸 អង់គ្លេស",
    "zh-CN": "🇨🇳 ចិន",
    "ja": "🇯🇵 ជប៉ុន",
    "ko": "🇰🇷 កូរ៉េ",
    "fr": "🇫🇷 បារាំង",
    "th": "🇹🇭 ថៃ",
    "vi": "🇻🇳 វៀតណាម",
    "de": "🇩🇪 អាល្លឺម៉ង់",
    "es": "🇪🇸 អេស្ប៉ាញ",
    "ru": "🇷🇺 រុស្សី",
    "ar": "🇸🇦 អារ៉ាប់",
    "pt": "🇵🇹 ព័រទុយហ្គាល់",
    "it": "🇮🇹 អ៊ីតាលី",
    "hi": "🇮🇳 ហិណ្ឌូ",
    "id": "🇮🇩 អ៊ីនដូនេស៊ី",
    "ms": "🇲🇾 ម៉ាឡេស៊ី",
    "tl": "🇵🇭 ហ្វីលីពីន",
    "tr": "🇹🇷 តួគី",
    "nl": "🇳🇱 ហូឡង់",
    "pl": "🇵🇱 ប៉ូឡូញ",
    "uk": "🇺🇦 អ៊ុយក្រែន",
    "sv": "🇸🇪 ស៊ុយអែត",
    "da": "🇩🇰 ដាណឺម៉ាក",
    "fi": "🇫🇮 ហ្វាំងឡង់",
    "no": "🇳🇴 នន័រវែស",
    "cs": "🇨🇿 ឆែក",
    "ro": "🇷🇴 រូម៉ានី",
    "hu": "🇭🇺 ហុងគ្រី",
    "el": "🇬🇷 ក្រិច",
    "he": "🇮🇱 អ៊ីស្រាអែល",
    "fa": "🇮🇷 ហ្វ័រស៊ី",
    "bn": "🇧🇩 បង់ក្លាដែស",
    "ur": "🇵🇰 អ៊ូតូ",
    "sw": "🇰🇪 ស្វាហ៊ីលី",
    "my": "🇲🇲 មីយ៉ាន់ម៉ា",
    "lo": "🇱🇦 ឡាវ",
    "mn": "🇲🇳 ម៉ុងហ្គោល",
    "si": "🇱🇰 ស្រីលង្កា",
    "ne": "🇳🇵 នេប៉ាល់",
}

_user_translate_lang: dict = {}

# ── Voice gender preference ────────────────────────────────────────────────────
_PREFS_FILE = os.path.join(os.path.dirname(__file__), "user_prefs.json")
_user_prefs: dict = {}

def _load_prefs():
    global _user_prefs
    try:
        if os.path.exists(_PREFS_FILE):
            with open(_PREFS_FILE, "r", encoding="utf-8") as f:
                _user_prefs = json.load(f)
    except Exception:
        _user_prefs = {}

def _save_prefs():
    try:
        with open(_PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(_user_prefs, f)
    except Exception:
        pass

def get_gender(user_id: int) -> str:
    return _user_prefs.get(str(user_id), "female")

def set_gender(user_id: int, gender: str):
    _user_prefs[str(user_id)] = gender
    _save_prefs()

_load_prefs()


# ── Keyboards ──────────────────────────────────────────────────────────────────
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 បង្កើត QR", callback_data="action_generate"),
            InlineKeyboardButton("📷 ស្កេន QR Code", callback_data="action_scan"),
        ],
        [
            InlineKeyboardButton("🔊 Text to Voice", callback_data="action_tts"),
            InlineKeyboardButton("🌐 បកប្រែ", callback_data="action_translate"),
        ],
    ])

def get_language_keyboard():
    buttons = []
    row = []
    for code, name in LANGUAGES.items():
        row.append(InlineKeyboardButton(name, callback_data=f"lang_{code}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 ត្រឡប់ក្រោយ", callback_data="action_back")])
    return InlineKeyboardMarkup(buttons)

def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 ត្រឡប់ក្រោយ", callback_data="action_back")]
    ])

def tts_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👨 សំឡេងប្រុស", callback_data="tts_male"),
            InlineKeyboardButton("👩 សំឡេងស្រី", callback_data="tts_female"),
        ],
    ])


# ── Business helpers ───────────────────────────────────────────────────────────
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
        return True
    try:
        owner_user_id = await get_business_owner_user_id(business_connection_id, context)
    except Exception:
        return False
    return sender.id == owner_user_id


# ── Menu sender ────────────────────────────────────────────────────────────────
async def send_menu(context: ContextTypes.DEFAULT_TYPE, chat_id, user, biz_id=None, topic_id=None, reply_to_msg_id=None):
    last_name = getattr(user, "last_name", "") or ""
    first_name = getattr(user, "first_name", "") or ""
    name = last_name or first_name or "បង"
    text = '<tg-emoji emoji-id="5472055112702629499">👋</tg-emoji> សួស្តីបង Jalaka'
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
        business_connection_id=biz_id,
        direct_messages_topic_id=topic_id,
        reply_parameters=ReplyParameters(message_id=reply_to_msg_id) if reply_to_msg_id else None,
    )


# ── Handlers ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return
    if await is_business_owner_message(message, context):
        return
    user = update.effective_user
    log_activity(user, "បើក Bot", "/start")
    biz_id = getattr(message, "business_connection_id", None)
    topic_id = direct_messages_topic_id(message)
    await context.bot.send_chat_action(
        chat_id=message.chat_id,
        action=constants.ChatAction.TYPING,
        business_connection_id=biz_id,
    )
    context.user_data["state"] = None
    await send_menu(context, message.chat_id, user, biz_id, topic_id, reply_to_msg_id=message.message_id)


async def business_connection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    connection = update.business_connection
    if not connection:
        return
    BUSINESS_OWNER_USER_IDS[connection.id] = connection.user.id
    logger.info("Business connection %s enabled=%s", connection.id, connection.is_enabled)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.business_message or update.message
    if not message:
        return
    if update.edited_business_message:
        return
    if await is_business_owner_message(message, context):
        return

    user = message.from_user
    if not user:
        return

    biz_id = getattr(message, "business_connection_id", None)
    topic_id = direct_messages_topic_id(message)
    state = context.user_data.get("state")

    await context.bot.send_chat_action(
        chat_id=message.chat_id,
        action=constants.ChatAction.TYPING,
        business_connection_id=biz_id,
    )

    msg_id = message.message_id

    if state == "awaiting_text" and message.text:
        await _generate_qr(context, message, user, biz_id, topic_id, msg_id)
        context.user_data["state"] = None
        return

    if state == "awaiting_photo" and message.photo:
        await _scan_qr(context, message, user, biz_id, topic_id, msg_id)
        context.user_data["state"] = None
        return

    if state == "awaiting_tts" and message.text:
        await _synthesize_voice(context, message, user, biz_id, topic_id, msg_id)
        return

    if state == "awaiting_translate" and message.text:
        await _translate_text(context, message, user, biz_id, topic_id, msg_id)
        return

    log_activity(user, "ទទួល Message", (message.text or "")[:80])
    await send_menu(context, message.chat_id, user, biz_id, topic_id, reply_to_msg_id=msg_id)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
    chat_id = query.message.chat_id
    biz_id = getattr(query.message, "business_connection_id", None)
    topic_id = getattr(query.message, "direct_messages_topic_id", None)


    if data == "action_generate":
        log_activity(user, "ជ្រើស បង្កើត QR", "")
        context.user_data["state"] = "awaiting_text"
        await context.bot.send_message(
            chat_id=chat_id,
            text='<tg-emoji emoji-id="4954458300235121703">📋</tg-emoji> <b>បង្កើត QR</b>\n\n'
                 "សូមផ្ញើ <b>Text</b> ឬ <b>Link</b> ដែលអ្នកចង់ធ្វើ QR Code:",
            parse_mode="HTML",
            business_connection_id=biz_id,
            direct_messages_topic_id=topic_id,
        )

    elif data == "action_scan":
        log_activity(user, "ជ្រើស ស្កេន QR", "")
        context.user_data["state"] = "awaiting_photo"
        await context.bot.send_message(
            chat_id=chat_id,
            text="📷 <b>ស្កេន QR Code</b>\n\n"
                 "សូមផ្ញើ <b>រូបភាព QR Code</b> ដែលអ្នកចង់ស្កេន:",
            parse_mode="HTML",
            business_connection_id=biz_id,
            direct_messages_topic_id=topic_id,
        )

    elif data == "action_tts":
        log_activity(user, "ជ្រើស Text to Voice", "")
        context.user_data["state"] = "awaiting_tts"
        gender = get_gender(user.id)
        current = "👩 សំឡេងស្រី" if gender == "female" else "👨 សំឡេងប្រុស"
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🔊 <b>Text to Voice</b>\n\n"
                 f"សំឡេងបច្ចុប្បន្ន: <b>{current}</b>\n\n"
                 "សូមផ្ញើ <b>Text</b> ណាមួយ ហើយខ្ញុំនឹងបំប្លែងជាសំឡេង\n"
                 "<i>(គាំទ្រ ខ្មែរ, English, Thai, 日本語 និងភាសាជាច្រើនទៀត)</i>",
            parse_mode="HTML",
            reply_markup=tts_keyboard(),
            business_connection_id=biz_id,
            direct_messages_topic_id=topic_id,
        )

    elif data == "tts_male":
        set_gender(user.id, "male")
        context.user_data["state"] = "awaiting_tts"
        await query.edit_message_text(
            "🔊 <b>Text to Voice</b>\n\n"
            "សំឡេងបច្ចុប្បន្ន: <b>👨 សំឡេងប្រុស</b>\n\n"
            "សូមផ្ញើ <b>Text</b> ណាមួយ ហើយខ្ញុំនឹងបំប្លែងជាសំឡេង\n"
            "<i>(គាំទ្រ ខ្មែរ, English, Thai, 日本語 និងភាសាជាច្រើនទៀត)</i>",
            parse_mode="HTML",
            reply_markup=tts_keyboard(),
        )

    elif data == "tts_female":
        set_gender(user.id, "female")
        context.user_data["state"] = "awaiting_tts"
        await query.edit_message_text(
            "🔊 <b>Text to Voice</b>\n\n"
            "សំឡេងបច្ចុប្បន្ន: <b>👩 សំឡេងស្រី</b>\n\n"
            "សូមផ្ញើ <b>Text</b> ណាមួយ ហើយខ្ញុំនឹងបំប្លែងជាសំឡេង\n"
            "<i>(គាំទ្រ ខ្មែរ, English, Thai, 日本語 និងភាសាជាច្រើនទៀត)</i>",
            parse_mode="HTML",
            reply_markup=tts_keyboard(),
        )

    elif data == "action_translate":
        log_activity(user, "ជ្រើស បកប្រែ", "")
        lang_code = _user_translate_lang.get(user.id, "km")
        lang_name = LANGUAGES.get(lang_code, lang_code)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🌐 <b>បកប្រែ</b>\n\n"
                 f"ភាសាគោលដៅបច្ចុប្បន្ន: <b>{lang_name}</b>\n\n"
                 "សូមជ្រើសរើសភាសាដែលអ្នកចង់បកប្រែទៅ:",
            parse_mode="HTML",
            reply_markup=get_language_keyboard(),
            business_connection_id=biz_id,
            direct_messages_topic_id=topic_id,
        )

    elif data.startswith("lang_"):
        lang_code = data.replace("lang_", "")
        lang_name = LANGUAGES.get(lang_code, lang_code)
        _user_translate_lang[user.id] = lang_code
        context.user_data["state"] = "awaiting_translate"
        await query.edit_message_text(
            f"🌐 <b>បកប្រែ</b>\n\n"
            f"✅ ភាសាគោលដៅ: <b>{lang_name}</b>\n\n"
            "សូមផ្ញើ Text ដែលអ្នកចង់បកប្រែ:",
            parse_mode="HTML",
            reply_markup=back_keyboard(),
        )

    elif data == "action_back":
        context.user_data["state"] = None
        await send_menu(context, chat_id, user, biz_id, topic_id)


# ── QR generation ──────────────────────────────────────────────────────────────
async def _generate_qr(context, message, user, biz_id, topic_id, reply_to_msg_id=None):
    text = message.text
    log_activity(user, "បង្កើត QR Code", text[:80])
    await context.bot.send_chat_action(
        chat_id=message.chat_id,
        action=constants.ChatAction.UPLOAD_PHOTO,
        business_connection_id=biz_id,
    )
    img = qrcode.make(text)
    file_path = "/tmp/qr_output.png"
    img.save(file_path)
    with open(file_path, "rb") as f:
        await context.bot.send_photo(
            chat_id=message.chat_id,
            photo=f,
            business_connection_id=biz_id,
            direct_messages_topic_id=topic_id,
            reply_markup=main_menu_keyboard(),
            reply_parameters=ReplyParameters(message_id=reply_to_msg_id) if reply_to_msg_id else None,
        )


# ── QR scanning ────────────────────────────────────────────────────────────────
async def _scan_qr(context, message, user, biz_id, topic_id, reply_to_msg_id=None):
    log_activity(user, "ស្កេន QR Code", "")
    quote = ReplyParameters(message_id=reply_to_msg_id) if reply_to_msg_id else None
    if not ZXING_AVAILABLE:
        await context.bot.send_message(
            chat_id=message.chat_id,
            text="❌ មុខងារស្កេន QR មិនទាន់ដំណើរការទេ",
            business_connection_id=biz_id,
            direct_messages_topic_id=topic_id,
            reply_markup=main_menu_keyboard(),
            reply_parameters=quote,
        )
        return
    photo = await message.photo[-1].get_file()
    file_path = "/tmp/qr_input.png"
    await photo.download_to_drive(file_path)
    try:
        img = PILImage.open(file_path)
        results = zxingcpp.read_barcodes(img)
        if results:
            data = results[0].text
            log_activity(user, "ស្កេន QR Code", data[:80])
            await context.bot.send_message(
                chat_id=message.chat_id,
                text=f"<code>{data}</code>",
                parse_mode="HTML",
                business_connection_id=biz_id,
                direct_messages_topic_id=topic_id,
                reply_markup=main_menu_keyboard(),
                reply_parameters=quote,
            )
        else:
            log_activity(user, "ស្កេន QR Code", "មិនអាចអាន")
            await context.bot.send_message(
                chat_id=message.chat_id,
                text="❌ មិនអាចអាន QR បានទេ សូមផ្ញើរូបភាពដែលច្បាស់ជាងនេះ",
                business_connection_id=biz_id,
                direct_messages_topic_id=topic_id,
                reply_markup=main_menu_keyboard(),
                reply_parameters=quote,
            )
    except Exception as e:
        logger.error("Decode error: %s", e)
        await context.bot.send_message(
            chat_id=message.chat_id,
            text="❌ មានបញ្ហា សូមព្យាយាមម្តងទៀត",
            business_connection_id=biz_id,
            direct_messages_topic_id=topic_id,
            reply_markup=main_menu_keyboard(),
            reply_parameters=quote,
        )


# ── Text-to-Voice ──────────────────────────────────────────────────────────────
async def _synthesize_voice(context, message, user, biz_id, topic_id, reply_to_msg_id=None):
    text = message.text
    log_activity(user, "Text to Voice", text[:80])
    quote = ReplyParameters(message_id=reply_to_msg_id) if reply_to_msg_id else None

    await context.bot.send_chat_action(
        chat_id=message.chat_id,
        action=constants.ChatAction.RECORD_VOICE,
        business_connection_id=biz_id,
    )

    gender = get_gender(user.id)
    voice_map = TTS.MALE_VOICES if gender == "male" else TTS.FEMALE_VOICES

    lang = TTS.detect_language(text)
    segments = TTS.segment_text(text)
    is_mixed = len(segments) > 1 or (segments and segments[0][1] != lang)

    cache_key = f"{text[:200]}:{gender}"
    cached_file_id = TTS.cache_get(cache_key)

    try:
        if cached_file_id:
            await context.bot.send_voice(
                chat_id=message.chat_id,
                voice=cached_file_id,
                business_connection_id=biz_id,
                direct_messages_topic_id=topic_id,
                reply_markup=tts_keyboard(),
                reply_parameters=quote,
            )
        else:
            if is_mixed:
                audio_buf = await TTS.synthesize_mixed(segments, voice_map)
            else:
                voice = voice_map.get(lang, voice_map.get("en"))
                audio_buf = await TTS.synthesize_to_bytes(text, voice, lang=lang)

            msg = await context.bot.send_voice(
                chat_id=message.chat_id,
                voice=audio_buf,
                business_connection_id=biz_id,
                direct_messages_topic_id=topic_id,
                reply_markup=tts_keyboard(),
                reply_parameters=quote,
            )
            TTS.cache_set(cache_key, msg.voice.file_id)
    except Exception as e:
        logger.error("TTS error: %s", e)
        await context.bot.send_message(
            chat_id=message.chat_id,
            text="⚠️ មានបញ្ហាក្នុងការបង្កើតសំឡេង។ សូមព្យាយាមម្តងទៀត។",
            business_connection_id=biz_id,
            direct_messages_topic_id=topic_id,
            reply_markup=main_menu_keyboard(),
            reply_parameters=quote,
        )


# ── Translation ─────────────────────────────────────────────────────────────────
async def _translate_text(context, message, user, biz_id, topic_id, reply_to_msg_id=None):
    text = message.text
    log_activity(user, "បកប្រែ", text[:80])
    quote = ReplyParameters(message_id=reply_to_msg_id) if reply_to_msg_id else None
    target_lang = _user_translate_lang.get(user.id, "km")
    lang_name = LANGUAGES.get(target_lang, target_lang)
    translate_again_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 ប្តូរភាសា", callback_data="action_translate")],
        [InlineKeyboardButton("🔙 ត្រឡប់ក្រោយ", callback_data="action_back")],
    ])
    try:
        translated = GoogleTranslator(source="auto", target=target_lang).translate(text)
        await context.bot.send_message(
            chat_id=message.chat_id,
            text=f"🌐 <b>បកប្រែទៅ {lang_name}:</b>\n\n{translated}",
            parse_mode="HTML",
            business_connection_id=biz_id,
            direct_messages_topic_id=topic_id,
            reply_markup=translate_again_keyboard,
            reply_parameters=quote,
        )
    except Exception as e:
        logger.error("Translation error: %s", e)
        await context.bot.send_message(
            chat_id=message.chat_id,
            text="❌ សូមទោស មានបញ្ហាក្នុងការបកប្រែ។ សូមព្យាយាមម្តងទៀត។",
            business_connection_id=biz_id,
            direct_messages_topic_id=topic_id,
            reply_markup=main_menu_keyboard(),
            reply_parameters=quote,
        )


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message:
        return
    user = update.effective_user
    log_activity(user, "ជ្រើស ភាសាបកប្រែ", "/language")
    lang_code = _user_translate_lang.get(user.id, "km")
    lang_name = LANGUAGES.get(lang_code, lang_code)
    await context.bot.send_chat_action(chat_id=message.chat_id, action=constants.ChatAction.TYPING)
    await message.reply_text(
        f"🌐 <b>ជ្រើសរើសភាសាបកប្រែ</b>\n\nភាសាបច្ចុប្បន្ន: <b>{lang_name}</b>\n\nសូមជ្រើសរើសភាសាគោលដៅ:",
        parse_mode="HTML",
        reply_markup=get_language_keyboard(),
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Handler error", exc_info=context.error)


def register_handlers(app: Application):
    app.add_handler(BusinessConnectionHandler(business_connection_handler))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^(action_|tts_|lang_)"))
    app.add_handler(TypeHandler(Update, handle_message), group=1)
    app.add_error_handler(error_handler)

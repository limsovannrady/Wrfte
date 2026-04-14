import re
import asyncio
import unicodedata
from io import BytesIO
from collections import OrderedDict

import edge_tts
import imageio_ffmpeg

from langdetect import detect as langdetect_detect, detect_langs, DetectorFactory

DetectorFactory.seed = 0
_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# ── Cache file_id to avoid re-uploading identical audio ───────────────────────
_FILE_ID_CACHE: OrderedDict[str, str] = OrderedDict()
_CACHE_MAX = 200

def cache_get(key: str):
    if key in _FILE_ID_CACHE:
        _FILE_ID_CACHE.move_to_end(key)
        return _FILE_ID_CACHE[key]
    return None

def cache_set(key: str, file_id: str):
    if key in _FILE_ID_CACHE:
        _FILE_ID_CACHE.move_to_end(key)
    else:
        if len(_FILE_ID_CACHE) >= _CACHE_MAX:
            _FILE_ID_CACHE.popitem(last=False)
        _FILE_ID_CACHE[key] = file_id


# ── Text helpers ───────────────────────────────────────────────────────────────
def strip_unspeakable(text: str) -> str:
    result = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith(('L', 'M', 'N', 'P', 'Z')):
            result.append(ch)
        elif ch in ('\n', '\r', '\t', ' '):
            result.append(ch)
    return ''.join(result)

def has_speakable_content(text: str) -> bool:
    return bool(re.search(r'\w', text, re.UNICODE))


# ── Voice maps ─────────────────────────────────────────────────────────────────
MALE_VOICES = {
    "af": "af-ZA-WillemNeural", "am": "am-ET-AmehaNeural",
    "ar": "ar-SA-HamedNeural", "az": "az-AZ-BabekNeural",
    "bg": "bg-BG-BorislavNeural", "bn": "bn-BD-PradeepNeural",
    "bs": "bs-BA-GoranNeural", "ca": "ca-ES-EnricNeural",
    "cs": "cs-CZ-AntoninNeural", "cy": "cy-GB-AledNeural",
    "da": "da-DK-JeppeNeural", "de": "de-DE-FlorianMultilingualNeural",
    "el": "el-GR-NestorasNeural", "en": "en-US-AndrewMultilingualNeural",
    "es": "es-ES-AlvaroNeural", "et": "et-EE-KertNeural",
    "fa": "fa-IR-FaridNeural", "fi": "fi-FI-HarriNeural",
    "fil": "fil-PH-AngeloNeural", "fr": "fr-FR-RemyMultilingualNeural",
    "ga": "ga-IE-ColmNeural", "gl": "gl-ES-RoiNeural",
    "gu": "gu-IN-NiranjanNeural", "he": "he-IL-AvriNeural",
    "hi": "hi-IN-MadhurNeural", "hr": "hr-HR-SreckoNeural",
    "hu": "hu-HU-TamasNeural", "id": "id-ID-ArdiNeural",
    "is": "is-IS-GunnarNeural", "it": "it-IT-GiuseppeMultilingualNeural",
    "ja": "ja-JP-KeitaNeural", "jv": "jv-ID-DimasNeural",
    "ka": "ka-GE-GiorgiNeural", "kk": "kk-KZ-DauletNeural",
    "km": "km-KH-PisethNeural", "kn": "kn-IN-GaganNeural",
    "ko": "ko-KR-HyunsuMultilingualNeural", "lo": "lo-LA-ChanthavongNeural",
    "lt": "lt-LT-LeonasNeural", "lv": "lv-LV-NilsNeural",
    "mk": "mk-MK-AleksandarNeural", "ml": "ml-IN-MidhunNeural",
    "mn": "mn-MN-BataaNeural", "mr": "mr-IN-ManoharNeural",
    "ms": "ms-MY-OsmanNeural", "mt": "mt-MT-JosephNeural",
    "my": "my-MM-ThihaNeural", "nb": "nb-NO-FinnNeural",
    "ne": "ne-NP-SagarNeural", "nl": "nl-NL-MaartenNeural",
    "pl": "pl-PL-MarekNeural", "ps": "ps-AF-GulNawazNeural",
    "pt": "pt-BR-AntonioNeural", "ro": "ro-RO-EmilNeural",
    "ru": "ru-RU-DmitryNeural", "si": "si-LK-SameeraNeural",
    "sk": "sk-SK-LukasNeural", "sl": "sl-SI-RokNeural",
    "so": "so-SO-MuuseNeural", "sq": "sq-AL-IlirNeural",
    "sr": "sr-RS-NicholasNeural", "su": "su-ID-JajangNeural",
    "sv": "sv-SE-MattiasNeural", "sw": "sw-KE-RafikiNeural",
    "ta": "ta-IN-ValluvarNeural", "te": "te-IN-MohanNeural",
    "th": "th-TH-NiwatNeural", "tr": "tr-TR-AhmetNeural",
    "uk": "uk-UA-OstapNeural", "ur": "ur-IN-SalmanNeural",
    "uz": "uz-UZ-SardorNeural", "vi": "vi-VN-NamMinhNeural",
    "zh-CN": "zh-CN-YunxiNeural", "zh-TW": "zh-TW-YunJheNeural",
    "zu": "zu-ZA-ThembaNeural",
}

FEMALE_VOICES = {
    "af": "af-ZA-AdriNeural", "am": "am-ET-MekdesNeural",
    "ar": "ar-SA-ZariyahNeural", "az": "az-AZ-BanuNeural",
    "bg": "bg-BG-KalinaNeural", "bn": "bn-BD-NabanitaNeural",
    "bs": "bs-BA-VesnaNeural", "ca": "ca-ES-JoanaNeural",
    "cs": "cs-CZ-VlastaNeural", "cy": "cy-GB-NiaNeural",
    "da": "da-DK-ChristelNeural", "de": "de-DE-KatjaNeural",
    "el": "el-GR-AthinaNeural", "en": "en-US-AvaMultilingualNeural",
    "es": "es-ES-ElviraNeural", "et": "et-EE-AnuNeural",
    "fa": "fa-IR-DilaraNeural", "fi": "fi-FI-SelmaNeural",
    "fil": "fil-PH-BlessicaNeural", "fr": "fr-FR-VivienneMultilingualNeural",
    "ga": "ga-IE-OrlaNeural", "gl": "gl-ES-SabelaNeural",
    "gu": "gu-IN-DhwaniNeural", "he": "he-IL-HilaNeural",
    "hi": "hi-IN-SwaraNeural", "hr": "hr-HR-GabrijelaNeural",
    "hu": "hu-HU-NoemiNeural", "id": "id-ID-GadisNeural",
    "is": "is-IS-GudrunNeural", "it": "it-IT-ElsaNeural",
    "ja": "ja-JP-NanamiNeural", "jv": "jv-ID-SitiNeural",
    "ka": "ka-GE-EkaNeural", "kk": "kk-KZ-AigulNeural",
    "km": "km-KH-SreymomNeural", "kn": "kn-IN-SapnaNeural",
    "ko": "ko-KR-SunHiNeural", "lo": "lo-LA-KeomanyNeural",
    "lt": "lt-LT-OnaNeural", "lv": "lv-LV-EveritaNeural",
    "mk": "mk-MK-MarijaNeural", "ml": "ml-IN-SobhanaNeural",
    "mn": "mn-MN-YesuiNeural", "mr": "mr-IN-AarohiNeural",
    "ms": "ms-MY-YasminNeural", "mt": "mt-MT-GraceNeural",
    "my": "my-MM-NilarNeural", "nb": "nb-NO-PernilleNeural",
    "ne": "ne-NP-HemkalaNeural", "nl": "nl-NL-ColetteNeural",
    "pl": "pl-PL-ZofiaNeural", "ps": "ps-AF-LatifaNeural",
    "pt": "pt-BR-ThalitaMultilingualNeural", "ro": "ro-RO-AlinaNeural",
    "ru": "ru-RU-SvetlanaNeural", "si": "si-LK-ThiliniNeural",
    "sk": "sk-SK-ViktoriaNeural", "sl": "sl-SI-PetraNeural",
    "so": "so-SO-UbaxNeural", "sq": "sq-AL-AnilaNeural",
    "sr": "sr-RS-SophieNeural", "su": "su-ID-TutiNeural",
    "sv": "sv-SE-SofieNeural", "sw": "sw-KE-ZuriNeural",
    "ta": "ta-IN-PallaviNeural", "te": "te-IN-ShrutiNeural",
    "th": "th-TH-PremwadeeNeural", "tr": "tr-TR-EmelNeural",
    "uk": "uk-UA-PolinaNeural", "ur": "ur-IN-GulNeural",
    "uz": "uz-UZ-MadinaNeural", "vi": "vi-VN-HoaiMyNeural",
    "zh-CN": "zh-CN-XiaoxiaoNeural", "zh-TW": "zh-TW-HsiaoChenNeural",
    "zu": "zu-ZA-ThandoNeural",
}

NORMALIZE = {
    "zh-cn": "zh-CN", "zh-tw": "zh-TW", "zh": "zh-CN",
    "iw": "he", "no": "nb", "tl": "fil", "jw": "jv", "in": "id",
}

LANG_FALLBACK = {
    "pa": "hi", "or": "bn", "hy": "en",
}

SCRIPT_MAP = [
    (r'[\u1780-\u17FF]', 'km'),
    (r'[\u0E00-\u0E7F]', 'th'),
    (r'[\u0E80-\u0EFF]', 'lo'),
    (r'[\u1000-\u109F]', 'my'),
    (r'[\u1200-\u137F]', 'am'),
    (r'[\u10A0-\u10FF]', 'ka'),
    (r'[\u0530-\u058F]', 'hy'),
    (r'[\u0590-\u05FF]', 'he'),
    (r'[\u0900-\u097F]', 'hi'),
    (r'[\u0980-\u09FF]', 'bn'),
    (r'[\u0A00-\u0A7F]', 'pa'),
    (r'[\u0A80-\u0AFF]', 'gu'),
    (r'[\u0B00-\u0B7F]', 'or'),
    (r'[\u0B80-\u0BFF]', 'ta'),
    (r'[\u0C00-\u0C7F]', 'te'),
    (r'[\u0C80-\u0CFF]', 'kn'),
    (r'[\u0D00-\u0D7F]', 'ml'),
    (r'[\u0D80-\u0DFF]', 'si'),
    (r'[\u0600-\u06FF]', 'ar'),
    (r'[\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]', 'ar'),
    (r'[\u0400-\u04FF]', 'ru'),
    (r'[\u0370-\u03FF]', 'el'),
    (r'[\u1800-\u18AF]', 'mn'),
    (r'[\uAC00-\uD7FF]', 'ko'),
    (r'[\u3040-\u30FF]', 'ja'),
    (r'[\u4E00-\u9FFF\u3400-\u4DBF]', 'zh-CN'),
]

_SCRIPT_LANG = {
    'km': 'km', 'th': 'th', 'lo': 'lo', 'my': 'my', 'am': 'am',
    'ka': 'ka', 'he': 'he', 'hi': 'hi', 'bn': 'bn', 'pa': 'hi',
    'gu': 'gu', 'ta': 'ta', 'te': 'te', 'kn': 'kn', 'ml': 'ml',
    'si': 'si', 'ar': 'ar', 'ru': 'ru', 'el': 'el', 'mn_s': 'mn',
    'ko': 'ko', 'ja': 'ja', 'zh': 'zh-CN',
}

_SEGMENT_RE = re.compile(
    r'(?P<km>[\u1780-\u17FF]+)'
    r'|(?P<th>[\u0E00-\u0E7F]+)'
    r'|(?P<lo>[\u0E80-\u0EFF]+)'
    r'|(?P<my>[\u1000-\u109F]+)'
    r'|(?P<am>[\u1200-\u137F]+)'
    r'|(?P<ka>[\u10A0-\u10FF]+)'
    r'|(?P<he>[\u0590-\u05FF]+)'
    r'|(?P<hi>[\u0900-\u097F]+)'
    r'|(?P<bn>[\u0980-\u09FF]+)'
    r'|(?P<pa>[\u0A00-\u0A7F]+)'
    r'|(?P<gu>[\u0A80-\u0AFF]+)'
    r'|(?P<ta>[\u0B80-\u0BFF]+)'
    r'|(?P<te>[\u0C00-\u0C7F]+)'
    r'|(?P<kn>[\u0C80-\u0CFF]+)'
    r'|(?P<ml>[\u0D00-\u0D7F]+)'
    r'|(?P<si>[\u0D80-\u0DFF]+)'
    r'|(?P<ar>[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]+)'
    r'|(?P<ru>[\u0400-\u04FF]+)'
    r'|(?P<el>[\u0370-\u03FF]+)'
    r'|(?P<ko>[\uAC00-\uD7FF]+)'
    r'|(?P<ja>[\u3040-\u30FF]+)'
    r'|(?P<zh>[\u4E00-\u9FFF\u3400-\u4DBF]+)'
    r'|(?P<other>[^\u1780-\u17FF\u0E00-\u0E7F\u0E80-\u0EFF\u1000-\u109F'
    r'\u1200-\u137F\u10A0-\u10FF\u0590-\u05FF\u0900-\u097F\u0980-\u09FF'
    r'\u0A00-\u0A7F\u0A80-\u0AFF\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF'
    r'\u0D00-\u0D7F\u0D80-\u0DFF\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF'
    r'\uFE70-\uFEFF\u0400-\u04FF\u0370-\u03FF\uAC00-\uD7FF\u3040-\u30FF'
    r'\u4E00-\u9FFF\u3400-\u4DBF]+)'
)


def detect_language(text: str) -> str:
    for pattern, lang in SCRIPT_MAP:
        if re.search(pattern, text):
            if lang == 'ar':
                try:
                    detected = langdetect_detect(text)
                    detected = NORMALIZE.get(detected, detected)
                    if detected in ('fa', 'ur', 'ps', 'ar'):
                        return detected
                except Exception:
                    pass
            if lang == 'ru':
                try:
                    detected = langdetect_detect(text)
                    detected = NORMALIZE.get(detected, detected)
                    if detected in ('ru', 'uk', 'bg', 'sr', 'mk', 'kk', 'mn'):
                        return detected
                except Exception:
                    pass
            return LANG_FALLBACK.get(lang, lang)
    try:
        detected = langdetect_detect(text)
        detected = NORMALIZE.get(detected, detected)
        return LANG_FALLBACK.get(detected, detected)
    except Exception:
        return 'en'


def segment_text(text: str) -> list:
    raw = []
    for m in _SEGMENT_RE.finditer(text):
        g = m.lastgroup
        chunk = m.group()
        if g == 'other':
            raw.append((chunk, None))
        else:
            lang = _SCRIPT_LANG.get(g, 'en')
            if g == 'ar':
                try:
                    d = NORMALIZE.get(langdetect_detect(chunk), langdetect_detect(chunk))
                    if d in ('fa', 'ur', 'ps', 'ar'):
                        lang = d
                except Exception:
                    pass
            elif g == 'ru':
                try:
                    d = NORMALIZE.get(langdetect_detect(chunk), langdetect_detect(chunk))
                    if d in ('ru', 'uk', 'bg', 'sr', 'mk', 'kk', 'mn'):
                        lang = d
                except Exception:
                    pass
            raw.append((chunk, lang))

    resolved = []
    for chunk, lang in raw:
        if lang is not None:
            resolved.append((chunk, lang))
            continue
        stripped = chunk.strip()
        if not stripped:
            if resolved:
                resolved[-1] = (resolved[-1][0] + chunk, resolved[-1][1])
            continue
        has_latin_letters = bool(re.search(r'[a-zA-Z]', chunk))
        if not has_latin_letters:
            if resolved:
                resolved[-1] = (resolved[-1][0] + chunk, resolved[-1][1])
            else:
                resolved.append((chunk, 'en'))
            continue
        detected = 'en'
        if len(stripped) >= 4:
            try:
                langs = detect_langs(stripped)
                if langs and langs[0].prob >= 0.65:
                    detected = NORMALIZE.get(langs[0].lang, langs[0].lang)
            except Exception:
                pass
        resolved.append((chunk, detected))

    resolved = [(c, LANG_FALLBACK.get(l, l)) for c, l in resolved]

    merged = []
    for chunk, lang in resolved:
        if merged and merged[-1][1] == lang:
            merged[-1] = (merged[-1][0] + chunk, lang)
        else:
            merged.append([chunk, lang])

    return [(c, l) for c, l in merged] if merged else [('', 'en')]


def voice_rate(lang: str) -> str:
    return "+0%"


async def _synth_segment_pcm(text: str, voice: str, lang: str = 'en') -> bytes:
    clean = strip_unspeakable(text)
    if not clean.strip() or not has_speakable_content(clean):
        return b''
    rate = voice_rate(lang)
    try:
        com = edge_tts.Communicate(clean, voice, rate=rate)
        pcm_chunks = []
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                pcm_chunks.append(chunk["data"])
        return b''.join(pcm_chunks)
    except Exception as e:
        return b''


async def _pcm_to_ogg(pcm: bytes) -> BytesIO:
    proc = await asyncio.create_subprocess_exec(
        _FFMPEG, "-y", "-f", "mp3", "-i", "pipe:0",
        "-c:a", "libopus", "-b:a", "64k", "-f", "ogg", "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate(input=pcm)
    return BytesIO(stdout)


async def synthesize_to_bytes(text: str, voice: str, lang: str = 'en') -> BytesIO:
    pcm = await _synth_segment_pcm(text, voice, lang=lang)
    return await _pcm_to_ogg(pcm)


async def synthesize_mixed(segments: list, voice_map: dict) -> BytesIO:
    tasks = [
        _synth_segment_pcm(chunk, voice_map.get(lang) or voice_map.get('en'), lang=lang)
        for chunk, lang in segments
        if strip_unspeakable(chunk).strip() and has_speakable_content(strip_unspeakable(chunk))
    ]
    if not tasks:
        return BytesIO(b'')
    pcm_parts = await asyncio.gather(*tasks)
    return await _pcm_to_ogg(b''.join(pcm_parts))

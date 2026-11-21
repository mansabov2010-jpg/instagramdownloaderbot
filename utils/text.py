START_TEXT = """Salom, <b>{name}</b>!

Men to‘g‘ridan-to‘g‘ri fayl havolasi yoki qo‘llab-quvvatlanadigan media URL manzilini qabul qilib, uni yuklab olaman va natijani Telegramga yuboraman.

<b>Nima yuborishingiz mumkin</b>
- to‘g‘ridan-to‘g‘ri fayl havolalari
- YouTube va boshqa qo‘llab-quvvatlanadigan `yt-dlp` havolalari
- `url|fayl_nomi`
- `url|fayl_nomi|login|parol`
- `url * fayl_nomi`

Tezkor ko‘rib chiqish uchun quyidagi tugmalardan foydalaning yoki boshlash uchun havola yuboring."""

HELP_TEXT = """<b>Botdan qanday foydalaniladi</b>

Quyidagi formatlardan birida xabar yuboring:

1. <b>To‘g‘ridan-to‘g‘ri havola</b>
   <code>https://example.com/file.mp4</code>

2. <b>Maxsus fayl nomi bilan to‘g‘ridan-to‘g‘ri havola</b>
   <code>https://example.com/file.mp4|my-video.mp4</code>

3. <b>Login va parol talab qiladigan himoyalangan URL</b>
   <code>https://example.com/file|my-file.mp4|username|password</code>

4. <b>Fayl nomini o‘zgartirishning muqobil formati</b>
   <code>https://example.com/file.mp4 * renamed.mp4</code>

<b>Qo‘shimcha buyruqlar</b>
- <code>/thumb</code> — saqlangan muqovangizni (thumbnail) ko‘rsatadi
- <code>/delthumb</code> — saqlangan muqovangizni o‘chiradi

Agar manba bir nechta formatni qo‘llab-quvvatlasa, yuklashdan oldin tanlov menyusini ko‘rsataman."""

ABOUT_TEXT = """<b>All Url Uploader</b>

<a href="https://docs.aiogram.dev/">aiogram 3</a> va <a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a> asosida yaratilgan.

<b>Repozitoriy</b>
<a href="https://github.com/mansabov2010-jpg/instagramdownloaderbot">github.com/mansabov2010-jpg/instagramdownloaderbot</a>

<b>Imkoniyatlari</b>
- to‘g‘ridan-to‘g‘ri havolalar va `yt-dlp` manbalaridan qo‘llab-quvvatlanadigan medialarni yuklab oladi
- manbada bir nechta variant bo‘lsa, format tanlash imkonini beradi
- video, audio va hujjatlarni Telegramga yuklaydi
- har bir foydalanuvchi uchun alohida muqova (thumbnail) qo‘llab-quvvatlaydi

Tayyor bo‘lganingizda qo‘llab-quvvatlanadigan havolani yuboring."""

THUMB_SAVED = "Maxsus muqovangiz saqlandi."
THUMB_MISSING = "Sizda hali muqova yo‘q. Saqlash uchun JPG rasm yuboring."
THUMB_REMOVED = "Muqovangiz muvaffaqiyatli o‘chirildi."

PROCESSING = "Havolangiz tekshirilmoqda..."
FORMAT_SELECTION = "Kerakli formatni tanlang."
DOWNLOAD_START = "Yuklanmoqda: <b>{name}</b>"
UPLOAD_START = "Telegramga yuklanmoqda: <b>{name}</b>"
QUICK_CHOICE = "Ushbu YouTube havolasini qanday yuklab olishni tanlang."
YOUTUBE_AUDIO_LABEL = "Audio"
YOUTUBE_VIDEO_LABEL = "Video"
RATE_LIMIT = (
    "Yangi so‘rov yuborishdan oldin biroz kuting. Taxminan {minutes} daqiqadan so‘ng qayta urinib ko‘ring."
)
DOWNLOAD_FAILED = "Ushbu havolani qayta ishlab bo‘lmadi."
DIRECT_DOWNLOAD_FAILED = "Ushbu faylni yuklab bo‘lmadi."
REQUEST_EXPIRED = "So‘rov muddati tugagan. Havolani qaytadan yuboring."
FILE_TOO_LARGE = (
    "{seconds} soniyada yuklab olindi.\nAniqlangan fayl hajmi: {size}\n"
    "Telegram ruxsat bergan hajmdan katta fayllarni yuklay olmayman."
)
DONE = "{download_seconds} soniyada yuklab olindi.\n{upload_seconds} soniyada yuklandi."


def upload_caption(name: str) -> str:
    return UPLOAD_START.format(name=name)


def download_caption(name: str) -> str:
    return DOWNLOAD_START.format(name=name)

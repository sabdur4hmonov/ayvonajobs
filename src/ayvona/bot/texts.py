"""Every text the bot shows, in one place (Uzbek Latin; a Russian version can be added later).

HTML parse mode: values put into these templates must be ``html.escape``-d by the caller.
"""

from __future__ import annotations

# ------------------------------------------------------------------ public (Bosqich 10 later)
PUBLIC_START = (
    "Assalomu alaykum! 👋\n"
    "<b>Ayvona Jobs</b> boti tez orada ishga tushadi: e'lon joylash, ish qidirish, obunalar.\n"
    "Hozircha e'lonlar kanalimizda: @{channel}"
)

# ------------------------------------------------------------------ admin: general
ADMIN_HELP = (
    "🛠 <b>Admin buyruqlari</b>\n\n"
    "📊 /stats — bugun va hafta: keldi, chiqdi, dublikat, xato, kategoriyalar\n"
    "📬 /queue — navbat (kanalga chiqishini kutayotganlar)\n"
    "❌ /failed — chiqmay qolgan e'lonlar\n"
    "🔁 /retry &lt;id | all&gt; — chiqmay qolganini qayta navbatga\n"
    "⏸ /pause — kanalga joylashni to'xtatish · ▶️ /resume — davom ettirish\n\n"
    "📡 /sources — manbalar (kanallar, saytlar): pauza, yoqish, o'chirish, statistika\n"
    "➕ /addsource &lt;@kanal | t.me/kanal | t.me/+taklif | web:nom | rss:URL&gt;\n\n"
    "🖼 /images — rasm bo'shliqlari · /images &lt;kasb&gt; — rasmlar ro'yxati\n"
    "➕ /addimage &lt;kasb | kategoriya&gt; — rasm qo'shish\n"
    "✖️ /cancel — boshlangan amalni bekor qilish"
)
CANCELLED = "✖️ Bekor qilindi."
NOTHING_TO_CANCEL = "Bekor qiladigan narsa yo'q."

# ------------------------------------------------------------------ /stats
STATS = (
    "📊 <b>Statistika</b> ({now})\n\n"
    "<b>Bugun</b> / <b>7 kun</b>\n"
    "📥 Keldi (post): {d.fetched} / {w.fetched}\n"
    "📢 Kanalga chiqdi: {d.published} / {w.published}\n"
    "♻️ Dublikat: {d.duplicates} / {w.duplicates}\n"
    "🚫 E'lon emas: {d.not_ads} / {w.not_ads}\n"
    "⚠️ Shubhali: {d.suspicious} / {w.suspicious}\n"
    "📵 Aloqasiz: {d.no_contact} / {w.no_contact}\n"
    "🪫 Past sifat: {d.low_quality} / {w.low_quality}\n"
    "❌ Xato (qayta ishlash): {d.errors} / {w.errors} · chiqmadi: {d.failed} / {w.failed}\n"
    "⏳ Eskirgan (chiqmadi): {d.skipped_old} / {w.skipped_old}\n\n"
    "📬 Navbat: {queue}{paused}\n"
    "🗂 <b>Kategoriyalar (7 kun, chiqqan)</b>:\n{categories}\n\n"
    "💓 Jarayonlar: {processes}"
)
STATS_NO_CATEGORIES = "—"
PAUSED_MARK = " · ⏸ <b>PAUZA</b>"
PROCESS_OK = "{name} ✅ ({ago})"
PROCESS_STALE = "{name} 🔴 ({ago} jim)"
PROCESS_NEVER = "{name} ⚪️ (hali ishlamagan)"

# ------------------------------------------------------------------ /queue, /failed, /retry
QUEUE_HEAD = (
    "📬 <b>Navbat</b>{paused}\n"
    "Kutmoqda: {queued} · qayta urinish: {retry} · yuborilmoqda: {sending} · chiqmagan: {failed}\n"
    "Hozir chiqishga tayyor: {due}"
)
QUEUE_ITEM = "#{id} {title} — {when}"
QUEUE_EMPTY = "Navbat bo'sh."
QUEUE_NOW = "hozir"
FAILED_HEAD = "❌ <b>Chiqmay qolgan e'lonlar</b> (oxirgi {n} ta):"
FAILED_ITEM = "#{id} {title} — {attempts} urinish\n   <code>{error}</code>"
FAILED_EMPTY = "Chiqmay qolgan e'lon yo'q. 👍"
FAILED_FOOT = "Qayta urinish: /retry &lt;id&gt; yoki /retry all"
RETRY_USAGE = "Ishlatish: /retry 123 yoki /retry 12 15 yoki /retry all"
RETRY_DONE = "🔁 {n} ta e'lon qayta navbatga qo'yildi."
RETRY_NONE = "Bunday chiqmay qolgan e'lon topilmadi."
RETRY_TOO_OLD = "⏳ {n} ta e'lon navbatga qo'yilmadi — {reason} (kanalga chiqmaydi): {ids}"
PAUSED = "⏸ Kanalga joylash to'xtatildi. E'lonlar navbatda yig'iladi. Davom ettirish: /resume"
RESUMED = "▶️ Kanalga joylash davom etmoqda."

# ------------------------------------------------------------------ sources
ADDSOURCE_USAGE = (
    "Ishlatish:\n"
    "/addsource @kanal\n/addsource t.me/kanal\n/addsource t.me/+TaklifHavola (yopiq kanal)\n"
    "/addsource web:hh_uz (kodi yozilgan sayt)\n/addsource rss:https://sayt.uz/feed"
)
ADDSOURCE_BAD = "Tushunmadim: <code>{text}</code>\n\n" + ADDSOURCE_USAGE
ADDSOURCE_RSS_SOON = (
    "📰 RSS manbalar tez orada (Bosqich 16.0). Havolani saqlab qo'ying: <code>{url}</code>"
)
ADDSOURCE_WEB_UNKNOWN = (
    "❌ <code>{key}</code> uchun kod hali yozilmagan. Mavjudlari: {known}.\n"
    "Saytlar Bosqich 16 da qo'shiladi."
)
ADDSOURCE_WEB_ENABLED = (
    "✅ Sayt yoqildi: <code>{key}</code> (har {interval} daqiqada tekshiriladi)."
)
ADDSOURCE_EXISTS = "ℹ️ {ident} allaqachon ro'yxatda va ishlayapti."
ADDSOURCE_REENABLED = "▶️ {ident} ro'yxatda bor edi — qayta yoqildi."
ADDSOURCE_PENDING_ALREADY = "⏳ {ident} allaqachon tekshirilmoqda."
ADDSOURCE_ASK_BACKFILL = (
    "➕ {ident}\nEski postlardan nechtasini olay?\n"
    "<i>Eski postlar bazaga olinadi (dublikat va qidiruv uchun). Kanalga chiqishi: "
    "settings.yaml → publisher.publish_backfill ({publish}).</i>"
)
ADDSOURCE_QUEUED = (
    "⏳ So'rov qabul qilindi: {ident} (eski postlar: {n}).\n"
    "Collector 1–2 daqiqada tekshiradi va natijani shu yerga yozadi."
)
YES = "ha"
NO = "yo'q"

SOURCES_HEAD = "📡 <b>Manbalar</b> ({n} ta) — batafsil uchun bosing:"
SOURCES_EMPTY = "Manba yo'q. Qo'shish: /addsource @kanal"
SOURCE_LINE = "{n}. {icon} {name} — {last}"
SOURCE_ICON_ACTIVE = "✅"
SOURCE_ICON_PAUSED = "⏸"
SOURCE_ICON_PENDING = "⏳"
SOURCE_ICON_REJECTED = "❌"
SOURCE_NEVER = "post yo'q"
SOURCE_CARD = (
    "{icon} <b>{name}</b>\n"
    "Turi: {type} · qo'shilgan: {via}\n"
    "Holati: {state}\n"
    "Oxirgi post: {last_post}\n"
    "Oxirgi tekshiruv: {last_check}\n"
    "Xatolar ketma-ket: {errors}{error}"
    "{interval}"
)
SOURCE_STATE = {
    "active": "ishlayapti",
    "paused": "pauzada",
    "pending": "tekshirilmoqda",
    "rejected": "qo'shilmadi",
}
SOURCE_INTERVAL = "\nTekshirish oralig'i: {m} daqiqa"
SOURCE_PAUSED = "⏸ {name} pauzaga qo'yildi."
SOURCE_RESUMED = "▶️ {name} yoqildi."
SOURCE_DELETE_CONFIRM = "🗑 {name} o'chirilsinmi?\nPostlari bazada qoladi, faqat o'qish to'xtaydi."
SOURCE_DELETED = "🗑 {name} o'chirildi (postlari bazada qoladi)."
SOURCE_RECHECK = "🔁 {name} qayta tekshiruvga yuborildi."
SOURCE_STATS = (
    "📊 <b>{name}</b>\n"
    "Jami post: {s.total} · oxirgi 7 kun: {s.week}\n"
    "E'lon bo'lib chiqdi: {s.jobs} · dublikat: {s.duplicates} · e'lon emas: {s.not_ads}\n"
    "Oxirgi post: {last}"
)
SOURCE_NOT_FOUND = "Manba topilmadi."
B_PAUSE = "⏸ Pauza"
B_RESUME = "▶️ Yoqish"
B_DELETE = "🗑 O'chirish"
B_STATS = "📊 Statistika"
B_BACK = "⬅️ Ro'yxat"
B_CONFIRM_DELETE = "✅ Ha, o'chirish"
B_CANCEL = "✖️ Yo'q"
B_RECHECK = "🔁 Qayta tekshirish"
B_INTERVALS = ((15, "15 daq"), (30, "30 daq"), (60, "1 soat"))

# ------------------------------------------------------------------ images
IMAGES_HEAD = (
    "🖼 <b>Rasmlar</b> (haqiqiy / vaqtinchalik)\n"
    "Kategoriya uchun kamida 3 ta haqiqiy rasm kerak, kasb uchun ixtiyoriy (3–4 ta).\n"
)
IMAGES_CATEGORY = "{icon} <b>{title}</b> <code>{key}</code>: {real} / {placeholder}"
IMAGES_PROFESSIONS_EMPTY = "   kasblar rasmsiz: {names}"
IMAGES_FOOT = "\nQo'shish: /addimage &lt;kasb|kategoriya&gt; · ko'rish: /images &lt;kasb&gt;"
IMAGES_UNKNOWN = "❌ <code>{key}</code> — bunday kasb yoki kategoriya yo'q. Ro'yxat: /images"
IMAGES_FOLDER = "🖼 <b>{title}</b> — <code>{folder}</code>\n{lines}"
IMAGES_FOLDER_EMPTY = "(bo'sh)"
IMAGES_FILE = "{n}. {name}{mark}"
IMAGES_PLACEHOLDER_MARK = " (vaqtinchalik)"
IMAGE_DELETED = "🗑 {name} o'chirildi (nusxasi: <code>{trash}</code>)."
IMAGE_NOT_FOUND = "Fayl topilmadi."
ADDIMAGE_USAGE = "Ishlatish: /addimage oshpaz yoki /addimage oshxona (kategoriya)"
ADDIMAGE_WAIT = (
    "📤 <b>{title}</b> uchun rasm yuboring (bir nechta bo'lsa — bittadan).\n"
    "Papka: <code>{folder}</code>\nTugatish: /cancel"
)
ADDIMAGE_SAVED = (
    "✅ Saqlandi: <code>{path}</code>\nPapkada endi {real} ta haqiqiy rasm. "
    "Keyingi e'londan navbatga qo'shiladi. Yana yuborishingiz mumkin yoki /cancel."
)
ADDIMAGE_NOT_IMAGE = "❌ Bu rasm emas. JPG/PNG rasm yuboring yoki /cancel."
ADDIMAGE_TOO_BIG = "❌ Fayl juda katta ({mb:.0f} MB). 10 MB gacha rasm yuboring."

"""Every text the bot shows, in one place (Uzbek Latin; a Russian version can be added later).

HTML parse mode: values put into these templates must be ``html.escape``-d by the caller.
"""

from __future__ import annotations

# ------------------------------------------------------------------ public: main menu
MENU_POST = "📢 E'lon joylash"
MENU_SEARCH = "🔍 Ish qidirish"
MENU_FAVORITES = "⭐ Saqlanganlar"
MENU_ALERTS = "🔔 Obunalar"
MENU_HELP = "ℹ️ Yordam"
MENU_MY_JOBS = "📋 Mening e'lonlarim"
MENU_PLACEHOLDER = "Bo'limni tanlang"

WELCOME = (
    "Assalomu alaykum, {name}! 👋\n"
    "<b>Ayvona Jobs</b> — O'zbekiston bo'ylab ish e'lonlari. Hammasi bepul.\n\n"
    "📢 <b>E'lon joylash</b> — xodim qidiryapsizmi? E'loningizni kanalga chiqaramiz.\n"
    "🔍 <b>Ish qidirish</b> — kasb, hudud va maosh bo'yicha.\n"
    "⭐ <b>Saqlanganlar</b> — yoqqan e'lonlaringiz.\n"
    "🔔 <b>Obunalar</b> — mos yangi e'lon chiqsa, darhol xabar beraman.\n\n"
    "Barcha e'lonlar: @{channel}"
)
HELP_PUBLIC = (
    "ℹ️ <b>Yordam</b>\n\n"
    "📢 <b>E'lon joylash</b> — bosqichma-bosqich forma. "
    "Aloqa (telefon yoki @username) majburiy. E'lon tekshirilgach kanalga chiqadi.\n"
    "🔍 <b>Ish qidirish</b> — kategoriya → kasb → hudud → maosh, yoki so'z bilan qidirish.\n"
    "⭐ <b>Saqlanganlar</b> — kanal postidagi yoki qidiruvdagi «⭐ Saqlash» tugmasi bilan.\n"
    "🔔 <b>Obunalar</b> — «dasturchi, Toshkent, 5 mln+» kabi obuna; "
    "mos e'lon chiqsa xabar keladi.\n\n"
    "/start — bosh menyu · /cancel — boshlangan amalni bekor qilish\n"
    "Kanal: @{channel}"
)
SOON = "⏳ Bu bo'lim tez orada ishga tushadi."
BANNED = "🚫 Siz botdan foydalana olmaysiz."
THROTTLED = "⏳ Sekinroq, iltimos."

# ------------------------------------------------------------------ public: jobs, favorites
JOB_NOT_FOUND = "😕 E'lon topilmadi yoki hali kanalga chiqmagan."
JOB_CLOSED_MARK = "❌ <b>YOPILGAN</b>\n\n"
SAVED = "⭐ Saqlandi. Ro'yxat: «⭐ Saqlanganlar»."
ALREADY_SAVED = "⭐ Bu e'lon allaqachon saqlangan."
SAVE_CLOSED = "❌ Bu e'lon yopilgan — saqlab bo'lmaydi."
UNSAVED = "Saqlanganlardan olib tashlandi."
BTN_SAVE = "⭐ Saqlash"
BTN_UNSAVE = "✅ Saqlangan"
BTN_SHARE = "📤 Ulashish"
BTN_DETAILS = "Batafsil"
BTN_PREV = "⬅️"
BTN_NEXT = "➡️"
BTN_REMOVE = "🗑 Olib tashlash"
FAV_EMPTY = (
    "⭐ Saqlangan e'lonlar yo'q.\nKanal postidagi yoki qidiruvdagi «⭐ Saqlash» tugmasini bosing."
)
FAV_HEAD = "⭐ <b>Saqlanganlar</b> — {total} ta (sahifa {page}/{pages})"
CARD_CLOSED = " ❌ Yopilgan"

# ------------------------------------------------------------------ public: 📢 E'lon joylash
BTN_BACK = "⬅️ Orqaga"
BTN_CANCEL = "❌ Bekor qilish"
BTN_SKIP = "⏭ O'tkazib yuborish"
BTN_NEGOTIABLE = "🤝 Kelishiladi"
BTN_SEND_PHONE = "📱 Raqamni yuborish"
BTN_MY_USERNAME = "👤 {username} ni ishlatish"
BTN_REMOTE = "🏠 Masofaviy"
BTN_SUBMIT = "✅ Yuborish"
BTN_EDIT = "✏️ Tahrirlash"
POST_INTRO = (
    "📢 <b>E'lon joylash</b>\n"
    "Bir necha savolga javob bering — e'lon kanalga chiroyli shaklda chiqadi.\n"
    "Istalgan paytda: «{back}» yoki «{cancel}»."
)
# The "n/total." prefix of every question is added by the form (bot/handlers/post_job.py).
POST_ASK_CATEGORY = "Qaysi soha? 👇"
POST_ASK_TITLE = "Lavozim nomi? (masalan: <i>Sotuvchi</i>, <i>Buxgalter</i>)"
POST_ASK_COMPANY = "Kompaniya yoki do'kon nomi? (ixtiyoriy)"
POST_ASK_SALARY = (
    "Maosh? (masalan: <i>4-6 mln so'm</i>, <i>5 000 000 so'mdan</i>, <i>500$</i>)\n"
    "yoki «{negotiable}»."
)
POST_ASK_REGION = "Hudud? 👇"
POST_ASK_CITY = "Shahar / tuman / mo'ljal? (masalan: <i>Chilonzor tumani</i>; ixtiyoriy)"
POST_ASK_SCHEDULE = "Ish vaqti? (masalan: <i>9:00-18:00, 5/2</i>; ixtiyoriy)"
POST_ASK_REQUIREMENTS = "Talablar va qo'shimcha ma'lumot? (ixtiyoriy)"
POST_ASK_CONTACT = (
    "<b>Aloqa — majburiy.</b>\n"
    "«{phone}» tugmasini bosing yoki yozing: <i>+998 90 123 45 67</i> yoki <i>@username</i>."
)
POST_ASK_DURATION = (
    "<b>E'lon necha kun faol tursin?</b> 👇\n"
    "Muddat kanalga chiqqan paytdan hisoblanadi. Tugashiga yaqin eslatma yuboraman — "
    "xohlasangiz uzaytirasiz."
)
BTN_DAYS = "{n} kun"
POST_PREVIEW_DAYS = "⏳ Faol muddat: <b>{n} kun</b> (kanalga chiqqan paytdan)"
POST_NEED_BUTTON = "👆 Tugmalardan birini tanlang."
POST_TOO_LONG = "✂️ Juda uzun yoki bo'sh. Ko'pi bilan {limit} belgi yozing."
POST_TOO_SHORT = "Lavozim nomini to'liqroq yozing (kamida 3 harf)."
POST_NO_CONTACT = (
    "❗️ Aloqa topilmadi. O'zbekiston raqami (+998...) yoki Telegram @username kerak — "
    "aloqasiz e'lon qabul qilinmaydi."
)
POST_PREVIEW_HEAD = "👀 <b>Kanalda shunday ko'rinadi:</b>"
POST_PREVIEW_ASK = "Hammasi to'g'rimi?"
POST_EDIT_WHICH = "Nimani o'zgartiramiz?"
POST_FIELDS = {
    "category": "Soha",
    "title": "Lavozim",
    "company": "Kompaniya",
    "salary": "Maosh",
    "region": "Hudud",
    "city": "Manzil",
    "schedule": "Ish vaqti",
    "requirements": "Talablar",
    "contact": "Aloqa",
    "duration": "Muddat",
}
POST_EXPIRED = "Forma eskirdi. «📢 E'lon joylash» ni qayta bosing."
POST_QUEUED = (
    "✅ Qabul qilindi! E'loningiz bir necha daqiqada kanalga chiqadi — havolasini yuboraman."
)
POST_REVIEW = "🕵️ E'loningiz qabul qilindi va tekshiruvga yuborildi. Natijasini shu yerga yozaman."
POST_REJECTED = "🚫 E'lon qabul qilinmadi: taqiqlangan so'zlar yoki spam belgilari bor."
POST_DUPLICATE = "♻️ Bunday e'lon yaqinda chiqqan — takror yuborilmaydi."
POST_LIMIT_DAILY = "⏳ Bir kunda ko'pi bilan {n} ta e'lon yuborish mumkin. Ertaga urinib ko'ring."
POST_LIMIT_INTERVAL = "⏳ E'lonlar orasida {total} daqiqa bo'lishi kerak. {left} daqiqadan keyin."
POST_LIMIT_WAITING = (
    "⏳ Oldingi e'loningiz hali tekshiruvda yoki navbatda. U chiqqach, yangisini yuboring."
)
POST_APPROVED_USER = "✅ E'loningiz tasdiqlandi va tez orada kanalga chiqadi."
POST_REJECTED_USER = "❌ Afsuski, e'loningiz tasdiqlanmadi (kanal qoidalariga mos emas)."
POST_PUBLISHED_USER = "📢 E'loningiz kanalga chiqdi: {url}"

# ------------------------------------------------------------------ public: 🔍 Ish qidirish
SEARCH_ASK_CATEGORY = "🔍 <b>Ish qidirish</b>\nQaysi soha? 👇"
SEARCH_ASK_PROFESSION = "🔍 {category}\nQaysi kasb? 👇"
SEARCH_ASK_REGION = "🔍 {summary}\nQaysi hudud? 👇"
SEARCH_ASK_SALARY = "🔍 {summary}\nMaosh (oyiga)? 👇"
SEARCH_ASK_KEYWORD = (
    "🔤 Qidiriladigan so'zni yozing (masalan: <i>oshpaz</i>, <i>sotuv menejeri</i>, "
    "<i>python</i>). Lotin yoki kirill — farqi yo'q."
)
SEARCH_BAD_KEYWORD = "Kamida 2 harfli so'z yozing."
SEARCH_ALL = "Hammasi"
SEARCH_ANY_SALARY = "Farqi yo'q"
SEARCH_SALARY_STEP = "{mln} mln+"
SEARCH_BY_WORD = "🔤 So'z bilan qidirish"
SEARCH_LAST = "🔁 Oxirgi qidiruv"
SEARCH_NEW = "🔄 Yangi qidiruv"
SEARCH_HEAD = (
    "🔍 <b>Natijalar</b>: {total} ta · {summary}\n(sahifa {page}/{pages}, eng yangisi tepada)"
)
SEARCH_EMPTY = "😕 {summary} bo'yicha hozircha e'lon yo'q.\nFiltrlarni kengaytirib ko'ring."
SEARCH_EVERYTHING = "barcha e'lonlar"
SEARCH_EXPIRED = "Qidiruv eskirdi — «🔍 Ish qidirish» ni qayta bosing."

# ------------------------------------------------------------------ public: 🔔 Obunalar
SUBS_HEAD = "🔔 <b>Obunalar</b> ({n}/{max})\nMos yangi e'lon kanalga chiqishi bilan xabar beraman."
SUBS_EMPTY = (
    "🔔 <b>Obunalar</b>\nHali obuna yo'q. Masalan: «Oshpaz, Toshkent sh., 4 mln+» — shunday e'lon "
    "chiqishi bilan xabar beraman."
)
SUBS_ITEM = "{n}. {summary} — {state}"
SUBS_ACTIVE = "✅ faol"
SUBS_PAUSED = "⏸ pauza"
SUBS_NEW = "➕ Yangi obuna"
SUBS_PAUSE = "⏸ {n}"
SUBS_RESUME = "▶️ {n}"
SUBS_DELETE = "🗑 {n}"
SUBS_FROM_SEARCH = "🔔 Shu qidiruvga obuna bo'lish"
SUBS_ASK_CATEGORY = "🔔 <b>Yangi obuna</b>\nQaysi soha? 👇"
SUBS_ASK_KEYWORD = (
    "🔔 {summary}\nQo'shimcha kalit so'z? (masalan: <i>python</i>, <i>ingliz tili</i>) "
    "yoki «{skip}»."
)
SUBS_CREATED = "✅ Obuna yaratildi: {summary}\nMos e'lon chiqishi bilan xabar beraman."
SUBS_LIMIT = "Ko'pi bilan {max} ta obuna bo'lishi mumkin. Keraksizini 🗑 bilan o'chiring."
SUBS_DUPLICATE = "Bunday obuna allaqachon bor."
SUBS_EMPTY_FILTERS = "Obuna uchun kamida bitta filtr (soha, hudud, maosh yoki so'z) tanlang."
SUBS_PAUSED_OK = "⏸ Obuna to'xtatildi."
SUBS_RESUMED_OK = "▶️ Obuna yoqildi."
SUBS_DELETED_OK = "🗑 Obuna o'chirildi."
ALERT_HEAD = "🔔 <b>Yangi e'lon</b> — obunangiz: {summary}\n\n"
ALERT_STOP = "🔕 Obunani to'xtatish"
DIGEST_HEAD = (
    "📬 <b>Obunalaringiz bo'yicha yana {n} ta e'lon</b> (bugungi limitdan keyin chiqqanlar):"
)

# ------------------------------------------------------------------ public: 📋 Mening e'lonlarim
MY_EMPTY = "📋 Sizda hali e'lon yo'q. «📢 E'lon joylash» bilan qo'shing."
MY_HEAD = "📋 <b>Mening e'lonlarim</b> (oxirgi {n} ta):"
MY_ITEM = "{n}. <b>{title}</b> — {state}"
MY_STATES = {
    "pending_review": "🕵️ tekshiruvda",
    "queued": "⏳ navbatda",
    "retry": "⏳ navbatda",
    "sending": "⏳ chiqmoqda",
    "published": "✅ kanalda, {until} gacha qidiruvda",
    "closed": "❌ yopilgan",
    "expired": "⌛ muddati tugagan",
}
BTN_MY_CLOSE = "✅ Ish topildi {n}"
BTN_MY_EXTEND = "🔄 Uzaytirish {n}"
MY_CLOSE_CONFIRM = (
    "«{title}» e'lonini yopamizmi?\nKanal postiga «❌ YOPILDI» yoziladi, tugmalari olinadi, "
    "qidiruvdan chiqadi."
)
BTN_YES_CLOSE = "✅ Ha, yopish"
BTN_NO = "↩️ Yo'q"
MY_CLOSED = "✅ E'lon yopildi. Omad!"
MY_CLOSE_FAIL = "Bu e'lonni hozir yopib bo'lmaydi (allaqachon yopilgan yoki kanalga chiqmoqda)."
MY_EXTENDED = "🔄 Uzaytirildi: {until} gacha qidiruvda."
MY_EXTEND_FAIL = "Bu e'lonni uzaytirib bo'lmaydi."
REMIND_TEXT = "⏳ «{title}» e'loningiz {until} da qidiruvdan chiqadi. Uzaytirasizmi?"
BTN_REMIND_EXTEND = "🔄 Uzaytirish (+{days} kun)"
BTN_REMIND_CLOSE = "✅ Ish topildi, yopish"

# ------------------------------------------------------------------ admin: extended
STATS_EXTRA = (
    "\n\n👥 Foydalanuvchilar: {users} (bugun yangi: {new_today}, 7 kunda faol: {active})\n"
    "🔔 Faol obunalar: {subs} · 📢 Foydalanuvchi e'lonlari (7 kun): {user_jobs}\n"
    "🔍 Ko'p qidirilgan sohalar (7 kun): {categories}\n"
    "📍 Ko'p qidirilgan hududlar (7 kun): {regions}\n"
    "📡 Manbalar (7 kun, kanalga chiqqan):\n{sources}"
)
ADDWORD_USAGE = "Ishlatish: /addword ban|spam|scam so'z yoki ibora"
ADDWORD_OK = "✅ Qo'shildi ({kind}): {word}"
ADDWORD_EXISTS = "Bu so'z allaqachon bor."
DELWORD_USAGE = "Ishlatish: /delword so'z yoki ibora"
DELWORD_OK = "🗑 O'chirildi: {word}"
DELWORD_NONE = "Bunday so'z topilmadi (filters.yaml dagilar faqat faylda o'zgaradi)."
WORDS_HEAD = "🧾 <b>Qo'shimcha filtr so'zlari</b> (filters.yaml dan tashqari):"
WORDS_EMPTY = "Qo'shimcha so'z yo'q. Qo'shish: /addword ban|spam|scam so'z"
BAN_USAGE = "Ishlatish: /ban 123456789 yoki /ban @username (xuddi shunday /unban)"
BAN_OK = "🚫 Bloklandi: {who}"
UNBAN_OK = "✅ Blokdan chiqarildi: {who}"
BAN_NOT_FOUND = "Foydalanuvchi topilmadi (@username faqat botga yozgan bo'lsa topiladi)."
BAN_ADMIN = "Adminni bloklab bo'lmaydi."
BROADCAST_USAGE = (
    "Ishlatish: /broadcast xabar matni (Telegram'dagi qalin / kursiv / havola formatlari saqlanadi)"
)
BROADCAST_CONFIRM = (
    "📣 Shu xabar <b>{n}</b> ta foydalanuvchiga yuboriladi:\n➖➖➖➖➖➖➖➖\n{text}"
)
BROADCAST_STARTED = "📣 Yuborish boshlandi: {n} ta, sekundiga {rate} ta. Tugagach yozaman."
BROADCAST_DONE = "📣 Tayyor: {ok} ta yuborildi, {failed} tasiga yetmadi (botni bloklagan va h.k.)."
BROADCAST_EXPIRED = "Xabar eskirdi — /broadcast ni qayta yozing."
BROADCAST_BAD_HTML = "HTML xato: {error}"

# ------------------------------------------------------------------ admin: 🤖 /ai
AI_STATUS = (
    "🤖 <b>Gemini yordamchi</b>\n"
    "Holat: {state}\n"
    "Model: <code>{model}</code> · kalitlar: {keys}{rotation}\n"
    "Bugun: {calls}/{limit} so'rov (✅ {ok}, ❌ {failed}), keshdan: {cache_hits}\n"
    "Keshda jami: {cached_total} ta javob{paused}\n\n"
    "<i>Faqat ishonchi past yoki ruscha/inglizcha e'lonlar uchun ishlatiladi. "
    "Xato bo'lsa — regex.</i>"
)
AI_ON = "✅ ishlayapti"
AI_OFF_ADMIN = "⏸ admin o'chirgan"
AI_NO_KEY = "⚪️ kalit yo'q (.env → GEMINI_API_KEY) — hammasi regex bilan"
AI_OFF_CONFIG = "⚪️ settings.yaml da o'chiq (ai.enabled: false)"
AI_ROTATION = " (aylanish YOQILGAN)"
AI_PAUSED = "\nDam olayotgan kalitlar: {list}"
BTN_AI_ON = "▶️ Yoqish"
BTN_AI_OFF = "⏸ O'chirish"
STATS_AI = "\n🤖 AI bugun: {calls}/{limit} so'rov · /ai"

# ------------------------------------------------------------------ admin: moderation
MOD_HEAD = (
    "🆕 <b>Yangi e'lon — tekshiring</b> (#{id})\n"
    "Muallif: {author}\nSabab: {reasons}\n⏳ Faol muddat: <b>{days}</b>\n➖➖➖➖➖➖➖➖\n"
)
MOD_OK = "✅ Tasdiqlash"
MOD_NO = "❌ Rad etish"
MOD_BAN = "🚫 Ban"
MOD_DONE_PUBLISHED = "\n\n✅ <b>Tasdiqlandi va kanalga chiqdi</b> ({admin})"
MOD_DONE_QUEUED = (
    "\n\n✅ <b>Tasdiqlandi</b> ({admin}) — kanalga hozir chiqmadi, navbatga qo'yildi "
    "(yo'qolmaydi; sababi logda)"
)
MOD_DONE_NO = "\n\n❌ <b>Rad etildi</b> ({admin})"
MOD_DONE_BAN = "\n\n🚫 <b>Rad etildi, muallif bloklandi</b> ({admin})"
MOD_ALREADY = "Bu e'lon allaqachon ko'rib chiqilgan."
SALARY_NEGOTIABLE = "Kelishiladi"
REMOTE = "Masofaviy"

# ------------------------------------------------------------------ admin: general
ADMIN_HELP = (
    "🛠 <b>Admin buyruqlari</b>\n\n"
    "📊 /stats — bugun va hafta: keldi, chiqdi, dublikat, xato, kategoriyalar\n"
    "📬 /queue — navbat (kanalga chiqishini kutayotganlar)\n"
    "❌ /failed — chiqmay qolgan e'lonlar\n"
    "🔁 /retry &lt;id | all&gt; — chiqmay qolganini qayta navbatga\n"
    "⏸ /pause — kanalga joylashni to'xtatish · ▶️ /resume — davom ettirish\n\n"
    "🧾 /addword ban|spam|scam so'z · /delword so'z · /words — filtr so'zlari\n"
    "🚫 /ban &lt;id | @username&gt; · /unban — foydalanuvchini bloklash\n"
    "📣 /broadcast matn — hamma foydalanuvchilarga (tasdiqlash bilan)\n"
    "🤖 /ai — Gemini yordamchi: holat, bugungi so'rovlar, yoqish/o'chirish\n\n"
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
    "📬 Navbat: {queue} ta{eta}{paused}{quiet}\n"
    "🗂 <b>Kategoriyalar (7 kun, chiqqan)</b>:\n{categories}\n\n"
    "💓 Jarayonlar: {processes}"
)
STATS_NO_CATEGORIES = "—"
PAUSED_MARK = " · ⏸ <b>PAUZA</b>"
QUEUE_ETA = ", taxminan {eta}da chiqadi"
ETA_MINUTES = "{n} daqiqa"
ETA_HOURS = "{n} soat"
QUIET_MARK = "\n🌙 Tungi tanaffus ({span}): {until} gacha kanalga chiqmaydi"
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
    "/addsource rss:https://sayt.uz/feed (istalgan RSS/Atom lenta)\n"
    "/addsource web:nom — kodi yozilgan sayt: web:himalayas, web:remotive, web:jobicy, "
    "web:remoteok, web:osonish, web:hh_uz"
)
ADDSOURCE_BAD = "Tushunmadim: <code>{text}</code>\n\n" + ADDSOURCE_USAGE
ADDSOURCE_RSS_FOUND = (
    "📰 <b>{title}</b>\n<code>{url}</code>\nLentada hozir {n} ta yozuv. Qo'shilsinmi?\n"
    "<i>Ish e'loni bo'lmagan yozuvlarni filtr o'tkazib yuboradi. Birinchi tekshiruvdagi eski "
    "yozuvlar kanalga chiqmaydi.</i>"
)
ADDSOURCE_RSS_BAD = "❌ Lentani o'qib bo'lmadi: {error}"
ADDSOURCE_RSS_ADDED = "✅ RSS qo'shildi: <b>{title}</b> (har {interval} daqiqada tekshiriladi)."
ADDSOURCE_RSS_EXPIRED = "So'rov eskirdi — /addsource rss:<URL> ni qayta yozing."
B_ADD = "✅ Qo'shish"
ADDSOURCE_WEB_UNKNOWN = "❌ <code>{key}</code> uchun kod yo'q. Mavjudlari: {known}."
ADDSOURCE_WEB_NEEDS = "❌ <code>{key}</code> hozir yoqilmaydi: {reason}"
ADDSOURCE_WEB_ENABLED = (
    "✅ Sayt yoqildi: <b>{title}</b> <code>{key}</code> "
    "(har {interval} daqiqada tekshiriladi).{note}"
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
SOURCE_SITE_MINIMUM = " (sayt shartlari: kamida {m} daqiqa — shunday tekshiriladi)"
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

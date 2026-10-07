# STATUS — Ayvona Jobs (2026-10-07): tasdiqlash, ustuvorlik, Loyihalar, rasmlar

Branch `feature/moderation-ranking-projects` → `main`. Serverda ishlayotgan loyiha ustida 6 ta imkoniyat qo'shildi;
**haqiqiy Telegram, haqiqiy sessiya, token va Gemini ishlatilmadi** — hammasi soxta Bot API, soxta stok-API va bazaning
nusxasida sinaldi. To'liq buyruqlar: [DEPLOY.md](DEPLOY.md) 6a-bo'lim.

## 1. Nima o'zgardi

| # | Imkoniyat | Commit | Asosiy fayllar |
|---|---|---|---|
| 1 | Tasdiqlansa e'lon **darhol** kanalga chiqadi (navbatsiz, ikki marta emas) | `5afefc0` | `services/job_submission.py` (`approve(publish_now)`), `publisher/outbox.py` (`publish_claimed`), `bot/moderation.py`, `db/repositories/jobs_repo.py` |
| 2 | Admin faqat "yangi e'lon tasdiqlash" so'rovini oladi | `84d040e` | `services/notifier.py`, `config.py` (`ADMIN_EXTRA_NOTIFICATIONS`), `apps/{bot,collector,worker}.py` |
| 3 | "E'lon necha kun faol tursin?" (3/7/14/30) | `0df52fe` | `bot/handlers/post_job.py`, `services/lifetime.py`, `services/expiry.py`, `services/my_jobs.py`, migratsiya `c9e1a4b7d2f5` |
| 4 | Ustuvorlik (1/2/3-daraja) | `30e50ce` | `processing/priority.py`, `services/priority_backfill.py`, `scripts/backfill_priority.py`, `publisher/outbox.py`, `services/search.py`, `bot/handlers/admin.py` (`/why`), `config/settings.yaml → priority:`, migratsiya `d1f5b8c3a7e2` |
| 5 | 🧩 Loyihalar | `30e50ce` | `processing/project_format.py`, `services/projects.py`, `bot/handlers/projects.py`, `bot/handlers/post_job.py`, migratsiya `e2a6c9d4b8f1` |
| 6 | `/images review` — rasmlarni birma-bir yangilash | `f1262a1` | `services/image_review.py`, `processing/image_gen.py`, `bot/handlers/admin_images.py`, `config/image_queries.yaml` |
| – | Hujjatlar | `432dbbd` | `DEPLOY.md`, `README.md`, `CLAUDE.md`, `docs/PROGRESS.md`, `.env.example` |

(4 va 5 bitta commit: ikkalasi `models.py`, `config.py`, `texts.py`, `job_submission.py` va migratsiya zanjirini bo'lishadi.)

**1. Tasdiqlash = darhol joylash.** Admin "✅" bossa e'lon bitta shartli UPDATE bilan `pending_review → sending` ga o'tadi
(shu paytda uni bitta jarayon "egallaydi"), keyin bot o'sha zahoti kanalga yuboradi → `published`. Navbatga tushmaydi. Ikki
marta bosish, ikkinchi admin yoki bir vaqtda to'rt marta bosish — kanalda bitta post (testlarda tekshirilgan). Rad etilgan
e'lon hech qachon chiqmaydi. Telegram xato bersa e'lon navbatga qaytadi (yo'qolmaydi), admin xabarida "navbatga qo'yildi"
yoziladi. 10 daqiqadan beri `sending` turgan e'lonni (bot o'sha paytda o'chgan) worker qayta navbatga qo'yadi.

**2. Admin xabarlari.** `Notifier` o'zi yubormoqchi bo'lgan hamma narsani (xatolar, jim qolgan jarayon, backup fayli,
shubhali postlar, "kanalga chiqmadi") faqat logga yozadi (`journalctl`, `data/logs/`). `ADMIN_EXTRA_NOTIFICATIONS=true`
bo'lsa — eskicha. Admin o'zi yozgan buyruqlar (`/stats`, `/queue`, `/why` ...) odatdagidek javob beradi.

**3. Muddat.** Forma oxirida (aloqadan keyin) inline tugmalar: 3 / 7 / 14 / 30 kun (`posting.duration_options`).
Admin so'rovida "Faol muddat: 7 kun" ko'rinadi. Hisob kanalga chiqqan paytdan: `expires_at = chiqqan payt + kun`. Mavjud
"Uzaytirasizmi?" mexanizmi ishlatiladi (`reminded_at` o'sha; yangi mexanizm yo'q). Muddati o'tgan e'lon qidiruvdan chiqadi.

**4. Ustuvorlik.** Qoidaga asoslangan (AI yo'q): eng kuchli "yuqori" qoida (kasb +3 / sarlavhadagi so'z +2 / soha +1) +
eng yomon "past" qoida (oddiy kasb/so'z −3, yumshoq −1) + maosh (butun oraliq ≥ 8 mln so'm/oy: +3; < 2,5 mln: −1).
Ball ≥ 2 → 1-daraja, ≤ −2 → 3-daraja. Hamma ro'yxat va raqamlar `config/settings.yaml → priority:` da (lotin, kirill, ruscha,
inglizcha). Navbat: daraja → eng yangisi; yaxshi e'lonni arzon e'lonlar to'dasi siqib chiqara olmaydi (testlangan: 60 ta
3-daraja + 1 ta 1-daraja → birinchi 1-daraja). 3-daraja kuniga ≤ 40, 12 soatdan keyin eskiradi; 1-daraja 48 soat yashaydi
(oddiy: avvalgidek 24). Qidiruvda ham daraja birinchi. Sabab: `/why <id>` (faqat so'ralganda) va logda `job #N: daraja ...`.

**5. 🧩 Loyihalar.** «📢 E'lon joylash» avval "💼 Ish / 🧩 Loyiha" deb so'raydi. Loyiha: nomi → tavsif → byudjet (bir martalik,
summa + valyuta, "Kelishiladi" mumkin) → muddat (o'tkazib yuborsa bo'ladi) → aloqa (majburiy) → faol muddat → ko'rik. Tasdiqlash,
darhol joylash va muddat savoli — ishlar bilan bir xil. Kanalda `🧩 LOYIHA`, "💰 Byudjet: … (bir martalik)", `#loyiha`; ish
postidan farq qiladi. Botda «🧩 Loyihalar» (5 tadan, yangisi birinchi) va kanal postidagi "🧩 Boshqa loyihalar" tugmasi
(`?start=projects`). Loyiha ustuvorlikka kirmaydi (2-daraja, eng yangisi birinchi), ish qidiruvi, obuna, sayt va kategoriya statistikasida
ko'rinmaydi (`/stats` dagi umumiy "kanalga chiqdi" soniga esa kiradi). Alohida kanal ochilmadi.

**6. Rasmlar.** Hozir postlar ishlatadigan rasmlar: `assets/images/` da **249 fayl, hammasi vaqtinchalik (placeholder), haqiqiy
rasm 0 ta** (19 kategoriya + 64 kasb papkasi × 3). `/images review` (eski `/images` o'zgarmadi) shu 249 o'rinni birma-bir
ko'rsatadi: hozirgi rasm + taklif, [✅ Tasdiqlash] [🔄 Boshqasi] [⏭ O'tkazish] [⏹ To'xtatish]. Manba: kalit bor bo'lsa Pexels →
Unsplash → Pixabay (faqat rasmiy API, faqat o'z CDN manzillaridan, 1280×720 ga qirqiladi, "Ayvona" chizig'i qo'yiladi); kalit
yo'q yoki natija tugasa — o'zimiz Pillow bilan chizgan original rasm (18 ta belgi, har variant boshqacha). Tasdiqlanmaguncha
hech narsa o'zgarmaydi; haqiqiy rasm almashtirilsa eskisi `data/images_backup/` ga ko'chiriladi; manba/litsenziya/muallif
rasm yonidagi `<nom>.json` ga yoziladi. Jarayon `kv_store` da saqlanadi (to'xtatib, keyin davom ettirsa bo'ladi).

## 2. Qabul qilgan qarorlarim

- **Tasdiqlangan e'lon tungi tanaffusda ham darhol chiqadi** (siz aytganingizdek) va 5 daqiqalik oraliqqa qaramaydi; `/pause`
  esa ushlab turadi (e'lon navbatda kutadi). Admin o'zi yozgan e'lon tasdiqlashsiz navbatga tushadi (avvalgidek).
- **`posting.moderation: suspicious_only` o'zgarmadi** → tasdiqlashga faqat yangi foydalanuvchining 1-e'loni va shubhali e'lonlar
  keladi, qolganlari navbat orqali (endi ustuvorlik bilan) chiqadi. Hammasi tasdiqlansin desangiz: `all` (bitta qator).
- **`/addsource` natijasi adminga baribir keladi** (u adminning o'z buyrug'iga javob). Backup fayli esa endi **yuborilmaydi** —
  serverdan tashqaridagi nusxani qo'lda olasiz (DEPLOY.md 8-bo'lim). `scripts/backup_now.py --send` (siz yozgan buyruq) yuboradi.
- Muddat: 3/7/14/30 (o'zgartirsa bo'ladi), hisob kanalga chiqqan paytdan. Qisqa e'londa eslatma umrining 1/3 qismida
  (3 kun → 1 kun oldin, 7+ kun → 2 kun oldin).
- Ustuvorlik: **Gemini ishlatilmadi** (qoidalar yetarli, bepul limit saqlanadi); maosh chegarasi 8 mln / 2,5 mln; USD kursi
  zaxira qiymati (12 800) bilan; faqat sarlavha/kasb/soha ko'riladi (tavsif emas). "Sotuvchi" va "Kassir" — yumshoq (−1, oddiy
  daraja), "sotuvchi-kassir" — 3-daraja; "Operator" — 3-daraja. Bir darajada **eng yangisi birinchi** (avval — kelgan tartib):
  `priority.within_tier: oldest` qaytaradi, `priority.enabled: false` — butunlay eski tartib.
- 3-daraja kunlik chegarasiga faqat kanal manbalari sanaladi (foydalanuvchi e'lonlari emas). Foydalanuvchi e'lonlari yoshi
  bo'yicha hech qachon "eskirgan" bo'lmaydi (avvalgidek).
- Loyiha: alohida jadval emas, `jobs.kind` ustuni; byudjet matni `salary_text` da, summa/valyuta alohida; muddat ixtiyoriy;
  kategoriya "boshqa" (rasm shu papkadan); tavsif ≤ 700 belgi; limitlar ishlar bilan umumiy (kuniga 2, bir vaqtda 1);
  tur o'zgartirilsa javoblar boshidan boshlanadi.
- Rasmlar: har papkada 3 ta o'rin; tartib — kategoriyalar, keyin ko'p uchraydigan kasblar, keyin qolganlari; vaqtinchalik
  rasm o'rni almashtirilganda uning yoniga **haqiqiy fayl** qo'shiladi (vaqtinchalisi qoladi, haqiqiy rasm o'zi ustun turadi);
  stok-rasm boshqa o'ringa qayta taklif qilinmaydi; tugma bosilishi aynan o'sha taklifga bog'langan.
- Yangi kutubxona qo'shilmadi; xotira: import hajmi o'zgarmadi (bot 196, worker 188, collector 86, web 61 MB).

## 3. Migratsiya haqida

Uchta **additiv** migratsiya (hammasi `ADD COLUMN`; mavjud ma'lumotga tegilmaydi): `c9e1a4b7d2f5` (`jobs.active_days`),
`d1f5b8c3a7e2` (`priority_tier/score/reason` + indeks), `e2a6c9d4b8f1` (`kind` — `server_default 'job'`, `budget_amount`,
`budget_currency`, `deadline_text` + indeks). Eski e'lonlarda yangi ustunlar bo'sh (`kind='job'`); ustuvorlikni worker birinchi
yonishda to'ldiradi.

**Sinov — haqiqiy bazaning nusxasida** (`D:\Coding projects\ayvona\data\ayvona.db` dan faqat o'qib olingan nusxa; ⚠️ bu
**kompyuterdagi eski nusxa**, serverdagi jonli baza emas — unga kira olmayman): yuqoriga, pastga (`b8d4f0a2c6e9` gacha) va yana
yuqoriga — hammasi muvaffaqiyatli, `integrity_check` ok.

| jadval | oldin | keyin |
|---|---|---|
| sources / raw_posts / jobs | 20 / 1306 / 340 | 20 / 1306 / 340 |
| images / kv_store / jobs_fts | 69 / 57 / 340 | 69 / 57 / 340 |
| users / subscriptions / favorites | 0 / 0 / 0 | 0 / 0 / 0 |

Kompyuterdagi nusxada foydalanuvchilar yo'q, shuning uchun **jonli ishlatishga o'xshash** nusxa ham yasab sinadim (3 foydalanuvchi,
2 obuna, 1 sevimli, 1 xabarnoma, 3 ta foydalanuvchi e'loni: chiqqan / tekshiruvda / yopilgan): yangilangandan keyin
**har bir mavjud qator bayt-bayt bir xil** (jadvallar bo'yicha qatorlar soni va xesh teng), `kind` hammasida `job`.
Ustuvorlikni shu nusxada `backfill_priority.py` bilan sinadim: 340 e'londan 126 ta 1-daraja, 131 ta 2-daraja, 83 ta 3-daraja.

## 4. Serverga qo'yish

```bash
# 🐧 server (ubuntu) — git pull, baza zaxirasi, kutubxonalar, MIGRATSIYA, restart: hammasini deploy.sh qiladi
sudo bash /home/ayvona/ayvona/scripts/deploy.sh
sudo bash /home/ayvona/ayvona/scripts/healthcheck.sh                 # 1–2 daqiqadan keyin
journalctl -u ayvona-worker -n 60 --no-pager | grep -iE "ustuvorlik|xato|error"
sudo -iu ayvona bash -c 'cd ~/ayvona && .venv/bin/alembic current'   # e2a6c9d4b8f1 (head)
```

`.env` ga hech narsa qo'shish shart emas (ixtiyoriy: `ADMIN_EXTRA_NOTIFICATIONS`, `PEXELS_API_KEY`, `UNSPLASH_ACCESS_KEY`,
`PIXABAY_API_KEY`). Orqaga qaytish (kod + baza) — DEPLOY.md 6a: eski kod yangi bazada ishga **tushmaydi**, shuning uchun
`alembic downgrade b8d4f0a2c6e9` + `git reset --hard 5e15946` yoki deploy oldidagi zaxirani tiklash.

## 5. Test natijalari va qo'lda tekshirish

- `pytest`: **1027 ta test o'tdi** (oldin 874); `ruff check` toza; butun repo `ruff format` bilan formatlangan.
- Yangi testlar: darhol joylash (ikki marta bosish, bir vaqtdagi bosishlar, Telegram xatosi, flood, `/pause`, tungi tanaffus, yopishib
  qolgan `sending`), admin xabarlari, muddat/eslatma/uzaytirish, ustuvorlik (60+ holat), navbat tartibi va "to'da" holati,
  3-daraja chegarasi, darajali eskirish, qidiruv tartibi, backfill, `/why`, loyiha formasi, byudjet, post matni, ro'yxat,
  qidiruv/sayt/obunadan chetda ekani, rasm generatori, stok-API'lar (soxta), tasdiqlash/zaxira/litsenziya fayli, tugmalar.
- **Siz qo'lda tekshiring** (haqiqiy Telegram'da, ikkinchi akkaunt bilan — birinchi e'loni tekshiruvga tushadi):
  1. «📢 E'lon joylash» → 💼 Ish → … → muddat → yuborish; sizga "Yangi e'lon — tekshiring" kelishi (muddat va tur ko'rinsin);
     «✅» bossangiz e'lon **zahoti** kanalda va muallifga havola.
  2. Xuddi shu «🧩 Loyiha» bilan: kanaldagi post `🧩 LOYIHA … #loyiha`; botda «🧩 Loyihalar» ro'yxatida; "🧩 Boshqa loyihalar" tugmasi.
  3. Admin: `/queue` (daraja ko'rinadi), `/why <id>`; birinchi soatda `journalctl -u ayvona-worker` da "Ustuvorlik hisoblandi".
  4. `/images review` — birinchi taklif rasm sifatini ko'ring (haqiqiy Telegram'da `edit_media` bilan "Boshqasi" ishlashini ham).
  5. Xatolar endi Telegram'ga **kelmaydi**: kunda bir `healthcheck.sh` ni ishga tushiring yoki `journalctl` ni qarang.

## 6. Qolgan risklar

- **Sinalmaganlar:** haqiqiy Telegram (rasm yuklash, `edit_media`, darhol joylash tezligi) va haqiqiy Pexels/Unsplash/Pixabay
  (javob shakllari rasmiy hujjatdan olingan, kalitsiz sinalmagan; Unsplash demo-kalit soatiga ~50 so'rov bilan cheklangan).
- **Jim xatolar:** admin chatga xato kelmagani uchun (masalan bot kanaldan chiqarilsa) buni faqat log/`healthcheck.sh` ko'rsatadi.
  Xohlasangiz `ADMIN_EXTRA_NOTIFICATIONS=true`.
- **Serverdan tashqaridagi zaxira endi qo'lda** (Telegram'ga yuborilmaydi) — haftada bir nusxa oling, aks holda server yo'qolsa
  faqat kompyuterdagi eski baza qoladi.
- **Ustuvorlik sozlamasi taxminiy:** kompyuterdagi nusxada e'lonlarning 37% i 1-daraja chiqdi — ko'p. Kerak bo'lsa
  `tier1_at: 3` yoki ro'yxatni qisqartiring (`/why` bilan tekshirib), so'ng `scripts/backfill_priority.py --all`. 3-daraja
  kuniga 40 ta va 12 soat — navbat uzun bo'lsa arzon e'lonlarning ko'pi kanalga chiqmaydi (bazada qoladi, `skipped_old`).
- **Birinchi deploy'da navbat:** worker yonganda eski navbat qayta baholanadi va 3-daraja uchun yangi 12 soatlik chegara
  darhol qo'llanadi — 12 soatdan eski arzon e'lonlar `skipped_old` bo'ladi (kutilgan).
- **Ikki marta chiqish ehtimoli (juda kam):** tasdiqlashdan so'ng bot aynan joylash paytida o'chsa, e'lon 10 daqiqadan keyin
  qayta navbatga tushadi; Telegram qabul qilgan bo'lsa — bitta takror (avvalgi "kamida bir marta" qoidasi).
- Stok-rasmlar litsenziyasi bepul, lekin muallifni ko'rsatish tavsiya etiladi (post matniga qo'yilmaydi, faqat `<nom>.json`
  da); rasmlarni nashr etishdan oldin o'zingiz ko'rib chiqasiz (har biri sizning tasdig'ingiz bilan).
- Loyihalar bo'limida narx/to'lov kafolati yo'q (faqat e'lon); spam/firibgarlik filtrlari ishlar bilan bir xil.

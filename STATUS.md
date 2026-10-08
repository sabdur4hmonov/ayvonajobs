# STATUS — Ayvona Jobs (2026-10-08): post sifati va «📖 To'liq ma'lumot»

Branch `fix/post-quality` → `main`. **Haqiqiy Telegram, sessiya, token va Gemini ishlatilmadi.** Hammasi soxta Bot API,
offline formatter va bazaning nusxasida sinaldi. Namuna fayli (`data/channel_sample_2026-10-07.txt`) git'ga kirmadi.
Testlarda faqat undan tiklangan **anonim** postlar bor (soxta telefon va username). Oldingi hisobot (tasdiqlash,
ustuvorlik, Loyihalar, rasmlar, filtrsiz obuna) git tarixida: `git show ff68d0f:STATUS.md`.

## 1. Nima o'zgardi

| Qism | Commit | Fayllar |
|---|---|---|
| A. «📖 To'liq ma'lumot» botda, kesish faqat gap/band oxirida | `66408c4`, `4d2f3f5` | `processing/formatter.py`, `processing/project_format.py`, `processing/pipeline.py`, `services/job_submission.py`, `bot/cards.py`, `bot/moderation.py`, `web/app.py`, `db/models.py`, migratsiya `a4d2e7f1c3b9` |
| B.5 Dublikatlar | `fefdb28` | `processing/dedup.py`, `processing/pipeline.py`, `config.py`, `settings.yaml → dedup:` |
| B.1–4, 6–8 Kategoriya, hudud, sarlavha, maosh, kompaniya, ma'nosiz maydon, ohang | `66408c4`, `017a9b1` | `processing/categorize.py`, `processing/extract.py`, `processing/salary.py`, `processing/tone.py` (yangi), `processing/formatter.py`, `config/categories.yaml`, `config/extract.yaml`, `config/title_translations.yaml`, `config/settings.yaml → tone:` |
| Testlar | — | `tests/test_full_info.py`, `tests/test_post_quality.py`, `tests/sample_posts.py` (anonim), `tests/test_formatter.py`, snapshotlar |
| Hujjatlar | `297c0ed` | `README.md` 5c, `DEPLOY.md` 6b, `CLAUDE.md` 16-qoida, `docs/PROGRESS.md` |

**A qismi.** Kanal postida endi "📝 To'liq ma'lumot: asl e'londa" (raqobatchi kanalga havola) **yo'q**. Uning o'rniga
«📖 To'liq ma'lumot» tugmasi bor: u **bizning botda** `/start job_<id>` bilan to'liq kartochkani ochadi. Bu mavjud
`?start=job_` oqimi, kartochka ham o'sha. Kartochka o'sha shablon, lekin hech narsa qisqartirilmagan:
- to'liq talablar va ish vaqti;
- maosh shartlari;
- uzun postning butun matni (lotin yozuvida, tinch ohangda);
- ruscha/inglizcha postda asl matn va AI bergan o'zbekcha tarjima.

Bu foydalanuvchi e'loni va loyihada ham ishlaydi. Pastdagi kichik «manba» yozuvi va boshqa tugmalar o'zgarmadi.

Kesish faqat to'liq qator, gap yoki ro'yxat bandidan keyin bo'ladi, "…" ham faqat shundan keyin qo'yiladi. Egasiz qolgan
sarlavha ("🔎 TALABLAR") ham olib tashlanadi. Lavozim, maosh, manzil va aloqa hech qachon kesilmaydi. Manzil butun
qismlar bilan qoladi, kompaniya esa kesilmaydi, butunlay tushiriladi.

**B qismi.**
1. **Kategoriya va teglar:**
   - `ignore_words` qo'shildi: "temir **banka**" bank emas, "texnologiyalar" texnolog emas.
   - Sarlavhadagi qo'shtirnoqli nom kasb hisoblanmaydi: `"HUNTER"` endi #hr emas.
   - Sarlavhasiz postda kasb nomi bor bosh qator hisobga olinadi.
   - Yangi kasb: kiberxavfsizlik (IT). Marketing, SMM va kontent so'zlari kengaytirildi.
   - Hudud tegi **faqat manzil maydonidan** olinadi (manzil bo'lsa).
2. **Sarlavha:**
   - "Talablar: ..." qatori endi sarlavha bo'lmaydi.
   - "Mutaxassis bo'yicha marketing" → "Marketing mutaxassisi".
   - "Erkak va ayollarini" kabi lavozimsiz parcha → kasb yoki kategoriya nomi.
   - Yalang'och "Ishchi" → "Ombor ishchisi".
   - "Kassir VA" → "va", "Sotuv Menejeri" → "Sotuv menejeri".
   - "X at Company" → sarlavha va kompaniyaga ajratiladi.
   - Trucking "Update" → "Yuk kuzatuvi mutaxassisi (Update)".
3. **Maosh:**
   - "3 –7 000 000" → "3 000 000 – 7 000 000 so'm".
   - Postda "$" bo'lsa summalar dollar deb olinadi.
   - So'm bo'la olmaydigan son ("1 000 – 5 000 so'm") → "Kelishiladi".
   - Uzun maosh gapi → "3 000 000 so'm (administrator)", shartlar to'liq kartochkada.
4. **Kompaniya:** shior, tavsif va gap kompaniya deb olinmaydi. Tiredan keyingi izoh olib tashlanadi, qo'shtirnoq juftlanadi.
5. **Dublikat:** yangi qatlam bor. Bir xil telefon/@username, bir xil lavozim (umumiy so'zlarsiz) va o'xshash matn bo'lsa,
   boshqa kanalda bo'lsa ham dublikat. "Begimqulov" va "Begimkulov" teng hisoblanadi. Filtrsiz admin obunasida bunday post
   «kanalga chiqmadi: dublikat» bo'lib keladi (testlangan).
6. **Ma'nosiz maydon:** "Talablar: Administrator uchun" kabi, 3 tadan kam ma'noli so'zli maydon tashlanadi.
7. **Ohang:** "FAQAT ERKAKLAR UCHUN ISH. AYOLLAR BEZOVTA QILMANG!" → "Faqat erkaklar uchun ish.". Iboralar
   `settings.yaml → tone:` da.
8. **Boshqa topilganlar:**
   - fallback sarlavhasi "Yangi ish e'loni — X" o'rniga topilgan lavozim;
   - "Grafik Dizayner" → "Grafik dizayner";
   - `RAINBOWSYSTEM” kompaniya` dagi ortiqcha qo'shtirnoq;
   - ombor postida talablar qatori sarlavha bo'lib qolgani;
   - "Kofe lady" → #barista.

## 2. Qabul qilgan qarorlarim

- **Yangi ustun `jobs.full_html`.** To'liq matn `description` da allaqachon bor edi. Lekin to'liq kartochka uchun maydonlar
  ham kerak, ularni bot ichida qayta hisoblamaslik uchun shablon bir marta yasalib saqlanadi.
- **Tugma qachon chiqadi:**
  - caption nimanidir yo'qotganda;
  - post ruscha yoki inglizcha bo'lganda;
  - matn 500 belgidan uzun va captiondan 1,5 marta uzun bo'lganda.

  Bazadagi 683 e'londan 403 tasida tugma bor, chunki kanallardagi postlar odatda uzun.
- Tugma alohida qatorda, «Murojaat/Ariza» va «Saqlash/Boshqa ishlar» orasida. Admin tekshiruvi xabari va sayt ham to'liq
  kartochkani ko'rsatadi.
- **Tarjima uchun yangi Gemini so'rovi yo'q.** AI baribir chaqirilgan bo'lsa (limit ichida, keshda), uning o'zbekcha
  maydonlari ko'rsatiladi. Bo'lmasa faqat asl matn. Joylash hech qachon tarjimani kutmaydi.
- **Maosh:**
  - parser qabul qilmagan raqam faqat hammasi ≥ 100 000 bo'lsa ko'rsatiladi ("250 000" kunlik); qolgani "Kelishiladi";
  - USD faqat postda $/USD/dollar belgisi bo'lsa, rol bo'yicha taxmin qilinmaydi.
- **Hudud tegi:** manzil maydonida hudud topilsa, faqat shu. Tuman esa matndan olinadi, agar o'sha hudud bo'lsa.
- **Dublikat:**
  - oyna 14 kun (`dedup.window_days`);
  - lavozim o'xshashligi ≥ 85, umumiy so'zlarsiz ("mutaxassis", "o'qituvchi"...);
  - matn ≥ 75;
  - ikki xil kompaniya hech qachon dublikat emas;
  - faqat umumiy so'zdan iborat sarlavha ("O'qituvchi") bu qatlamda solishtirilmaydi.

  Birinchi variantda 17 ta mos kelishdan 6 tasi xato chiqqan edi, shuning uchun qattiqlashtirdim.
- Ingliz sarlavhalari harf o'lchamini saqlaydi ("Digital Content Specialist"). Brend nomlari ("Uzum Tezkor") ham.
- Kanalga chiqqan postlarga tegilmadi. Navbatdagilar worker yonganda o'zi qayta yasaladi.

## 3. Namunadagi xatolar: oldin / keyin

**a) Namunadagi 21 ta muammoli post** (anonim tiklangan; eski kod → yangi kod):

| Xato | Oldin | Keyin |
|---|---|---|
| Captionda manba kanalga havola | 4 | 0 |
| So'z/gap o'rtasida kesish | 2 | 0 |
| Noto'g'ri kategoriya (moliya, ishlab_chiqarish, boshqa) | 9 | 0 |
| Noto'g'ri hudud tegi (#qashqadaryo) | 1 | 0 |
| Buzuq sarlavha | 7 | 0 |
| Maosh xatosi | 3 | 0 |
| Shior kompaniya / ortiqcha qo'shtirnoq | 3 / 1 | 0 / 0 |
| Topilmagan dublikat (Begimqulov/Begimkulov) | 1 | 0 |
| Ma'nosiz maydon | 1 | 0 |
| Baqiriq / qo'pol ibora | 1 | 0 |
| Sotuv menejeriga #hr | 1 | 0 |

**b) Kompyuterdagi baza nusxasining hamma 1306 posti** (offline, chiqqan e'lonlar):

| Xato | Oldin | Keyin |
|---|---|---|
| Captionda manba havolasi | 186 | 0 |
| So'z/gap o'rtasida kesish | 25 | 0 |
| To'liq gap/banddan keyin bo'lmagan kesish | 26 | 1 (vergulli bo'lak) |
| Buzuq sarlavha | 19 | 0 |
| Shubhali kompaniya | 32 | 0 |
| Baqiriq qatori | 11 | 0 |
| Ma'nosiz talablar | 4 | 1 |
| Bir nechta hudud tegi | 19 | 13 |
| "Yangi ish e'loni" sarlavhasi | 44 | 31 |
| Dublikat (yangi qatlam) | — | +11 (barchasi qo'lda tekshirildi) |
| `#boshqa` | 27 | 27 |

## 4. Migratsiya

`a4d2e7f1c3b9`: `jobs.full_html` — bitta bo'sh `TEXT` ustun. Faqat qo'shiladi, mavjud qatorlarga tegmaydi. Eski e'lonlarda
bo'sh qoladi, ularning bot kartochkasi avvalgidek kanal posti bo'ladi. Kompyuterdagi baza nusxasida sinaldi: yuqoriga,
pastga va yana yuqoriga. Hamma jadvallarning har bir qatori bir xil qoldi, `integrity_check` ok, `alembic check` toza.
Obuna, foydalanuvchi va sevimli qatorlari yozilgan nusxada ham sinaldi.

| jadval | oldin | keyin |
|---|---|---|
| sources / raw_posts / jobs | 20 / 1306 / 340 | 20 / 1306 / 340 |
| images / kv_store / jobs_fts | 69 / 57 / 340 | 69 / 57 / 340 |

⚠️ Bu kompyuterdagi **eski** nusxa, serverdagi jonli bazaga kira olmayman.

## 5. Serverga qo'yish

```bash
sudo bash /home/ayvona/ayvona/scripts/deploy.sh
```
```bash
sudo bash /home/ayvona/ayvona/scripts/healthcheck.sh
```
```bash
sudo -iu ayvona bash -c 'cd ~/ayvona && .venv/bin/alembic current'
```
Oxirgi buyruq `a4d2e7f1c3b9 (head)` ko'rsatishi kerak. `deploy.sh` migratsiyani o'zi qiladi. `.env` ga hech narsa qo'shish
shart emas. Orqaga qaytish DEPLOY.md 6b-bo'limda: `alembic downgrade f3c8a1d6e9b4` + `git reset --hard ff68d0f`.

## 6. Qo'lda tekshiring

1. Kanalda yangi uzun post chiqqach, «📖 To'liq ma'lumot» tugmasini bosing. Bot ochilishi va to'liq matnni ko'rsatishi
   kerak (telefon va kompyuterda). Telegram'da `start=job_<id>` ishlashini haqiqiy akkauntda sinab ko'ring.
2. Ruscha yoki inglizcha postdagi tugma: botda "📄 Asl matn" va o'zbekcha maydonlar chiqishi kerak.
3. Uzun foydalanuvchi e'loni va uzun loyiha: tugma bo'lsin, botda yozilgan hamma narsa ko'rinsin.
4. Admin tekshiruv xabari to'liq kartochka bilan keladi. Juda uzun e'londa xabar sig'ishini ko'ring (4096 belgi).
5. Bir necha kun postlarni ko'zdan kechiring: kategoriya, sarlavha, "Kelishiladi" bo'lib qolgan maosh, tushib qolgan
   kompaniya, dublikat.

## 7. Qolgan risklar

- **Haqiqiy Telegram'da sinalmagan:** tugma va deep link (soxta Bot API bilan sinaldi).
- **Tugma ko'p postda** (~59%). Kerak bo'lsa `RICH_TEXT_MIN` / `RICH_TEXT_RATIO` (`processing/formatter.py`) ni oshiring.
- **Dublikat qatlami:** bitta recruiter bir xil lavozimni ikki xil joyga, kompaniya nomini yozmasdan bersa, ular bitta e'lon
  deb hisoblanishi mumkin. 11 ta topilgan holatning hammasini qo'lda tekshirdim, xato topmadim.
- **Ehtiyotkor qoidalar ba'zan foydali ma'lumotni yashiradi:** "Kelishiladi" bo'lgan maosh, tushib qolgan kompaniya,
  tashlangan qisqa talablar. Ular to'liq kartochkada qoladi.
- **Faqat manzildan olingan hudud:** manzilida bitta shahar yozilgan, matnida bir nechta viloyat sanalgan e'lon endi
  bitta hudud tegini oladi.
- **Baqiriq tuzatish:** butunlay katta harfli qatordagi atoqli otlar ham kichik harfga o'tishi mumkin ("koreyada"); ro'yxatdagi
  qisqartmalar (HR, KPI, IT...) qoladi.
- **`#boshqa` 27 ta qoldi:** bularning asosiy sababi lavozimi umuman topilmagan e'lonlar.

# Manba kanallar tahlili

**Sana:** 2026-09-29 · **Hajm:** 19 kanal, 377 post (har kanaldan oxirgi ~20 ta) · **Kim:** Claude (chat), `data/ayvona.db` asosida

Bu hujjat 4–6-bosqichlar uchun asos: parser, klassifikator va tozalovchi shu yerdagi qoidalarga qarab yoziladi.
Mashina o'qiydigan qoidalar: `config/source_rules.yaml` (kanalga xos) va `config/filters.yaml` (umumiy).
Real misollar va kutilgan natijalar: `docs/POST_EXAMPLES.md`.

---

## 1. Asosiy raqamlar

| Ko'rsatkich | Qiymat | Xulosa |
|---|---|---|
| Jami post | 377 | |
| Rasmli / video / so'rovnoma / hujjat | 229 / 4 / 3 / 1 | Ko'p postda rasm bor, lekin matn ham bor |
| Matnsiz post | 7 | Albom qismlari va so'rovnomalar |
| **Dublikatlar** (bir kunda) | **50 post, 22 guruh (13%)** | Kanallar bir-biridan ko'chiradi + o'zini qayta postlaydi |
| **E'lon EMAS** (reklama, yangilik, rezyume, yopilgan, imkoniyat) | **≈ 60–65 post (≈ 17%)** | Klassifikator shart |
| Chiqarishga yaroqli noyob e'lonlar | **≈ 70%** | |
| Kutilayotgan oqim | **kuniga ≈ 200–300 xom → ≈ 150–200 e'lon** | `publish_interval_seconds: 60` bemalol yetadi |

Tillar (taxminan): o'zbek lotin ~65%, inglizcha ~13% (IT, logistika), o'zbek kirill ~10%, ruscha ~10%, aralash ~2%.

---

## 2. Kanallar profili

| Kanal | Mavzu / til | Qolip | E'lon ulushi | Aloqa qayerda | Diqqat |
|---|---|---|---|---|---|
| @ishtoparuz_kanal | umumiy, uz (+kirill) | erkin | ~100% | matnda | Ko'p kross-dublikat; YouTube reklama qatori |
| @beminnatvakant_ish | ta'lim, uz | yarim tartibli | ~65% | matnda | **Rezyumelar**, albom-reklama, 1 postda 3 vakansiya, yashirin reklama havola |
| @ishmi_ish | IT/marketing (hh.uz), uz | juda tartibli | ~80% | **faqat hh.uz havola** | `#reklama`, bot reklamalari, noto'g'ri teglar |
| @ish_kerak_edu | umumiy, uz/ru/kirill | aralash | ~100% | matnda | O'zini qayta postlaydi; ko'p vakansiyali post (telegra.ph) |
| @manavakansiya_uz | umumiy, uz/kirill | erkin | ~100% | matnda | Uzun reklama-footer; 1️⃣ 2️⃣ ko'p vakansiya |
| @ishlaUZ_rasmiy | umumiy, uz/kirill | yarim tartibli | ~95% | matnda | Bezak sarlavha; "Suxoy arenda, Depozit 200$" (ish emas) |
| @ishtopuz_rasmiy | umumiy, uz/kirill/ru | erkin | ~90% | matnda | Katta ogohlantirish footeri; menyu posti |
| @unilance | IT, en/uz | erkin | **~50%** | **email**, @username | Hazil, AI yangiliklari, reklama |
| @kasbdoruz | umumiy, uz | **juda tartibli** | ~95% | matnda | `#vakansiya` = e'lon; `N3311` tartib raqami |
| @jobmakon | IT/ofis, en/ru/uz | erkin | ~85% | email, LinkedIn, @ | Grant/fellowship/akademiya aralash |
| @NextHireX | logistika (AQSh), en | tartibli | ~70% | **yashirin "Get the job."** | 2–3 marta qayta post; "New"/"Without" axlat qator |
| @huntmejob | logistika/IT, en | juda tartibli | ~95% | `Contact: @x` + tugma | Xizmat reklamasi; katta footer |
| @huntmeglobal | umumiy, uz | tartibli | ~100% | **yashirin "Aloqa uchun 👈"** | @huntmejob bilan dublikat |
| @toshkentda_ish_bor_ishchi | ishchi kasblar, uz | **eng tartibli** | 100% | matnda | `—` = bo'sh maydon |
| @Buxgalteriyaishorinlarii | buxgalteriya, uz/kirill/ru | erkin | ~70% | matnda | Kurs/xizmat reklamasi, **rezyume** |
| @edustaffs | ta'lim, uz/kirill/ru/en | yarim tartibli | ~70% | matnda, telegra.ph | Huquqiy maslahat, yangiliklar |
| @Ish_Toshkent | umumiy, uz | tartibli | ~90% | matnda | Oxirida teglar; reklama; keycap raqamlar |
| @digitalitvacancy | IT/davlat, uz | erkin | **~50%** | **yashirin "havola"** | Tadbir, kurs, forum, bepul amaliyot |
| @jobs_fba | moliya, uz/ru/en | tartibli | ~50% | @, tugma | **Yopilgan vakansiyalar**, muddati o'tgan, so'rovnoma. Juda sekin kanal |

---

## 3. E'lon turlari (klassifikator natijasi)

| Tur | Nima qilinadi | Qanday tanish (misollar) |
|---|---|---|
| `job` | Kanalga chiqadi | `job_markers` dan ≥ 2 ball + aloqa yoki ariza havolasi |
| `not_job` | Chiqmaydi, bazada qoladi | `#reklama`, `erid=`, kurs narxi, tadbir, maslahat, hazil, so'rovnoma, matnsiz albom, kanal menyusi |
| `resume` | Chiqmaydi (keyin "Rezyumelar" bo'limi) | "ish joyi kerak", "Ism-familiya:", "Иш излаяпман", tug'ilgan sana |
| `closed` | Chiqmaydi | "VAKANSIYA YOPILDI", `#Vakansiyayopildi`; yoki `Ariza muddati` o'tgan |
| `opportunity` | v1 da chiqmaydi | grant, fellowship, bepul kurs, Dev Camp, **haq to'lanmaydigan** amaliyot |
| `suspicious` | Chiqmaydi, admin'ga | `scam` so'zlari: depozit, oldindan to'lov, "suxoy arenda" |

Qoida tartibi: `closed` → `resume` → `suspicious` → `not_job/opportunity` (agar job ball kuchsiz bo'lsa) → `job`.
Muhim: "QABUL OCHIQ" o'quv markaz reklamasida ham, ish e'lonida ham uchraydi — shuning uchun `job_markers` ustun.

Kanal teglari yordam beradi: `#vakansiya`, `#job`, `#hiring`, `#Buxgalter_kerak` → deyarli aniq job;
`#hazil`, `#dayjest`, `#маьлумот`, `#фойдали` → deyarli aniq not_job (`source_rules.yaml`).

---

## 4. Aloqa ma'lumoti — 6 xil joyda bo'ladi

1. **Matndagi telefon** — eng ko'p.
2. **Matndagi @username** yoki `t.me/username`.
3. **Yashirin havola** (so'z ostida) — `Aloqa uchun 👈`, `Get the job.`, `havola`, `GET A JOB`, `Link`.
   Collector bularni `raw_posts.extra.links` ga saqlaydi. `t.me/<username>` → username; boshqa URL → `apply_url`.
4. **Tugma** — `📝 Apply here`, `✋ Qiziqish bildirish` → `apply_url` (`extra.buttons`).
5. **`t.me/+998996552224`** — bu taklif linki emas, **TELEFON**.
6. **Email**, Google Forms, hh.uz, LinkedIn (`lnkd.in`), telegra.ph.

**Qoida (aggregator):** aloqa = telefon YOKI username YOKI email YOKI apply_url. Hech biri yo'q → `no_contact`
statusi, chiqmaydi, admin'ga kunlik hisobotda. Faqat URL bo'lsa, postda `🔗 Ariza topshirish` tugmasi.

**Olib tashlanadigan havolalar:** matni bo'sh yashirin havolalar (masalan `t.me/JahongirAcademy/2432`),
`t.me/addlist/...`, `t.me/+<taklif>`, Instagram/Facebook/YouTube, manba kanalning o'z akkauntlari
(`own_usernames`). URL'lardan `utm_*`, `?text=` parametrlari o'chiriladi.

⚠️ `own_usernames` **aniq moslik** bilan solishtirilsin: `@JahongirAcademy_admin` — haqiqiy aloqa,
`JahongirAcademy/2432` esa reklama.

---

## 5. Telefon formatlari (hammasi uchradi)

```
+998901171112        +998 50 977 33 36     +998-90-996-97-77     +99897 425 28 87
998-90-068-41-70     953538444             772701545             88-401-12-30
87-805-33-33         33 077 14 03          99 191 09 08          97.798 67 22
(97) 137-16-94       🔔99)208-65-53        +998 99-001-23-32     "Telegram: +998 333378888"
```
Normallashtirish: hamma raqam bo'lmagan belgini olib tashlash → 9 raqam qolsa `+998` qo'shish, 12 raqam `998` bilan
boshlansa `+`. Operator kodlari: 20, 33, 50, 55, 71 (Toshkent shahar), 77, 78, 87, 88, 90, 91, 93, 94, 95, 97, 98, 99.
Shahar kodlari (65–79) ham bo'ladi. Kod ro'yxatda bo'lmasa — faqat yonida "tel/aloqa/bog'lanish" so'zi bo'lsa telefon deb olinadi (aks holda bu yil, narx va h.k. bo'lishi mumkin). Bitta postda 2–4 telefon bo'lishi mumkin; dublikatlarni birlashtirish.

---

## 6. Maosh formatlari (hammasi uchradi)

```
4 000 000 so‘m                  3.000.000 Fix + KPI            5 - 30 mln so'm
7 500 000 - 15 000 000          4,000,000 / от 4,000,000        от 7 000 000 до 15 000 000 сум
5–15 mln so‘m                   2 mln+                          4million - 9 million
6 000 000 so‘mdan boshlanadi    9 000 000 so‘mgacha             Иш хаки 6 млндан бошланади
$500 – 800                      $2 000 dan                      Up to 3800 USD Gross
1 500 – 2 000 USD               300$-2500$                      1000$ gacha / до 1000$
Kunlik 250 000 - 550 000        Haftasiga 1 000 000 dan 7 000 000   (9 - 15 mln) soatbay
Kelishiladi / Suhbat asosida / Shtat jadvali asosida / Negotiable / Обговаривается
```
Xatolar ham bor: `15 00 000` (=1.5 mln?), `10 00 0000`, `5 00 000 – 7 000 000`, `3 000 000 mln`, `4 500 000 – so‘m`,
keycap raqamlar `3️⃣.000.000 – 6️⃣.000.000`, `8 000 000dan –10 000 000 MLN`.
Qoidalar:
- Davr: oylik (standart) / kunlik / haftalik / soatbay → `salary_period`. Qidiruv faqat oylikka keltirilgan son bilan.
- Aql-hush tekshiruvi: oylik so'mda 500 000 dan kichik yoki 200 mln dan katta chiqsa — `salary_text` ni saqlab,
  son maydonlarini bo'sh qoldirish (xato raqamni ko'rsatmaslik).
- **`Depozit 200$` — maosh EMAS** (scam belgisi).
- "fiks + KPI" bo'lsa: min = fiks, max = yuqori chegara (bo'lsa).

---

## 7. Joylashuv

- Postlarning ~85% i **Toshkent**. Tumanlar va mo'ljallar ko'p: Chilonzor, Yunusobod, Yakkasaroy, Shayxontohur,
  Mirzo Ulug'bek, Olmazor, Uchtepa, Sergeli, Yangihayot, Yashnobod, Mirobod, Bektemir; metro nomlari (Novza, Chorsu,
  Olmazor, Shahriston...). Yozilishi: lotin/kirill/ruscha/inglizcha (`Yunusabad`, `Юнусабад`), xatolar (`Sergili`, `Yunsobot`).
- Boshqa hududlar: Samarqand, Buxoro (G'ijduvon), Andijon, Jizzax, Navoiy, Urganch, Namangan, Farg'ona, Qo'qon,
  Toshkent viloyati (Olmaliq, Chirchiq, Nazarbek, Zangiota, Parkent, Keles, Ohangaron, Yangiyo'l, Chinoz).
- Bir postda **bir nechta shahar** (Yandex Eats, Uzum Tezkor) → `region = "ko'p hudud"`, hudud teglari ro'yxat.
- Hudud ba'zan birinchi qatorda katta harf bilan: `SAMARQAND`, `BUXORO`.
- Masofaviy: `Remote`, `online`, `uydan turib`, `masofadan`, `удаленно`.

---

## 8. Dublikatlar

Bir kunlik namunada **22 guruh**. Turlari:
1. **Kanal o'zini qayta postlaydi** (bir necha soatdan keyin) — @ish_kerak_edu, @ishlaUZ_rasmiy, @NextHireX (3 marta), @kasbdoruz.
2. **Kross-post** — bir ish beruvchi 3–4 kanalga beradi ("YIGITLAR, KUCHLI JAMOAGA OPERATORLAR KERAK" → 4 kanalda).
3. **Deyarli bir xil** — bittasida qo'shimcha `#Toshkent` qatori yoki imlo farqi ("shugʻillanadi"/"shugʻullanadi").

Tavsiya: tozalangan matn bo'yicha taqqoslash (footer'lar olingandan KEYIN), oyna **14 kun**,
fingerprint = normallashtirilgan lavozim + birinchi telefon/username, rapidfuzz ≥ 90%.
Birinchi kelgani chiqadi, keyingilari `duplicate` (qaysi post dublikati ekani saqlanadi).

---

## 9. Ko'p vakansiyali postlar

Uchragan shakllar: ro'yxat (`• Sotuvchi; • Shofyor`), raqamli (`1️⃣ SOMSA SOTUVCHI ... 2️⃣ TAJRIBALI OSHPAZ`),
bir postda bir necha to'liq e'lon (@beminnatvakant_ish/24497 — 3 xil maktab).
**v1 qarori:** bitta post bo'lib chiqadi; sarlavha = kompaniya yoki "Bir nechta vakansiya", lavozimlar ro'yxat
sifatida; kategoriya = eng ko'p ball olgani. (Keyin: to'liq alohida e'lonlarni bo'lib chiqarish.)

---

## 10. Boshqa maxsus holatlar

- **Unicode "qalin" harflar** (`𝗨𝗫/𝗨𝗜 𝗗𝗲𝘀𝗶𝗴𝗻𝗲𝗿`) → `unicodedata.normalize("NFKC")` bilan oddiy harfga.
- **Keycap raqamlar** (`3️⃣`) → oddiy raqam.
- **`—` belgisi** maydon qiymati sifatida = bo'sh.
- **Telegra.ph havolasi** — ba'zan e'lonning to'liq matni faqat u yerda. v1: havola `apply_url` bo'ladi.
- **Ariza muddati** (`📅 Ariza muddati: 2026-09-19`) — o'tgan bo'lsa `closed`.
- **Keyin yopilgan e'lonlar**: @jobs_fba eski postini tahrirlab "yopildi" qiladi. v1 tahrirlarni kuzatmaydi (keyingi versiya).
- **Faqat rasm** (matn rasmning ichida) — `no_text`, admin'ga. Keyin Gemini bilan rasmdan o'qish mumkin.
- Rasmlar: manba rasmlari ishlatilmaydi — bizda har kategoriya uchun o'z rasmi bor.

---

## 11. Sardor qarorlari (2026-09-29)

1. **Rezyumelar** — kerak emas. Kanalga chiqmaydi (bazada `resume` statusi bilan qoladi, xolos).
2. **Imkoniyatlar** (grant, kurs, tadbir, haq to'lanmaydigan amaliyot) — kerak emas. **Kanalga faqat ish e'lonlari.**
3. **Yozuv** — hammasi **lotin** alifbosida. O'zbek kirill e'lonlar lotinga o'giriladi.
4. **Til** — hammasi **o'zbekcha**. Ruscha/inglizcha e'lonlar uchun v1 (AI'siz) qoidasi:
   - yorliqlar va tuzilgan maydonlar o'zbekcha (maosh, manzil, ish vaqti, aloqa — regex bilan olinadi, tilga bog'liq emas);
   - lavozim `config/title_translations.yaml` lug'ati bilan o'giriladi (topilmasa asl holida);
   - erkin matn (talablar, vazifalar) o'girib bo'lmaydi → postga **qo'yilmaydi**, o'rniga `📝 To'liq ma'lumot: asl e'londa` havolasi;
   - Bosqich 15 (Gemini, bepul) ulangach — ruscha/inglizcha matn to'liq o'zbekchaga o'giriladi va keshlanadi;
     Gemini ishlamasa — yana v1 qoidasi.
5. **Manba** — post oxirida kichik "manba" havolasi (POST_EXAMPLES.md dagi shablon).

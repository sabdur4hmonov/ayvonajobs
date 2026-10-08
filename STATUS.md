# STATUS — Ayvona Jobs (2026-10-08): rezyume postlari kanalga chiqmaydi

Branch `fix/resume-posts` → `main`. **Haqiqiy Telegram, sessiya, token va Gemini ishlatilmadi.** Hammasi testlar va kompyuterdagi
bazaning nusxasida (offline) sinaldi. Migratsiya **yo'q**, `.env` o'zgarmaydi. Testlarda faqat anonim postlar (soxta ism, telefon,
username).

## 1. Nima o'zgardi

**Xato.** @freelancer_Uzbek kanalidagi ish izlovchining posti (`#rezyume`, "Xodim: <ism>", "Portfolio:", "proyekt kerak" — ya'ni
odam o'ziga LOYIHA qidiryapti) "Proyekt" nomli, "Maosh: Kelishiladi" vakansiya bo'lib kanalga chiqib ketdi. Qo'shimcha: kanalning
o'z reklama admini (@FreelancerUz_ads) post aloqasi sifatida olindi.

| Qism | Fayllar |
|---|---|
| Rezyume aniqlash: markerlar, sarlavha qatori, shakl bo'yicha | `config/filters.yaml` (`resume_markers`, `resume_line_markers`, `resume_structure`), `processing/classify.py`, `config.py` |
| Kanalning o'z reklama aloqasi | `config/source_rules.yaml` (`defaults.ads_contact_phrases`), `processing/boilerplate.py`, `classify.py`, `extract.py`, `clean.py` |
| `@freelancer_Uzbek` manba qoidalari | `config/source_rules.yaml` |
| Testlar | `tests/test_resume.py` (31 ta, anonim) |
| Hujjatlar | `README.md`, `DEPLOY.md` 6c, `CLAUDE.md` 17-qoida, `docs/PROGRESS.md` |

Commitlar: `0bd757a` (tuzatish), `5941900` (hujjatlar).

**Rezyume uch yo'l bilan topiladi** (hammasi `config/filters.yaml` da, kodda emas):
1. **Marker.** Heshteglar (`#rezyume`, `#resume`, `#cv`, `#резюме`, `#ishizlayman` ...) va aniq iboralar ("ish izlayman",
   "proyekt kerak", "ищу подработку", "open to work" ...).
2. **Sarlavha qatori.** Qator FAQAT "REZYUME" / "CV" / "Ish kerak!" dan iborat bo'lsa.
3. **Shakl.** Quyidagi UCHALASI birga bo'lsa: (a) kamida 3 ta har xil profil yorlig'i (Xodim, Yosh, Tajriba, Hudud, Ish turi,
   Oylik, Portfolio, Qo'shimcha... qator boshida, ikki nuqta bilan); (b) ish izlovchiga xos dalil: "Portfolio:" kabi yorliq YOKI
   "Xodim:/Ism:" maydonida odam ismi (2–4 ta bosh harfli so'z, kasb nomi emas); (c) ish beruvchi belgisi YO'Q (Talablar, Vazifalar,
   Kompaniya, Vakansiya, "ishga taklif", "xodim kerak", `#vakansiya`...).

Tartib o'zgarmadi: yopilgan → rezyume → shubhali → ... Rezyume bazada `raw_posts.status = resume` bo'lib qoladi, kanalga chiqmaydi,
**filtrsiz admin obunasi** uni "🚫 Kanalga chiqmadi: rezyume (ish izlovchi posti)" holati bilan ko'rsatadi (testlangan).

**Reklama aloqasi.** Iboradan ("e'lon joylashtirish uchun", "e'lon va rezyume joylashtirish uchun", "reklama uchun", "reklama
bo'yicha", "по рекламе", "for ads" ...) DARHOL keyin @username / t.me havola kelsa (yoki ibora qator oxirida bo'lib, hisob
keyingi qatorda yolg'iz tursa), qator olib tashlanadi va undagi hisob post aloqasi bo'lmaydi: klassifikatorda, extractorda va
cleaner'da (yashirin havola ham). Iboralar `source_rules.yaml → defaults.ads_contact_phrases` da. `@freelancer_Uzbek` uchun
o'z hisoblari (`FreelancerUz_ads`, `freelancer_Uzbek`) va "Ish va xodim bir joyda!", "Kanalda e'lon va rezyume joylashtirish
uchun..." qatorlari ham yozildi.

## 2. Qabul qilgan qarorlarim

- **Yalang'och "rezyume" so'zi marker EMAS.** Kompyuterdagi 1306 postning **90 tasi** oddiy vakansiya bo'lib, ularda "Rezyume
  yuborish uchun: ...", "Rezyume jo'nating", "To'liq rezyume (CV)" bor. Shuning uchun faqat `#rezyume` kabi heshteglar. Xuddi
  shu sabab "ish kerak" ham yo'q (vakansiyada `"Ish kerak edi."` iqtibosi uchradi); u faqat alohida qator bo'lsa hisoblanadi.
- **"Rezyume:" (ikki nuqta bilan) sarlavha emas:** vakansiyada bu aloqa qatorining boshi bo'lishi mumkin.
- **Shakl qoidasi qasddan qattiq.** Yo'qolgan rezyume (kanalda keraksiz post) — arzon xato; yo'qolgan vakansiya — qimmat. "Xodim:
  Sotuvchi" (bitta so'z) yoki "Xodim: Sotuv Menejeri" (kasb) ism emas. Ish beruvchi belgisi bo'lsa, qancha yorliq va ism
  bo'lmasin, rezyume hisoblanmaydi.
- **`*_ads` / `*reklama*` / `*admin*` nomlari ko'r-ko'rona olinmaydi:** faqat reklama iborasidan keyingi hisob olinadi. Bu o'zi
  yetarli (nom andozasi qo'shimcha hech narsa bermas edi) va "Reklama bo'yicha menejer kerak. Murojaat: @Sales_Admin_Uz"
  kabi haqiqiy aloqani yo'qotmaydi (testlangan).
- Reklama qatori **butunlay olib tashlanadi** (matnda ham ko'rinmaydi), chunki cleaner aloqali qatorni "qaytarib qo'yadi".
- `Classifier` endi ixtiyoriy 3-argument (`categories`) oladi: "Xodim: Sotuv menejeri" kabi kasb nomini ism deb olmaslik uchun.
  Berilmasa avvalgidek ishlaydi.
- Kanalga chiqib bo'lgan postlarga tegilmadi.

## 3. Haqiqiy 1306 postda (kompyuterdagi baza nusxasi, offline)

| | Oldin | Keyin |
|---|---|---|
| Matni bor postlar | 1279 | 1279 |
| Rezyume deb topilgan | 5 | 5 |
| Vakansiya (`job`) | 1134 | 1134 |
| Boshqa turlar (not_job / opportunity / closed / suspicious) | 140 | 140 |

**Hech bir post turi o'zgarmadi** — ya'ni yangi qoidalar bu bazadagi birorta haqiqiy vakansiyani yo'qotmadi (yolg'on mos kelish
**0**). Bu nusxada ish izlovchi posti ham yo'q (manbalar vakansiya kanallari), shuning uchun "nechta rezyume topildi" o'sishi 0:
qoidalarni **tiklangan haqiqiy post** bilan sinadim (pastda).

**Har bir yangi marker** 1306 postga qarshi sinaldi: `#rezyume`, `#resume`, `#cv`, `#rezume`, `#резюме`, `#ishizlayman`,
`#ish_izlayman`, `#ishqidiraman`, `#ish_qidiraman`, `#ishkerak`, `#ish_kerak`, `#opentowork`, "ish izlayman", "ish qidiraman",
"ish qidirayapman", "иш излайман", "proyekt kerak", "loyiha kerak", "buyurtma qidiryapman/izlayapman", "ищу подработку",
"ищу вакансию", "ищу проект", "ищу заказы", "looking for a job", "looking for work", "seeking a job", "open to work",
"available for hire" va sarlavha qatorlari (`rezyume`, `resume`, `cv`, `резюме`, `ish kerak`, `ish izlayman`) — **hammasi 0 ta
postga mos keldi**, ya'ni namuna ko'rsatadigan narsa yo'q. Rad etilgan (ishlatilmagan) nomzodlar: yalang'och `rezyume` — 90 ta
vakansiya ("Rezyume yuborish uchun: ...", "📞 Aloqa: Rezyume jo'nating", "@... - rezyume yuboring"), `ish kerak` — 1 ta
(`"Ish kerak edi."`).

**Shakl qoidasi.** 10 ta post 3 va undan ko'p profil yorlig'iga ega ("Yosh:", "Tajriba:", "Hudud:" ...) — **hammasi vakansiya**,
10 tasida ham ish beruvchi yorlig'i bor (Talablar/Kompaniya...), 3 tasida ish beruvchi iborasi; shakl bo'yicha rezyume = 0.
Ish izlovchiga xos dalil ("Portfolio:" yorlig'i yoki ism) 3 postda uchraydi, lekin ularda 3 tadan kam profil yorlig'i bor, shuning
uchun ham rezyume deb olinmadi (ular vakansiya).

**Boshqa "rezyumega o'xshash" postlar** (ish deb topilgani orasida): xizmat taklifi ("qilib beramiz", "xizmat ko'rsataman") — **0**,
birinchi shaxsdan ish qidirish ("men ish izlayman", "ishga kirmoqchi") — **0**, ruscha "резюме" — 22 ta, hammasi "резюме
отправляйте" (vakansiya). Ya'ni bu bazada bir xil xato boshqa postda yo'q.

**Reklama aloqasi.** 3 ta postda kanalning o'z reklama admini avval aloqa bo'lib olinayotgan edi, endi olinmaydi:
`@ish_kerak_edu_adminstratori` ("E'lon joylashtirish uchun:" ostida; vakansiyaning haqiqiy aloqasi `@HR_ish` qoldi) va
`@manavakansiya_adminka` ("Vakansiya joylash uchun @... ga yozing", 2 post). Oxirgi ikkitasi kanalning o'z reklamasi
("Xodim topolmay qiynalayapsizmi?") va boshqa aloqasi yo'q edi: avval admin akkaunti "Murojaat" tugmasi bilan chiqib ketardi, endi
`no_contact` bo'lib chiqmaydi.

**Tiklangan post (testda, anonim).** Eski kod → yangi kod:

| Post | Oldin | Keyin |
|---|---|---|
| `#rezyume ... Xodim: <ism> ... Portfolio` | `job`, aloqalar: portfolio, poster, **reklama admini** | `resume`, aloqalar: portfolio, poster |
| Shu post `#rezyume` va "proyekt kerak"siz (faqat shakl) | `job` | `resume` |
| Ish beruvchi: "Xodim kerak: ... Yosh/Tajriba/Hudud/Oylik" | `job` | `job` |
| Ish beruvchi: "Xodim: Sotuv menejeri ... Talablar:" | `job` | `job` |

Testlar (31 ta) ham: `Rezyume yuboring`, `Rezyume:`, "Ish kerak bo'lsa", "Ish kerak edi", "Loyiha uchun dasturchi kerak" qatorli vakansiya `job`
bo'lib qoladi; yopilgan post rezyumedan oldin `closed` bo'ladi; 7 xil reklama qatori (lotin, ruscha, inglizcha, t.me havola,
keyingi qatordagi hisob) aloqadan chiqadi, post egasining aloqasi qoladi.

## 4. Serverga qo'yish

```bash
sudo bash /home/ayvona/ayvona/scripts/deploy.sh
```
```bash
sudo bash /home/ayvona/ayvona/scripts/healthcheck.sh
```
Migratsiya yo'q, `.env` ga hech narsa yozilmaydi. `deploy.sh` servislarni o'zi qayta yoqadi. Navbatda allaqachon turgan rezyumeni
ko'rish va (xohlasangiz) chiqarmaslik buyruqlari DEPLOY.md 6c-bo'limida. Orqaga qaytish: `git reset --hard 6724db5`.

**Natijalar:** 1125 ta test o'tdi (oldin 1094; +31), `ruff` toza.

## 5. Qolgan risklar

- **Haqiqiy @freelancer_Uzbek postlarida sinalmagan.** Kompyuterdagi nusxada bu kanal yo'q; qoidalar bitta haqiqiy postdan
  tiklangan namunada va 1306 ta boshqa postda (yolg'on mos kelish 0) sinaldi. Deploydan keyin bir-ikki kun shu kanalning
  chiqqan postlarini ko'zdan kechiring.
- **Shakl qoidasi ehtiyotkor:** ism yozilmagan, "Portfolio" yo'q rezyume (faqat "Yosh/Tajriba/Hudud") rezyume deb topilmaydi.
  Agar shunday post chiqib qolsa — shu postdagi aniq iborani `resume_markers` ga qo'shing (qo'shishdan oldin 1306 postga qarshi
  tekshiring: `CLAUDE.md` 17-qoida).
- **Navbatda turgan rezyume.** Deploydan oldin navbatga tushgan rezyume postlari (agar bo'lsa) o'zi qayta baholanmaydi. Ularni
  DEPLOY.md 6c dagi so'rov bilan toping.
- **Reklama iborasi + darhol hisob** — katta ehtimol bilan faqat kanal reklamasi. Bu qoida bilan ish beruvchining o'zi shunday
  yozsa ("Reklama bo'yicha: @hr_menejer" deb o'z HR'ini ko'rsatsa), uning hisobi aloqadan chiqadi; telefon va boshqa hisoblari
  qoladi. Aloqasi faqat shu bo'lgan post `no_contact` bo'ladi.
- Ruscha/inglizcha markerlar (`ищу подработку`, `open to work`) haqiqiy postlarda sinalmagan (bazada ularga mos post yo'q).

---

## Oldingi yangilanish (2026-10-08, `6724db5`): post sifati va «📖 To'liq ma'lumot»

Hamma narsa hanuz amalda; batafsil: `git show 6724db5:STATUS.md`.

- Kanal postida manba kanalga havola yo'q; qisqargan/uzun/ruscha-inglizcha postda **«📖 To'liq ma'lumot»** tugmasi botda to'liq
  kartochkani ochadi (`jobs.full_html`, migratsiya `a4d2e7f1c3b9`). Matn faqat gap/band oxirida kesiladi.
- Kategoriya, hudud tegi, sarlavha, maosh, kompaniya, dublikat, baqiriq/qo'pol ibora, ma'nosiz maydon tuzatildi (qoidalar config'da:
  `categories.yaml → ignore_words/default_title`, `extract.yaml → company_reject_words/title_role_words`, `settings.yaml → tone:/dedup:`).
- Namunadagi 21 ta muammoli post: 0 xato qoldi; 1306 postda manba havolasi 186 → 0, so'z o'rtasida kesish 25 → 0, buzuq sarlavha 19 → 0.
- Birinchi yangilanishlarning (tasdiqlash, ustuvorlik, Loyihalar, rasmlar, filtrsiz admin obuna) tavsifi: `git show ff68d0f:STATUS.md`.
- Haqiqiy Telegram'da «📖» tugmasi va deep link hanuz qo'lda tekshirilmagan (DEPLOY.md 6b).

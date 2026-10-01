# Veb-sayt va xalqaro manbalar

**Sana:** 2026-09-29 · **Kim:** Claude (chat) · **Qachon ulanadi:** Bosqich 9 dan keyin (MVP 1–2 hafta barqaror ishlagach) — Bosqich 16.

> **Holat (2026-10-01):** kod tayyor — `src/ayvona/sources/web/`. Yoqish: botda `/addsource web:himalayas`
> (`remotive`, `jobicy`, `remoteok`, `osonish`, `hh_uz`) yoki `/addsource rss:<URL>`. Shartlar 2026-10-01 da qayta
> o'qildi (PROGRESS.md, Bosqich 16). hh.uz — `HH_ACCESS_TOKEN` kerak; vacancy.gov.uz — qo'shilmadi.
> Himalayas/Remotive: Google Jobs'ga yuborish taqiq → saytimizda ularning e'lonlariga JobPosting belgisi yo'q.

Tanlov mezonlari: 1) ruxsat bor (rasmiy API yoki `robots.txt` ruxsat beradi, shartlari bilan), 2) bepul,
3) O'zbekiston fuqarosi **haqiqatan ariza topshira oladi**, 4) har e'londa ariza havolasi bor.

---

## A. O'zbekiston saytlari

| # | Manba | Kim yuritadi | Qanday olinadi | Nima beradi | Diqqat |
|---|---|---|---|---|---|
| 1 | **hh.uz** (HeadHunter) | xususiy, eng katta ish sayti | Rasmiy API — dev.hh.uz da **bepul ilova ro'yxatdan o'tkaziladi** | IT, ofis, bank, savdo; tuzilgan maydonlar (maosh, hudud, tajriba) | hh logotipi/brend qoidalari; ko'p e'lonlar Telegram kanallarda ham bor → dedup ushlaydi. API cheklovlarini Bosqich 16 da tekshirish |
| 2 | **Oson Ish** (osonish.uz) | **Davlat** axborot tizimi (dgov.uz ro'yxatida) | HTML sahifalar. `robots.txt`: sahifalar ruxsat, `/api/` taqiq, `Crawl-delay: 1` | ~9 900 e'lon / 46 000 ish o'rni, **barcha 14 hudud** (bizning Telegram manbalarimiz 85% Toshkent — bu viloyatlarni qoplaydi) | Faqat ro'yxat va e'lon sahifalarini o'qish, `/api/` ga tegmaslik, 30 daqiqada bir, so'rovlar orasida ≥ 1 s. Ariza saytda ("Taklif yuborish") |
| 3 | **vacancy.gov.uz** | Davlat — fuqarolik xizmati vakansiyalari portali | Bosqich 16 da texnik tekshiriladi | Vazirlik, hokimlik, maktab, shifoxona lavozimlari | Ixtiyoriy, 1–2 dan keyin |

Tavsiya qilinmaydi: rasmiy API'si bo'lmagan e'lon doskalari (masalan OLX) — shartlari avtomatik yig'ishni cheklashi mumkin.

## B. Xalqaro — chet elda qonuniy ish

| # | Manba | Nima | Qanday olinadi |
|---|---|---|---|
| 4 | **"Xorijda ish" — Migratsiya agentligi** (rasmiy davlat idorasi) | Germaniya, Buyuk Britaniya (mavsumiy), Koreya, Yaponiya, Qatar va b. — **qonuniy**, viza va ish beruvchi tekshirilgan | Telegram kanal **@migratsiyaagentligi** — collector'ga oddiy kanal sifatida qo'shildi (kod shart emas). Sayti: xorijdaish.uz |

Bu juda muhim: Telegramdagi "chet elda ish" e'lonlarining ko'pi firibgarlik ("viza uchun pul"). Rasmiy manba — xavfsiz alternativa.
Kategoriya: `chet_el`, teg `#xorijda_ish`.

## C. Xalqaro — masofaviy (uydan, dollarda) ish

Faqat **O'zbekistondan ariza topshirsa bo'ladigan** e'lonlar olinadi: joylashuv "Worldwide / Anywhere" yoki
Uzbekistan / Central Asia / CIS / Asia ro'yxatida bo'lsa, yoki vaqt mintaqasi UTC+5 ni qamrasa.

| # | Manba | API | Shartlar (qisqa) |
|---|---|---|---|
| 5 | **Himalayas** | Bepul, kalitsiz: `/jobs/api/search?country=...&worldwide=true` | Asl e'longa havola + "Himalayas" nomini manba sifatida ko'rsatish; Jooble/Google Jobs/LinkedIn ga yubormaslik |
| 6 | **Remotive** | Bepul: `https://remotive.com/api/remote-jobs` | Havola + "Remotive" nomi; **kuniga ≤ 4 so'rov**; `candidate_required_location` bo'yicha filtr |
| 7 | **Jobicy** | Bepul: `https://jobicy.com/api/v2/remote-jobs?geo=...` | Soatiga ≤ 1 marta; asl havola va "Jobicy" manba saqlansin |
| 8 | **Remote OK** | Bepul: `https://remoteok.com/api` | Havola + "Remote OK" nomi (logotip emas) |

**Kanalni to'ldirib yubormaslik uchun:** masofaviy xalqaro e'lonlar **kuniga ≤ 10–15 ta**, eng yaxshilari
(maosh ko'rsatilgan, worldwide, yangi). Hammasi inglizcha — til qoidasi: maydonlar o'zbekcha, lavozim lug'at bilan,
tafsilot o'rniga havola; Gemini ulangach to'liq tarjima. Teglar: `#masofaviy #xalqaro`, "Ingliz tili kerak" belgisi.
Keyinchalik alohida kanal (masalan "Ayvona Remote") ochish mumkin.

---

## Manba va ariza (hamma veb-manbalar uchun)

- Postda **"🔗 Ariza topshirish"** tugmasi — asl e'lon sahifasiga (hh.uz / osonish.uz / Himalayas ...). Odam o'sha yerda ariza beradi.
- Oxirgi qator: `<i>manba: <a href="ASL_URL">Himalayas</a></i>` — veb-manbalarda **sayt nomi yoziladi**
  (API shartlari shuni talab qiladi). Telegram manbalarda — faqat "manba" so'zi (avvalgidek).
- Link preview o'chiq.

## Ulanish tartibi (Bosqich 16)

1. @migratsiyaagentligi — **allaqachon qo'shildi** (Telegram).
2. hh.uz (API) → 3. Oson Ish (HTML) → 4. Himalayas + Remotive → 5. Jobicy, Remote OK → 6. vacancy.gov.uz.
Har biri alohida sessiyada, oldin Claude Code sayt shartlarini qayta tekshiradi.

## Manbalar (tekshirilgan sahifalar)
- https://dev.hh.uz/ · https://osonish.uz/vacancies · https://osonish.uz/robots.txt · https://dgov.uz/uz/solution/detail/143/
- https://vacancy.argos.uz/hrm-vacancy-list · https://t.me/s/migratsiyaagentligi · https://www.xorijdaish.uz/
- https://himalayas.app/api · https://github.com/remotive-com/remote-jobs-api · https://github.com/Jobicy/remote-jobs-api · https://remoteok.com/api

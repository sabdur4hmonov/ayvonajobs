# Post misollari

**Qayerdan:** 19 kanaldan yig'ilgan 377 ta real post ichidan Claude tanlagan **41 ta** eng xilma-xil misol (2026-09-29).
Har birida: asl matn (aynan), yashirin havolalar/tugmalar va **kutilgan natija**.
Bosqich 4 da Claude Code bularni `tests/fixtures/posts/` ga test sifatida ko'chiradi.
Tahlil va qoidalar: `docs/SOURCE_ANALYSIS.md`, `config/source_rules.yaml`, `config/filters.yaml`.

**Kutilgan natija maydonlari:** `kind` (job / not_job / resume / closed / opportunity / suspicious), `category` va `profession` (`config/categories.yaml` kalitlari),
`title_contains` (lavozimda bo'lishi kerak bo'lgan so'z), `salary_min/max` (son), `currency`, `salary_period`,
`region` (`regions.yaml` kaliti), `district`, `phones`, `usernames`, `emails`, `apply_url`, `multi` (bir necha vakansiya),
`strip` (olib tashlanishi kerak bo'lgan qismlar). Yozilmagan maydon = tekshirilmaydi.


---

## 1. Oddiy, toza e'lon

**Manba:** [@ishtoparuz_kanal/25030](https://t.me/ishtoparuz_kanal/25030) · **Media:** photo

**Matn:**

````text
⚡️ Maktabga Ayol oshpaz kerak

📣 Ish haqida:
Maktab oshxonasiga tajribali va o‘z ishining ustasi bo‘lgan oshpaz taklif etiladi.

❗️ Talablar:
– Oshpazlik sohasida malaka va yetarli tajribaga ega bo‘lish

⏰ Ish vaqti:
– 07:00 dan 16:00 gacha

💵 Oylik maosh:
– 4 000 000 so‘m

✉️ Murojaat uchun:
– Tel: +998 50 977 33 36
– Tel: +998 94 138 14 14

📌 Manzil:
– Toshkent shahri, Yunusobod tumani
````

**Kutilgan natija:**

```yaml
kind: job
category: oshxona
profession: oshpaz
title_contains: oshpaz
salary_min: 4000000
salary_max: 4000000
currency: UZS
salary_period: month
region: toshkent_sh
district: Yunusobod
phones:
- '+998509773336'
- '+998941381414'
usernames: []
```


---

## 2. Kunlik maosh + kanal reklama qatori

**Manba:** [@ishtoparuz_kanal/25039](https://t.me/ishtoparuz_kanal/25039) · **Media:** photo

**Matn:**

````text
✨ MAR MAR OILAVIY RESTORANIGA KASSIR KERAK

KASSIR — O‘G‘IL BOLA 

⏰ Ish vaqti: [09:00-21:00] 

💵 Maosh: 250 000 
❗️Stajirofka 5 kun 100 000 so’mdan to’lanadi

NOMZODGA TALABLAR:
• Rus tilini bilishi shart ❗️
• Kassirlik sohasida kamida 1 yillik tajriba
• Naqd va karta orqali to‘lovlarni aniq qabul qilish
• iiko dasturida ishlay olish
• Kassa hisobini yuritish va smena yakunida hisobot topshirish
• Mijozlar bilan xushmuomala muloqot qilish
• Mas’uliyatli, chaqqon va tartibli bo‘lish

⚠️ TALABALAR BEZOVTA QILMASIN!

📍Manzil: Toshkent shahar
MAR MAR oilaviy restorani

☎️Murojaat uchun:
Resume bilan murojat qilin @asaminov

INSTAGRAMDAN QAYSIDIR ISHNI KO’RIB KANALGA KIRIB TOPA OLMAYOTGAN BO’LSANGIZ 👇👇👇👇 PASTDAGI LINKGA BOSING O’SHA KO’RGAN ISHINGIZNI TOPISH O’RGATILGAN !👇👇👇👇

https://youtu.be/qkPn4_8IoEw?si=rpCnQfqRpLePbJvq
````

**Kutilgan natija:**

```yaml
kind: job
category: sotuv
profession: kassir
title_contains: kassir
salary_min: 250000
salary_max: 250000
currency: UZS
salary_period: day
region: toshkent_sh
usernames:
- '@asaminov'
phones: []
strip:
- INSTAGRAMDAN QAYSIDIR ISHNI...
- youtu.be havola
```


---

## 3. O'zbek kirill

**Manba:** [@ishtoparuz_kanal/25042](https://t.me/ishtoparuz_kanal/25042) · **Media:** photo

**Matn:**

````text
🔥 САВДО КОМПАНИЯСИГА ИШГА ТАКЛИФ ҚИЛАМИЗ! 🔥

📍 ИШ ЖОЙИ: Тошкент шаҳри

💰 ОЙЛИК ДАРОМАД:
7 000 000 — 15 000 000 сўм
➕ Бонуслар мавжуд!

👥 БИЗ КИМЛАРНИ ИШГА ТАКЛИФ ҚИЛАМИЗ?

18 ёшдан 40 ёшгача бўлган йигитлар ва қизлар.

⭐ БИЗДА:

🚀 Карьера ўсиши имконияти
🤝 Қувноқ ва аҳил жамоа
🎁 Қўшимча бонуслар
📈 Ривожланиш ва ўсиш имконияти

⏰ ИШ ВАҚТИ:

08:00 — 18:00
📅 6 кун иш / 1 кун дам

❗ ТАЛАБЛАР:

▪️ Ишга ўз вақтида келиш
▪️ Хушмуомала ва киришимли бўлиш
▪️ Берилган вазифаларни ўз вақтида бажариш
▪️ Иш фақат Тошкент шаҳрида

📌 Батафсил маълумот суҳбат давомида берилади.

📞 МУРОЖААТ УЧУН:

+998 77 027 97 71
+998 77 021 97 71

📍 Манзил: Мирабад тумани, Куйлюк,Компас
🧭 Ориентир: IBR заправка
````

**Kutilgan natija:**

```yaml
kind: job
category: sotuv
salary_min: 7000000
salary_max: 15000000
currency: UZS
region: toshkent_sh
district: Mirobod
phones:
- '+998770279771'
- '+998770219771'
usernames: []
```


---

## 4. Xato yozilgan maosh + 88 kodli telefon

**Manba:** [@ishtoparuz_kanal/25043](https://t.me/ishtoparuz_kanal/25043) · **Media:** -

**Matn:**

````text
⚡️ Tekstil aksesuarlar ishlab chiqarish fabrikasiga yigitlar va ayollarni ishga taklif qilamiz
 
💵 Maosh: 
Yigitlar uchun 4 000 000-10 00 0000
Ayollar uchun 3 000 000 - 5 000 000

- Elonni yaxshilab o’qib keyin aloqaga chiqing o’zingizni va boshqani voxtini bekorga olmang !!

📣 Ish haqida: 
- Asosiy ishimiz 
Yigitlar uchun - to’qima stanoklarni ishlatishdan iborat
Ayollar uchun - ishlab chiqarilgan maxsulotlarni upakovka qilinadi

— Ish  bilmaganlar uchun 0 dan o’rgatiladi !!

 
❗️ Talablar:
- 22-35 yosh oralig’ida bo‘lishi
- Mas'uliyatli va intizomli bo‘lishi
- Jismonan va ruhiy sog‘lom bo‘lishi
- Ishga suhbat va sinov muddati asosida qabul qilinadi
 - Doyimiy ishlashga xodim kerak

✅ Biz taklif qilamiz:
- Viloyatdan kelgan yigitlar uchun yotoqxona va 3 mahal ovqat ish xona hisobidan
- Oylik har 15 kunda beriladi
- Yaxshi ishlagan xodimga bonuslar
- Sinov muddati 2 kun !!

- Ayollar uchun yotoqxonamiz yo’q !!


⏰ Ish vaqti:
- Erkaklar uchun 8:00 - 20:00
- Ayollar uchun    8:00 - 18:00
- Ish kuni 6 kun ish 1 kun dam 
 
📌 Manzil:
Yunusobod tumani, Bog‘ishamolko‘chasi, 160-uy
 
☎️ Bog‘lanish:
88-401-12-30
@Brunto_tex
````

**Kutilgan natija:**

```yaml
kind: job
category: ishlab_chiqarish
profession: sex_ishchisi
salary_min: 3000000
salary_max: 10000000
currency: UZS
region: toshkent_sh
district: Yunusobod
phones:
- '+998884011230'
usernames:
- '@Brunto_tex'
note: '''10 00 0000'' = 10 000 000'
```


---

## 5. Bitta postda 3 ta vakansiya + yashirin reklama havolalar

**Manba:** [@beminnatvakant_ish/24497](https://t.me/beminnatvakant_ish/24497) · **Media:** -

**Matn:**

````text
📢 Tajribali kimyo, tarbiya va rus tili (rus sinf) oʻqituvchilari kerak.

🏛 Tashkilot: 169-sonli maktab
⏱ Ish vaqti: Kelishuv asosida
💵 Maosh: Shtat jadvali asosids
📍Manzil: Toshkent shahar Shayxontohur tumani

📩Telegram: +998-93-588-84-88


📢 Tajribali matematika va boshlang'ich ta'lim (vaqtinchalik) oʻqituvchilari kerak.    1 stavka dars vakant.

🏛 Tashkilot: 315-sonli maktab
⏱ Ish vaqti: Kelishuv asosida
💵 Maosh: Shtat jadvali asosids
📍Manzil: Toshkent shahar Olmazor tumani

📩Telegram: +998-95-505-65-65


📢 O'quv markazga ingliz tili oʻqituvchilari kerak.

📌 Talablar:
— Oliy ma'lumotli, kamida 2 yillik (main teacher sifatida) ish tajribaga ega;
— Rus tilida ham dars bera olishi (ustunlik beradi);
— IELTS 7.0+ sertifikat bo'lishi kerak;
— Talabalar ishga olinmaydi (4-kurslardan tashqari);
— Pedagogika mahorati va o'quvchilar bilan ishlash ko'nikmasi;
— Zamonaviy o'qitish metodlarini bilishi;
— Ishga ma'suliyatli va intizomli.
✅ Vazifalar:
 • Guruh va individual darslar o‘tish;
 • General English va IELTS bo‘yicha o‘qitish;
 • Dars rejalarini tuzish, natija uchun ishlash;
 • O‘quvchilar bilan samarali muloqot.
🏛 Tashkilot: "Harward Academy"
⏱ Ish vaqti: Full time: 09:00 - 18:00; 6/1 ⏰ Part time: 14:00 - 20:00; 6/1
💵 Maosh: 12 - 20 mln so'm+
📍Manzil: Toshkent shahar Sergeli tumani Sergeli dehqon bozori.

📞 Aloqa: Rezyume va sertifikatlaringizni jo'nating👇
📩Telegram: @Medicaldoct

📍Ish yoki ishchi xodim topish: @beminnatvakant_ish va ta'limiy: @tilchi_tarjimon_jobs kanalidan izlang!

🔎 Maklersiz kvartira yoki kvartirant toping: @Kvartira_uylar_Tashkent
````

**Yashirin havolalar / tugmalar:**

- havola `⏎` → https://t.me/JahongirAcademy/2432
- havola `⏎` → https://t.me/JahongirAcademy/2432
- havola `⏎` → https://t.me/JahongirAcademy/2432

**Kutilgan natija:**

```yaml
kind: job
multi: true
category: talim
profession: oqituvchi
region: toshkent_sh
phones:
- '+998935888488'
- '+998955056565'
usernames:
- '@Medicaldoct'
drop_links:
- t.me/JahongirAcademy/2432 (matni bo'sh)
strip:
- 📍Ish yoki ishchi xodim topish... dan oxirigacha
```


---

## 6. REZYUME (ish qidiruvchi)

**Manba:** [@beminnatvakant_ish/24489](https://t.me/beminnatvakant_ish/24489) · **Media:** photo

**Matn:**

````text
📢 O’quv markaz, davlat va xususiy maktablardan biologiya fani bo'yicha ish joyi kerak.

Ism-familiya: Dinara
⏱️ Ish vaqti: Kelishiladi.
📍Manzil: Toshkent shahar istalgan tuman hududlaridan
💵 Maosh: Suhbatda kelishiladi.
📞 Telefon: +998-97-877-07-26
📲 Telegram:  @dinarahamroqulova

📌 Malaka va tajriba: 
➖ Biologiya o'qituvchisi.
➖ O'zbekiston Milliy Pedagogika universitetni tugatganman.
➖ Ingliz tili va rus tili B2 sertifikatim bor, shuningdek o'qitish bo'yicha
1 yillik ish tajribaga egaman.
````

**Kutilgan natija:**

```yaml
kind: resume
```


---

## 7. Albom + kurs reklamasi

**Manba:** [@beminnatvakant_ish/24486](https://t.me/beminnatvakant_ish/24486) · **Media:** photo

**Matn:**

````text
HR kasbi haqida eshitganmisiz? 

HR kasbida o’sish va rivojlanish, uning ortidan keladigan savob amallar va daromadlar haqidachi? 🔥

Men, Madina Farkhadovna, 5 yildan buyon HR sohasida faoliyat yuritib kelaman. Va 60 dan oshiq shogirdlar lar ustoziman . 

Sahifamda:

- Qalb kasbiga yo’l, qalb kasbini aniqlash;
- HR sohasiga kirish va rivojlanish
- Daromadni o’stirish
haqida gaplashamiz 💎

Shu kasbim orqali chet ellarga sayohat qildim, TOP kompaniyalarga ishga kirdim, orzuyimdagi hayotda yashash nasib qildi va sizga ham nasib qiladi. 🎁

https://t.me/+IzVF00vLNjg2NjIy

https://t.me/+IzVF00vLNjg2NjIy
````

**Kutilgan natija:**

```yaml
kind: not_job
note: grouped_id bilan 24483-24485 (matnsiz rasmlar) bilan bitta albom
```


---

## 8. hh.uz qolipi, aloqa faqat yashirin havolada, USD

**Manba:** [@ishmi_ish/7922](https://t.me/ishmi_ish/7922) · **Media:** -

**Matn:**

````text
📢 Marketing Manager kerak

🏢 Kompaniya: Jana Post

💰 Maosh: $900 – 1 000

💼 Tajriba: 1-3 yil tajriba

🛠 Vositalar: SMM

📍 Manzil: Toshkent

🌐 Format: Offline

👉 Batafsil: Link

📌 Obuna bo'ling: @ishmi_ish

#Marketing #SMM
````

**Yashirin havolalar / tugmalar:**

- havola `Link` → https://tashkent.hh.uz/vacancy/137865831

**Kutilgan natija:**

```yaml
kind: job
category: marketing
profession: marketolog
title_contains: Marketing Manager
company: Jana Post
salary_min: 900
salary_max: 1000
currency: USD
region: toshkent_sh
phones: []
usernames: []
apply_url: https://tashkent.hh.uz/vacancy/137865831
strip:
- '📌 Obuna bo''ling: @ishmi_ish'
- oxiridagi teglar
```


---

## 9. Bank reklamasi

**Manba:** [@ishmi_ish/7908](https://t.me/ishmi_ish/7908) · **Media:** photo

**Matn:**

````text
InfinBANKdan biznes-kreditlarini optimallashtirish

Turli banklardagi yuqori stavkalar va murakkab to'lovlardan charchadingizmi? 💰InfinBANKdan qayta moliyalashtirish - kichik va o'rta biznes uchun aqlli vositadir. Mutaxassislarimiz sizning joriy qarzlaringizni tahlil qilib, eng maqbul shartlarni tanlaydilar. Eski kreditlar yopiladi, siz esa tushunarli foiz stavkasi va qulay jadvali bilan bitta yangi qarz olasiz. Kamroq ortiqcha to'lovlar, o'sish uchun ko'proq imkoniyatlar va hech qanday murakkab muolajalarsiz! O'z biznesingizni kengaytirishga e'tibor qarating, moliyaviy tashvishlarni esa bizga ishonib topshiring. Qo'ng'iroq qiling va ariza topshiring: +998 71 202 50 80. 📞 

Batafsil

#reklama 
infinbank.com
````

**Yashirin havolalar / tugmalar:**

- havola `InfinBANKdan biznes-kreditlarini optimallashtirish` → https://ya.cc/t/PAepIUiWBB6VAt/?erid=j1SUkxjEe1QeSw4Ho
- havola `Batafsil` → https://ya.cc/t/PAepIUiWBB6VAt/?erid=j1SUkxjEe1QeSw4Ho
- havola `⏎infinbank.com` → https://ya.cc/t/PAepIUiWBB6VAt/?erid=j1SUkxjEe1QeSw4Ho

**Kutilgan natija:**

```yaml
kind: not_job
note: '#reklama va erid= havola'
```


---

## 10. Bot reklamasi

**Manba:** [@ishmi_ish/7913](https://t.me/ishmi_ish/7913) · **Media:** -

**Matn:**

````text
━━━━━━━━━━━━━━
🔥 O'zingizni sinab ko'ring!
📚 Yuzlab testlar shu yerda:
👉 @Zehndon_bot
━━━━━━━━━━━━━━
````

**Kutilgan natija:**

```yaml
kind: not_job
```


---

## 11. Ruscha

**Manba:** [@ish_kerak_edu/5550](https://t.me/ish_kerak_edu/5550) · **Media:** -

**Matn:**

````text
Вакансия: Оператор колл-центра (Интернет-провайдер)

Компания FreeLink - ведущий интернет провайдер Ташкента.Оказание полного комплекса телекоммуникационных услуг.
График работы: с 10:00 до 19:00

Обязанности:
• Базовые знания об интернет провайдера
• Прием входящих звонков от клиентов.
• Консультирование по тарифам и услугам интернета.
• Решение технических вопросов и помощь в настройке оборудования.

Требования:
• Грамотная речь, коммуникабельность.
• Ответственность, желание учиться.
• Опыт работы в колл-центре — приветствуется.
• Русский и узбекский обязательно.

Условия:
• Заработная плата от 4,000,000.
• Обучение и возможность роста.
• Официальное трудоустройство.

+998909395129 - Али
@HRFlink
````

**Kutilgan natija:**

```yaml
kind: job
category: operator
profession: operator
title_contains: Оператор колл-центра
company: FreeLink
salary_min: 4000000
currency: UZS
region: toshkent_sh
phones:
- '+998909395129'
usernames:
- '@HRFlink'
```


---

## 12. Strukturasiz bitta paragraf

**Manba:** [@ish_kerak_edu/5555](https://t.me/ish_kerak_edu/5555) · **Media:** -

**Matn:**

````text
Toshkent viloyati Parkent tumani ,,XAKIM OTA'' fermer xoʻjaligiga bogʻga va molga qarashga bitta yaxshi nomozxon, halol, mollarni arqonlab boqishni biladigan oʻzini ishini qilgandek ishlidigan odam kk ish qiyin emas  55 yoshgacha oylik 4.5mln sharoit+ovqat (ovqatni oʻzi tayyorlab yiydi) bn taminlanadi faqat astoydil ishlidigan odam yozsin

TELEFON :  +998991976796

TELEGRAM : @OzodXakimov

Agar vakansiya sizga mos bo‘lmasa — tanishingizga ulashing! Balki aynan u kishi ushbu imkoniyatni kutyapti.

📍Ish yoki ishchi xodim topish: @ish_kerak_edu

E'LON JOYLASH UCHUN :  @ish_kerak_edu_admini
````

**Kutilgan natija:**

```yaml
kind: job
category: boshqa
salary_min: 4500000
currency: UZS
region: toshkent_vil
district: Parkent
phones:
- '+998991976796'
usernames:
- '@OzodXakimov'
strip:
- Agar vakansiya sizga mos bo'lmasa... dan oxirigacha
note: Past ishonch bo'lishi mumkin → fallback shablon ham to'g'ri
```


---

## 13. Ko'p vakansiya, har biri telegra.ph havolali

**Manba:** [@ish_kerak_edu/5549](https://t.me/ish_kerak_edu/5549) · **Media:** -

**Matn:**

````text
Yaxshi ish qidirayotgan erkakalar uchun yangi imkoniyat!!!

🛒 EL MAGNAT Oziq-ovqat distribyutsiyasi 
 SIZNI KUTMOQDA❗️❗️❗️

Ochiq vakansiyalar:

📈 Sotuv agenti — 5–15 mln so‘m

👨‍💼 Administrator — 3–10 mln so‘m

📦 Ta’minot menejeri — 3–10 mln so‘m

📋 Yig‘uvchi — 3–7 mln so‘m

📦 Gruzchik — 3–5 mln so‘m


🎁 Qo‘shimcha shartlar:
🏠 Yotoq joyi mavjud
🍽 3 mahal ovqat kompaniya hisobidan
👨 Faqat erkak nomzodlar

📞Murojaat uchun:
+998 50-153-23-15

@Recruiter_IDI
````

**Yashirin havolalar / tugmalar:**

- havola `📈` → https://telegra.ph/SAVDO-AGENTLARNI-ISHGA-OLAMIZ-08-27
- havola `Sotuv agenti` → https://telegra.ph/SAVDO-AGENTLARNI-ISHGA-OLAMIZ-08-27
- havola `— 5–15 mln so‘m` → https://telegra.ph/SAVDO-AGENTLARNI-ISHGA-OLAMIZ-08-27
- havola `👨‍💼` → https://telegra.ph/ADMINISTRATOR-KERAK-08-27
- havola `Administrator` → https://telegra.ph/ADMINISTRATOR-KERAK-08-27
- havola `— 3–10 mln so‘m` → https://telegra.ph/ADMINISTRATOR-KERAK-08-27
- havola `📦` → https://telegra.ph/TAMINOT-BOLIMIGA-SHOGIRTlLAR-ISHGA-QABUL-BOSHLANDI-08-27
- havola `Ta’minot menejeri` → https://telegra.ph/TAMINOT-BOLIMIGA-SHOGIRTlLAR-ISHGA-QABUL-BOSHLANDI-08-27
- havola `— 3–10 mln so‘m` → https://telegra.ph/TAMINOT-BOLIMIGA-SHOGIRTlLAR-ISHGA-QABUL-BOSHLANDI-08-27
- havola `📋` → https://telegra.ph/OMBORGA-YIGUVCHI-ISHGA-TAKLIF-QILAMIZ-08-27
- havola `Yig‘uvchi` → https://telegra.ph/OMBORGA-YIGUVCHI-ISHGA-TAKLIF-QILAMIZ-08-27
- havola `— 3–7 mln so‘m` → https://telegra.ph/OMBORGA-YIGUVCHI-ISHGA-TAKLIF-QILAMIZ-08-27
- havola `📦` → https://telegra.ph/EL-MAGNAT-KOMPANIYASIGA-GRUZCHIKLAR-KERAK-08-27
- havola `Gruzchik` → https://telegra.ph/EL-MAGNAT-KOMPANIYASIGA-GRUZCHIKLAR-KERAK-08-27
- havola `— 3–5 mln so‘m` → https://telegra.ph/EL-MAGNAT-KOMPANIYASIGA-GRUZCHIKLAR-KERAK-08-27

**Kutilgan natija:**

```yaml
kind: job
multi: true
category: sotuv
profession: savdo_agenti
salary_min: 3000000
salary_max: 15000000
currency: UZS
phones:
- '+998501532315'
usernames:
- '@Recruiter_IDI'
```


---

## 14. 1️⃣ 2️⃣ ikki vakansiya, 87 kodli telefon

**Manba:** [@manavakansiya_uz/68947](https://t.me/manavakansiya_uz/68947) · **Media:** photo

**Matn:**

````text
⚡️ISHGA TAKLIF QILAMIZ!

1️⃣ SOMSA SOTUVCHI 

❗️25-35 yoshgacha boʻlgan ayol/qizlarni ishga olamiz

⏰Ish vaqti:  08:00 dan 19:00 gacha

💰Oylik:  3.000.000 dan
            4.500.000 gacha

📍Manzil:  Toshkent, Zangiota raysenterda

📞Murojaat uchun:  87-805-33-33
😎Telegram:  @MANAMAN_SOMSA
_________________________________



2️⃣ TAJRIBALI OSHPAZ

❗️ Yaxshi tajribali faqat erkaklarni ishga olamiz

⏰Ish vaqti:  07:00 dan 17:00 gacha

💰Oylik:  10.000.000 soʻm

📍Manzil:  Uchtepa t. Zamahshariy 2 uy 
Moʻljal: “Bedapoya”

📞Murojaat uchun: 87-805-33-33
😎Telegram:  @MANAMAN_SOMSA

👉 Ish kanallari to'plami / Подборка каналов с вакансиями

❗️Diqqat: Agar ish beruvchi ishga kirish uchun pul so‘rasa, ishonmang. Biz eʼlonlarni imkon qadar tekshiramiz, lekin shubha uyg'otsa siz ham o‘zingiz mustaqil tekshirib ko‘ring!

🫶Telegram
🫶Instagram
````

**Yashirin havolalar / tugmalar:**

- havola `Ish kanallari to'plami / Подборка каналов с вакансиями` → https://t.me/addlist/QYI-9SJ8WtpmMjIy
- havola `Telegram` → https://t.me/+rctzJySaV0IwZGY6
- havola `Instagram` → https://www.instagram.com/manavakansiya?igsh=cjBkNGtwNDlnOXc0

**Kutilgan natija:**

```yaml
kind: job
multi: true
category: oshxona
profession: oshpaz
region: toshkent_sh
phones:
- '+998878053333'
usernames:
- '@MANAMAN_SOMSA'
strip:
- 👉 Ish kanallari to'plami... dan oxirigacha
```


---

## 15. 9 raqamli telefon

**Manba:** [@manavakansiya_uz/68957](https://t.me/manavakansiya_uz/68957) · **Media:** photo

**Matn:**

````text
🔴 Vakansiya: OPERATSION TRENING MUTAXASSISI

💰Oklad: 5 000 000 so'm

💼Ofis: Yangi hayot, Indeks

📌3 ta asosiy missiyangiz.
— Yangi filial xodimlarini adaptatsiya qilish
— Savdo rejasini 80%dan oshirib bajarish
— Filialni reviziya tekshiruvidan balansda olib chiqish

❓Biz kimni qidiryapmiz.
— Savdo yoki o'qitish sohasida 2+ yil tajribali
— Odamlarni o'qita oladigan, natijaga olib bora oladigan
— Komandirovkalarga tayyor (viloyatlar bo'ylab)
— Bosim ostida reja bajara oladigan
— Yoshi: 24–35, erkak

✅Biz taklif qilamiz:
— har bir adaptatsiya qilingan filial uchun 2 million so'mdan
— Barcha komandirovka xarajatlari qoplanadi
— Filial menejeri yoki mintaqaviy trener sifatida o'sish
— Rasmiy ish joyi,

📞Murojaat: 772701545
📱 @askohr

👉 Ish kanallari to'plami / Подборка каналов с вакансиями

❗️Diqqat: Agar ish beruvchi ishga kirish uchun pul so‘rasa, ishonmang. Biz eʼlonlarni imkon qadar tekshiramiz, lekin shubha uyg'otsa siz ham o‘zingiz mustaqil tekshirib ko‘ring!

🫶Telegram
🫶Instagram
````

**Yashirin havolalar / tugmalar:**

- havola `Ish kanallari to'plami / Подборка каналов с вакансиями` → https://t.me/addlist/QYI-9SJ8WtpmMjIy
- havola `Telegram` → https://t.me/+rctzJySaV0IwZGY6
- havola `Instagram` → https://www.instagram.com/manavakansiya?igsh=cjBkNGtwNDlnOXc0

**Kutilgan natija:**

```yaml
kind: job
category: ofis
title_contains: TRENING
salary_min: 5000000
currency: UZS
region: toshkent_sh
district: Yangihayot
phones:
- '+998772701545'
usernames:
- '@askohr'
```


---

## 16. Ish emas: mashina ijarasi + depozit

**Manba:** [@ishlaUZ_rasmiy/11778](https://t.me/ishlaUZ_rasmiy/11778) · **Media:** photo

**Matn:**

````text
👨‍💻👨‍💻👨‍💻👨‍💻👨‍💻👨‍💻👨‍💻

✅Suxoy arenda yangi mashinalar 
 
💵 Maosh:  Depozit 200$
📍 Hudud: Toshkent 
 
#Toshkent #Ayollar #Erkaklar 
  
📣 Ish haqida: 
– DEPO TAXPARKDA SUXOY ARENDA MASHINALAR BERAMIZ 
 
❗️ Talablar: 
– Yosh: 24 yoshdan yuqori 
 
⏰ Ish vaqti: 
– 24/7 
 
📌 Manzil: 
– Toshkent sh. Uchtepa Depo Mall 
 
☎️ Bog‘lanish: 
– +998950007979 
– +998993171661

📷Instagram

📲Telegram
````

**Yashirin havolalar / tugmalar:**

- havola `Instagram` → https://www.instagram.com/ishla.uz?igsh=MXBldzNkY2Nsb3NuaA%3D%3D&utm_source=qr
- havola `Telegram` → https://t.me/ishlaUZ_rasmiy

**Kutilgan natija:**

```yaml
kind: suspicious
note: '''Depozit 200$'' maosh emas'
```


---

## 17. Kirill, ko'p lavozim, qisqa telefon

**Manba:** [@ishlaUZ_rasmiy/11788](https://t.me/ishlaUZ_rasmiy/11788) · **Media:** photo

**Matn:**

````text
👨‍💻👨‍💻👨‍💻👨‍💻👨‍💻👨‍💻👨‍💻

✅"Доброе" корхонасига ишга таклиф киламиз! 

Биз таклиф киламиз:

- Ойлик маош 4.000.000 дан бошланади

- Ётокхона хамда 3 махал овкат             корхона ҳисобидан

- Ахил жамоада ишлаш хамда ўсиш имконияти мавжуд

Мавжуд иш уринлари:

- Цех бошкарувчига ёрдамчи ( Тажриба булиши шарт) тунги смена 19:00-07:00 Ойлик келишилади

- Лаборант (Тажриба булиши шарт) тунги смена 19:00 - 07:00

- Грузчик (омбор га) кундузги смена 08:00 - 20:00

- Ишчи (холодильник бўлимига) кундузги смена 07:00-19:00


Манзил: Тошкент шахар Олмазор тумани Чукурсой 82
Тел: 33 077 14 03 t.me/HR_dobroe

📷Instagram

📲Telegram
````

**Yashirin havolalar / tugmalar:**

- havola `Instagram` → https://www.instagram.com/ishla.uz?igsh=MXBldzNkY2Nsb3NuaA%3D%3D&utm_source=qr
- havola `Telegram` → https://t.me/ishlaUZ_rasmiy

**Kutilgan natija:**

```yaml
kind: job
multi: true
category: ishlab_chiqarish
salary_min: 4000000
currency: UZS
region: toshkent_sh
district: Olmazor
phones:
- '+998330771403'
usernames:
- '@HR_dobroe'
strip:
- 👨‍💻👨‍💻... sarlavha
- 📷Instagram
- 📲Telegram
```


---

## 18. Kanal menyusi

**Manba:** [@ishtopuz_rasmiy/40835](https://t.me/ishtopuz_rasmiy/40835) · **Media:** photo

**Matn:**

````text
Ўзингизга керакли бўлган вилоятларни танланг👇

1. TOSHKENT | ISHTOP
2. VODIY | ISHTOP
3. SAMARQAND | ISHTOP
4. JIZZAX | ISHTOP
5. SIRDARYO | ISHTOP
6. NAVOIY | ISHTOP
7. BUXORO | ISHTOP
8. QASHQADARYO | ISHTOP
9. SURXONDARYO | ISHTOP
10. XORAZM | ISHTOP
11. QORAQALPOG’ISTON | ISHTOP

Ўзбекистон бўйлаб ишончли ва сара иш ўринларини биз билан топинг.
````

**Yashirin havolalar / tugmalar:**

- havola `TOSHKENT | ISHTOP` → https://t.me/ishtopuz_rasmiy
- havola `VODIY | ISHTOP` → https://t.me/+eeIiUnZsibs4MDJi
- havola `SAMARQAND | ISHTOP` → https://t.me/+ouGj3kZX2XtiYjMy
- havola `JIZZAX | ISHTOP` → https://t.me/+WBO-L24KR9w4MGYy
- havola `SIRDARYO | ISHTOP` → https://t.me/+SvSrGDJ8l8ljMjYy
- havola `NAVOIY | ISHTOP` → https://t.me/+OszatvKsEKE3Y2Ji
- havola `BUXORO | ISHTOP` → https://t.me/+jR8tkCn2lbo5MzUy
- havola `QASHQADARYO | ISHTOP` → https://t.me/+orsNHzxR5jVjOGJi
- havola `SURXONDARYO | ISHTOP` → https://t.me/+bbKC27-qDAdhODE6
- havola `XORAZM | ISHTOP` → https://t.me/+eku1lSACp9Q3MDcy
- havola `QORAQALPOG’ISTON | ISHTOP` → https://t.me/+6ykmxnt3bPljYTBi
- TUGMA `VILOYATNI TANLANG👈` → https://t.me/ishbor_ishtop_ishkerak/5

**Kutilgan natija:**

```yaml
kind: not_job
```


---

## 19. Lavozimsiz, faqat forma havolasi

**Manba:** [@ishtopuz_rasmiy/40829](https://t.me/ishtopuz_rasmiy/40829) · **Media:** photo

**Matn:**

````text
✅✅✅✅

Siz ham Crafers jamoasiga qo’shiling! 🤩

Qo'ng'iroq qilish shart emas — so’rovnomani to'ldiring, biz o'zimiz bog'lanamiz 👇

SO’ROVNOMANI TO’LDIRING👈

Diqqat⚠️ Hurmatli obunachi!
e’lonlarning texnik holatiga, oyliklarga va ish beruvchi bilan kelishuvingizga kanal ma’muriyati javob bermaydi!!!
Shaxsiy ma’lumotingizni (pasport,karta) hechkimga bermang!!!
Ish beruvchi pul talab qilsa kanal adminini ogohlantiring !!!
Ogohlik-davr talabi…


✅ instagram  |  ✅ telegram  | ✅ facebook

                                                                
✅✅✅✅✅✅
````

**Yashirin havolalar / tugmalar:**

- havola `SO’ROVNOMANI TO’LDIRING👈` → https://docs.google.com/forms/d/e/1FAIpQLSdS6CiLwqPRncUyjg_TYV6L7ahGcoOfmN7D3BMJGd8GANY4LQ/viewform
- havola `instagram` → https://instagram.com/ishtop.uz
- havola `telegram` → https://t.me/ishbor_ishtop_ishkerak
- havola `facebook` → https://www.facebook.com/profile.php?id=100088232062935&mibextid=LQQJ4d

**Kutilgan natija:**

```yaml
kind: job
confidence: past (fallback)
apply_url: https://docs.google.com/forms/d/e/1FAIpQLSdS6CiLwqPRncUyjg_TYV6L7ahGcoOfmN7D3BMJGd8GANY4LQ/viewform
strip:
- ✅✅✅✅
- Diqqat⚠️ Hurmatli obunachi! ... dan oxirigacha
```


---

## 20. Inglizcha, Unicode qalin harflar

**Manba:** [@unilance/7761](https://t.me/unilance/7761) · **Media:** -

**Matn:**

````text
We are looking for a 𝗨𝗫/𝗨𝗜 𝗗𝗲𝘀𝗶𝗴𝗻𝗲𝗿, 𝗣𝗿𝗼𝗱𝘂𝗰𝘁 𝗗𝗲𝘀𝗶𝗴𝗻𝗲𝗿 (WEB, Native)

𝗣𝗿𝗼𝗱𝘂𝗰𝘁: PropTech+Fintech Marketplace from 0 of a European Holding and an Uzbek Bank

𝗧𝗮𝘀𝗵𝗸𝗲𝗻𝘁, 𝗢𝗳𝗳𝗶𝗰𝗲 (𝗹𝗮𝘁𝗲𝗿 𝗛𝘆𝗯𝗿𝗶𝗱/𝗥𝗲𝗺𝗼𝘁𝗲)
Up to 3800 USD Gross
Spoken English from B2!

𝗧𝗮𝘀𝗸𝘀
- Ensuring a positive user experience across all processes, and participate in and support the design, development, and testing of digital interfaces 
- Defining client/user research needs, conduct field research at external parties and analyze the results, then incorporate them into the final product 
- Preparing, organize, and independently lead design workshops with the inclusion of internal business team 

 📩 Write via @anna_beexec with portfolio and cv

@unilance - the best for you
````

**Yashirin havolalar / tugmalar:**

- havola `𝗨𝗫/𝗨𝗜 𝗗𝗲𝘀𝗶𝗴𝗻𝗲𝗿, 𝗣𝗿𝗼𝗱𝘂𝗰𝘁 𝗗𝗲𝘀𝗶𝗴𝗻𝗲𝗿` → https://lnkd.in/dAvz75RZ

**Kutilgan natija:**

```yaml
kind: job
category: dizayn_media
profession: dizayner
title_contains: UX/UI Designer
salary_max: 3800
currency: USD
region: toshkent_sh
usernames:
- '@anna_beexec'
apply_url: https://lnkd.in/dAvz75RZ
note: 'NFKC: 𝗨𝗫 → UX'
```


---

## 21. Hazil

**Manba:** [@unilance/7770](https://t.me/unilance/7770) · **Media:** -

**Matn:**

````text
#hazil

- Oʻzbekistonda eng mashhur dasturlash tili qaysi? Qaysi dasturlash tilini oʻrgansam osonroq ish topaman?

- Rus tili degan dasturlash tilini oʻrgangin ukam, shunda osonroq ish topasan :)

© Ayyubxon Kamoldinov

@unilance - eng yaxshisi siz uchun
````

**Kutilgan natija:**

```yaml
kind: not_job
```


---

## 22. Juda tartibli qolip

**Manba:** [@kasbdoruz/5372](https://t.me/kasbdoruz/5372) · **Media:** photo

**Matn:**

````text
#vakansiya

📌 Call operator

• Maosh: 3 500 000 so‘m kafolatlangan maosh + bonuslar + KPI
• Manzil: Yunusobod, Ahmad Donish ko‘chasi, 20A, S-Space Biznes markazi, mo‘ljal — Turkiston metro bekati
• Ish vaqti: 9:00-18:00 6/1
• Ish beruvchi: UYSOT
• Holat: #faol

🔰 Sizdan talab qilinadi:
-Ish tajribasi shart emas — barchasini o‘rgatamiz! 
-O‘zbek tilini yaxshi bilish;
-Kirishimlilik va faollik;
-Mas’uliyatlilik;
-Rivojlanish va kompaniya bilan birga o‘sish istagi.

Siz nima bilan shug‘ullanasiz:
-Mijozlardan kelgan qo‘ng‘iroqlarni qabul qilish;
-Mahsulotlarimiz va xizmatlarimiz haqida ma’lumot berish;
-Sayt orqali kelib tushgan murojaatlarni qayta ishlash;
-Bajarilgan ishlar bo‘yicha hisobotlar tayyorlash.

➕ Qo‘shimcha:

- Greyd tizimi — kompaniyada o‘sasiz → daromadingiz ham oshadi;
- Ishning dastlabki bosqichida o‘quv-trening;
- Karyerada o‘sish imkoniyati;
- Tushlik xarajatining 50% kompaniya tomonidan qoplanadi;

- Barcha zarur sharoitlarga ega qulay ofis;

- Biz tashabbuskorlik, halollik, ochiqlik va rivojlanishga bo‘lgan intilishni qadrlaymiz.

UYSOT — ko‘chmas mulk sohasi uchun zamonaviy texnologiyalarni yaratayotgan PropTech kompaniya. So‘nggi bir yil ichida biz 3 baravarga o‘sdik — va bu hali boshlanishi! 
Yosh va jadal rivojlanayotgan IT-kompaniyada ishlashni, o‘zingizni rivojlantirishni va ajoyib jamoaning bir qismi bo‘lishni xohlaysizmi? Unda sizni jamoamizga taklif qilamiz! 

📞 Bog‘lanish uchun: 

@uysot_elyor - rezyume yuboring

👉🏻 E’lon joylash uchun: @kasbdor_uz

🌏 @Kasbdoruz— kasbiy o‘sishdagi ideal platformangiz!

N3311
````

**Kutilgan natija:**

```yaml
kind: job
category: operator
profession: operator
title_contains: Call operator
company: UYSOT
salary_min: 3500000
currency: UZS
region: toshkent_sh
district: Yunusobod
usernames:
- '@uysot_elyor'
phones: []
strip:
- 👉🏻 E'lon joylash uchun... dan oxirigacha (N3311 bilan)
```


---

## 23. Maslahat posti

**Manba:** [@kasbdoruz/5371](https://t.me/kasbdoruz/5371) · **Media:** photo

**Matn:**

````text
📌 Ish beruvchilarga yozishda yo‘l qo‘yiladigan xatolar va tavsiyalar

❌ Xatolar:

🔴 “Ish bormi?” yoki “Oylik qancha?” deb yozish.
🔴 O‘zingizni tanishtirmaslik.
🔴 Rasmiy ohangda yozmaslik – “salom”, “aka”, “opa” deb murojaat qilish rasmiyati yo‘qligini bildiradi
🔴 Xatolar bilan yozish, ortiqcha savollar berish.
🔴 Ketma-ket yozib, bezovta qilish.

✅ Tavsiyalar:

🟢 O‘zingizni tanishtiring – Ismingiz, kasbingiz va tajribangizni qisqacha yozing.
🟢 Aniq va lo‘nda yozing – “Sizning [lavozim] bo‘yicha vakansiyangizga qiziqayapman” kabi.
🟢 Hurmat bilan murojaat qiling – Rasmiy ohangni saqlang.
🟢 Savollaringizni aniq bering – Ish majburiyatlari va sharoitlari haqida so‘rang.

✅ Namuna:
“Assalomu alaykum. Mening ismim Ali, grafik dizayn sohasida 1 yillik tajribaga egaman. Sizning vakansiyangizga qiziqdim, batafsil ma’lumot bersangiz.”

🎯 Siz ushbu xatolarning qaysi birini qilgansiz? Fikrlaringizni izohlarda yozib qoldiring!

👉 Ko‘proq maslahatlar uchun @Kasbdoruz kanaliga obuna bo‘ling!
````

**Kutilgan natija:**

```yaml
kind: not_job
```


---

## 24. Ruscha, 'до 1000$'

**Manba:** [@jobmakon/1464](https://t.me/jobmakon/1464) · **Media:** -

**Matn:**

````text
🔥 WELKIN ИЩЕТ HR / RECRUITER

Если ты умеешь не просто «закрывать вакансии», а находить сильных людей и понимаешь цифры в рекрутинге — будем рады познакомиться!

🎯 Что нужно делать:
• Полный цикл подбора персонала;
• Основной фокус — поиск и найм менеджеров по продажам;
• Анализ эффективности рекрутинга: воронка, конверсии, источники кандидатов, скорость и качество найма;
• Работа с показателями и улучшение процесса найма.

👤 Кого мы ищем:
• Мужчина или женщина;
• С опытом работы в подборе персонала;
• Сильный навык поиска и оценки кандидатов;
• Опыт найма менеджеров по продажам будет большим преимуществом;
• Умеешь работать с аналитикой и делать выводы на основе цифр;
• Ответственный человек, который привык работать на результат.

💰 Условия:
🗓 График: 5/2
📍 Локация: Ракат Махалля
💵 Зарплата до 1000$ 

💬 Для отклика: отправляй резюме и пару слов о своём опыте в личные сообщения.@ainna_hr

@jobmakon - центр возможностей
````

**Kutilgan natija:**

```yaml
kind: job
category: ofis
profession: hr
title_contains: RECRUITER
company: WELKIN
salary_max: 1000
currency: USD
region: toshkent_sh
usernames:
- '@ainna_hr'
```


---

## 25. Imkoniyat (UNDP amaliyot dasturi)

**Manba:** [@jobmakon/1444](https://t.me/jobmakon/1444) · **Media:** -

**Matn:**

````text
🇺🇳 UNDP Internship 2026 — talabalar uchun haq to'lanadigan onlayn amaliyot dasturi

Moliyalashtirish: To'liq
Til talabi: Ingliz tili (sertifikat shart emas)

Kimlar uchun
- Bakalavr oxirgi kursida yoki magistraturada tahsil olayotgan bo'lish;
- Yaqinda bitirgan va bir yil ichida amaliyotni boshlay oladigan bo'lish.

Foydali tomonlari
- Oylik stipendiya;
- BMTning AI va raqamli texnologiyalar sohasida tajriba orttirish;
- Xalqaro networking imkoni;
- To'liq onlayn formatda ishlash imkoniyati.

Dastur haqida
Dastur raqamli texnologiyalar, sun'iy intellekt va innovatsiyalar sohasida talabalarga onlayn tajriba orttirish imkonini beradi. 

⏰️ Oxirgi muddat: 1-oktyabr, 2026
➡️ Batafsil: grantgo.uz/go/4c0zmj

@jobmakon - imkoniyatlar markazi
````

**Yashirin havolalar / tugmalar:**

- havola `UNDP Internship 2026` → http://grantgo.uz/go/4c0zmj

**Kutilgan natija:**

```yaml
kind: opportunity
```


---

## 26. Aloqa yashirin: 'Get the job.'

**Manba:** [@NextHireX/2516](https://t.me/NextHireX/2516) · **Media:** photo

**Matn:**

````text
💼 Job Title: Logistics #SALES Specialist
🏢 Company: Konida International Trading and Logistics
📍 Location: Tashkent, Yunusabad
💵 Salary / Rate: Negotiable based on experience
🕒 Schedule: Monday–Saturday, 09:00–18:00
📅 Experience: 1–2 years
Age: 22+

✅ Requirements:
• 1–2 years of experience in logistics, freight forwarding, or logistics sales
• Experience finding clients and/or cargo
• Understanding of logistics and container transportation
• Strong communication and sales skills
• Russian and English required
• Chinese or Uzbek is an advantage
• Experience developing the China–Central Asia route is an advantage
Code:667

📞 Contact: Get the job.
 | +998936765056


🔗 Posted by: @NextHireX – Find your next job in logistics and beyond!
````

**Yashirin havolalar / tugmalar:**

- havola `Get the job.` → http://t.me/HR_KONIDA

**Kutilgan natija:**

```yaml
kind: job
category: logistika
company: Konida International Trading and Logistics
region: toshkent_sh
district: Yunusobod
phones:
- '+998936765056'
usernames:
- '@HR_KONIDA'
```


---

## 27. Tugma + katta footer

**Manba:** [@huntmejob/37074](https://t.me/huntmejob/37074) · **Media:** photo

**Matn:**

````text
🏢 Safar TS LLC

👉 🚀 APPLY VIA HUNTER AI 👈

👔 Position: Fleet Specialist
🌎 Location: Tashkent, Uzbekistan
💼 Experience: 1-2 years
👤 Gender: Any
💵 Salary: $500 - $1,000

📋 Job Requirements:
• fleet management

💬 Contact: @Alex_fuel_fleet

Huntme Jobs
Platform | Hunter AI | Telegram

Try our products:

Jobs | Services | HRMS

All telegram channels

HUNTME — Endless Opportunities
````

**Yashirin havolalar / tugmalar:**

- havola `🚀 APPLY VIA HUNTER AI` → https://t.me/huntmesmartassistantbot?start=ch_apply_61e2357a-d4b7-4ad9-a604-1b8bf549deee
- havola `@Alex_fuel_fleet` → https://t.me/Alex_fuel_fleet
- havola `Platform` → https://jobs.huntmegroup.com/
- havola `Hunter AI` → https://t.me/huntmesmartassistantbot?start=ch_apply_61e2357a-d4b7-4ad9-a604-1b8bf549deee
- havola `Telegram` → https://t.me/huntmejob
- havola `Jobs` → https://jobs.huntmegroup.com/
- havola `Services` → https://marketplace.huntmegroup.com/
- havola `HRMS` → https://hrms.huntmegroup.com/
- havola `All telegram channels` → https://t.me/huntmegroup
- TUGMA `📝 Apply here` → https://backend.huntmegroup.com/track/apply/61e2357a-d4b7-4ad9-a604-1b8bf549deee?source=telegram_channel

**Kutilgan natija:**

```yaml
kind: job
category: logistika
profession: trucking
title_contains: Fleet Specialist
company: Safar TS LLC
salary_min: 500
salary_max: 1000
currency: USD
region: toshkent_sh
usernames:
- '@Alex_fuel_fleet'
apply_url: https://backend.huntmegroup.com/track/apply/61e2357a-d4b7-4ad9-a604-1b8bf549deee
strip:
- 👉 🚀 APPLY VIA HUNTER AI 👈
- Huntme Jobs... dan oxirigacha
```


---

## 28. Xizmat reklamasi

**Manba:** [@huntmejob/37080](https://t.me/huntmejob/37080) · **Media:** video

**Matn:**

````text
🚛 Toll & Fuel monitoring and saving 🇺🇸

Our area of ​​expertise is monitoring Toll and Fuel systems,  eliminating fraud  cases, reducing Fuel price and Toll costs.

⭐️ Features:
✅ 24/7 monitoring
✅ Avoiding from Toll roads
✅ Saving from Toll charges 30% up to %50
✅ Navigating Drivers from cheap (no Toll) Truck roads
✅ Pre-pass, Bestpass device monitoring
✅ Working with fuel stations at optimal prices
✅ Fuel card control & state limits
✅ Fraud detection & prevention
✅ MPG monitoring per truck
✅ APU & idling analysis
✅ Fuel cost savings $0.2 up to $0.4 per gallon

⭐️ Why choose us:
• you only pay when we save you money

💰 Pricing: 18–20% of savings

🔗 For more info

Huntme Marketplace
List your Service | Telegram

Try our products:

Jobs | Service | HRMS

All telegram channels 📱

HUNTME - Endless Opportunities
````

**Yashirin havolalar / tugmalar:**

- havola `For more info` → https://marketplace.huntmegroup.com/services/jtsmartroutes-jackson
- havola `List your Service` → https://marketplace.huntmegroup.com/
- havola `Telegram` → https://t.me/huntmemarketplace
- havola `Jobs` → https://app.huntmegroup.com/
- havola `Service` → https://marketplace.huntmegroup.com/
- havola `HRMS` → https://hrms.huntmegroup.com/
- havola `All telegram channels` → https://t.me/huntmegroup

**Kutilgan natija:**

```yaml
kind: not_job
```


---

## 29. Aloqa yashirin: 'Aloqa uchun 👈'

**Manba:** [@huntmeglobal/726](https://t.me/huntmeglobal/726) · **Media:** photo

**Matn:**

````text
☑️Lavozim: Grafik Dizayner 
☑️ Firma: ALSTAR ACP ishlab chiqarish zavodi
☑️ Maosh: 1000$ gacha
☑️ Manzil: Zangiota tumani, Katta Chinor MFY
☑️ Ish vaqti: 09:00–18:00
☑️ Ish tartibi: 5/2

☑️ TALABLAR:
•  Grafik dizayn sohasida kamida 2 yillik tajriba
•  Kreativ fikrlash va yangi g‘oyalar yaratish qobiliyati
•  Avval boshqa dizayn loyihalarida ishlagan bo‘lish
•  Dizayn yo‘nalishida amaliy tajriba va portfolio

☑️ BIZ TAKLIF QILAMIZ:
•  1000$ gacha maosh
•  Bepul tushlik
•  Professional rivojlanish imkoniyati
•  Barqaror va professional ish muhiti

Aloqa uchun 👈

Huntme Global Jobs 💜
Telegram

Try our products:

Jobs | Services | HRMS 

All telegram channels 📱
````

**Yashirin havolalar / tugmalar:**

- havola `Aloqa uchun` → https://t.me/hr_alstar
- havola `Telegram` → https://t.me/huntmeglobal
- havola `Jobs` → https://app.huntmegroup.com/
- havola `Services` → https://marketplace.huntmegroup.com/
- havola `HRMS` → https://hrms.huntmegroup.com/
- havola `All telegram channels` → https://t.me/huntmegroup

**Kutilgan natija:**

```yaml
kind: job
category: dizayn_media
profession: dizayner
title_contains: Grafik Dizayner
company: ALSTAR ACP
salary_max: 1000
currency: USD
region: toshkent_vil
district: Zangiota
usernames:
- '@hr_alstar'
```


---

## 30. Eng tartibli qolip, '—' bo'sh maydon

**Manba:** [@toshkentda_ish_bor_ishchi/6031](https://t.me/toshkentda_ish_bor_ishchi/6031) · **Media:** photo

**Matn:**

````text
#ish
📊Lavozim: Mobilograf
⏳Ish grafigi: 1-smena 09:00–18:00; 2-smena 15:00–22:00
📍Manzil: Shayxontohur tumani, Qoratosh ko‘chasi 5, Samarqand Darvoza ro‘parasi, DILNOZA BRAND magazini
📌Talablar: Tajribali bo‘lishi shart. Studentlar va o‘quvchilar kerak emas.
📚Vazifalar: —
💰Maosh: 4 000 000–7 000 000 so‘m
📝 Qo'shimchalar: —
📞Bog'lanish uchun: —
Telegram: @Dilnozaabrand, @Dilnozaa_brand


Siz ham ishchi yoki ish qidirayotgan bo'lsangiz, bizning kanalda hoziroq e'lon joylang
````

**Yashirin havolalar / tugmalar:**

- havola `Siz ham ishchi yoki ish qidirayotgan bo'lsangiz, bizning kan` → https://t.me/toshkentda_ish_bor_ishchi

**Kutilgan natija:**

```yaml
kind: job
category: dizayn_media
profession: mobilograf
title_contains: Mobilograf
salary_min: 4000000
salary_max: 7000000
currency: UZS
region: toshkent_sh
district: Shayxontohur
usernames:
- '@Dilnozaabrand'
- '@Dilnozaa_brand'
note: '''Vazifalar: —'' va ''Qo''shimchalar: —'' postda ko''rinmasin'
```


---

## 31. REZYUME (kirill)

**Manba:** [@Buxgalteriyaishorinlarii/5475](https://t.me/Buxgalteriyaishorinlarii/5475) · **Media:** -

**Matn:**

````text
Исмим: Зилола 
Aссалому алайкум 😊
Иш излаяпман 📢
Лавозим номи: бухгалтер
🏠 Яшаш жойим:__тошкент вилояти Келес шахри
📅 Туғулган сана 30.09.1991
🎓Маълумотим:_урта махсус
Иш тажрибаси: 10 йил
" Didox, Soliq uz, Банк клиент, Mehnat uz " ⚠️
1C, Word, Excel, ✅
☎️ Телефон рақам:  94 688 49 57
Телеграм: @ZILOLA1991
````

**Kutilgan natija:**

```yaml
kind: resume
```


---

## 32. Kurs narxi reklamasi

**Manba:** [@Buxgalteriyaishorinlarii/5451](https://t.me/Buxgalteriyaishorinlarii/5451) · **Media:** -

**Matn:**

````text
Dars narxi 650.000 som chegirma. 

Tajribali ustoz tarafidan  1 yil Qollab quvatlash
````

**Kutilgan natija:**

```yaml
kind: not_job
```


---

## 33. Kirill, viloyat, nuqtali telefon

**Manba:** [@Buxgalteriyaishorinlarii/5469](https://t.me/Buxgalteriyaishorinlarii/5469) · **Media:** -

**Matn:**

````text
#Buxgalter_kerak 
SAMARQAND
 Самарканд шахрида жойлашган Курилиш ташкилотига моддий ашёвий хисобчи керак
 
·         Аёл киши бўлса яхширок
·         Харакатчан, билим олишга чанкок, пунктуал
·         Иш вакти душанба-жума
·         Компьютерда ворд эксселда ишлаб биладиган
·         1С 8.3 версиясида ишлаб билиши керак
·         Ташкилотнинг ички хисоботларини килиб биладиган,
·         Жавобгар шахслар билан ишлайдиган
·         Иш хаки 6 млндан бошланади.
·         Колган билмаганларини иш давомида ургатамиз.                                                                   
·         Мабодо талабалар бўлса келаверинглар. Иш ўрганишга. Билганларимизни ургатамиз.
 
Тел: 97.798 67 22. Ўткир;
````

**Kutilgan natija:**

```yaml
kind: job
category: moliya
profession: buxgalter
salary_min: 6000000
currency: UZS
region: samarqand
phones:
- '+998977986722'
```


---

## 34. Ruscha, to'liq matn telegra.ph da

**Manba:** [@edustaffs/6797](https://t.me/edustaffs/6797) · **Media:** photo

**Matn:**

````text
#Вакансия #Ru

📌 Ночной Преподаватель английского языка

— Зарплата: от 5 000 000 до 15 000 000 сум;
 
— Адрес: Ташкент.

— Описание работы.

👉 Чтобы разместить объявление или резюме: Admin

📣 @EduStaffs — Место, где талант встречается с возможностями
````

**Yashirin havolalar / tugmalar:**

- havola `Описание работы` → https://telegra.ph/Nochnoj-Prepodavatel-anglijskogo-yazyka-09-28
- havola `Admin` → https://t.me/Entrepreneur_J

**Kutilgan natija:**

```yaml
kind: job
category: talim
profession: oqituvchi
salary_min: 5000000
salary_max: 15000000
currency: UZS
region: toshkent_sh
phones: []
usernames: []
apply_url: https://telegra.ph/Nochnoj-Prepodavatel-anglijskogo-yazyka-09-28
note: '@Entrepreneur_J (kanal admini) aloqa EMAS'
```


---

## 35. Huquqiy maslahat

**Manba:** [@edustaffs/6780](https://t.me/edustaffs/6780) · **Media:** -

**Matn:**

````text
❓Савол: Matematikadan SAT, Gmat yoki GRE sertifikat bor ustozlsrga toifa olishda qanday imtiyozlar bor?

❗️Жавоб: Бу сертификатлар учун тоифа олишда ҳеч қандай имтиёзлар берилмайди . 

 Низомнинг 36-банди (янги таҳрирда). Педагог кадрлар учун малака синовлари ҳар йили март – май ҳамда октябрь – ноябрь ойларида ваколатли вазирликлар томонидан ўтказилади.
...
(учинчи хатбоши) Умумий ўрта, ўрта махсус ва профессионал таълим ташкилотларининг камида C1 даражадаги миллий ёки унга мос даражадаги халқаро тан олинган сертификатга эга чет (инглиз, француз, немис, испан, итальян, араб, хитой, япон, корейс, турк, форс, пушту, дари, урду, ҳиндий) тили, Олий таълим, фан ва инновациялар вазирлиги ҳузуридаги Билим ва малакаларни баҳолаш агентлиги томонидан бериладиган умумтаълим фанини билиш даражаси тўғрисида сертификат ёки бошланғич таълим ўқитувчисининг билим даражаси ва педагогик маҳорати тўғрисидаги миллий сертификатдан камида B+ (аввалги тизимда 80 балл ёки ундан юқори) даражадаги сертификатга эга ўқитувчиларига сертификатнинг амал қилиш даврида навбатдаги мажбурий аттестацияда мутахассислик фани ва касб стандарти бўйича билим даражасини аниқлаш ҳамда ўқув фани бўйича малака синовидан максимал балл берилади ҳамда улар ушбу ўқув фани бўйича малака синовидан озод этилади. 

Бунда, сертификатга эга педагоглар иккинчи босқич синовида иштирок этишлари мажбурий ҳисобланади.

#маьлумот #фойдали

👉Эьлон ёки резюме жойлаш учун: Admin

📣 @EduStaffs — Иктидор имконият билан учрашадиган манзил
````

**Yashirin havolalar / tugmalar:**

- havola `Низомнинг 36-банди` → https://lex.uz/docs/5641270
- havola `Admin` → https://t.me/Entrepreneur_J

**Kutilgan natija:**

```yaml
kind: not_job
```


---

## 36. Keycap raqamli maosh + t.me/+998 telefon

**Manba:** [@Ish_Toshkent/6751](https://t.me/Ish_Toshkent/6751) · **Media:** video

**Matn:**

````text
📢 ДИҚҚАТ!

3️⃣.000.000 – 6️⃣.000.000 so‘m

«BRANDO TECH» kompaniyasi ishlab chiqarishni kengaytirish munosabati bilan maishiy texnika yo‘nalishida ishlagan, razryadi bor mutaxassislarni hamda ISH TAJRIBASIGA EGA BO‘LMAGAN YOSHLARNI ishga qabul qiladi.

❗️ Ish tartibi:
➖ 6 kunlik ish haftasi yoki smenali ish
➖ Ish vaqti: 08:00 – 18:00

✅ Afzalliklar:
🫥 Rasmiy ishga olinadi
🫥 Oylik o‘z vaqtida to‘lanadi
🫥 Har oyning 15-sanasi kuni avans beriladi
🫥 Bepul tushlik
🫥 Yangi bitirgan, tajribasiz yoshlarga ham ish o‘rinlari mavjud

🏠 Yotib qolib ishlovchilar uchun:
— Turar joy — bepul
— 3 mahal issiq ovqat + zakuskalar
— Ko‘plab bonus va rag‘batlantirishlar

✅ Kompaniyamiz Respublikamizning barcha hududlaridan qabul qiladi.

🧑‍✈️ VAKANT ISH O‘RINLARIMIZ O‘G‘IL BOLALAR VA QIZLAR UCHUN MO‘LJALLANGAN. 🧑‍✈️

📞 Murojaat uchun:
☎️ Telefon: +998 99 655 22 24
📝 Telegram: t.me/+998996552224

ERKAKLAR VA AYOLLAR ISHGA OLINADI

📍 Manzil: O‘zbekiston, Toshkent viloyati, Zangiota tumani, Bitavoy hududi.
````

**Kutilgan natija:**

```yaml
kind: job
category: ishlab_chiqarish
salary_min: 3000000
salary_max: 6000000
currency: UZS
region: toshkent_vil
district: Zangiota
phones:
- '+998996552224'
```


---

## 37. O'quv markaz reklamasi

**Manba:** [@Ish_Toshkent/6737](https://t.me/Ish_Toshkent/6737) · **Media:** photo

**Matn:**

````text
Maktabda darslar boshlandi — farzandingiz tayyormi?

⚡️ Yangi sinf, yangi mavzular, yangi talablar. Farzandingiz tengdoshlaridan ortda qolib ketmasin — tayyorgarlikni hoziroq boshlang.

✅ Hozirda Registonda:
— Ingliz tili;
— Rus tili;
— Matematika fanlari uchun qabul ochiq!

📞 920012700
Dastlabki BEPUL darsga yozilish uchun bosing
````

**Yashirin havolalar / tugmalar:**

- havola `Dastlabki BEPUL darsga yozilish uchun bosing` → https://www.registan-edu.uz/chorsu

**Kutilgan natija:**

```yaml
kind: not_job
```


---

## 38. Yashirin 'havola' + email

**Manba:** [@digitalitvacancy/740](https://t.me/digitalitvacancy/740) · **Media:** photo

**Matn:**

````text
Amerika bozoridagi startup uchun tajribali UI/UX veb dizayner izlanmoqda

📌Toshkent | Inhouse  
⚡️ Oylik: Tajribaga qarab ($300 - $1000)  
⌛ Ish vaqti: 13:00 dan 22:00 gacha

💼 Talablar:
➡️ Ofisdan ishlay olish
➡️ 2 yil+ ish tajribasi bo'lishi 
➡️ Figma bilan professional ishlay olish
➡️ Web-based SaaS, CRM, ERP loyihalarida tajriba
➡️AI dan professional foydalana olish
➡️Yangi g‘oyalarga ochiq bo‘lish
➡️Startap muhitida ishlay olish
➡️Ingliz tilini bilish

 📩 CV yuborish uchun: havola
🔗 Murojaat uchun e-pochta: rustamjon.business@gmail.com

⌛ Shoshiling, bunday qulay imkoniyatni qo‘ldan boy bermang!

🚀 Telegram
````

**Yashirin havolalar / tugmalar:**

- havola `havola` → https://t.me/rustamjon_019
- havola `Telegram` → https://t.me/digitalitvacancy

**Kutilgan natija:**

```yaml
kind: job
category: dizayn_media
profession: dizayner
title_contains: UI/UX
salary_min: 300
salary_max: 1000
currency: USD
region: toshkent_sh
usernames:
- '@rustamjon_019'
emails:
- rustamjon.business@gmail.com
```


---

## 39. Haq to'lanmaydigan amaliyot

**Manba:** [@digitalitvacancy/747](https://t.me/digitalitvacancy/747) · **Media:** photo

**Matn:**

````text
Yurideks jamoasi kengaymoqda!

💡 Yurideks jamoasiga 2 nafar stajyor AI Engineer / Full Stack Developer yo‘nalishida amaliyotga qabul qilinmoqda.

📌 Talablar:
✔️Ingliz tili – kamida B2 daraja;
✔️Git va GitHub bilan ishlash ko‘nikmasi;
✔️Kamida bitta dasturlash tilida boshlang‘ich tajriba (JavaScript/TypeScript yoki Python afzal);
✔️Mustaqil o‘rganish va muammolarga yechim topa olish;
✔️Tashabbuskorlik va startap muhitida faol ishlashga tayyorlik.

🧳 Imkoniyatlar:
✔️Real startap vazifalari ustida ishlash;
✔️Kuchli jamoa bilan amaliy tajriba orttirish;
✔️UzCombinator tomonidan tanlangan startap jamoasida ishlash;
✔️Amaliyot yakunida rasmiy tasdiqlovchi xat.

⚠️ Amaliyot uchun haq to‘lanmaydi.

📩 Murojaat uchun: havola

⌛ Shoshiling, bunday qulay imkoniyatni qo‘ldan boy bermang!

🚀 Telegram
````

**Yashirin havolalar / tugmalar:**

- havola `havola` → https://t.me/zilolakhon_yoldosheva
- havola `Telegram` → https://t.me/digitalitvacancy

**Kutilgan natija:**

```yaml
kind: opportunity
```


---

## 40. Yopilgan vakansiya

**Manba:** [@jobs_fba/60](https://t.me/jobs_fba/60) · **Media:** -

**Matn:**

````text
❌ VAKANSIYA YOPILDI

💼 IFRS Project Team Member
🏢 Central Bank of Uzbekistan
📍 Toshkent
🎯 Tajriba: 3-6 yil
💼 To'liq bandlik
🗓 Ish grafigi: To'liq kun · 5/2
⏰ Ish vaqti: 09:00-18:00
📅 Ariza muddati: 2026-08-24

Talablar:
• Oliy ma'lumot
• Rus tili
• Uzbek tili
• ACCA sertifikatlari
• Big Four kompaniyalari yoki Bankda ishlash tajribasi ustunlik beradi

🏷 Kalit ko'nikmalar: IFRS · Excel

Bu vakansiya yopilgan — arizalar qabul qilinmaydi.
````

**Kutilgan natija:**

```yaml
kind: closed
```


---

## 41. Ariza muddati o'tgan (2026-09-19)

**Manba:** [@jobs_fba/63](https://t.me/jobs_fba/63) · **Media:** -

**Matn:**

````text
💼 Financist
🏢 Multinational Mining Group
📍 Toshkent viloyati  Olmaliq shahar
💰 Maosh: 7 000 000 — 10 000 000 so'm
🎯 Tajriba: 1-3 yil
💼 To'liq bandlik
🗓 Ish grafigi: To'liq kun · 6/1
⏰ Ish vaqti: 09:00-18:00
📅 Ariza muddati: 2026-09-19

Talablar:
• Oliy ma'lumot
• Ingliz tili
• ACCA sertifikatlari (MA/FA/FM)
• Excel , Google sheet

👇 Qiziqsangiz — tugmani bosing, FBA Connect orqali ariza beriladi.
````

**Yashirin havolalar / tugmalar:**

- TUGMA `✋ Qiziqish bildirish` → https://t.me/fba_connect_bot?start=vak7

**Kutilgan natija:**

```yaml
kind: closed
note: 'Muddat hali o''tmagan bo''lsa: job, moliya/moliyachi, 7-10 mln, Olmaliq, apply_url
  fba_connect_bot tugmasi'
```


---

## KELISHILGAN SHABLON

**To'liq ajratilgan post** (kategoriya rasmi tepada, pastda matn, ≤ 1024 belgi):
```
💼 <b>Sotuvchi-konsultant</b>
🏢 Kompaniya: Texnomart

💰 Maosh: 4 000 000 – 6 000 000 so'm
📍 Manzil: Toshkent sh., Chilonzor tumani
🕒 Ish vaqti: 09:00–18:00, 6/1
📋 Talablar: 18–30 yosh, rus tili bilan ishlash

📞 Aloqa: +998 90 123 45 67
✉️ Telegram: @hr_texnomart

#sotuvchi #toshkent
➖➖➖➖➖➖➖➖
🔍 Ish qidiryapsizmi? @ayvonabot
📢 @ayvona — Ayvona Jobs
<i><a href="https://t.me/manba_kanal/12345">manba</a></i>
```
Tugmalar: `📩 Murojaat` (username bo'lsa) · `🔗 Ariza topshirish` (faqat apply_url bo'lsa) · `⭐ Saqlash` · `🔍 Boshqa ishlar`

**Manba qoidasi (Sardor so'rovi):** eng oxirgi qatorda kichik, qiya "manba" so'zi — asl postga havola
(`https://t.me/<kanal>/<post_id>`). Kanal nomi yozilmaydi, shuning uchun bizning imzomizdan ko'zga kamroq tashlanadi,
lekin bosgan odam asl postni ko'radi. Postda havola oldindan ko'rinishi (link preview) **o'chiq** bo'lishi shart
(`link_preview_options.is_disabled=True`), aks holda manba kanalning kartochkasi chiqib qoladi.
Foydalanuvchi e'lonlarida (bot orqali) manba qatori bo'lmaydi.

**Qoidalar:**
- Bo'sh maydon qatori chiqmaydi. Maosh bo'lmasa: `💰 Maosh: Kelishiladi`.
- Ko'p vakansiyali post: sarlavha = kompaniya yoki "Bir nechta vakansiya", `📌 Lavozimlar:` ro'yxati.
- Hammasi o'zbekcha va lotinda. Kirill o'zbekcha → lotinga o'giriladi. Ruscha/inglizcha e'londa: maydonlar o'zbekcha,
  lavozim lug'at bilan o'giriladi, erkin matn o'rniga `📝 To'liq ma'lumot: asl e'londa` havolasi (SOURCE_ANALYSIS 11-bo'lim).
- 1024 belgidan oshsa: avval "Talablar/Tafsilotlar" qisqartiriladi. Lavozim, maosh, manzil, aloqa, imzo, manba — hech qachon.

**Fallback** (regex yetarlicha ajrata olmaganda):
```
💼 <b>Yangi ish e'loni — Sotuv</b>

(manba reklamasidan tozalangan original matn)

📞 Aloqa: +998 90 123 45 67

#sotuvchi
➖➖➖➖➖➖➖➖
🔍 Ish qidiryapsizmi? @ayvonabot
📢 @ayvona — Ayvona Jobs
<i><a href="https://t.me/manba_kanal/12345">manba</a></i>
```

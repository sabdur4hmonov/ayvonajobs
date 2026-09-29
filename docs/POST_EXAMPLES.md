# Post misollari

Har bir manba kanaldan **2–3 ta** turli xil e'lon qo'ying (oddiy, chalkash, ruscha, rasmli...).
Matnni **aynan** ko'chiring — emoji, bo'sh qatorlar, havolalar bilan birga. Keyin shablonni shu misollarga qarab kelishamiz.

Nusxa olish uchun bo'sh qolip:

````markdown
## <kanal_username> — misol <n>
**Kanal:** @kanal_username
**Rasm bormi:** ha / yo'q
**Matn:**
```
(postni shu yerga aynan qo'ying)
```
**Kutilgan natija (bilsangiz):** kategoriya: ..., lavozim: ..., maosh: ..., hudud: ..., aloqa: ...
**Olib tashlanishi kerak:** (masalan: "Kanalimizga obuna bo'ling @xxx")
````

---

<!-- Misollarni shu chiziqdan pastga qo'ying -->



---

## KELISHILGAN SHABLON (loyiha — misollardan keyin yakunlaymiz)

**To'liq ajratilgan post** (kategoriya rasmi tepada, pastda matn):
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
```
Tugmalar: `📩 Murojaat` · `⭐ Saqlash` · `🔍 Boshqa ishlar`

**Fallback** (regex yetarlicha ajrata olmaganda):
```
💼 <b>Yangi ish e'loni — Sotuv</b>

(manba reklamasidan tozalangan original matn)

📞 Aloqa: +998 90 123 45 67

#sotuvchi
➖➖➖➖➖➖➖➖
🔍 Ish qidiryapsizmi? @ayvonabot
📢 @ayvona — Ayvona Jobs
```

Ochiq savollar (misollardan keyin hal qilamiz):
- Manba kanal nomini ko'rsatamizmi ("Manba: @...")? — tavsiya: yo'q, lekin agar manba so'rasa qo'shiladi.
- Maosh bo'lmasa: qatorni yashiramizmi yoki "Kelishiladi" deb yozamizmi?
- Kanal tili: faqat lotin, yoki rus postlarni ruscha qoldiramizmi?

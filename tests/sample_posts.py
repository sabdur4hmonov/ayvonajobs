# ruff: noqa: E501 — the posts are kept as they were written
"""Anonymized source posts behind the problems seen in the channel sample of 2026-10-07.

The sample file itself (data/channel_sample_2026-10-07.txt) holds real phone numbers and stays out
of git; these are reconstructions of the source posts with FAKE phones (+998 90 000 ...), fake
usernames (@test_...) and changed names. Each one reproduced its bug with the old code.
"""

from __future__ import annotations

# B.1 — a tin-can workshop titled "Buxgalteriya va moliya" (#moliya), with a stray #qashqadaryo
TIN_CAN_WORKSHOP = """⚡️ Temir banka ishlab chiqarish sehiga ishga taklif qilamiz

💵 Maosh: 4 000 000 - 7 000 000 so'm gacha

🆔 Yosh: 18-40

📣 Ish haqida:
Temir banka ishlab chiqarish sehiga quyidagi lavozimlarga ishchilar taklif qilinadi:
– Shtamplovchi
– Ishlab chiqarishda umumiy ishlar
– Mexanik (oylik alohida kelishiladi)

!!️FAQAT ERKAKLAR UCHUN ISH. AYOLLAR BEZOVTA QILMANG!

❗️ Talablar:
– Shtamplovchi presda ishlashni bilishi yaxshi
– Ishga o'z vaqtida kelish
– Xarakatchan va mehnatkash bo'lishi
– Yoshi: 18-40
– Toshkent shahridan bo'lishi

⏰ Ish vaqti:
– 8:00 dan 18:00gacha
– 6 kun ish, 1 kun dam
– Sinov muddati 7 kun (ishni o'zimiz o'rgatamiz)
– Oylik o'z vaqtida beriladi
– Yotib qolishga joy yo'q
– Yolkira beriladi
– Qarshi va boshqa viloyatlardan kelganlarga yotoqxona berilmaydi

📌 Manzil:
Toshkent shahar, Shayhontohur tumani, Shoahmad Shomahmudov ko'chasi 12-uy

📞 Aloqa: +998 90 000 11 01"""

# B.1 — a cybersecurity engineer became "Ishlab chiqarish" (#texnolog)
CYBERSECURITY = """🔐 Testlab'ga kiberxavfsizlik bo'yicha mutaxassis kerak!

Agar siz DLP, PAM, NGFW, WAF, MFA, IAM/IDM, EDR/XDR ni tushunsangiz va shunchaki infratuzilma bilan emas, balki haqiqiy to'lov mahsuloti bilan ishlashni istasangiz, biz aynan sizni izlayotgan bo'lishimiz mumkin.

Vazifalarda nimalar bo'ladi:
- xavfsizlik yechimlarini joriy etish va rivojlantirish;
- Yangi texnologiyalar PoC;
- AD / Entra ID, SIEM va infratuzilma bilan integratsiya;
- mustahkamlash, tekshirish va muammolarni bartaraf etish;
- sotuvchilar va infratuzilma jamoalari bilan ishlash.

Biz uchun quyidagilar muhim:
Axborot xavfsizligi / Xavfsizlik muhandisligi sohasida 2 yildan ortiq tajriba va tarmoqlar, Windows/Linux hamda AD bo'yicha yaxshi bilimga ega.

🚀 Nimalarni taklif etamiz:
• zamonaviy xavfsizlik vositalari bilan ishlash;
• rasmiy ishga joylashish;
• Toshkentdagi ofis.

Ariza: https://example.com/test-apply"""


def hh_post(title: str, company: str, salary: str = "Kelishiladi", n: int = 1) -> str:
    """The hh.uz-style posts of @ishmi_ish (labels, an apply link)."""
    return (
        f"💼 Vakansiya: {title}\n🏢 Kompaniya: {company}\n💰 Maosh: {salary}\n"
        f"📍 Manzil: Toshkent\n\n👉 Ariza: https://tashkent.hh.uz/vacancy/10000{n}"
    )


# B.1 / B.2 / B.3 — marketing roles: #boshqa, word order, a salary that is surely not so'm
HEAD_OF_MARKETING = hh_post(
    "Head of Marketing / Marketing-lid", "TEST CORP", "20 000 000 so'mdan", 1
)
DIGITAL_CONTENT = hh_post("Digital Content Specialist", "TEST CA", n=2)
CONTENT_MANAGER = hh_post("Kontent Menejer", "OOO TEST WORLD", n=3)
GROWTH_MARKETING = hh_post("B2B Growth Marketing Lead", "TEST CENTER", n=4)
MARKETING_SPECIALIST = hh_post(
    "Mutaxassis bo'yicha marketing", "TEST STEEL", "12 000 000 – 14 000 000 so'm", 5
)
MARKETING_DIRECTOR = hh_post("Direktor bo'yicha marketing", "TESTAXIS", "1 000 – 5 000 so'm", 6)

# B.2 — a garbage fragment as the title
MEN_AND_WOMEN = """Ishlab chiqarish sexiga erkak va ayollarini ishga taklif qilamiz

Oylik: 3 500 000 - 4 100 000 so'm
Yotoqxona bor, 3 mahal ovqat
Manzil: Toshkent shahri

Tel: +998 90 000 11 02, +998 90 000 11 03"""

# B.2 — the bare "Ishchi" of a warehouse job
WAREHOUSE_WORKER = """Omborga ishchilar kerak

Oylik: 7 000 000 so'mdan
Manzil: Toshkent shahri, Qo'yliq
Talablar: Yosh 19 dan 45 gacha, talabalar bo'lmasligi kerak

Tel: +998 90 000 11 04"""

# B.2 — trucking "Update specialist"
UPDATE_SPECIALIST = """We are hiring: Update Specialist

Company: TEST TRUCKING
Night shift, Yunusobod office
Contact: @test_trucking_hr"""

# B.3 — "3 –7 000 000 so'm"
SALES_OPERATOR = """Sotuv operatori kerak

Maosh: 3 –7 000 000 so'm
Ish vaqti: 08:00 - 14:00 yoki 14:00 – 20:00
Talablar: 17–22 yosh atrofidagi yigit-qizlar, xushmuomala va kirishimli
Manzil: Toshkent shahri

Ariza: https://forms.gle/testform"""

# B.3 / B.6 — a salary sentence and the meaningless "Talablar: Administrator uchun"
TEACHER_AND_ADMIN = """Rus tili o'qituvchisi va administrator kerak

🏢 Kompaniya: TestMaster o'quv markazi
💰 Maosh: Administrator oyligi 3 mln so'm, O'qituvchilar uchun har bir o'quvchidan 50 000 so'm
🕒 Ish vaqti: Administrator uchun: 13:30 dan 21:30 gacha
📋 Talablar: Administrator uchun
📍 Manzil: Toshkent sh., Yunusobod tumani, Minor metro yaqinida

📞 +998 90 000 11 05
✉️ @test_russmaster"""

# B.4 — slogans / sentences / stray quotes in the company field
CALL_OPERATOR_SLOGAN = """Call-markaz operatori kerak

🏢 Kompaniya: Zamonaviy va qulay ofis
💰 Maosh: 3 000 000 – 15 000 000 so'm
📍 Manzil: Toshkent sh., Yakkasaroy tumani
📋 Talablar: 18–30 yosh; Muloqot qilishni yoqtiradigan; O'rganishga tayyor

📞 +998 90 000 11 06"""

SALES_SLOGAN = """Sotuv menejeri kerak

🏢 Kompaniya: Shinam va qulay ish joyi
💰 Maosh: 8 000 000 – 14 000 000 so'm
📍 Manzil: Toshkent sh., Sergeli tumani
📋 Talablar: Call-markazda tajriba bo'lsa afzallik; Mijozlar bilan xushmuomala suhbat qura olish

📞 +998 90 000 11 07"""

COFFEE_LADY = """Kofe lady kerak

🏢 Kompaniya: Test A.Ş. kompaniyasining bosh ofisiga xodimlar va mehmonlarga choy-kofe damlash uchun xodim kerak
💰 Maosh: 5 000 000 so'm
📍 Manzil: Toshkent sh., Yunusobod tumani, 19-kvartal
📋 Talablar: Yosh: 18–35; Hushmuomala va chaqqon bo'lish

✉️ Telegram: @test_silkroad"""

SCHOOL_QUOTE = """Fan o'qituvchilari kerak

🏢 Kompaniya: "Testismus school" xususiy maktabi
💰 Maosh: Kelishiladi
📍 Manzil: Toshkent sh., Shayxontohur tumani
📋 Talablar: O'z sohasida 3 yillik ish tajribaga ega; Rus tilini bilishi kerak

📞 +998 90 000 11 08
✉️ @test_school"""

# B.5 — the same vacancy in two channels, 45 minutes apart, a name spelled two ways
_DUP_BODY = """📋 Talablar:
- 20–30 yosh oralig'idagi qizlar
- Kuniga 70–100 ta qo'ng'iroq qila oladigan
- Kuniga 2–5 ta sotuv yopa oladigan
- Kamida 25%+ konversiya ko'rsatgan
- Sotuv sohasida kamida 1 yil amaliy tajriba
- CRM bilan ishlash tajribasi shart
📍 Manzil: Toshkent sh., Nest One

📞 +998 90 000 11 09
✉️ @test_sevinch_hr"""

DUPLICATE_A = f"""Sotuv menejer kerak

🏢 Kompaniya: Ilhom Testqulov
💰 Maosh: 4 000 000 – 35 000 000 so'm
🕒 Ish vaqti: 9:00-18:00 6/1
{_DUP_BODY}"""

DUPLICATE_B = """🔥 Nest One'dagi ofisimizga jamoa kengaymoqda!
💼 Lavozim: "HUNTER" sotuv menejeri
🏢 Kompaniya: Ilxom Testkulov
💰 Maosh: 4 000 000 – 35 000 000 so'm + KPI (fiks + foiz)
🕒 Ish vaqti: 6/1 | 09:00–18:00

Nomzodga talablar:
✅ 20–30 yosh oralig'idagi qizlar
✅ Kuniga 70–100 ta qo'ng'iroq qila oladigan
✅ Kuniga 2–5 ta sotuv yopa oladigan
✅ Kamida 25%+ konversiya ko'rsatgan
✅ Sotuv sohasida kamida 1 yil amaliy tajriba
✅ CRM bilan ishlash tajribasi shart

Biz taklif qilamiz: rasmiy ish, o'qitish, karyera o'sishi.
📍 Manzil: Toshkent sh., Nest one
☎️ Murojaat: +998 90 000 11 09 yoki @test_sevinch_hr"""

# B.8 — upper-case "VA" in a title
CASHIER = """Kassir VA vitrinachi kerak

Maosh: 6 000 000 – 15 000 000 so'm
Manzil: Toshkent shahri
Talablar: Yigit, 18–35 yosh; Savdoda kamida 3 oy tajriba

✉️ @test_nilufar"""

# B.8 — "Illustration designer at <company>" left the company in the title
ILLUSTRATOR = """Vacancy: Illustration designer at Test Agency

We are hiring a designer for children's books. Remote, full-time job.
Requirements: portfolio, 2+ years of experience in illustration.
Salary: negotiable
Email: jobs@test-agency.example"""

ALL = {
    "tin_can_workshop": TIN_CAN_WORKSHOP,
    "cybersecurity": CYBERSECURITY,
    "head_of_marketing": HEAD_OF_MARKETING,
    "digital_content": DIGITAL_CONTENT,
    "content_manager": CONTENT_MANAGER,
    "growth_marketing": GROWTH_MARKETING,
    "marketing_specialist": MARKETING_SPECIALIST,
    "marketing_director": MARKETING_DIRECTOR,
    "men_and_women": MEN_AND_WOMEN,
    "warehouse_worker": WAREHOUSE_WORKER,
    "update_specialist": UPDATE_SPECIALIST,
    "sales_operator": SALES_OPERATOR,
    "teacher_and_admin": TEACHER_AND_ADMIN,
    "call_operator_slogan": CALL_OPERATOR_SLOGAN,
    "sales_slogan": SALES_SLOGAN,
    "coffee_lady": COFFEE_LADY,
    "school_quote": SCHOOL_QUOTE,
    "duplicate_a": DUPLICATE_A,
    "duplicate_b": DUPLICATE_B,
    "cashier": CASHIER,
    "illustrator": ILLUSTRATOR,
}

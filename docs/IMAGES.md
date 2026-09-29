# Post rasmlari

Har bir kanal postining tepasida rasm turadi. Rasm **kasb** bo'yicha tanlanadi (`#shifokor` → shifokor rasmi),
kasb rasmi bo'lmasa — **kategoriya** rasmi, u ham bo'lmasa — **boshqa**.
Har turda **3–4 ta variant**; ular **navbat bilan** ishlatiladi (1 → 2 → 3 → 1 ...), shuning uchun ketma-ket
kelgan ikki "shifokor" posti har xil rasm bilan chiqadi.

## Papkalar (tayyor, bo'sh)

```
assets/images/
  tibbiyot/            ← kategoriya rasmlari: 1.jpg 2.jpg 3.jpg
    shifokor/          ← kasb rasmlari: 1.jpg 2.jpg 3.jpg 4.jpg
    hamshira/
  sotuv/
    sotuvchi/
  ...
  boshqa/              ← hech narsa topilmasa (majburiy!)
```
Fayl nomi ahamiyatsiz (`1.jpg`, `doctor-2.png` — hammasi olinadi), tartib — nom bo'yicha.
Yangi rasm qo'shilsa yoki o'chirilsa — bot o'zi sezadi (restart kerak emas).

## Rasm talablari

- **O'lcham:** 1280 × 720 px (16:9, kanal lentasida eng chiroyli). Format: JPG yoki PNG, **< 1 MB**.
- **Uslub hamma rasmda bir xil** (brend): bir xil ranglar, bir xil shrift, burchakda kichik `@ayvona` / "Ayvona Jobs" logotipi.
- Rasmda kasb nomi o'zbekcha (masalan "SHIFOKOR"). Telefon, maosh kabi o'zgaruvchan ma'lumot **yozilmaydi**.
- Faqat ruxsatli rasmlar: o'zingiz chizgan/yasagan, yoki bepul litsenziyali fotolar (Unsplash, Pexels).
  Boshqa kanallarning rasmlarini, tanilgan brend logotiplarini ishlatmang.
- Bepul vosita: Canva (bepul tarif) — bitta shablon yasab, faqat rasm va yozuvni almashtirib chiqish eng tez yo'l.

## Qaysi tartibda yasash (ko'p uchraydiganlari birinchi)

**1-navbat — kategoriyalar (19 × 3 = 57 rasm).** Shular bo'lsa, tizim to'liq ishlaydi.
**2-navbat — ko'p uchraydigan kasblar:** sotuvchi, sotuv_menejeri, operator, oshpaz, ofitsiant, haydovchi, kuryer,
tikuvchi, oqituvchi, administrator, buxgalter, dasturchi, dispetcher, mobilograf, smm, farrosh.
**3-navbat — qolgan kasblar** (vaqt bo'lganda).

Rasm hali yo'q joyda Bosqich 6 avtomatik **vaqtinchalik** rasm (rangli fon + kasb nomi) yasaydi — kanal hech qachon rasmsiz qolmaydi.

## Admin botdan boshqarish (Bosqich 8)

- `/images` — qaysi kategoriya/kasbda nechta rasm bor, qaysilari vaqtinchalik (bo'shliqlar ro'yxati).
- `/addimage shifokor` → botga rasm yuborasiz → saqlanadi, darhol navbatga qo'shiladi.
- `/images shifokor` → rasmlar ko'rinadi, har birida [🗑 O'chirish].

## To'liq ro'yxat (64 kasb, 19 kategoriya)

| # | Tur | Papka | Nechta |
|---|---|---|---|
| 1 | **Sotuv va savdo** | `assets/images/sotuv/` | 3 ta (majburiy) |
|  | └ Sotuvchi (#sotuvchi) | `assets/images/sotuv/sotuvchi/` | 3–4 ta (ixtiyoriy) |
|  | └ Kassir (#kassir) | `assets/images/sotuv/kassir/` | 3–4 ta (ixtiyoriy) |
|  | └ Sotuv menejeri (#sotuv_menejeri) | `assets/images/sotuv/sotuv_menejeri/` | 3–4 ta (ixtiyoriy) |
|  | └ Savdo agenti (#savdo_agenti) | `assets/images/sotuv/savdo_agenti/` | 3–4 ta (ixtiyoriy) |
|  | └ Promouter (#promouter) | `assets/images/sotuv/promouter/` | 3–4 ta (ixtiyoriy) |
| 2 | **Operator / Call-markaz** | `assets/images/operator/` | 3 ta (majburiy) |
|  | └ Call-markaz operatori (#operator) | `assets/images/operator/operator/` | 3–4 ta (ixtiyoriy) |
| 3 | **Oshxona va restoran** | `assets/images/oshxona/` | 3 ta (majburiy) |
|  | └ Oshpaz (#oshpaz) | `assets/images/oshxona/oshpaz/` | 3–4 ta (ixtiyoriy) |
|  | └ Ofitsiant (#ofitsiant) | `assets/images/oshxona/ofitsiant/` | 3–4 ta (ixtiyoriy) |
|  | └ Barista (#barista) | `assets/images/oshxona/barista/` | 3–4 ta (ixtiyoriy) |
|  | └ Nonvoy / Qandolatchi (#nonvoy) | `assets/images/oshxona/nonvoy/` | 3–4 ta (ixtiyoriy) |
|  | └ Idish yuvuvchi (#idish_yuvuvchi) | `assets/images/oshxona/idish_yuvuvchi/` | 3–4 ta (ixtiyoriy) |
| 4 | **Haydovchi va kuryer** | `assets/images/transport/` | 3 ta (majburiy) |
|  | └ Haydovchi (#haydovchi) | `assets/images/transport/haydovchi/` | 3–4 ta (ixtiyoriy) |
|  | └ Kuryer (#kuryer) | `assets/images/transport/kuryer/` | 3–4 ta (ixtiyoriy) |
| 5 | **Ishlab chiqarish** | `assets/images/ishlab_chiqarish/` | 3 ta (majburiy) |
|  | └ Tikuvchi (#tikuvchi) | `assets/images/ishlab_chiqarish/tikuvchi/` | 3–4 ta (ixtiyoriy) |
|  | └ Sex ishchisi (#sex_ishchisi) | `assets/images/ishlab_chiqarish/sex_ishchisi/` | 3–4 ta (ixtiyoriy) |
|  | └ Qadoqlovchi (#qadoqlovchi) | `assets/images/ishlab_chiqarish/qadoqlovchi/` | 3–4 ta (ixtiyoriy) |
|  | └ Texnolog / Laborant (#texnolog) | `assets/images/ishlab_chiqarish/texnolog/` | 3–4 ta (ixtiyoriy) |
| 6 | **Ombor va ishchi** | `assets/images/ombor/` | 3 ta (majburiy) |
|  | └ Omborchi (#omborchi) | `assets/images/ombor/omborchi/` | 3–4 ta (ixtiyoriy) |
|  | └ Yuk tashuvchi (#yuk_tashuvchi) | `assets/images/ombor/yuk_tashuvchi/` | 3–4 ta (ixtiyoriy) |
|  | └ Ishchi (#ishchi) | `assets/images/ombor/ishchi/` | 3–4 ta (ixtiyoriy) |
| 7 | **Ta'lim** | `assets/images/talim/` | 3 ta (majburiy) |
|  | └ O'qituvchi (#oqituvchi) | `assets/images/talim/oqituvchi/` | 3–4 ta (ixtiyoriy) |
|  | └ Tarbiyachi (#tarbiyachi) | `assets/images/talim/tarbiyachi/` | 3–4 ta (ixtiyoriy) |
|  | └ Kurator / Yordamchi o'qituvchi (#kurator) | `assets/images/talim/kurator/` | 3–4 ta (ixtiyoriy) |
| 8 | **Ofis va boshqaruv** | `assets/images/ofis/` | 3 ta (majburiy) |
|  | └ Administrator (#administrator) | `assets/images/ofis/administrator/` | 3–4 ta (ixtiyoriy) |
|  | └ HR / Rekruter (#hr) | `assets/images/ofis/hr/` | 3–4 ta (ixtiyoriy) |
|  | └ Menejer (#menejer) | `assets/images/ofis/menejer/` | 3–4 ta (ixtiyoriy) |
|  | └ Kotiba / Ofis menejeri (#kotiba) | `assets/images/ofis/kotiba/` | 3–4 ta (ixtiyoriy) |
|  | └ Yurist (#yurist) | `assets/images/ofis/yurist/` | 3–4 ta (ixtiyoriy) |
| 9 | **IT** | `assets/images/it/` | 3 ta (majburiy) |
|  | └ Dasturchi (#dasturchi) | `assets/images/it/dasturchi/` | 3–4 ta (ixtiyoriy) |
|  | └ Tester (QA) (#tester) | `assets/images/it/tester/` | 3–4 ta (ixtiyoriy) |
|  | └ DevOps / Tizim administratori (#devops) | `assets/images/it/devops/` | 3–4 ta (ixtiyoriy) |
|  | └ Data / AI mutaxassisi (#data) | `assets/images/it/data/` | 3–4 ta (ixtiyoriy) |
|  | └ IT menejer (#it_menejer) | `assets/images/it/it_menejer/` | 3–4 ta (ixtiyoriy) |
| 10 | **Logistika** | `assets/images/logistika/` | 3 ta (majburiy) |
|  | └ Dispetcher (#dispetcher) | `assets/images/logistika/dispetcher/` | 3–4 ta (ixtiyoriy) |
|  | └ Logist (#logist) | `assets/images/logistika/logist/` | 3–4 ta (ixtiyoriy) |
|  | └ Trucking mutaxassisi (#trucking) | `assets/images/logistika/trucking/` | 3–4 ta (ixtiyoriy) |
| 11 | **Dizayn va media** | `assets/images/dizayn_media/` | 3 ta (majburiy) |
|  | └ Dizayner (#dizayner) | `assets/images/dizayn_media/dizayner/` | 3–4 ta (ixtiyoriy) |
|  | └ Mobilograf / Videograf (#mobilograf) | `assets/images/dizayn_media/mobilograf/` | 3–4 ta (ixtiyoriy) |
|  | └ Fotograf (#fotograf) | `assets/images/dizayn_media/fotograf/` | 3–4 ta (ixtiyoriy) |
| 12 | **Marketing va SMM** | `assets/images/marketing/` | 3 ta (majburiy) |
|  | └ SMM menejer (#smm) | `assets/images/marketing/smm/` | 3–4 ta (ixtiyoriy) |
|  | └ Marketolog (#marketolog) | `assets/images/marketing/marketolog/` | 3–4 ta (ixtiyoriy) |
|  | └ Targetolog (#targetolog) | `assets/images/marketing/targetolog/` | 3–4 ta (ixtiyoriy) |
|  | └ PR menejer (#pr) | `assets/images/marketing/pr/` | 3–4 ta (ixtiyoriy) |
| 13 | **Buxgalteriya va moliya** | `assets/images/moliya/` | 3 ta (majburiy) |
|  | └ Buxgalter (#buxgalter) | `assets/images/moliya/buxgalter/` | 3–4 ta (ixtiyoriy) |
|  | └ Moliyachi / Iqtisodchi (#moliyachi) | `assets/images/moliya/moliyachi/` | 3–4 ta (ixtiyoriy) |
|  | └ Auditor (#auditor) | `assets/images/moliya/auditor/` | 3–4 ta (ixtiyoriy) |
| 14 | **Tibbiyot** | `assets/images/tibbiyot/` | 3 ta (majburiy) |
|  | └ Shifokor (#shifokor) | `assets/images/tibbiyot/shifokor/` | 3–4 ta (ixtiyoriy) |
|  | └ Stomatolog (#stomatolog) | `assets/images/tibbiyot/stomatolog/` | 3–4 ta (ixtiyoriy) |
|  | └ Hamshira (#hamshira) | `assets/images/tibbiyot/hamshira/` | 3–4 ta (ixtiyoriy) |
|  | └ Farmatsevt (#farmatsevt) | `assets/images/tibbiyot/farmatsevt/` | 3–4 ta (ixtiyoriy) |
|  | └ Tibbiy vakil (#tibbiy_vakil) | `assets/images/tibbiyot/tibbiy_vakil/` | 3–4 ta (ixtiyoriy) |
| 15 | **Qurilish va ustalar** | `assets/images/qurilish/` | 3 ta (majburiy) |
|  | └ Quruvchi (#quruvchi) | `assets/images/qurilish/quruvchi/` | 3–4 ta (ixtiyoriy) |
|  | └ Elektrik (#elektrik) | `assets/images/qurilish/elektrik/` | 3–4 ta (ixtiyoriy) |
|  | └ Santexnik (#santexnik) | `assets/images/qurilish/santexnik/` | 3–4 ta (ixtiyoriy) |
|  | └ Payvandchi (#payvandchi) | `assets/images/qurilish/payvandchi/` | 3–4 ta (ixtiyoriy) |
|  | └ Mebel ustasi (#mebel_ustasi) | `assets/images/qurilish/mebel_ustasi/` | 3–4 ta (ixtiyoriy) |
|  | └ Avto usta (#avto_usta) | `assets/images/qurilish/avto_usta/` | 3–4 ta (ixtiyoriy) |
| 16 | **Xizmat ko'rsatish** | `assets/images/xizmat/` | 3 ta (majburiy) |
|  | └ Farrosh / Tozalovchi (#tozalik) | `assets/images/xizmat/tozalik/` | 3–4 ta (ixtiyoriy) |
|  | └ Qo'riqchi (#qoriqchi) | `assets/images/xizmat/qoriqchi/` | 3–4 ta (ixtiyoriy) |
|  | └ Enaga / Uy yordamchisi (#enaga) | `assets/images/xizmat/enaga/` | 3–4 ta (ixtiyoriy) |
|  | └ Mehmonxona xodimi (#mehmonxona) | `assets/images/xizmat/mehmonxona/` | 3–4 ta (ixtiyoriy) |
| 17 | **Go'zallik** | `assets/images/gozallik/` | 3 ta (majburiy) |
|  | └ Sartarosh (#sartarosh) | `assets/images/gozallik/sartarosh/` | 3–4 ta (ixtiyoriy) |
|  | └ Kosmetolog (#kosmetolog) | `assets/images/gozallik/kosmetolog/` | 3–4 ta (ixtiyoriy) |
|  | └ Manikyur ustasi (#manikyur) | `assets/images/gozallik/manikyur/` | 3–4 ta (ixtiyoriy) |
| 18 | **Xorijda ish** | `assets/images/chet_el/` | 3 ta (majburiy) |
| 19 | **Boshqa** | `assets/images/boshqa/` | 3 ta (majburiy) |

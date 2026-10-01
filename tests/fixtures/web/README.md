# Saqlangan veb-javob namunalari (Bosqich 16)

Testlar haqiqiy saytlarga so'rov yubormaydi (`tests/conftest.py` har qanday HTTP so'rovni to'xtatadi).
Bu fayllar har saytning **API hujjatidagi maydon nomlari** bo'yicha qo'lda yozilgan, ma'lumotlar sun'iy
(kompaniya va e'lonlar o'ylab topilgan). Sayt javob formati o'zgarsa — shu yerdagi namunani yangilab, testni moslang.

| Fayl | Sayt | Manba hujjati (2026-10-01 o'qilgan) |
|---|---|---|
| `himalayas.json` | Himalayas | https://himalayas.app/api |
| `remotive.json` | Remotive | https://github.com/remotive-com/remote-jobs-api |
| `jobicy.json` | Jobicy | https://github.com/Jobicy/remote-jobs-api |
| `remoteok.json` | Remote OK | https://remoteok.com/api (1-element — huquqiy eslatma) |
| `hh_vacancies.json` | hh.uz | https://github.com/hhru/api (vacancies) |
| `feed_rss.xml`, `feed_atom.xml`, `feed_nodates.xml` | istalgan RSS/Atom | RSS 2.0 / Atom 1.0 |
| `osonish_*.xml`, `osonish_vacancy_*.html` | Oson Ish | robots.txt: `Sitemap:`, `Crawl-delay: 1`, `/api/` taqiq |

⚠️ Oson Ish sahifa tuzilishi jonli saytda tekshirilmagan: kod avval JSON-LD `JobPosting` ni, bo'lmasa
`og:title` / `og:description` ni o'qiydi. Birinchi haqiqiy ishga tushirishda natijani tekshiring.

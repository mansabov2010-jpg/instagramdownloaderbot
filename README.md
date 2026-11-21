<p align="center">
  <a href="https://www.fiverr.com/share/kpLBoo">
    <img src="https://iili.io/BOeHp5J.jpg" alt="All Url Uploader banner" width="100%"/>
  </a>
</p>

<div align="center">

# All Url Uploader

**To‘g‘ridan-to‘g‘ri havolalar va qo‘llab-quvvatlanadigan media manbalarni Telegramga yuklang.**

Qulay lokal ish jarayoni uchun `aiogram`, `yt-dlp` va `uv` asosida yaratilgan.

[![CI](https://github.com/mansabov2010-jpg/instagramdownloaderbot/actions/workflows/ci.yml/badge.svg)](https://github.com/mansabov2010-jpg/instagramdownloaderbot/actions/workflows/ci.yml)
[![CodeQL](https://github.com/mansabov2010-jpg/instagramdownloaderbot/actions/workflows/codeql.yml/badge.svg)](https://github.com/mansabov2010-jpg/instagramdownloaderbot/actions/workflows/codeql.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/release/python-3110/)
[![License](https://img.shields.io/github/license/mansabov2010-jpg/instagramdownloaderbot)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/mansabov2010-jpg/instagramdownloaderbot?style=flat)](https://github.com/mansabov2010-jpg/instagramdownloaderbot/stargazers)

[Hujjatlar](docs/README.md) · [Hissa qo‘shish](CONTRIBUTING.md) · [Docker](Dockerfile) · [Muammolar](https://github.com/mansabov2010-jpg/instagramdownloaderbot/issues) · [Muhokamalar](https://github.com/mansabov2010-jpg/instagramdownloaderbot/discussions) 

</div>

**All Url Uploader** — bu to‘g‘ridan-to‘g‘ri fayl URL manzillarini va qo‘llab-quvvatlanadigan media havolalarini qabul qiladigan, ularni vazifaga mos vosita yordamida yuklab oladigan hamda natijani mos media turi, metama’lumotlar va ixtiyoriy maxsus muqova (thumbnail) bilan Telegramga yuboradigan bot.

## Nimalarni qo‘llab-quvvatlaydi

- to‘g‘ridan-to‘g‘ri fayl havolalari
- `url|fayl_nomi`
- `url|fayl_nomi|login|parol`
- `url * fayl_nomi`
- YouTube audio va videoni tezkor yuklab olish
- qo‘llab-quvvatlanadigan `yt-dlp` manbalari uchun format tanlash
- `/thumb` va `/delthumb` buyruqlari orqali har bir foydalanuvchi uchun alohida muqova (thumbnail) sozlash

## Bot buyruqlari

- `/start` - salomlashish xabari, tezkor imkoniyatlar va foydalanish bo‘yicha yo‘riqnoma
- `/help` - qo‘llab-quvvatlanadigan havola formatlari va ish jarayoni haqida ma’lumot
- `/about` - ishga tushirish tafsilotlari, repozitoriy havolasi va loyiha eslatmalari
- `/thumb` - hozir saqlangan maxsus muqovani ko‘rsatish
- `/delthumb` - saqlangan maxsus muqovani o‘chirish

## Tezkor ishga tushirish

1. Repozitoriyani klonlang va ichiga kiring:

```bash
git clone [https://github.com/mansabov2010-jpg/instagramdownloaderbot.git](https://github.com/mansabov2010-jpg/instagramdownloaderbot.git)
cd instagramdownloaderbot

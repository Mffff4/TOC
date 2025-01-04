# TOC Bot

[🇷🇺 Русский](README-RU.md) | [🇬🇧 English](README.md)

[![Bot Link](https://img.shields.io/badge/Telegram_Бот-Link-blue?style=for-the-badge&logo=Telegram&logoColor=white)](https://t.me/TheOpenCoin_bot?start=ref_b2434667eb27d01f)
[![Channel Link](https://img.shields.io/badge/Telegram_Канал-Link-blue?style=for-the-badge&logo=Telegram&logoColor=white)](https://t.me/+0ZTdqLZEVvk1ZTZi)
[![MARKET](https://img.shields.io/badge/Telegram_Market-Link-blue?style=for-the-badge&logo=Telegram&logoColor=white)](https://t.me/MaineMarketBot?start=01FNMXZP)

---

## 📑 Оглавление
1. [Описание](#описание)
2. [Бесплатная и платная версии](#бесплатная-и-платная-версии)
3. [Ключевые особенности](#ключевые-особенности)
4. [Установка](#установка)
   - [Быстрый старт](#быстрый-старт)
   - [Ручная установка](#ручная-установка)
5. [Настройки](#настройки)
6. [Поддержка и донаты](#поддержка-и-донаты)
7. [Контакты](#контакты)

---

## 📜 Описание
**TOC Bot** — это автоматизированный бот для игры TOC. Поддерживает многопоточность, интеграцию прокси и автоматическое управление игрой.

---
## 💰 Бесплатная и платная версии
Функционал|Бесплатная версия|[Платная версия](https://t.me/MaineMarketBot?start=01FNMXZP)|
|---|---|---|
|Многопоточная работа с аккаунтами|✅|✅|
|Поддержка HTTP/SOCKS5 прокси|✅|✅|
|Автоматическое выполнение всех заданий|✅|✅|
|Автоматическое обновление|✅|✅|
|Защита от изменений API|❌|✅|
|100% рефералов идут вам|❌|✅|
|Приоритетные обновления|❌|✅|
|Персональный Telegram бот для управления|❌|✅|
|Доступ к закрытому каналу|❌|✅|

## 🌟 Ключевые особенностиё
- 🔄 **Многопоточность** — возможность работы с несколькими аккаунтами параллельно
- 🔐 **Поддержка прокси** — безопасная работа через прокси-серверы
- 🎯 **Управление заданиями** — автоматическое выполнение квестов

---

## 🛠️ Установка

### Быстрый старт
1. **Скачайте проект:**
   ```bash
   git clone https://github.com/Mffff4/TOC.git
   cd TOC
   ```

2. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Настройте параметры в файле `.env`:**
   ```bash
   API_ID=ваш_api_id
   API_HASH=ваш_api_hash
   ```

### Ручная установка
1. **Linux:**
   ```bash
   sudo sh install.sh
   python3 -m venv venv
   source venv/bin/activate
   pip3 install -r requirements.txt
   cp .env-example .env
   nano .env  # Укажите свои API_ID и API_HASH
   python3 main.py
   ```

2. **Windows:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   copy .env-example .env
   python main.py
   ```

---

## ⚙️ Настройки

```
REF_ID - это часть ссылки, например, в ссылке 

https://t.me/TheOpenCoin_bot?start=ref_b2434667eb27d01f 

значение ref_b2434667eb27d01f является идентификатором реферала.
```

| Параметр                  | Значение по умолчанию | Описание                                                 |
|---------------------------|----------------------|---------------------------------------------------------|
| **API_ID**                |                      | Идентификатор приложения Telegram API                   |
| **API_HASH**              |                      | Хэш приложения Telegram API                              |
| **GLOBAL_CONFIG_PATH**    |                      | Путь к файлам конфигурации. По умолчанию используется переменная окружения TG_FARM |
| **FIX_CERT**              | False                | Исправить ошибки сертификата SSL                        |
| **SESSION_START_DELAY**   | 360                  | Задержка перед началом сессии (в секундах)             |
| **REF_ID**                |                      | Идентификатор реферала для новых аккаунтов             |
| **USE_PROXY**             | True                 | Использовать прокси                                     |
| **SESSIONS_PER_PROXY**    | 1                    | Количество сессий на один прокси                        |
| **DISABLE_PROXY_REPLACE** | False                | Отключить замену прокси при ошибках                     |
| **BLACKLISTED_SESSIONS**  | ""                   | Сессии, которые не будут использоваться (через запятую)|
| **DEBUG_LOGGING**         | False                | Включить подробный логгинг                              |
| **DEVICE_PARAMS**         | False                | Использовать пользовательские параметры устройства        |
| **AUTO_UPDATE**           | True                 | Автоматические обновления                               |
| **CHECK_UPDATE_INTERVAL** | 300                  | Интервал проверки обновлений (в секундах)              |
| **SUBSCRIBE_TELEGRAM_CHANNEL** | False                | Подписка на канал              |
---

## 💰 Поддержка и донаты

Поддержите разработку с помощью криптовалют или платформ:

| Валюта               | Адрес кошелька                                                                       |
|----------------------|-------------------------------------------------------------------------------------|
| Bitcoin (BTC)        |bc1qt84nyhuzcnkh2qpva93jdqa20hp49edcl94nf6| 
| Ethereum (ETH)       |0xc935e81045CAbE0B8380A284Ed93060dA212fa83| 
| TON                  |UQBlvCgM84ijBQn0-PVP3On0fFVWds5SOHilxbe33EDQgryz|
| Binance Coin         |0xc935e81045CAbE0B8380A284Ed93060dA212fa83| 
| Solana (SOL)         |3vVxkGKasJWCgoamdJiRPy6is4di72xR98CDj2UdS1BE| 
| Ripple (XRP)         |rPJzfBcU6B8SYU5M8h36zuPcLCgRcpKNB4| 
| Dogecoin (DOGE)      |DST5W1c4FFzHVhruVsa2zE6jh5dznLDkmW| 
| Polkadot (DOT)       |1US84xhUghAhrMtw2bcZh9CXN3i7T1VJB2Gdjy9hNjR3K71| 
| Litecoin (LTC)       |ltc1qcg8qesg8j4wvk9m7e74pm7aanl34y7q9rutvwu| 
| Matic                |0xc935e81045CAbE0B8380A284Ed93060dA212fa83| 
| Tron (TRX)           |TQkDWCjchCLhNsGwr4YocUHEeezsB4jVo5| 

---

## 📞 Контакты

Если у вас возникли вопросы или предложения:
- **Telegram**: [Присоединяйтесь к нашему каналу](https://t.me/+0ZTdqLZEVvk1ZTZi)

---
## ⚠️ Дисклеймер

Данное программное обеспечение предоставляется "как есть", без каких-либо гарантий. Используя этот бот, вы принимаете на себя полную ответственность за его использование и любые последствия, которые могут возникнуть.

Автор не несет ответственности за:
- Любой прямой или косвенный ущерб, связанный с использованием бота
- Возможные нарушения условий использования сторонних сервисов
- Блокировку или ограничение доступа к аккаунтам

Используйте бота на свой страх и риск и в соответствии с применимым законодательством и условиями использования сторонних сервисов.

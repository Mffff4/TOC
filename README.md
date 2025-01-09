# WebEmoji Bot

[🇷🇺 Русский](README_RU.md) | [🇬🇧 English](README.md)

[![Bot Link](https://img.shields.io/badge/Telegram_Bot-Link-blue?style=for-the-badge&logo=Telegram&logoColor=white)](https://t.me/TheOpenCoin_bot?start=ref_b2434667eb27d01f)
[![Channel Link](https://img.shields.io/badge/Telegram_Channel-Link-blue?style=for-the-badge&logo=Telegram&logoColor=white)](https://t.me/+0ZTdqLZEVvk1ZTZi)
[![MARKET](https://img.shields.io/badge/Telegram_Market-Link-blue?style=for-the-badge&logo=Telegram&logoColor=white)](https://t.me/MaineMarketBot?start=01FNMXZP)

---

## 📑 Table of Contents
1. [Description](#description)
2. [Free and Paid Versions](#free-and-paid-versions)
3. [Key Features](#key-features)
4. [Installation](#installation)
   - [Quick Start](#quick-start)
   - [Manual Installation](#manual-installation)
5. [Settings](#settings)
6. [Support and Donations](#support-and-donations)
7. [Contacts](#contacts)
---

## 📜 Description
**The Open Coin** is an automated bot for the TOC game. Supports multithreading, proxy integration, and automatic game management.

---
## 💰 Free and Paid Versions
| Functionality | Free Version | [Paid Version](https://t.me/MaineMarketBot?start=01FNMXZP) |
| --- | --- | --- |
| Multithreading with accounts | ✅ | ✅ |
| Support for HTTP/SOCKS5 proxies | ✅ | ✅ |
| Automatic completion of all tasks | ✅ | ✅ |
| Automatic updates | ✅ | ✅ |
| API change protection | ✅ | ✅ |
| 100% referrals go to you | ❌ | ✅ |
| Priority updates | ❌ | ✅ |
| Personal Telegram bot for management | ❌ | ✅ |
| Access to the closed channel | ❌ | ✅ |

---
## 🌟 Key Features
- 🔄 **Multithreading** — ability to work with multiple accounts in parallel
- 🔐 **Proxy Support** — secure operation through proxy servers
- 🎯 **Quest Management** — automatic quest completion
- 📊 **Statistics** — detailed session statistics tracking

---

## 🛠️ Installation

### Quick Start
1. **Download the project:**
   ```bash
   git clone https://github.com/Mffff4/TOC.git
   cd TOC
   ```

2. **Install dependencies:**
   - **Windows**:
     ```bash
     run.bat
     ```
   - **Linux**:
     ```bash
     run.sh
     ```

3. **Get API keys:**
   - Go to [my.telegram.org](https://my.telegram.org) and get your `API_ID` and `API_HASH`
   - Add this information to the `.env` file

4. **Run the bot:**
   ```bash
   python3 main.py --action 3  # Run the bot
   ```

### Manual Installation
1. **Linux:**
   ```bash
   sudo sh install.sh
   python3 -m venv venv
   source venv/bin/activate
   pip3 install -r requirements.txt
   cp .env-example .env
   nano .env  # Add your API_ID and API_HASH
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

## ⚙️ Settings

REF_ID is a part of the link, for example, in the link 

https://t.me/TheOpenCoin_bot?start=ref_b2434667eb27d01f 

the value ref_b2434667eb27d01f is the referral identifier.

| Parameter                  | Default Value         | Description                                                 |
|---------------------------|----------------------|-------------------------------------------------------------|
| **API_ID**                |                      | Telegram API application ID                                 |
| **API_HASH**              |                      | Telegram API application hash                               |
| **GLOBAL_CONFIG_PATH**    |                      | Path for configuration files. By default, uses the TG_FARM environment variable |
| **FIX_CERT**              | False                | Fix SSL certificate errors                                  |
| **CHECK_API_HASH**        | True                 | Check for API hash changes                                 |
| **SESSION_START_DELAY**   | 360                  | Delay before starting the session (seconds)               |
| **REF_ID**                |                      | Referral ID for new accounts                                |
| **USE_PROXY**             | True                 | Use proxy                                                  |
| **SESSIONS_PER_PROXY**    | 1                    | Number of sessions per proxy                                |
| **DISABLE_PROXY_REPLACE** | False                | Disable proxy replacement on errors                         |
| **BLACKLISTED_SESSIONS**  | ""                   | Sessions that will not be used (comma-separated)           |
| **DEBUG_LOGGING**         | False                | Enable detailed logging                                     |
| **DEVICE_PARAMS**         | False                | Use custom device parameters                                 |
| **AUTO_UPDATE**           | True                 | Automatic updates                                           |
| **CHECK_UPDATE_INTERVAL** | 300                  | Update check interval (seconds)                            |
| **SUBSCRIBE_TELEGRAM_CHANNEL** | False                | Subscribe to the channel                                  |
| **NIGHT_MODE** | False                | Night mode                                                  |
| **NIGHT_TIME** | (0, 7)                | Night time (UTC)                                           |
| **NIGHT_CHECKING** | (10800, 14400)         | Night checking interval (seconds)                         |

## 💰 Support and Donations

Support development using cryptocurrencies:

| Currency              | Wallet Address                                                                     |
|----------------------|------------------------------------------------------------------------------------|
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

## 📞 Contact

If you have questions or suggestions:
- **Telegram**: [Join our channel](https://t.me/+0ZTdqLZEVvk1ZTZi)

---

## ⚠️ Disclaimer

This software is provided "as is" without any warranties. By using this bot, you accept full responsibility for its use and any consequences that may arise.

The author is not responsible for:
- Any direct or indirect damages related to the use of the bot
- Possible violations of third-party service terms of use
- Account blocking or access restrictions

Use the bot at your own risk and in compliance with applicable laws and third-party service terms of use.


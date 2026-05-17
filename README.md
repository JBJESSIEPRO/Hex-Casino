# HEX CASINO 🎰

A full-stack cyberpunk-themed casino web app built with Flask + SQLite + vanilla JS.

## Stack
- **Backend:** Python (Flask), SQLAlchemy, SQLite
- **Frontend:** HTML, CSS, JavaScript (no frameworks)
- **Auth:** Werkzeug password hashing, Flask sessions

## Games
- 🎰 **Slots** — 3 reel, symbol matching with multipliers
- 🃏 **Blackjack** — Full hit/stand/bust logic vs dealer
- 💣 **Mines** — Minesweeper-style risk/reward with cashout
- ♠️ **Video Poker** — 5 card draw with full hand evaluation

## Features
- User registration & login with hashed passwords
- Fake coin economy (1,000 HEX starting balance)
- Transaction history
- Live leaderboard
- Full mobile responsive UI

## Run Locally
```bash
pip install -r requirements.txt
python app.py
```
Then open http://localhost:5000

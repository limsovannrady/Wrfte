# QR Code Telegram Bot

## Overview

Python Telegram bot that generates and scans QR codes. Includes a web dashboard for monitoring activity.

## Stack

- Python 3.11+
- `python-telegram-bot` — Telegram Bot API
- `qrcode` + `pillow` — QR code generation
- `zxing-cpp` — QR code scanning/decoding
- SQLite — activity and user logging
- Built-in HTTP server — admin dashboard on port 5000

## Files

- `main.py` — entry point: starts bot (long polling) + dashboard (background thread)
- `bot_handlers.py` — /start, generate QR, decode QR handlers
- `db.py` — SQLite database: users and activity logging
- `dashboard.py` — HTTP server for admin dashboard API
- `templates/index.html` — dashboard frontend (Telegram Web App auth)
- `pyproject.toml` — Python package metadata and dependencies

## Bot behavior

- `/start` — greeting with instructions in Khmer
- Send any text or link → bot generates and returns a QR code image
- Send a photo of a QR code → bot scans and returns the decoded text

## Dashboard

- Runs on port 5000 (preview pane)
- Protected by Telegram Web App authentication (admin only)
- Shows total users, total actions, user list, and recent activity log

## Setup

Requires `TELEGRAM_BOT_TOKEN` secret in Replit Secrets.

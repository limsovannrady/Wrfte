# Telegram Business Bot

## Overview

This project is a Python Telegram bot using `python-telegram-bot`. It runs with long polling and reads the bot token from the `TELEGRAM_BOT_TOKEN` environment variable.

## Stack

- Python 3.11+
- `python-telegram-bot`
- Replit workflow: `Telegram Bot`

## Files

- `bot.py` — bot entry point, handlers, and polling setup
- `pyproject.toml` — Python package metadata and dependencies
- `uv.lock` — locked dependency versions

## Bot behavior

- `/start` replies with a Khmer greeting in normal Telegram chats.
- Telegram Business connection updates are logged and acknowledged when enabled.
- Telegram Business chat messages are handled via `business_message` and `edited_business_message` updates.
- Business replies include the message's `business_connection_id`, which is required for sending through a Telegram Business connection.
- Business direct-message topics are preserved with `direct_messages_topic_id` when Telegram provides one.
- Incoming update types are logged to help diagnose Telegram Business and third-party connection issues.
- Polling uses `Update.ALL_TYPES` so Telegram Business updates are received.

## Setup notes

The bot requires a valid `TELEGRAM_BOT_TOKEN` secret. To use it in Telegram Business, the bot must also be enabled for Business use in Telegram/BotFather and connected from the Telegram Business account settings.

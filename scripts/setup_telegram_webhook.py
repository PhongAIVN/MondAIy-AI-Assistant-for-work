"""Đăng ký webhook Telegram cho APP_PUBLIC_URL của môi trường hiện tại."""

import asyncio

from src.services.telegram_channel import configure_webhook

if __name__ == "__main__":
    asyncio.run(configure_webhook())
    print("Telegram webhook configured.")

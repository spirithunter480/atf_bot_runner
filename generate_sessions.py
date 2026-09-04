import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

# ۱. بارگذاری از .env با python-dotenv یا خواندن دستی در صورت عدم نصب پکیج
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # فال‌بک: خواندن دستی فایل .env بدون نیاز به کتابخانه خارجی
    if os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
        except Exception:
            pass

# دریافت مقادیر
raw_api_id = os.getenv("TG_API_ID", "").strip()
API_ID = int(raw_api_id) if raw_api_id.isdigit() else 0
API_HASH = os.getenv("TG_API_HASH", "").strip()

# ۲. در صورتی که در .env نبود، از ترمینال دریافت می‌شود
if not API_ID:
    input_id = input("Enter API_ID: ").strip()
    API_ID = int(input_id) if input_id.isdigit() else 0

if not API_HASH:
    API_HASH = input("Enter API_HASH: ").strip()


async def generate():
    if not API_ID or not API_HASH:
        print("[ERROR] Valid API_ID and API_HASH are required!")
        return

    print("--- Connecting to Telegram ---")
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        session_str = client.session.save()
        me = await client.get_me()
        print("\n" + "=" * 50)
        print(f"Logged in successfully: {me.first_name} (@{me.username})")
        print("Your Session String:")
        print(session_str)
        print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(generate())
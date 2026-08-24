import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

# ۱. اولویت اول: خواندن از متغیرهای محیطی
# ۲. اولویت دوم: خواندن از فایل‌های تکست محلی کنار کد
API_ID = int(os.getenv("TG_API_ID", 0))
API_HASH = os.getenv("TG_API_HASH", "")

if not API_ID and os.path.exists("TG_API_ID.txt"):
    try:
        with open("TG_API_ID.txt", "r", encoding="utf-8") as f:
            val = f.read().strip()
            if val.isdigit():
                API_ID = int(val)
    except Exception:
        pass

if not API_HASH and os.path.exists("TG_API_HASH.txt"):
    try:
        with open("TG_API_HASH.txt", "r", encoding="utf-8") as f:
            API_HASH = f.read().strip()
    except Exception:
        pass

# ۳. در صورتی که فایل‌ها هم نبودند، در ترمینال می‌پرسد
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
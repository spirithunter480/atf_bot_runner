import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

# Read sensitive API credentials from environment variables
API_ID = int(os.getenv("TG_API_ID", 0))
API_HASH = os.getenv("TG_API_HASH", "")

async def generate():
    if not API_ID or not API_HASH:
        print("[ERROR] TG_API_ID or TG_API_HASH is missing from environment variables!")
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
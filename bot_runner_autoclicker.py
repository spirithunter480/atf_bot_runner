import os
import json
import asyncio
import time
import uuid
import random
import urllib.parse
import aiohttp
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest

API_ID = 33536389
API_HASH = "916c4272b50ee8e6b76d41416f2756d6"
BOT_USERNAME = "ATF_AIRDROP_bot"
BASE_URL = "https://atfminers.asloni.online/miner/index.php"

# خواندن لیست اکانت‌ها از سکرت مشترک گیت‌هاب
RAW_ACCOUNTS = os.getenv("ACCOUNTS_JSON")
if RAW_ACCOUNTS:
    try:
        ACCOUNTS = json.loads(RAW_ACCOUNTS)
    except Exception as e:
        print(f"Error parsing ACCOUNTS_JSON: {e}")
        ACCOUNTS = []
else:
    ACCOUNTS = []

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://atfminers.asloni.online",
    "Referer": "https://atfminers.asloni.online/miner/"
}

async def fetch_init_data(session_str):
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.connect()
    bot_peer = await client.get_input_entity(BOT_USERNAME)
    
    web_view = await client(RequestWebViewRequest(
        peer=bot_peer,
        bot=bot_peer,
        platform="android",
        from_bot_menu=True,
        url="https://atfminers.asloni.online/miner/"
    ))
    await client.disconnect()
    
    parsed_url = urllib.parse.urlparse(web_view.url)
    params = urllib.parse.parse_qs(parsed_url.fragment)
    return params.get("tgWebAppData", [""])[0]

async def boost_worker(acc):
    acc_name = acc.get("name", "Account")
    device_id = acc.get("device_id", "")
    
    await asyncio.sleep(random.uniform(0.5, 3.0))
    
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        while True:
            try:
                init_data = await fetch_init_data(acc["session"])
                
                login_payload = {
                    "initData": init_data,
                    "device_id": device_id,
                    "request_id": str(uuid.uuid4())
                }
                async with session.post(f"{BASE_URL}?action=login&t={int(time.time()*1000)}", data=login_payload) as resp:
                    login_json = await resp.json(content_type=None)
                    if login_json.get("status") != "success":
                        print(f"[{acc_name}] Login failed. Retrying in 10s...")
                        await asyncio.sleep(10)
                        continue
                    
                    user_info = login_json.get("user", {})
                    tg_id = user_info.get("tg_id")
                    current_preview = float(user_info.get("pending_reward", 1.0))
                    print(f"[{acc_name}] Session Active | Synced Preview: {current_preview:.4f}")

                session_start = time.time()
                last_break_time = time.time()
                
                while time.time() - session_start < 2700:
                    current_preview += round(random.uniform(0.002, 0.008), 4)
                    
                    boost_payload = {
                        "device_id": device_id,
                        "display_preview": f"{current_preview:.4f}",
                        "initData": init_data,
                        "request_id": str(uuid.uuid4()),
                        "tg_id": tg_id
                    }
                    
                    async with session.post(f"{BASE_URL}?action=activate_boost&t={int(time.time()*1000)}", data=boost_payload) as b_resp:
                        if b_resp.status == 200:
                            try:
                                b_json = await b_resp.json(content_type=None)
                                if "pending_reward" in b_json:
                                    current_preview = float(b_json["pending_reward"])
                            except Exception:
                                pass
                            print(f"[{acc_name}] Tap Triggered -> Boost Active")
                        elif b_resp.status == 429:
                            cool_down = random.uniform(9.0, 15.0)
                            print(f"[{acc_name}] Rate limited (429)! Cooling down for {cool_down:.1f}s...")
                            await asyncio.sleep(cool_down)
                            continue
                        else:
                            print(f"[{acc_name}] Boost HTTP status: {b_resp.status}")

                    current_time = time.time()
                    
                    # وقفه کوتاه خستگی
                    next_break_interval = random.randint(600, 900)
                    if current_time - last_break_time > next_break_interval:
                        micro_break = random.uniform(20.0, 40.0)
                        print(f"[{acc_name}] Human short break: resting for {micro_break:.1f}s...")
                        await asyncio.sleep(micro_break)
                        last_break_time = time.time()
                    
                    # استراحت پایان سشن
                    elif (current_time - session_start) > random.randint(2400, 3600):
                        long_break = random.uniform(90.0, 120.0)
                        print(f"[{acc_name}] Session fatigue break: resting for {long_break:.1f}s...")
                        await asyncio.sleep(long_break)
                        session_start = time.time()
                        last_break_time = time.time()
                    else:
                        await asyncio.sleep(random.uniform(3.8, 7.3))

            except Exception as e:
                print(f"[{acc_name}] Worker error: {e}. Retrying in 5s...")
                await asyncio.sleep(5)

async def main():
    if not ACCOUNTS:
        print("No accounts found in ACCOUNTS_JSON.")
        return

    print("==================================================")
    print(">>> ATF Boost Auto-Clicker (Optimized Delays)")
    print(f">>> Running {len(ACCOUNTS)} Accounts Concurrently")
    print(">>> Press Ctrl + C to stop.")
    print("==================================================")
    
    await asyncio.gather(*(boost_worker(acc) for acc in ACCOUNTS))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOPPED] Auto-clicker stopped gracefully.")
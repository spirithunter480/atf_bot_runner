import os
import json
import asyncio
import time
import uuid
import random
import urllib.parse
import re
import aiohttp
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import RequestWebViewRequest

API_ID = 33536389
API_HASH = "916c4272b50ee8e6b76d41416f2756d6"
BOT_USERNAME = "ATF_AIRDROP_bot"

# BASE_URL = "https://atfminers.asloni.online/miner/index.php"
BASE_URL = "https://atf-bot-runner.mrankit4892.workers.dev/miner/index.php"

# ۱. اولویت اول: خواندن از سکرت گیت‌هاب (برای سرور)
# ۲. اولویت دوم: خواندن از فایل محلی accounts.json (برای لپ‌تاپ و ترموکس)
RAW_ACCOUNTS = os.getenv("ACCOUNTS_JSON")
if RAW_ACCOUNTS:
    try:
        ACCOUNTS = json.loads(RAW_ACCOUNTS)
    except Exception as e:
        print(f"Error parsing ACCOUNTS_JSON from env: {e}")
        ACCOUNTS = []
elif os.path.exists("accounts.json"):
    try:
        with open("accounts.json", "r", encoding="utf-8") as f:
            ACCOUNTS = json.load(f)
    except Exception as e:
        print(f"Error reading local accounts.json: {e}")
        ACCOUNTS = []
else:
    ACCOUNTS = []

TASKS = [
    "telegram_react_latest",
    "website_visit",
    "youtube_like_comment",
    "twitter_retweet"
]

def get_account_headers(acc):
    ua = acc.get("user_agent") or "Mozilla/5.0 (Linux; Android 14; SM-S928B Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.88 Mobile Safari/537.36"
    match = re.search(r"Chrome/(\d+)", ua)
    chrome_ver = match.group(1) if match else "128"
    
    return {
        "User-Agent": ua,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-CH-UA": f'"Chromium";v="{chrome_ver}", "Not;A=Brand";v="24", "Android WebView";v="{chrome_ver}"',
        "Sec-CH-UA-Mobile": "?1",
        "Sec-CH-UA-Platform": '"Android"',
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "X-Requested-With": "org.telegram.messenger",
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

async def process_single_account(acc):
    initial_delay = random.uniform(0.5, 4.0)
    await asyncio.sleep(initial_delay)
    
    acc_name = acc.get("name", "Account")
    device_id = acc.get("device_id", "")
    acc_headers = get_account_headers(acc)
    print(f"[{acc_name}] Initializing worker...")

    try:
        init_data = await fetch_init_data(acc["session"])
    except Exception as e:
        print(f"[{acc_name}] Telegram auth failed: {e}")
        return

    async with aiohttp.ClientSession(headers=acc_headers) as session:
        # شبیه‌سازی لود اولیه صفحه مینی‌اپ در فرانت‌اند
        try:
            async with session.get(f"{BASE_URL}", timeout=aiohttp.ClientTimeout(total=10)) as landing_resp:
                await landing_resp.text()
            await asyncio.sleep(random.uniform(1.0, 2.5))
        except Exception:
            pass

        # 1. Login with safe retry (max 3 attempts)
        login_json = None
        for attempt in range(3):
            try:
                login_payload = {
                    "initData": init_data,
                    "device_id": device_id,
                    "request_id": str(uuid.uuid4())
                }
                async with session.post(f"{BASE_URL}?action=login&t={int(time.time()*1000)}", data=login_payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    login_json = await resp.json(content_type=None)
                    if login_json and login_json.get("status") == "success":
                        break
            except Exception as ex:
                if attempt == 2:
                    print(f"[{acc_name}] Login network error after 3 attempts: {ex}")
                    return
            await asyncio.sleep(2.0)

        if not login_json or login_json.get("status") != "success":
            print(f"[{acc_name}] Login rejected or failed.")
            return
            
        user_info = login_json.get("user", {})
        tg_id = user_info.get("tg_id")
        pending_mining = user_info.get("pending_reward", 0)
        print(f"[{acc_name}] Logged in | Pool: {user_info.get('mined_balance')} | Pending Mine: {pending_mining}")

        # 2. Trigger Tasks
        start_timestamps = {}
        shuffled_tasks = TASKS.copy()
        random.shuffle(shuffled_tasks)

        for task_id in shuffled_tasks:
            client_started_at = int(time.time())
            start_timestamps[task_id] = client_started_at
            
            payload = {
                "initData": init_data,
                "device_id": device_id,
                "request_id": str(uuid.uuid4()),
                "task_id": task_id,
                "tg_id": tg_id,
                "client_started_at": client_started_at
            }
            
            for attempt in range(3):
                try:
                    async with session.post(f"{BASE_URL}?action=start_task&t={int(time.time()*1000)}", data=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            print(f"[{acc_name}] Started '{task_id}' [OK]")
                            break
                except Exception:
                    pass
                await asyncio.sleep(1.5)
            
            await asyncio.sleep(random.uniform(1.2, 2.5))

        # 3. Enhanced Dynamic Safe Wait Window
        processing_wait = random.uniform(38.0, 44.0)
        print(f"[{acc_name}] Waiting {processing_wait:.1f}s for timer verification...")
        await asyncio.sleep(processing_wait)

        # 4. Claim Tasks with Smart Cooldown Retries
        for task_id in shuffled_tasks:
            client_start = start_timestamps.get(task_id, int(time.time()) - 45)
            payload = {
                "initData": init_data,
                "device_id": device_id,
                "request_id": str(uuid.uuid4()),
                "task_id": task_id,
                "tg_id": tg_id,
                "client_started_at": client_start
            }
            
            for attempt in range(3):
                try:
                    async with session.post(f"{BASE_URL}?action=claim_task&t={int(time.time()*1000)}", data=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        claim_res = await resp.text()
                        if '"status":"success"' in claim_res:
                            print(f"[{acc_name}] Claimed '{task_id}' [SUCCESS]")
                            break
                        elif 'Cooldown active' in claim_res:
                            if attempt < 2:
                                print(f"[{acc_name}] '{task_id}' Cooldown active. Waiting 15s for release...")
                                await asyncio.sleep(15.0)
                                continue
                            else:
                                print(f"[{acc_name}] Claimed '{task_id}' [COOLDOWN SKIPPED]")
                                break
                        elif 'already claimed' in claim_res.lower():
                            print(f"[{acc_name}] Task '{task_id}' was already claimed.")
                            break
                        elif attempt == 2:
                            print(f"[{acc_name}] Claimed '{task_id}' failed -> {claim_res[:50]}")
                except Exception as ex:
                    if attempt == 2:
                        print(f"[{acc_name}] Network error on '{task_id}': {ex}")
                await asyncio.sleep(2.0)
            
            await asyncio.sleep(random.uniform(1.5, 2.5))

        # 5. Main Mining Claim (Yellow Button)
        await asyncio.sleep(random.uniform(2.0, 4.0))
        yellow_button_payload = {
            "initData": init_data,
            "device_id": device_id,
            "request_id": str(uuid.uuid4()),
            "tg_id": tg_id,
            "claim_preview": pending_mining
        }
        for attempt in range(3):
            try:
                async with session.post(f"{BASE_URL}?action=claim&t={int(time.time()*1000)}", data=yellow_button_payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    yellow_res = await resp.text()
                    print(f"[{acc_name}] Big Yellow Mine Claim -> {yellow_res[:70]}")
                    break
            except Exception:
                await asyncio.sleep(2.0)

    print(f"[{acc_name}] All actions completed.")

async def main():
    if not ACCOUNTS:
        print("No accounts found in ACCOUNTS_JSON environment variable or accounts.json file.")
        return

    # ایجاد نوسان طبیعی در زمان شروع هر ران برای شکستن ریتم کرون‌جاب
    start_jitter = random.uniform(10.0, 90.0)
    print(f">>> Applying random start jitter: sleeping for {start_jitter:.1f}s...")
    await asyncio.sleep(start_jitter)

    print("==================================================")
    print(f">>> Starting Parallel Automation for {len(ACCOUNTS)} Account(s)")
    print("==================================================")
    
    await asyncio.gather(*(process_single_account(acc) for acc in ACCOUNTS))
    
    print("\n==================================================")
    print(">>> All Accounts Processed Successfully.")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(main())
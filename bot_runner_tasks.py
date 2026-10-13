# ==============================================================================
# ATF TASKS & MINING CLAIM AUTO-RUNNER — اسکریپت انجام تسک‌ها و دریافت پاداش
# ==============================================================================
# وضعیت و ماهیت اجرا:
#   - اسکریپت دوره‌ای و یک‌باره (One-Shot Task): بر خلاف کلیکر که دائمی اجرا می‌شود،
#     این کد پس از یک دور انجام تسک‌ها و کلیم ماینینگ، کارش تمام شده و خارج می‌شود.
#   - متصل به گیت‌هاب اکشنز (اجرا هر ۱۰ دقیقه از طریق Cron-Job یا اجرای محلی).
#   - هدایت ترافیک از طریق پروکسی معکوس کلودفلر ورکر جهت ماسک کردن IP گیت‌هاب.
#
# زنجیره مراحل اجرایی برای هر اکانت (Parallel Tasks):
#   1. Start Jitter: ایجاد تاخیر تصادفی اولیه (۱۰ تا ۹۰ ثانیه) برای شکستن ریتم زمانی کران‌جاب.
#   2. Telegram Auth & Startup Clean: اتصال به تلگرام، پاکسازی لینک/چشم احتمالی قبلی و دریافت initData.
#   3. Login: ارسال درخواست ورود و ثبت پالس اولیه آنلاین بودن.
#   4. Start Tasks: شروع تسک‌های شبکه‌های اجتماعی با ترتیب رندوم.
#   5. Wait Window: وقفه تصادفی (۳۸ تا ۴۴ ثانیه) همراه با ارسال پالس‌های Heartbeat جهت ثبت تایم آنلاین.
#   6. Claim Tasks: تایید و کلیم امتیاز تسک‌های استاندارد.
#   7. Special Name & Bio Check: بررسی وضعیت تسک چشم و بیو؛ فقط در صورت آماده بودن (remaining <= 0):
#      تغییر موقت Last Name (👁) و Bio -> کلیم با سیستم نوبت‌بندی و Retry -> پاکسازی فوری و تاییدشده.
#   8. Big Mine Claim: فشردن دکمه زرد ماینر اصلی و دریافت پاداش نهایی.
# ==============================================================================

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
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.errors import FloodWaitError
from pathlib import Path
from dotenv import load_dotenv

# پیدا کردن دقیق فایل .env در کنار خود فایل پایتون
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

API_ID = int(os.getenv("TG_API_ID") or 0)
API_HASH = os.getenv("TG_API_HASH", "")
BOT_USERNAME = "ATF_AIRDROP_bot"

if not API_ID or not API_HASH:
    raise ValueError("TG_API_ID or TG_API_HASH is missing! Set them in .env or environment variables.")

BASE_URL = "https://atfminers.asloni.online/miner/index.php"
# BASE_URL = "https://atf-bot-runner.mrankit4892.workers.dev/miner/index.php"

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

REQUIRED_BIO = "https://t.me/AI_TRADING_FOREX"
REQUIRED_EMOJI = "👁"

# محدودکننده همزمانی کلیم تسک‌های خاص برای جلوگیری از خطای telegram_unavailable در سمت سرور بازی
SPECIAL_CLAIM_SEMAPHORE = asyncio.Semaphore(2)

def clean_bio_text(text):
    """حذف کامل لینک تبلیغاتی از متن بیو"""
    if not text:
        return ""
    for pattern in [
        "https://t.me/AI_TRADING_FOREX",
        "http://t.me/AI_TRADING_FOREX",
        "t.me/AI_TRADING_FOREX",
        "@AI_TRADING_FOREX",
        "AI_TRADING_FOREX"
    ]:
        text = text.replace(pattern, "")
    return text.strip()

def clean_name_text(text):
    """حذف کامل ایموجی چشم از نام و نام خانوادگی"""
    if not text:
        return ""
    return text.replace("👁️", "").replace("👁", "").strip()

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
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://atfminers.asloni.online",
        "Referer": "https://atfminers.asloni.online/miner/index.php"
    }

async def fetch_init_data(client):
    bot_peer = await client.get_input_entity(BOT_USERNAME)
    web_view = await client(RequestWebViewRequest(
        peer=bot_peer,
        bot=bot_peer,
        platform="android",
        from_bot_menu=False,
        url="https://atfminers.asloni.online/miner/"
    ))
    
    match = re.search(r"#tgWebAppData=([^&]+)", web_view.url)
    if match:
        return urllib.parse.unquote(match.group(1))

    parsed_url = urllib.parse.urlparse(web_view.url)
    params = urllib.parse.parse_qs(parsed_url.fragment)
    return params.get("tgWebAppData", [""])[0]

async def safe_update_profile(client, acc_name, first_name, last_name, about, verify_clean=False):
    """ویرایش تضمینی پروفایل تلگرام همراه با ارسال اجباری first_name، مدیریت FloodWait و تایید نهایی"""
    for attempt in range(5):
        try:
            if not client.is_connected():
                await client.connect()
            await client(UpdateProfileRequest(
                first_name=first_name or "User",
                last_name=last_name or "",
                about=about or ""
            ))
            if verify_clean:
                await asyncio.sleep(1.0)
                me = await client.get_me()
                full = await client(GetFullUserRequest(me.id))
                curr_last = me.last_name or ""
                curr_bio = full.full_user.about or ""
                if "👁" in curr_last or "AI_TRADING_FOREX" in curr_bio:
                    await asyncio.sleep(1.5)
                    continue
            return True
        except FloodWaitError as fw:
            wait_sec = fw.seconds + 1.5
            print(f"[{acc_name}] Telegram FloodWait ({fw.seconds}s). Waiting {wait_sec:.1f}s...")
            await asyncio.sleep(wait_sec)
        except Exception as ex:
            print(f"[{acc_name}] Profile update attempt {attempt+1} error: {ex}")
            await asyncio.sleep(2.0)
            try:
                await client.disconnect()
            except Exception:
                pass
    return False

async def send_heartbeat(session, tg_id):
    """ارسال پالس آنلاین بودن (get_level_journey) به سرور"""
    if not tg_id:
        return
    try:
        url = f"{BASE_URL}?action=get_level_journey&tg_id={tg_id}&t={int(time.time()*1000)}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            await resp.text()
    except Exception:
        pass

async def handle_name_and_bio_tasks(acc, session, acc_headers, init_data, tg_id, device_id, clean_profile):
    """بررسی وضعیت تسک‌های نام و بیو و انجام سریع عملیات فقط در صورت آماده بودن دکمه Claim"""
    acc_name = acc.get("name", "Account")
    status_headers = acc_headers.copy()
    status_headers["Content-Type"] = "application/json"
    status_headers["x-telegram-init-data"] = init_data

    name_eye_ready = False
    bio_ready = False

    # 1. استعلام وضعیت تسک چشم (بدون تغییر اکانت)
    try:
        chk_payload = json.dumps({
            "initData": init_data,
            "request_id": str(uuid.uuid4()),
            "device_id": device_id,
            "tg_id": str(tg_id)
        })
        async with session.post(f"{BASE_URL}?action=name_eye_task_status&t={int(time.time()*1000)}", data=chk_payload, headers=status_headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            data = await resp.json(content_type=None)
            if data and data.get("status") == "success":
                rem_eye = int(data.get("remaining", 9999))
                if rem_eye <= 0:
                    name_eye_ready = True
                else:
                    print(f"[{acc_name}] 'name_eye' on timer ({rem_eye}s left). Skipping profile edit.")
    except Exception:
        pass

    # 2. استعلام وضعیت تسک بیو (بدون تغییر اکانت)
    try:
        chk_payload = json.dumps({
            "initData": init_data,
            "request_id": str(uuid.uuid4()),
            "device_id": device_id,
            "tg_id": str(tg_id)
        })
        async with session.post(f"{BASE_URL}?action=bio_task_status&t={int(time.time()*1000)}", data=chk_payload, headers=status_headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            data = await resp.json(content_type=None)
            if data and data.get("status") == "success":
                rem_bio = int(data.get("remaining", 9999))
                if rem_bio <= 0:
                    bio_ready = True
                else:
                    print(f"[{acc_name}] 'bio_referral' on timer ({rem_bio}s left). Skipping profile edit.")
    except Exception:
        pass

    # اگر هیچ‌کدام آماده نبودند، بدون دست زدن به مشخصات خارج می‌شویم
    if not name_eye_ready and not bio_ready:
        return

    # نوبت‌بندی بین اکانت‌ها تا سرور بازی هنگام استعلام از تلگرام خطای telegram_unavailable ندهد
    async with SPECIAL_CLAIM_SEMAPHORE:
        print(f"[{acc_name}] Special Tasks Ready -> Name Eye: {name_eye_ready} | Bio: {bio_ready}")

        orig_first = clean_profile["first_name"]
        orig_last = clean_profile["last_name"]
        orig_bio = clean_profile["about"]

        client = TelegramClient(StringSession(acc["session"]), API_ID, API_HASH)
        profile_modified = False

        try:
            await client.connect()

            temp_first = orig_first
            temp_last = f"{orig_last} {REQUIRED_EMOJI}".strip() if name_eye_ready else orig_last
            temp_bio = REQUIRED_BIO if bio_ready else orig_bio

            print(f"[{acc_name}] Setting temporary profile -> Last Name: '{temp_last}' | Bio: '{temp_bio}'")
            updated = await safe_update_profile(client, acc_name, temp_first, temp_last, temp_bio)
            if updated:
                profile_modified = True
                await asyncio.sleep(1.5)

            # دریافت initData جدید که شامل نام خانوادگی ویرایش‌شده (👁) باشد
            fresh_init_data = await fetch_init_data(client)

            claim_headers = status_headers.copy()
            claim_headers["x-telegram-init-data"] = fresh_init_data

            # کلیم تسک چشم (همراه با Retry در صورت خطای موقت telegram_unavailable)
            if name_eye_ready:
                for attempt in range(4):
                    eye_payload = json.dumps({
                        "initData": fresh_init_data,
                        "device_id": device_id,
                        "request_id": str(uuid.uuid4()),
                        "tg_id": str(tg_id),
                        "task_id": "name_eye"
                    })
                    try:
                        async with session.post(f"{BASE_URL}?action=name_eye_task_claim&t={int(time.time()*1000)}", data=eye_payload, headers=claim_headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            res_txt = await resp.text()
                            if '"status":"success"' in res_txt:
                                print(f"[{acc_name}] Claimed 'name_eye' [SPECIAL SUCCESS] -> {res_txt[:80]}")
                                break
                            elif "telegram_unavailable" in res_txt and attempt < 3:
                                print(f"[{acc_name}] 'name_eye' server busy (telegram_unavailable), retrying in 2s...")
                                await asyncio.sleep(2.0)
                                continue
                            else:
                                print(f"[{acc_name}] Claimed 'name_eye' [SPECIAL] -> {res_txt[:85]}")
                                break
                    except Exception:
                        await asyncio.sleep(1.5)

            # کلیم تسک بیو (همراه با Retry در صورت خطای موقت telegram_unavailable)
            if bio_ready:
                for attempt in range(4):
                    bio_payload = json.dumps({
                        "initData": fresh_init_data,
                        "device_id": device_id,
                        "request_id": str(uuid.uuid4()),
                        "tg_id": str(tg_id),
                        "task_id": "bio_referral"
                    })
                    try:
                        async with session.post(f"{BASE_URL}?action=bio_task_claim&t={int(time.time()*1000)}", data=bio_payload, headers=claim_headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            res_txt = await resp.text()
                            if '"status":"success"' in res_txt:
                                print(f"[{acc_name}] Claimed 'bio_referral' [SPECIAL SUCCESS] -> {res_txt[:80]}")
                                break
                            elif "telegram_unavailable" in res_txt and attempt < 3:
                                print(f"[{acc_name}] 'bio_referral' server busy (telegram_unavailable), retrying in 2s...")
                                await asyncio.sleep(2.0)
                                continue
                            else:
                                print(f"[{acc_name}] Claimed 'bio_referral' [SPECIAL] -> {res_txt[:85]}")
                                break
                    except Exception:
                        await asyncio.sleep(1.5)

        except Exception as ex:
            print(f"[{acc_name}] Error during special tasks processing: {ex}")
        finally:
            # بازگرداندن فوری و ۱۰۰٪ تضمینی پروفایل به حالت تمیز اولیه
            if profile_modified:
                await asyncio.sleep(1.5)
                print(f"[{acc_name}] Immediately reverting Last Name & Bio to clean state...")
                restored = await safe_update_profile(client, acc_name, orig_first, orig_last, orig_bio, verify_clean=True)
                if restored:
                    print(f"[{acc_name}] Profile cleaned & verified successfully.")
                else:
                    print(f"[{acc_name}] WARNING: Profile restore could not be verified!")
            try:
                await client.disconnect()
            except Exception:
                pass

async def process_single_account(acc):
    initial_delay = random.uniform(0.5, 4.0)
    await asyncio.sleep(initial_delay)
    
    acc_name = acc.get("name", "Account")
    device_id = acc.get("device_id", "")
    acc_headers = get_account_headers(acc)
    print(f"[{acc_name}] Initializing worker...")

    # اتصال اولیه به تلگرام، پاکسازی لینک یا چشم احتمالی قبلی، دریافت initData و بستن اتصال
    client = TelegramClient(StringSession(acc["session"]), API_ID, API_HASH)
    clean_profile = {"first_name": "User", "last_name": "", "about": ""}
    try:
        await client.connect()
        me = await client.get_me()
        full = await client(GetFullUserRequest(me.id))

        raw_first = me.first_name or "User"
        raw_last = me.last_name or ""
        raw_bio = full.full_user.about or ""

        clean_first = clean_name_text(raw_first) or "User"
        clean_last = clean_name_text(raw_last)
        clean_bio = clean_bio_text(raw_bio)

        clean_profile = {
            "first_name": clean_first,
            "last_name": clean_last,
            "about": clean_bio
        }

        # اگر از اجرای قبلی لینک در بیو یا چشم در نام جا مانده باشد، بلافاصله پاک می‌شود
        if raw_first != clean_first or raw_last != clean_last or raw_bio != clean_bio:
            print(f"[{acc_name}] Found leftover link/emoji on profile! Cleaning immediately...")
            await safe_update_profile(client, acc_name, clean_first, clean_last, clean_bio, verify_clean=True)
            print(f"[{acc_name}] Leftover link/emoji cleaned.")

        init_data = await fetch_init_data(client)
    except Exception as e:
        print(f"[{acc_name}] Telegram auth failed: {e}")
        return
    finally:
        # بستن اتصال تلگرام تا در طول زمان انتظار، سوکت باز نماند
        try:
            await client.disconnect()
        except Exception:
            pass

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

        # ثبت حضور آنلاین در بدو ورود (Heartbeat)
        await send_heartbeat(session, tg_id)

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

        # 3. Enhanced Dynamic Safe Wait Window همراه با ارسال پالس فعالیت
        processing_wait = random.uniform(39.0, 44.0)
        print(f"[{acc_name}] Waiting {processing_wait:.1f}s for timer verification...")
        await asyncio.sleep(processing_wait / 2.0)
        await send_heartbeat(session, tg_id)
        await asyncio.sleep(processing_wait / 2.0)
        await send_heartbeat(session, tg_id)

        # 4. Claim Tasks with Smart Cooldown Retries
        for task_id in shuffled_tasks:
            client_start = start_timestamps.get(task_id, int(time.time()) - 45)
            
            for attempt in range(3):
                payload = {
                    "initData": init_data,
                    "device_id": device_id,
                    "request_id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "tg_id": tg_id,
                    "client_started_at": client_start
                }
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

        # 5. بررسی و کلیم هوشمند تسک‌های نام (👁) و بیو (فقط در صورت آماده بودن دکمه Claim)
        await handle_name_and_bio_tasks(acc, session, acc_headers, init_data, tg_id, device_id, clean_profile)

        # 6. Main Mining Claim (Yellow Button)
        await asyncio.sleep(random.uniform(2.0, 4.0))
        await send_heartbeat(session, tg_id)

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
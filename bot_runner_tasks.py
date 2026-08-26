async def process_single_account(acc):
    # ۱. تاخیر اولیه تصادفی برای جلوگیری از درخواست همزمان
    initial_delay = random.uniform(0.5, 4.0)
    await asyncio.sleep(initial_delay)
    
    acc_name = acc.get("name", "Account")
    device_id = acc.get("device_id", "")
    print(f"[{acc_name}] Initializing worker...")

    try:
        init_data = await fetch_init_data(acc["session"])
    except Exception as e:
        print(f"[{acc_name}] Telegram auth failed: {e}")
        return

    # ۲. یک دقیقه استراحت کامل قبل از شروع تسک‌ها
    print(f"[{acc_name}] Waiting 60s before starting tasks...")
    await asyncio.sleep(60)

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        # ورود (Login)
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
                    print(f"[{acc_name}] Login network error: {ex}")
                    return
            await asyncio.sleep(1.0)

        if not login_json or login_json.get("status") != "success":
            print(f"[{acc_name}] Login rejected or failed.")
            return
            
        user_info = login_json.get("user", {})
        tg_id = user_info.get("tg_id")
        pending_mining = user_info.get("pending_reward", 0)
        print(f"[{acc_name}] Logged in | Pool: {user_info.get('mined_balance')} | Pending: {pending_mining}")

        # ۳. استارت تسک‌ها با تاخیر تصادفی بین ۰ تا ۲ ثانیه
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
            
            try:
                async with session.post(f"{BASE_URL}?action=start_task&t={int(time.time()*1000)}", data=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        print(f"[{acc_name}] Started '{task_id}' [OK]")
            except Exception:
                pass
            
            # تاخیر بین ۰ تا ۲ ثانیه بین استارت هر تسک
            await asyncio.sleep(random.uniform(0.0, 2.0))

        # ۴. یک دقیقه استراحت کامل قبل از کلیم پاداش‌ها
        print(f"[{acc_name}] Waiting 60s for task completion...")
        await asyncio.sleep(60)

        # ۵. کلیم تسک‌ها با تاخیر تصادفی بین ۰ تا ۲ ثانیه
        for task_id in shuffled_tasks:
            client_start = start_timestamps.get(task_id, int(time.time()) - 60)
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
                    else:
                        print(f"[{acc_name}] Claim '{task_id}' -> {claim_res[:50]}")
            except Exception as ex:
                print(f"[{acc_name}] Network error on '{task_id}': {ex}")
            
            # تاخیر بین ۰ تا ۲ ثانیه بین کلیم هر تسک
            await asyncio.sleep(random.uniform(0.0, 2.0))

        # ۶. کلیم ماینینگ نهایی (دکمه زرد) با تاخیر تصادفی ۰ تا ۲ ثانیه
        await asyncio.sleep(random.uniform(0.0, 2.0))
        yellow_button_payload = {
            "initData": init_data,
            "device_id": device_id,
            "request_id": str(uuid.uuid4()),
            "tg_id": tg_id,
            "claim_preview": pending_mining
        }
        try:
            async with session.post(f"{BASE_URL}?action=claim&t={int(time.time()*1000)}", data=yellow_button_payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                yellow_res = await resp.text()
                print(f"[{acc_name}] Big Yellow Mine Claim -> {yellow_res[:70]}")
        except Exception as ex:
            print(f"[{acc_name}] Mine Claim error: {ex}")

    print(f"[{acc_name}] All actions completed.")
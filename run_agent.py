import os
import json
import asyncio
from datetime import datetime, timezone

import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import FastAPI, Request, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import openai
import uvicorn

# Environment variables
WHOOP_CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
WHOOP_CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
WHOOP_REDIRECT_URI = os.getenv("WHOOP_REDIRECT_URI")
WHOOP_ACCESS_TOKEN = os.getenv("WHOOP_ACCESS_TOKEN")
WHOOP_REFRESH_TOKEN = os.getenv("WHOOP_REFRESH_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
USER_CHAT_ID = int(os.getenv("USER_CHAT_ID", "0")) or None
WHOOP_DATA_FILE = os.getenv("WHOOP_DATA_FILE", "whoop_data.json")
MORNING_CHECKIN_FILE = os.getenv("MORNING_CHECKIN_FILE", "morning_checkins.json")
HABITS_FILE = os.getenv("HABITS_FILE", "habits.json")
HABIT_LOG_FILE = os.getenv("HABIT_LOG_FILE", "habit_log.json")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PORT = int(os.getenv("PORT", "8000"))
TOKEN_FILE = os.getenv("WHOOP_TOKEN_FILE", "whoop_tokens.json")

bot = Bot(TG_TOKEN)
dp = Dispatcher()
app = FastAPI()
scheduler = AsyncIOScheduler(timezone="UTC")

# --------------------------------- Helpers ----------------------------------

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save {path}:", e)

# Token persistence ----------------------------------------------------------

def load_tokens():
    global WHOOP_ACCESS_TOKEN, WHOOP_REFRESH_TOKEN
    data = load_json(TOKEN_FILE, {})
    WHOOP_ACCESS_TOKEN = data.get("access_token") or WHOOP_ACCESS_TOKEN
    WHOOP_REFRESH_TOKEN = data.get("refresh_token") or WHOOP_REFRESH_TOKEN


def save_tokens(access: str, refresh: str):
    global WHOOP_ACCESS_TOKEN, WHOOP_REFRESH_TOKEN
    WHOOP_ACCESS_TOKEN = access
    WHOOP_REFRESH_TOKEN = refresh
    save_json(TOKEN_FILE, {"access_token": access, "refresh_token": refresh})

load_tokens()

# ------------------------------- WHOOP API ---------------------------------

WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
WHOOP_SUMMARY_URL = "https://api.prod.whoop.com/users/me/summary/latest"

async def exchange_code_for_tokens(code: str) -> dict:
    async with aiohttp.ClientSession() as session:
        payload = {
            "grant_type": "authorization_code",
            "client_id": WHOOP_CLIENT_ID,
            "client_secret": WHOOP_CLIENT_SECRET,
            "code": code,
            "redirect_uri": WHOOP_REDIRECT_URI,
        }
        async with session.post(WHOOP_TOKEN_URL, json=payload) as resp:
            if resp.status != 200:
                raise HTTPException(resp.status, await resp.text())
            return await resp.json()

async def refresh_access_token() -> str:
    global WHOOP_ACCESS_TOKEN, WHOOP_REFRESH_TOKEN
    if not WHOOP_REFRESH_TOKEN:
        raise RuntimeError("Missing refresh token")
    async with aiohttp.ClientSession() as session:
        payload = {
            "grant_type": "refresh_token",
            "client_id": WHOOP_CLIENT_ID,
            "client_secret": WHOOP_CLIENT_SECRET,
            "refresh_token": WHOOP_REFRESH_TOKEN,
        }
        async with session.post(WHOOP_TOKEN_URL, json=payload) as resp:
            if resp.status != 200:
                raise RuntimeError(await resp.text())
            data = await resp.json()
            save_tokens(data["access_token"], data["refresh_token"])
            return data["access_token"]

async def fetch_latest_metrics() -> dict:
    if not WHOOP_ACCESS_TOKEN and WHOOP_REFRESH_TOKEN:
        await refresh_access_token()
    if not WHOOP_ACCESS_TOKEN:
        raise RuntimeError("No WHOOP access token")
    headers = {"Authorization": f"Bearer {WHOOP_ACCESS_TOKEN}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(WHOOP_SUMMARY_URL, headers=headers) as resp:
            if resp.status == 401 and WHOOP_REFRESH_TOKEN:
                await refresh_access_token()
                headers["Authorization"] = f"Bearer {WHOOP_ACCESS_TOKEN}"
                async with session.get(WHOOP_SUMMARY_URL, headers=headers) as r2:
                    r2.raise_for_status()
                    return await r2.json()
            resp.raise_for_status()
            return await resp.json()

# ----------------------------- Data storage ---------------------------------

def append_json_line(path: str, data: dict):
    try:
        with open(path, "a", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print(f"Failed to append {path}:", e)

def load_latest(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            pos = f.tell()
            line = b""
            while pos > 0:
                pos -= 1
                f.seek(pos)
                if f.read(1) == b"\n" and line:
                    break
                f.seek(pos)
                char = f.read(1)
                line = char + line
            if line:
                return json.loads(line.decode("utf-8"))
    except Exception:
        return None
    return None

# -------------------------- Telegram Handlers -------------------------------

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="/dailyreport"), KeyboardButton(text="/morningcheckin")],
        [KeyboardButton(text="/goals"), KeyboardButton(text="/mynotes")],
        [KeyboardButton(text="/addhabit"), KeyboardButton(text="/habits")],
        [KeyboardButton(text="/done"), KeyboardButton(text="/ask")],
    ], resize_keyboard=True)
    await message.answer("Привет! Я бот для WHOOP и привычек.", reply_markup=kb)

@dp.message(Command("authorize"))
async def cmd_authorize(message: types.Message):
    params = (
        f"client_id={WHOOP_CLIENT_ID}&redirect_uri={WHOOP_REDIRECT_URI}"
        "&response_type=code&scope=read:recovery read:cycles read:workout"
    )
    url = f"{WHOOP_AUTH_URL}?{params}"
    await message.answer(f"Авторизация WHOOP: {url}")

@dp.message(Command("dailyreport"))
async def cmd_daily(message: types.Message):
    data = load_latest(WHOOP_DATA_FILE) or {}
    sleep = data.get("sleep")
    recovery = data.get("recovery")
    strain = data.get("strain")
    steps = data.get("steps")
    report = [
        f"Сон: {sleep} ч." if sleep is not None else "Нет данных о сне",
        f"Восстановление: {recovery}%" if recovery is not None else "Нет данных о восстановлении",
        f"Нагрузка: {strain}" if strain is not None else "Нет данных о нагрузке",
        f"Шаги: {steps}" if steps is not None else "Нет данных о шагах",
        "Совет: пейте больше воды!",
    ]
    await message.answer("\n".join(report))

@dp.message(Command("morningcheckin"))
async def cmd_morning(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Good", callback_data="mood_good"),
         InlineKeyboardButton(text="Okay", callback_data="mood_ok")],
        [InlineKeyboardButton(text="Bad", callback_data="mood_bad")],
    ])
    await message.answer("Как самочувствие?", reply_markup=kb)

@dp.callback_query(F.data.startswith("mood_"))
async def cb_mood(call: types.CallbackQuery):
    mood = call.data.split("_", 1)[1]
    entry = {"user": call.from_user.id, "mood": mood, "ts": datetime.now(timezone.utc).isoformat()}
    data = load_json(MORNING_CHECKIN_FILE, [])
    data.append(entry)
    save_json(MORNING_CHECKIN_FILE, data)
    await call.answer("Записано")

@dp.message(Command("goals"))
async def cmd_goals(message: types.Message):
    await message.answer("Установи цели на сегодня")

@dp.message(Command("mynotes"))
async def cmd_notes(message: types.Message):
    text = message.text.split(maxsplit=1)
    if len(text) < 2:
        await message.answer("Пришли текст заметки после команды")
        return
    note = {"user": message.from_user.id, "text": text[1], "ts": datetime.now(timezone.utc).isoformat()}
    notes = load_json("notes.json", [])
    notes.append(note)
    save_json("notes.json", notes)
    await message.answer("Заметка сохранена")

@dp.message(Command("addhabit"))
async def cmd_addhabit(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Название привычки?")
        return
    habits = load_json(HABITS_FILE, {})
    user_habits = habits.get(str(message.from_user.id), [])
    if parts[1] not in user_habits:
        user_habits.append(parts[1])
    habits[str(message.from_user.id)] = user_habits
    save_json(HABITS_FILE, habits)
    await message.answer("Привычка добавлена")

@dp.message(Command("done"))
async def cmd_done(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Какая привычка выполнена?")
        return
    logs = load_json(HABIT_LOG_FILE, [])
    logs.append({"user": message.from_user.id, "habit": parts[1], "ts": datetime.now(timezone.utc).isoformat()})
    save_json(HABIT_LOG_FILE, logs)
    await message.answer("Отмечено")

@dp.message(Command("habits"))
async def cmd_habits(message: types.Message):
    habits = load_json(HABITS_FILE, {})
    user_habits = habits.get(str(message.from_user.id), [])
    if user_habits:
        await message.answer("\n".join(user_habits))
    else:
        await message.answer("Привычек нет")

@dp.message(Command("ask"))
async def cmd_ask(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Вопрос после команды")
        return
    openai.api_key = OPENAI_API_KEY
    loop = asyncio.get_event_loop()
    try:
        resp = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": parts[1]}],
        ))
        ans = resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("openai error", e)
        ans = "Не удалось получить ответ"
    await message.answer(ans)

@dp.message()
async def fallback(message: types.Message):
    await message.answer("Используй кнопки или команды")

# ------------------------- Background Jobs ---------------------------------

async def poll_whoop_and_notify():
    try:
        metrics = await fetch_latest_metrics()
    except Exception as e:
        print("WHOOP fetch error:", e)
        return
    metrics_with_ts = {**metrics, "timestamp": datetime.now(timezone.utc).isoformat()}
    append_json_line(WHOOP_DATA_FILE, metrics_with_ts)
    if USER_CHAT_ID:
        text = f"Новые данные WHOOP: {metrics}"
        await bot.send_message(USER_CHAT_ID, text)

async def daily_whoop_report():
    data = load_latest(WHOOP_DATA_FILE)
    if not data or not USER_CHAT_ID:
        return
    sleep = data.get("sleep")
    recovery = data.get("recovery")
    strain = data.get("strain")
    steps = data.get("steps")
    report = [
        "Ежедневный отчёт WHOOP:",
        f"Сон: {sleep} ч." if sleep is not None else "- сон: нет данных",
        f"Восстановление: {recovery}%" if recovery is not None else "- восстановление: нет данных",
        f"Нагрузка: {strain}" if strain is not None else "- нагрузка: нет данных",
        f"Шаги: {steps}" if steps is not None else "- шаги: нет данных",
    ]
    await bot.send_message(USER_CHAT_ID, "\n".join(report))

async def habit_reminder():
    if not USER_CHAT_ID:
        return
    habits = load_json(HABITS_FILE, {}).get(str(USER_CHAT_ID), [])
    if habits:
        text = "Напоминание о привычках:\n- " + "\n- ".join(habits)
        await bot.send_message(USER_CHAT_ID, text)

async def smart_reminders():
    data = load_latest(WHOOP_DATA_FILE)
    if not data or not USER_CHAT_ID:
        return
    msgs = []
    if data.get("recovery") is not None and data["recovery"] < 60:
        msgs.append("Восстановление низкое. Отдохните сегодня.")
    if data.get("steps") is not None and data["steps"] < 5000:
        msgs.append("Пока меньше 5000 шагов. Прогулка?")
    for m in msgs:
        await bot.send_message(USER_CHAT_ID, m)

async def weekly_report():
    if not USER_CHAT_ID:
        return
    if not os.path.exists(WHOOP_DATA_FILE):
        return
    with open(WHOOP_DATA_FILE, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    last7 = [json.loads(line) for line in lines[-7:]]
    if not last7:
        return
    def avg(key):
        vals = [e.get(key) for e in last7 if e.get(key) is not None]
        return sum(vals) / len(vals) if vals else None
    sleep = avg("sleep")
    recovery = avg("recovery")
    strain = avg("strain")
    steps = avg("steps")
    report = [
        "Недельный отчёт WHOOP:",
        f"Средний сон: {sleep:.1f} ч." if sleep is not None else "- сон: нет данных",
        f"Среднее восстановление: {recovery:.0f}%" if recovery is not None else "- восстановление: нет данных",
        f"Средняя нагрузка: {strain:.1f}" if strain is not None else "- нагрузка: нет данных",
        f"Средние шаги: {steps:.0f}" if steps is not None else "- шаги: нет данных",
    ]
    await bot.send_message(USER_CHAT_ID, "\n".join(report))

# ------------------------------- FastAPI -----------------------------------

@app.get("/oauth-callback")
async def oauth_callback(code: str):
    data = await exchange_code_for_tokens(code)
    save_tokens(data["access_token"], data["refresh_token"])
    return {"ok": True}

@app.post("/whoop-webhook")
async def whoop_webhook(req: Request):
    payload = await req.json()
    append_json_line(WHOOP_DATA_FILE, {**payload, "timestamp": datetime.now(timezone.utc).isoformat()})
    if USER_CHAT_ID:
        await bot.send_message(USER_CHAT_ID, f"Webhook данные WHOOP: {payload}")
    return {"ok": True}

@app.get("/health")
async def health():
    return {"status": "ok"}

# Startup tasks --------------------------------------------------------------

async def start_bot():
    await dp.start_polling(bot)

@app.on_event("startup")
async def on_startup():
    scheduler.add_job(poll_whoop_and_notify, "interval", hours=1)
    scheduler.add_job(daily_whoop_report, "cron", hour=8, minute=0)
    scheduler.add_job(habit_reminder, "cron", hour=8, minute=30)
    scheduler.add_job(habit_reminder, "cron", hour=13, minute=0)
    scheduler.add_job(habit_reminder, "cron", hour=19, minute=0)
    scheduler.add_job(smart_reminders, "cron", hour=18, minute=0)
    scheduler.add_job(weekly_report, "cron", day_of_week="sun", hour=20, minute=0)
    scheduler.start()
    asyncio.create_task(start_bot())

if __name__ == "__main__":
    uvicorn.run("run_agent:app", host="0.0.0.0", port=PORT)

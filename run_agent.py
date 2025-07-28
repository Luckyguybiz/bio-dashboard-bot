import os
import asyncio
import json
from datetime import datetime, timezone, timedelta
import random

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from fastapi import FastAPI, Request
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import uvicorn
import openai

TG_TOKEN = os.getenv("TG_TOKEN")
USER_CHAT_ID = os.getenv("USER_CHAT_ID")
WHOOP_DATA_FILE = os.getenv("WHOOP_DATA_FILE", "whoop_data.json")
MORNING_CHECKIN_FILE = os.getenv("MORNING_CHECKIN_FILE", "morning_checkins.json")
HABITS_FILE = os.getenv("HABITS_FILE", "habits.json")
HABIT_LOG_FILE = os.getenv("HABIT_LOG_FILE", "habit_log.json")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NOTES_FILE = os.getenv("NOTES_FILE", "notes.json")
LANGUAGE_FILE = os.getenv("LANGUAGE_FILE", "user_langs.json")

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()
app = FastAPI()
scheduler = AsyncIOScheduler(timezone="UTC")

STARTED_USERS_FILE = os.getenv("STARTED_USERS_FILE", "started_users.json")
STARTED_USERS: set[int] = set()
USER_LANGS: dict[str, str] = {}


def load_languages() -> dict:
    if os.path.exists(LANGUAGE_FILE):
        try:
            with open(LANGUAGE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def save_languages() -> None:
    try:
        with open(LANGUAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(USER_LANGS, f, ensure_ascii=False)
    except Exception as e:
        print("Failed to save languages:", e)


def set_language(user_id: int, lang: str) -> None:
    USER_LANGS[str(user_id)] = lang
    save_languages()


def get_language(user_id: int) -> str:
    return USER_LANGS.get(str(user_id), "ru")


def get_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    lang = get_language(user_id)
    if lang == "ru":
        keyboard = [
            [
                KeyboardButton(text="/dailyreport 📊 Отчёт"),
                KeyboardButton(text="/morningcheckin 🌅 Настроение"),
            ],
            [
                KeyboardButton(text="/goals 🎯 Цели"),
                KeyboardButton(text="/mynotes 📝 Заметка"),
            ],
        ]
    else:
        keyboard = [
            [
                KeyboardButton(text="/dailyreport 📊"),
                KeyboardButton(text="/morningcheckin 🌅"),
            ],
            [
                KeyboardButton(text="/goals 🎯"),
                KeyboardButton(text="/mynotes 📝"),
            ],
        ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=False)


def get_intro_text(lang: str) -> str:
    if lang == "en":
        return (
            "✅ Welcome!\n"
            "I will help you track health and habits.\n\n"
            "<b>Main commands:</b>\n"
            "• /dailyreport — latest WHOOP stats\n"
            "• /morningcheckin — how do you feel?\n"
            "• /goals — set goals\n"
            "• /mynotes <i>text</i> — personal notes"
        )
    return (
        "✅ <b>Добро пожаловать!</b>\n"
        "Я помогу следить за здоровьем и привычками.\n\n"
        "<b>Основные команды:</b>\n"
        "• /dailyreport — свежая статистика WHOOP\n"
        "• /morningcheckin — как ты себя чувствуешь?\n"
        "• /goals — цели на день\n"
        "• /mynotes <i>текст</i> — личные заметки"
    )


def load_started_users() -> set[int]:
    if not STARTED_USERS and os.path.exists(STARTED_USERS_FILE):
        try:
            with open(STARTED_USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    STARTED_USERS.update(data)
        except Exception:
            pass
    return STARTED_USERS


def add_started_user(user_id: int) -> None:
    users = load_started_users()
    if user_id not in users:
        users.add(user_id)
        try:
            with open(STARTED_USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(sorted(users), f, ensure_ascii=False)
        except Exception as e:
            print("Failed to save started users:", e)


# Инициализируем список пользователей, запустивших бота и языковые настройки
load_started_users()
USER_LANGS.update(load_languages())


def _read_whoop_lines() -> list[dict]:
    if not os.path.exists(WHOOP_DATA_FILE):
        return []
    records: list[dict] = []
    try:
        with open(WHOOP_DATA_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
    except Exception as e:
        print("Failed to read WHOOP data:", e)
    return records


def load_whoop_data(days: int | None = None) -> list[dict]:
    records = _read_whoop_lines()
    if days is None:
        return records
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered: list[dict] = []
    for r in records:
        ts = r.get("timestamp")
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                if dt >= cutoff:
                    filtered.append(r)
            except Exception:
                filtered.append(r)
        else:
            filtered.append(r)
    return filtered


def load_latest_whoop_data() -> dict | None:
    records = _read_whoop_lines()
    return records[-1] if records else None


def save_morning_checkin(user_id: int, response: str) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "response": response,
    }
    try:
        with open(MORNING_CHECKIN_FILE, "a", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print("Failed to save morning check-in:", e)


def load_habits() -> dict:
    if not os.path.exists(HABITS_FILE):
        return {}
    try:
        with open(HABITS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_habits(data: dict) -> None:
    try:
        with open(HABITS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print("Failed to save habits:", e)


def add_habit(user_id: int, habit: str) -> None:
    data = load_habits()
    habits = set(data.get(str(user_id), []))
    habits.add(habit)
    data[str(user_id)] = sorted(habits)
    save_habits(data)


def log_habit_completion(user_id: int, habit: str) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "habit": habit,
    }
    try:
        with open(HABIT_LOG_FILE, "a", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print("Failed to log habit completion:", e)


def save_note(user_id: int, text: str) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "text": text,
    }
    try:
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print("Failed to save note:", e)


def load_notes(days: int) -> list[dict]:
    if not os.path.exists(NOTES_FILE):
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    notes: list[dict] = []
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                ts = entry.get("timestamp")
                if not ts:
                    continue
                try:
                    dt = datetime.fromisoformat(ts)
                    if dt >= cutoff:
                        notes.append(entry)
                except Exception:
                    continue
    except Exception as e:
        print("Failed to load notes:", e)
    return notes


@dp.message(F.text == "/start")
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    if str(user_id) not in USER_LANGS:
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="Русский", callback_data="lang_ru")],
                [types.InlineKeyboardButton(text="English", callback_data="lang_en")],
            ]
        )
        await message.answer("Выберите язык / Choose language:", reply_markup=keyboard)
        return

    first_time = user_id not in load_started_users()
    kb = get_keyboard(user_id)
    lang = get_language(user_id)
    if first_time:
        add_started_user(user_id)
        await message.answer(get_intro_text(lang), reply_markup=kb, parse_mode="HTML")
        if lang == "en":
            await message.answer("Try /morningcheckin or get /dailyreport to begin!")
        else:
            await message.answer(
                "Чтобы начать, попробуй /morningcheckin или получи /dailyreport!"
            )
    else:
        if lang == "en":
            await message.answer("Welcome back! Choose a command:", reply_markup=kb)
        else:
            await message.answer("С возвращением! Выбирай команды ниже:", reply_markup=kb)


@dp.message(Command("dailyreport"))
async def dailyreport_handler(message: types.Message):
    data = load_latest_whoop_data()
    if not data:
        await message.answer("Нет данных WHOOP для отчёта.")
        return

    sleep = data.get("sleep")
    recovery = data.get("recovery")
    strain = data.get("strain")
    steps = data.get("steps")

    report = [
        f"Вы спали {sleep} часов." if sleep is not None else "Данных о сне нет.",
        (
            f"Восстановление {recovery}% и нагрузка {strain}."
            if recovery is not None and strain is not None
            else "Нет данных о восстановлении или нагрузке."
        ),
        f"Сегодня {steps} шагов." if steps is not None else "Данных о шагах нет.",
        "Совет: прислушивайтесь к самочувствию и отдыхайте при необходимости.",
    ]
    await message.answer("\n".join(report))


@dp.message(Command("morningcheckin"))
async def morningcheckin_handler(message: types.Message):
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Good 😊", callback_data="mc_good")],
            [types.InlineKeyboardButton(text="Okay 😐", callback_data="mc_okay")],
            [types.InlineKeyboardButton(text="Bad 😔", callback_data="mc_bad")],
        ]
    )
    await message.answer("Как ты себя чувствуешь сегодня?", reply_markup=keyboard)


@dp.callback_query(F.data.in_(["mc_good", "mc_okay", "mc_bad"]))
async def morningcheckin_callback(call: types.CallbackQuery):
    mapping = {"mc_good": "Good", "mc_okay": "Okay", "mc_bad": "Bad"}
    response = mapping.get(call.data, call.data)
    save_morning_checkin(call.from_user.id, response)
    await call.message.answer("Спасибо! Ваш ответ сохранён.")
    await call.answer()


@dp.callback_query(F.data.in_(["lang_ru", "lang_en"]))
async def language_callback(call: types.CallbackQuery):
    lang = "ru" if call.data == "lang_ru" else "en"
    set_language(call.from_user.id, lang)
    add_started_user(call.from_user.id)
    kb = get_keyboard(call.from_user.id)
    await call.message.answer(get_intro_text(lang), reply_markup=kb, parse_mode="HTML")
    await call.answer()


@dp.message(Command("goals"))
async def goals_handler(message: types.Message):
    await message.answer(
        "Установи свои цели на сегодня:\n"
        "• Шаги\n"
        "• Сон\n"
        "• Восстановление"
    )


@dp.message(Command("mynotes"))
async def notes_handler(message: types.Message):
    text = message.text or ""
    note = text[len("/mynotes") :].strip()
    if not note or note == "📝":
        await message.answer(
            "Напиши заметку после команды, например:\n" "`/mynotes Купил продукты`",
            parse_mode="Markdown",
        )
        return
    save_note(message.from_user.id, note)
    await message.answer("Заметка сохранена ✅")


@dp.message(Command("addhabit"))
async def addhabit_handler(message: types.Message):
    text = message.text.split(maxsplit=1)
    if len(text) < 2:
        await message.answer("Использование: /addhabit название_привычки")
        return
    habit = text[1].strip()
    add_habit(message.from_user.id, habit)
    await message.answer(f"Добавлена привычка: {habit}")


@dp.message(Command("done"))
async def done_handler(message: types.Message):
    text = message.text.split(maxsplit=1)
    if len(text) < 2:
        await message.answer("Использование: /done название_привычки")
        return
    habit = text[1].strip()
    log_habit_completion(message.from_user.id, habit)
    await message.answer(f"Отмечено выполнение: {habit}")


@dp.message(Command("habits"))
async def habits_handler(message: types.Message):
    habits = load_habits().get(str(message.from_user.id), [])
    if not habits:
        await message.answer("Привычки не заданы. Используй /addhabit")
    else:
        await message.answer("Твои привычки:\n- " + "\n- ".join(habits))


@dp.message(Command("ask"))
async def ask_handler(message: types.Message):
    text = message.text.split(maxsplit=1)
    if len(text) < 2:
        await message.answer("Использование: /ask вопрос")
        return
    question = text[1]
    openai.api_key = OPENAI_API_KEY
    try:
        resp = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful health assistant.",
                    },
                    {"role": "user", "content": question},
                ],
            ),
        )
        answer = resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("GPT error:", e)
        answer = "Не удалось получить ответ."
    await message.answer(answer)


@dp.message()
async def fallback_handler(message: types.Message):
    await message.answer("Используй кнопки ниже или введи команду вручную.")


@app.post("/whoop-webhook")
async def whoop_webhook(request: Request):
    data = await request.json()
    # Сохраняем WHOOP-данные
    data_with_ts = {
        **data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(WHOOP_DATA_FILE, "a", encoding="utf-8") as f:
            json.dump(data_with_ts, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print("Failed to save WHOOP data:", e)

    # Нотификация в Telegram
    if USER_CHAT_ID:
        try:
            await bot.send_message(USER_CHAT_ID, f"Получены данные от WHOOP: {data}")
        except Exception as e:
            print("Failed to send Telegram notification:", e)

    return {"ok": True}


async def send_daily_whoop_summary():
    if not USER_CHAT_ID:
        return
    data = load_latest_whoop_data()
    if not data:
        return
    sleep = data.get("sleep")
    recovery = data.get("recovery")
    strain = data.get("strain")
    steps = data.get("steps")
    hrv = data.get("hrv")
    tips = [
        "Сделайте лёгкую растяжку сегодня.",
        "Не забывайте про воду в течение дня.",
        "Короткая медитация поможет сосредоточиться.",
    ]
    report = [
        f"Сон: {sleep} ч." if sleep is not None else "Данных о сне нет.",
        (
            f"Восстановление {recovery}%"
            if recovery is not None
            else "Нет данных о восстановлении."
        ),
        f"Нагрузка {strain}" if strain is not None else "Нет данных о нагрузке.",
        f"HRV {hrv}" if hrv is not None else "Нет данных HRV.",
        f"Шаги {steps}" if steps is not None else "Нет данных о шагах.",
        random.choice(tips),
    ]
    await bot.send_message(USER_CHAT_ID, "\n".join(report))


async def send_habit_reminder():
    if not USER_CHAT_ID:
        return
    habits = load_habits().get(str(USER_CHAT_ID), [])
    if not habits:
        return
    text = "Напоминание о привычках:\n- " + "\n- ".join(habits)
    text += "\nОтметь выполнение: /done название_привычки"
    await bot.send_message(USER_CHAT_ID, text)


async def smart_reminders():
    if not USER_CHAT_ID:
        return
    data = load_latest_whoop_data()
    if not data:
        return
    messages = []
    recovery = data.get("recovery")
    steps = data.get("steps")
    if recovery is not None and recovery < 60:
        messages.append("Сегодня восстановление низкое. Лучше отдохнуть.")
    if steps is not None and steps < 5000:
        messages.append("К вечеру меньше 5000 шагов. Прогуляйтесь!")
    for msg in messages:
        await bot.send_message(USER_CHAT_ID, msg)


async def _summarize_notes(days: int, title: str):
    if not USER_CHAT_ID:
        return
    notes = load_notes(days)
    if not notes:
        return
    text = "\n".join(f"- {n.get('text','')}" for n in notes if n.get("text"))
    openai.api_key = OPENAI_API_KEY
    try:
        resp = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Summarize the following notes in a short paragraph in the same language as the notes.",
                    },
                    {"role": "user", "content": text},
                ],
            ),
        )
        summary = resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("GPT summary error:", e)
        summary = "Не удалось получить сводку."
    await bot.send_message(USER_CHAT_ID, f"{title}\n{summary}")


async def send_daily_notes_summary():
    await _summarize_notes(1, "Сводка дня:")


async def send_weekly_notes_summary():
    await _summarize_notes(7, "Сводка недели:")


def _average(lst):
    return sum(lst) / len(lst) if lst else None


async def send_weekly_report():
    if not USER_CHAT_ID:
        return
    data7 = load_whoop_data(7)
    if not data7:
        await bot.send_message(USER_CHAT_ID, "Нет данных WHOOP за неделю.")
        return
    sleep = _average([d.get("sleep") for d in data7 if d.get("sleep") is not None])
    recovery = _average(
        [d.get("recovery") for d in data7 if d.get("recovery") is not None]
    )
    strain = _average([d.get("strain") for d in data7 if d.get("strain") is not None])
    hrv = _average([d.get("hrv") for d in data7 if d.get("hrv") is not None])
    steps = _average([d.get("steps") for d in data7 if d.get("steps") is not None])
    report = [
        "Недельный отчёт WHOOP:",
        f"Средний сон: {sleep:.1f} ч." if sleep is not None else "- сон: нет данных",
        (
            f"Среднее восстановление: {recovery:.0f}%"
            if recovery is not None
            else "- восстановление: нет данных"
        ),
        (
            f"Средняя нагрузка: {strain:.1f}"
            if strain is not None
            else "- нагрузка: нет данных"
        ),
        f"Средний HRV: {hrv:.1f}" if hrv is not None else "- HRV: нет данных",
        f"Средние шаги: {steps:.0f}" if steps is not None else "- шаги: нет данных",
    ]
    await bot.send_message(USER_CHAT_ID, "\n".join(report))


async def start_bot():
    await dp.start_polling(bot)


@app.on_event("startup")
async def on_startup() -> None:
    scheduler.add_job(send_daily_whoop_summary, "cron", hour=8, minute=0)
    scheduler.add_job(send_habit_reminder, "cron", hour=8, minute=30)
    scheduler.add_job(send_habit_reminder, "cron", hour=13, minute=0)
    scheduler.add_job(send_habit_reminder, "cron", hour=19, minute=0)
    scheduler.add_job(smart_reminders, "cron", hour=18, minute=0)
    scheduler.add_job(send_weekly_report, "cron", day_of_week="sun", hour=20, minute=0)
    scheduler.add_job(send_daily_notes_summary, "cron", hour=21, minute=0)
    scheduler.add_job(send_weekly_notes_summary, "cron", day_of_week="sun", hour=21, minute=5)
    scheduler.start()
    asyncio.create_task(start_bot())


if __name__ == "__main__":
    uvicorn.run("run_agent:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

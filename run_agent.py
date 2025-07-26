import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import FastAPI, Request, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import openai
import uvicorn

# ---------------------------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------------------------
TG_TOKEN = os.getenv("TG_TOKEN")
USER_CHAT_ID = int(os.getenv("USER_CHAT_ID", "0")) or None
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

WHOOP_DATA_FILE = os.getenv("WHOOP_DATA_FILE", "whoop_data.json")
MORNING_FILE = os.getenv("MORNING_CHECKIN_FILE", "morning_checkins.json")
HABITS_FILE = os.getenv("HABITS_FILE", "habits.json")
HABIT_LOG_FILE = os.getenv("HABIT_LOG_FILE", "habit_log.json")
NOTES_FILE = os.getenv("NOTES_FILE", "notes.json")
LANG_FILE = os.getenv("LANG_FILE", "user_langs.json")

if not TG_TOKEN:
    raise RuntimeError("TG_TOKEN is not set")

bot = Bot(TG_TOKEN)
dp = Dispatcher()
app = FastAPI()
scheduler = AsyncIOScheduler(timezone="UTC")

# ---------------------------------------------------------------------------
# Helpers for JSON persistence
# ---------------------------------------------------------------------------

def load_json(path: str, default: Any) -> Any:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to read {path}: {e}")
    return default


def save_json(path: str, data: Any) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save {path}: {e}")


def append_json_line(path: str, data: Dict[str, Any]) -> None:
    try:
        with open(path, "a", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.write("\n")
    except Exception as e:
        print(f"Failed to append {path}: {e}")


def read_last_json(path: str) -> Dict[str, Any] | None:
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
                char = f.read(1)
                if char == b"\n" and line:
                    break
                line = char + line
            if line:
                return json.loads(line.decode("utf-8"))
    except Exception as e:
        print(f"Failed to read last json from {path}: {e}")
    return None

# ---------------------------------------------------------------------------
# Localization
# ---------------------------------------------------------------------------

MESSAGES = {
    "ru": {
        "choose_lang": "Привет! \u2753 Выбери язык:",
        "welcome": "Привет! \u2728 Готов к работе, используй кнопки ниже!",
        "daily_none": "Нет данных WHOOP \u2639\ufe0f",
        "ask_note": "\ud83d\udcdd Пришли текст заметки после команды",
        "note_saved": "\u2705 Заметка сохранена",
        "habit_added": "\u2705 Привычка добавлена",
        "habit_prompt": "Какую привычку добавляем?",
        "habits_empty": "Привычек пока нет",
        "habit_list": "\ud83d\udcc5 Твои привычки:\n- {items}",
        "habit_done_prompt": "Какая привычка выполнена?",
        "habit_done": "\ud83c\udf89 Отлично, отмечено!",
        "ask_question": "\u2753 Напиши вопрос после команды",
        "openai_error": "Не удалось получить ответ \ud83d\ude1e",
        "goals": "\ud83c\udf1e Какие цели на сегодня?",
        "morning_q": "Как самочувствие?",
        "mood_saved": "Записал!",
    },
    "en": {
        "choose_lang": "Hi! \u2753 Choose your language:",
        "welcome": "Hi! \u2728 Ready to work. Use the buttons below!",
        "daily_none": "No WHOOP data yet",
        "ask_note": "\ud83d\udcdd Send your note after the command",
        "note_saved": "\u2705 Note saved",
        "habit_added": "\u2705 Habit added",
        "habit_prompt": "Which habit to add?",
        "habits_empty": "No habits yet",
        "habit_list": "\ud83d\udcc5 Your habits:\n- {items}",
        "habit_done_prompt": "Which habit is done?",
        "habit_done": "\ud83c\udf89 Great, marked!",
        "ask_question": "\u2753 Send your question after the command",
        "openai_error": "Failed to get response \ud83d\ude1e",
        "goals": "\ud83c\udf1e What are your goals today?",
        "morning_q": "How do you feel?",
        "mood_saved": "Saved!",
    },
}

ADVICE = {
    "ru": "Не забудь размяться \ud83d\udcaa",
    "en": "Don't forget to stretch \ud83d\udcaa",
}


def get_lang(user_id: int) -> str:
    langs = load_json(LANG_FILE, {})
    return langs.get(str(user_id), "ru")


def main_kb() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="/дневнойотчет \ud83d\udcca"), KeyboardButton(text="/утреннийчекап \u2600\ufe0f")],
        [KeyboardButton(text="/цели \ud83c\udf97\ufe0f"), KeyboardButton(text="/заметки \ud83d\udcdd")],
        [KeyboardButton(text="/добавитьпривычку \u2705"), KeyboardButton(text="/привычки \ud83d\udccb")],
        [KeyboardButton(text="/готово \ud83c\udf89"), KeyboardButton(text="/спросить \ud83e\udd14")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

@dp.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    langs = load_json(LANG_FILE, {})
    if str(message.from_user.id) not in langs:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="\ud83c\uddf7\ud83c\uddfa Русский", callback_data="setlang_ru"),
            InlineKeyboardButton(text="\ud83c\uddec\ud83c\udde7 English", callback_data="setlang_en"),
        ]])
        await message.answer(MESSAGES["ru"]["choose_lang"], reply_markup=kb)
    else:
        lang = langs[str(message.from_user.id)]
        await message.answer(MESSAGES[lang]["welcome"], reply_markup=main_kb())


@dp.callback_query(F.data.startswith("setlang_"))
async def cb_set_lang(call: types.CallbackQuery) -> None:
    lang = call.data.split("_", 1)[1]
    langs = load_json(LANG_FILE, {})
    langs[str(call.from_user.id)] = lang
    save_json(LANG_FILE, langs)
    await call.message.answer(MESSAGES[lang]["welcome"], reply_markup=main_kb())
    await call.answer()


@dp.message(Command("дневнойотчет"))
async def cmd_daily_report(message: types.Message) -> None:
    lang = get_lang(message.from_user.id)
    data = read_last_json(WHOOP_DATA_FILE)
    if not data:
        await message.answer(MESSAGES[lang]["daily_none"])
        return
    lines = [
        f"\ud83d\udecc Сон: {data.get('sleep')} ч." if data.get('sleep') is not None else "\ud83d\udecc Сон: н/д",
        f"\ud83d\udc9a Восстановление: {data.get('recovery')}%" if data.get('recovery') is not None else "\ud83d\udc9a Восстановление: н/д",
        f"\ud83c\udfcb\ufe0f\u200d♂️ Нагрузка: {data.get('strain')}" if data.get('strain') is not None else "\ud83c\udfcb\ufe0f\u200d♂️ Нагрузка: н/д",
        f"\ud83d\udc63 Шаги: {data.get('steps')}" if data.get('steps') is not None else "\ud83d\udc63 Шаги: н/д",
    ]
    text = "\n".join(lines) + f"\n{ADVICE[lang]}"
    await message.answer(text)


@dp.message(Command("утреннийчекап"))
async def cmd_morning_check(message: types.Message) -> None:
    lang = get_lang(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\ud83d\ude0a Хорошо", callback_data="mood_good"),
         InlineKeyboardButton(text="\ud83d\ude10 Нормально", callback_data="mood_ok")],
        [InlineKeyboardButton(text="\ud83d\ude14 Плохо", callback_data="mood_bad")],
    ])
    await message.answer(MESSAGES[lang]["morning_q"], reply_markup=kb)


@dp.callback_query(F.data.startswith("mood_"))
async def cb_mood(call: types.CallbackQuery) -> None:
    mood = call.data.split("_", 1)[1]
    entry = {
        "user": call.from_user.id,
        "mood": mood,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    data = load_json(MORNING_FILE, [])
    data.append(entry)
    save_json(MORNING_FILE, data)
    lang = get_lang(call.from_user.id)
    await call.answer(MESSAGES[lang]["mood_saved"], show_alert=False)


@dp.message(Command("цели"))
async def cmd_goals(message: types.Message) -> None:
    lang = get_lang(message.from_user.id)
    await message.answer(MESSAGES[lang]["goals"])


@dp.message(Command("заметки"))
async def cmd_notes(message: types.Message) -> None:
    lang = get_lang(message.from_user.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(MESSAGES[lang]["ask_note"])
        return
    note = {
        "user": message.from_user.id,
        "text": parts[1],
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    notes = load_json(NOTES_FILE, [])
    notes.append(note)
    save_json(NOTES_FILE, notes)
    await message.answer(MESSAGES[lang]["note_saved"])


@dp.message(Command("добавитьпривычку"))
async def cmd_add_habit(message: types.Message) -> None:
    lang = get_lang(message.from_user.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(MESSAGES[lang]["habit_prompt"])
        return
    habit = parts[1]
    habits = load_json(HABITS_FILE, {})
    user_habits = habits.get(str(message.from_user.id), [])
    if habit not in user_habits:
        user_habits.append(habit)
    habits[str(message.from_user.id)] = user_habits
    save_json(HABITS_FILE, habits)
    await message.answer(MESSAGES[lang]["habit_added"])


@dp.message(Command("привычки"))
async def cmd_habits(message: types.Message) -> None:
    lang = get_lang(message.from_user.id)
    habits = load_json(HABITS_FILE, {}).get(str(message.from_user.id), [])
    if habits:
        text = MESSAGES[lang]["habit_list"].format(items="\n- ".join(habits))
    else:
        text = MESSAGES[lang]["habits_empty"]
    await message.answer(text)


@dp.message(Command("готово"))
async def cmd_done(message: types.Message) -> None:
    lang = get_lang(message.from_user.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(MESSAGES[lang]["habit_done_prompt"])
        return
    habit = parts[1]
    logs = load_json(HABIT_LOG_FILE, [])
    logs.append({"user": message.from_user.id, "habit": habit, "ts": datetime.now(timezone.utc).isoformat()})
    save_json(HABIT_LOG_FILE, logs)
    await message.answer(MESSAGES[lang]["habit_done"])


@dp.message(Command("спросить"))
async def cmd_ask(message: types.Message) -> None:
    lang = get_lang(message.from_user.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(MESSAGES[lang]["ask_question"])
        return
    if not OPENAI_API_KEY:
        await message.answer("OPENAI_API_KEY is not set")
        return
    openai.api_key = OPENAI_API_KEY
    try:
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": parts[1]}],
            ),
        )
        ans = resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("OpenAI error:", e)
        ans = MESSAGES[lang]["openai_error"]
    await message.answer(ans)


@dp.message()
async def fallback(message: types.Message) -> None:
    lang = get_lang(message.from_user.id)
    await message.answer("Выбери команду на клавиатуре \ud83d\ude42" if lang == "ru" else "Please use the keyboard \ud83d\ude42")

# ---------------------------------------------------------------------------
# Background jobs
# ---------------------------------------------------------------------------

async def daily_whoop_report() -> None:
    if not USER_CHAT_ID:
        return
    data = read_last_json(WHOOP_DATA_FILE)
    if not data:
        return
    lang = get_lang(USER_CHAT_ID)
    lines = [
        f"\ud83d\udecc Сон: {data.get('sleep')} ч." if data.get('sleep') is not None else "\ud83d\udecc Сон: н/д",
        f"\ud83d\udc9a Восстановление: {data.get('recovery')}%" if data.get('recovery') is not None else "\ud83d\udc9a Восстановление: н/д",
        f"\ud83c\udfcb\ufe0f\u200d♂️ Нагрузка: {data.get('strain')}" if data.get('strain') is not None else "\ud83c\udfcb\ufe0f\u200d♂️ Нагрузка: н/д",
        f"\ud83d\udc63 Шаги: {data.get('steps')}" if data.get('steps') is not None else "\ud83d\udc63 Шаги: н/д",
    ]
    text = "\n".join(lines) + f"\n{ADVICE[lang]}"
    await bot.send_message(USER_CHAT_ID, text)


async def habit_reminder() -> None:
    if not USER_CHAT_ID:
        return
    lang = get_lang(USER_CHAT_ID)
    habits = load_json(HABITS_FILE, {}).get(str(USER_CHAT_ID), [])
    if not habits:
        return
    text = MESSAGES[lang]["habit_list"].format(items="\n- ".join(habits))
    await bot.send_message(USER_CHAT_ID, text)


async def smart_reminders() -> None:
    if not USER_CHAT_ID:
        return
    data = read_last_json(WHOOP_DATA_FILE)
    if not data:
        return
    lang = get_lang(USER_CHAT_ID)
    msgs = []
    if data.get("recovery") is not None and data["recovery"] < 60:
        msgs.append("\ud83d\udca4 Отдохни сегодня" if lang == "ru" else "\ud83d\udca4 Take a rest today")
    if data.get("steps") is not None and data["steps"] < 5000:
        msgs.append("\ud83d\udeb6\ufe0f\u200d♂️ Прогуляйся немного" if lang == "ru" else "\ud83d\udeb6\ufe0f\u200d♂️ Time for a walk")
    for m in msgs:
        await bot.send_message(USER_CHAT_ID, m)


async def weekly_report() -> None:
    if not USER_CHAT_ID or not os.path.exists(WHOOP_DATA_FILE):
        return
    try:
        with open(WHOOP_DATA_FILE, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception as e:
        print("Weekly report read error:", e)
        return
    if not lines:
        return
    last7 = [json.loads(l) for l in lines[-7:]]
    def avg(key: str) -> float | None:
        vals = [e.get(key) for e in last7 if e.get(key) is not None]
        return sum(vals) / len(vals) if vals else None
    sleep = avg("sleep")
    recovery = avg("recovery")
    strain = avg("strain")
    steps = avg("steps")
    lang = get_lang(USER_CHAT_ID)
    lines = [
        f"\ud83d\udecc {sleep:.1f} ч. средний сон" if sleep is not None else None,
        f"\ud83d\udc9a {recovery:.0f}% среднее восстановление" if recovery is not None else None,
        f"\ud83c\udfcb\ufe0f\u200d♂️ {strain:.1f} средняя нагрузка" if strain is not None else None,
        f"\ud83d\udc63 {steps:.0f} средние шаги" if steps is not None else None,
    ]
    text_lines = [l for l in lines if l]
    if not text_lines:
        return
    header = "\ud83d\udcc8 Итоги недели:\n" if lang == "ru" else "\ud83d\udcc8 Weekly summary:\n"
    await bot.send_message(USER_CHAT_ID, header + "\n".join(text_lines))

# ---------------------------------------------------------------------------
# FastAPI routes
# ---------------------------------------------------------------------------

@app.post("/whoop-webhook")
async def whoop_webhook(request: Request) -> Dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    payload["ts"] = datetime.now(timezone.utc).isoformat()
    append_json_line(WHOOP_DATA_FILE, payload)
    if USER_CHAT_ID:
        await bot.send_message(USER_CHAT_ID, "Получены данные WHOOP \u2705")
    return {"ok": True}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

async def start_bot() -> None:
    await dp.start_polling(bot)


@app.on_event("startup")
async def on_startup() -> None:
    scheduler.add_job(daily_whoop_report, "cron", hour=8, minute=0)
    scheduler.add_job(habit_reminder, "cron", hour=9, minute=0)
    scheduler.add_job(habit_reminder, "cron", hour=13, minute=0)
    scheduler.add_job(habit_reminder, "cron", hour=19, minute=0)
    scheduler.add_job(smart_reminders, "cron", hour=18, minute=0)
    scheduler.add_job(weekly_report, "cron", day_of_week="sun", hour=20, minute=0)
    scheduler.start()
    asyncio.create_task(start_bot())


if __name__ == "__main__":
    uvicorn.run("run_agent:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

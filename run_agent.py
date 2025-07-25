import os
import asyncio
import json
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from fastapi import FastAPI, Request
import uvicorn

TG_TOKEN = os.getenv("TG_TOKEN")
USER_CHAT_ID = os.getenv("USER_CHAT_ID")
WHOOP_DATA_FILE = os.getenv("WHOOP_DATA_FILE", "whoop_data.json")
MORNING_CHECKIN_FILE = os.getenv("MORNING_CHECKIN_FILE", "morning_checkins.json")

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()
app = FastAPI()

# Reply‑keyboard с основными командами
kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/dailyreport")],
        [KeyboardButton(text="/morningcheckin")],
        [KeyboardButton(text="/goals")],
        [KeyboardButton(text="/mynotes")],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


def load_latest_whoop_data() -> dict | None:
    if not os.path.exists(WHOOP_DATA_FILE):
        return None
    try:
        with open(WHOOP_DATA_FILE, "r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
        if not lines:
            return None
        return json.loads(lines[-1])
    except Exception as e:
        print("Failed to read WHOOP data:", e)
        return None


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


@dp.message(F.text == "/start")
async def start_handler(message: types.Message):
    await message.answer(
        "Привет! Я помогу тебе следить за здоровьем.\n\n"
        "Выбирай команды ниже или вводи вручную:",
        reply_markup=kb
    )


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
        f"Восстановление {recovery}% и нагрузка {strain}." if recovery is not None and strain is not None
            else "Нет данных о восстановлении или нагрузке.",
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


@dp.message(Command("goals"))
async def goals_handler(message: types.Message):
    await message.answer(
        "Установи свои цели на сегодня:\n"
        "- Шаги\n"
        "- Сон\n"
        "- Восстановление"
    )


@dp.message(Command("mynotes"))
async def notes_handler(message: types.Message):
    text = message.text or ""
    note = text[len("/mynotes"):].strip()
    if not note:
        await message.answer(
            "Напиши заметку после команды, например:\n"
            "`/mynotes Купил продукты`"
        )
        return
    # TODO: сохранить заметку в файл или БД
    await message.answer("Заметка сохранена ✅")


@dp.message()
async def fallback_handler(message: types.Message):
    await message.answer("Используй кнопки ниже или введи команду вручную.")


@app.post("/whoop-webhook")
async def whoop_webhook(request: Request):
    data = await request.json()
    # Сохраняем WHOOP-данные
    try:
        with open(WHOOP_DATA_FILE, "a", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
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


async def start_bot():
    await dp.start_polling(bot)


@app.on_event("startup")
async def on_startup() -> None:
    asyncio.create_task(start_bot())


if __name__ == "__main__":
    uvicorn.run("run_agent:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

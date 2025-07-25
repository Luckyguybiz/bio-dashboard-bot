import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from fastapi import FastAPI, Request

# --- FastAPI app для Railway ---
app = FastAPI()

TG_TOKEN = os.getenv("TG_TOKEN")
bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

@dp.message(F.text == "/start")
async def start_handler(message: types.Message):
    await message.reply("Бот успешно запущен! 🚀")

@dp.message()
async def echo_handler(message: types.Message):
    await message.reply("Я работаю на Railway! Твой бот готов :)")

# Пример обработчика Webhook (можно удалить, если не нужен)
@app.post("/whoop-webhook")
async def whoop_webhook(request: Request):
    data = await request.json()
    print("Получены данные от WHOOP:", data)
    return {"ok": True}

# Запуск aiogram-поллинга в фоне
async def start_bot():
    await dp.start_polling(bot)

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(start_bot())

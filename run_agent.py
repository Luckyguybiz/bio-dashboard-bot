import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from fastapi import FastAPI, Request
import uvicorn

TG_TOKEN = os.getenv("TG_TOKEN")

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()
app = FastAPI()

@dp.message(F.text == "/start")
async def start_handler(message: types.Message):
    await message.reply("Бот успешно запущен! 🚀")

@dp.message()
async def echo_handler(message: types.Message):
    await message.reply("Я работаю на Railway/Codex! Твой бот готов :)")

@app.post("/whoop-webhook")
async def whoop_webhook(request: Request):
    data = await request.json()
    print("Получены данные от WHOOP:", data)
    return {"ok": True}

async def start_bot():
    await dp.start_polling(bot)

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(start_bot())

if __name__ == "__main__":
    uvicorn.run("run_agent:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

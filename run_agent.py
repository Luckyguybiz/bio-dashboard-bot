import os
import asyncio
from aiogram import Bot, Dispatcher, types

# Получаем токен Telegram из переменной окружения
TG_TOKEN = os.getenv("TG_TOKEN")

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()

@dp.message(commands=["start"])
async def start_handler(message: types.Message):
    await message.reply("Бот успешно запущен! 🚀")

@dp.message()
async def echo_handler(message: types.Message):
    await message.reply("Я работаю на Railway! Твой бот готов :)")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

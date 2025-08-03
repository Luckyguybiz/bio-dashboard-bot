import os
import asyncio
from typing import Set

import openai
from aiogram import Bot, Dispatcher, types

TG_TOKEN = os.getenv("TG_TOKEN")
DEST_CHANNEL_ID = int(os.getenv("DEST_CHANNEL_ID", "0"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TG_TOKEN or not DEST_CHANNEL_ID or not OPENAI_API_KEY:
    raise RuntimeError("TG_TOKEN, DEST_CHANNEL_ID and OPENAI_API_KEY must be set")

SOURCE_CHANNELS: Set[str] = {"chatgptv", "denissexy"}

bot = Bot(TG_TOKEN)
dp = Dispatcher()
openai.api_key = OPENAI_API_KEY


async def rewrite_text(text: str) -> str:
    loop = asyncio.get_running_loop()
    prompt = f"Перепиши текст своими словами, сохрани смысл.\n\n{text}"
    response = await loop.run_in_executor(
        None,
        lambda: openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
        ),
    )
    return response["choices"][0]["message"]["content"].strip()


@dp.channel_post()
async def handle_channel_post(message: types.Message) -> None:
    username = message.chat.username
    if not username or username.lower() not in SOURCE_CHANNELS:
        return
    text = message.text or message.caption
    if not text:
        return
    try:
        rewritten = await rewrite_text(text)
    except Exception as e:
        print("Rewrite failed:", e)
        return
    final_text = f"{rewritten}\n\nИсточник - @{username}"
    if message.photo:
        file_id = message.photo[-1].file_id
        await bot.send_photo(DEST_CHANNEL_ID, file_id, caption=final_text)
    elif message.video:
        file_id = message.video.file_id
        await bot.send_video(DEST_CHANNEL_ID, file_id, caption=final_text)
    else:
        await bot.send_message(DEST_CHANNEL_ID, final_text)


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

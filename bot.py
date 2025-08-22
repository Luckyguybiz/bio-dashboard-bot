import os
import re
import tempfile
import openai
import yt_dlp
from moviepy.editor import VideoFileClip
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# Читаем токены из переменных окружения
BOT_TOKEN = os.getenv("TG_TOKEN")              # ваш токен телеграм-бота
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")   # API-ключ OpenAI (Whisper)

openai.api_key = OPENAI_API_KEY

# Регулярное выражение для поиска URL-ов на reels
REEL_PATTERN = re.compile(r"https?://(?:www\\.)?instagram\\.com/reel/[\\w\\-]+/?")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение."""
    await update.message.reply_text(
        "Привет! Отправь одну или несколько ссылок на Instagram Reels, "
        "а я скачаю их и верну видео и текстовую расшифровку."
    )

async def process_links(links, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает список ссылок — скачивает, транскрибирует и отправляет."""
    for idx, url in enumerate(links, 1):
        await update.message.reply_text(f"({idx}/{len(links)}) Обрабатываю ссылку: {url}")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                video_path = os.path.join(tmpdir, "video.mp4")

                # 1. Скачиваем видео через yt-dlp
                ydl_opts = {
                    "format": "mp4",
                    "outtmpl": video_path,
                    "quiet": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                # 2. Извлекаем аудио
                wav_path = os.path.join(tmpdir, "audio.wav")
                with VideoFileClip(video_path) as clip:
                    clip.audio.write_audiofile(wav_path, logger=None)

                # 3. Отправляем аудио на распознавание в Whisper (OpenAI)
                with open(wav_path, "rb") as audio_file:
                    transcript_text = openai.Audio.transcribe(
                        model="whisper-1",
                        file=audio_file,
                        response_format="text"
                    )

                # 4. Отправляем оригинальное видео пользователю
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=InputFile(video_path),
                    caption=f"Ролик по ссылке {url}"
                )

                # 5. Отправляем транскрипцию
                await update.message.reply_text(f"Текст:\n{transcript_text.strip()}")

        except Exception as e:
            await update.message.reply_text(f"Ошибка при обработке {url}: {e}")

async def transcribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /transcribe с поддержкой нескольких ссылок."""
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите хотя бы один URL после /transcribe.")
        return
    links = [arg for arg in context.args if REEL_PATTERN.match(arg)]
    if not links:
        await update.message.reply_text("Не найдено валидных ссылок на Reels.")
        return
    await process_links(links, update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик обычных сообщений — ищет ссылки."""
    text = update.message.text or ""
    links = REEL_PATTERN.findall(text)
    if not links:
        await update.message.reply_text("Пришлите ссылку на Reel, и я скачиваю и расшифрую.")
        return
    await process_links(links, update, context)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    # Команда start
    app.add_handler(CommandHandler("start", start))
    # Команда /transcribe
    app.add_handler(CommandHandler("transcribe", transcribe_command))
    # Сообщения с URL-ами
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()

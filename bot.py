import os, re, tempfile
import yt_dlp
import openai
from moviepy.editor import VideoFileClip

from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

BOT_TOKEN = os.getenv("TG_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

REEL_PATTERN = re.compile(r"https?://(?:www\\.)?instagram\\.com/reel/[\\w\\-]+/?")

# телеграм ограничение 4096 символов
def chunk_text(text, limit=4096):
    out = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        out.append(text[:cut])
        text = text[cut:]
    if text:
        out.append(text)
    return out

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Пришли одну или несколько ссылок на Instagram Reels — "
        "я скачаю видео и верну транскрипцию в чат.\n"
        "Можно командой /transcribe <url1> <url2> … или просто текстом со ссылками."
    )

async def transcribe_url(url: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(chat_id, f"Скачиваю: {url}")
        with tempfile.TemporaryDirectory() as tmp:
            mp4 = os.path.join(tmp, "video.mp4")
            wav = os.path.join(tmp, "audio.wav")

            # 1) скачиваем видео
            ydl_opts = {"format": "mp4", "outtmpl": mp4, "quiet": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # 2) извлекаем аудио
            with VideoFileClip(mp4) as clip:
                if not clip.audio:
                    raise RuntimeError("В видео нет аудио-дорожки")
                clip.audio.write_audiofile(wav, logger=None)

            # 3) транскрипция (OpenAI Whisper)
            await context.bot.send_message(chat_id, "Распознаю речь…")
            with open(wav, "rb") as f:
                txt = openai.Audio.transcribe(
                    model="whisper-1",
                    file=f,
                    response_format="text"
                )

            # 4) отправляем видео и текст
            try:
                await context.bot.send_video(chat_id, InputFile(mp4), caption="Видео")
            except Exception as e:
                await context.bot.send_message(chat_id, f"⚠️ Не удалось отправить видео ({e}).")

            text = txt.strip()
            if not text:
                text = "(пустая транскрипция)"

            for part in chunk_text(f"Транскрипция:\n{text}"):
                await context.bot.send_message(chat_id, part)

    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ Ошибка при обработке {url}: {e}")

async def transcribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Используйте: /transcribe <url1> <url2> …")
        return
    links = [u for u in context.args if REEL_PATTERN.match(u)]
    if not links:
        await update.message.reply_text("Не нашёл валидные ссылки вида https://www.instagram.com/reel/…")
        return
    for i, link in enumerate(links, 1):
        await update.message.reply_text(f"({i}/{len(links)}) В работу: {link}")
        await transcribe_url(link, update.effective_chat.id, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text or ""
    links = REEL_PATTERN.findall(txt)
    if not links:
        await update.message.reply_text("Пришлите ссылку(и) на Reels.")
        return
    for i, link in enumerate(links, 1):
        await update.message.reply_text(f"({i}/{len(links)}) В работу: {link}")
        await transcribe_url(link, update.effective_chat.id, context)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("transcribe", transcribe_cmd))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()

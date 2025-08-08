from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from ..services import llm_service, postwindow_service


async def addchannel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("channel added")


async def list_(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("listed")


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("top")


async def gaps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("gaps")


async def ideas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("\n".join(llm_service.generate_ideas("niche", 1)))


async def script(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(llm_service.generate_script_60s("topic"))


async def titles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("\n".join(llm_service.generate_titles("topic")))


async def postwindows(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(", ".join(postwindow_service.get_postwindows()))


async def brief(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("brief")


def build_app(token: str):
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("addchannel", addchannel))
    app.add_handler(CommandHandler("list", list_))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("gaps", gaps))
    app.add_handler(CommandHandler("ideas", ideas))
    app.add_handler(CommandHandler("script", script))
    app.add_handler(CommandHandler("titles", titles))
    app.add_handler(CommandHandler("postwindows", postwindows))
    app.add_handler(CommandHandler("brief", brief))
    return app

import asyncio
from types import SimpleNamespace

from scc.bot import bot


class DummyMessage:
    def __init__(self):
        self.texts = []

    async def reply_text(self, text):
        self.texts.append(text)


class DummyUpdate(SimpleNamespace):
    def __init__(self):
        super().__init__(message=DummyMessage())


class DummyContext(SimpleNamespace):
    args: list[str] = []


def test_handlers_smoke():
    update = DummyUpdate()
    ctx = DummyContext()
    handlers = [
        bot.addchannel,
        bot.list_,
        bot.top,
        bot.gaps,
        bot.ideas,
        bot.script,
        bot.titles,
        bot.postwindows,
        bot.brief,
    ]

    async def run():
        for h in handlers:
            await h(update, ctx)

    asyncio.run(run())
    assert update.message.texts

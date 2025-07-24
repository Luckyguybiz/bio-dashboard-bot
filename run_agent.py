import os
import time
from autogen import Agent, Step
from autogen.integrations.github import GitHubAPI
from autogen.integrations.railway import RailwayAPI
from autogen.integrations.telegram import TelegramAPI

# Загружаем токены из .env
from dotenv import load_dotenv
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
RAILWAY_TOKEN = os.getenv("RAILWAY_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
USER_CHAT_ID = os.getenv("USER_CHAT_ID")  # ваш Telegram ID или username

# Инициализация инструментов
github = GitHubAPI(token=GITHUB_TOKEN)
railway = RailwayAPI(token=RAILWAY_TOKEN)
telegram = TelegramAPI(token=TG_TOKEN)

# Создаём агента
agent = Agent(
    name="bio_deployer",
    model="gpt-4o",
    tools=[github, railway, telegram],
)

# Шаги пайплайна
workflow = [
    Step("create_github_repo", args={"name": "bio-dashboard-bot", "private": True}),
    Step("generate_and_commit_files", args={
        "files": ["requirements.txt", "run_agent.py", "playbook.yaml", ".env"]
    }),
    Step("create_railway_project", args={"name": "bio-dashboard-bot"}),
    Step("set_railway_env", args={
        "VARS": {
            "TG_TOKEN": TG_TOKEN,
            "GITHUB_TOKEN": GITHUB_TOKEN,
            "RAILWAY_TOKEN": RAILWAY_TOKEN,
            "USER_CHAT_ID": USER_CHAT_ID,
        }
    }),
    Step("deploy_from_github"),
    Step("poll_deploy_status"),
    Step("set_telegram_webhook", args={"url_path": "/webhook"}),
    Step("notify_user", args={"chat_id": USER_CHAT_ID, "message": "✅ Бот деплоен и готов: t.me/your_bot_username"}),
]

# Запускаем агент
if __name__ == "__main__":
    agent.run(workflow)

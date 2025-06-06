from os import getenv
from dotenv import load_dotenv

load_dotenv()

class Settings:
    BOT_TOKEN = getenv("BOT_TOKEN")
    DATABASE_URL = getenv("DATABASE_URL")

    def __post_init__(self):
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не найден в переменных окружения")
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL не найден в переменных окружения")

settings = Settings()
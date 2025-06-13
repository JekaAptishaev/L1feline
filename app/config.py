from os import getenv
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = getenv("DATABASE_URL")
BOT_TOKEN = getenv("BOT_TOKEN")

# Проверка на наличие переменных
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не найден в переменных окружения")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")
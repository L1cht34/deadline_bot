import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
STAROSTA_PASSWORD: str = os.getenv("STAROSTA_PASSWORD", "stud_admin_2024")
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")

# Список доступных направлений/групп
ALLOWED_GROUPS = [
    "ВХТ-101",
    "ВВТ-106",
    "ВИП-108",
    "ВЭ-111",
    "ВЭ-112"
]

if not BOT_TOKEN:
    raise ValueError("Ошибка: переменная BOT_TOKEN не задана в файле .env!")
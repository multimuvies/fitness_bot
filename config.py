# config.py
"""
Читает переменные среды и хранит все глобальные настройки бота.

Скопируй .env.example → .env и заполни там BOT_TOKEN и OPENAI_API_KEY.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# загружаем переменные из .env в окружение
load_dotenv()


@dataclass(slots=True, frozen=True)
class Settings:
    # обязательные секреты
    BOT_TOKEN: str = os.environ["BOT_TOKEN"]          # Telegram Bot API token
    OPENAI_API_KEY: str = os.environ["OPENAI_API_KEY"]  # ключ OpenAI

    # модель и параметры GPT
    GPT_MODEL: str = "gpt-4o-mini"   # можно заменить на gpt-4o при необходимости
    GPT_TIMEOUT: int = 30            # секунд ожидания ответа

    # коэффициент активности для TDEE
    ACTIVITY_COEF: float = 1.25

    # База данных
    DB_PATH: str = os.getenv("DB_PATH", "fitness.db")
    DB_ECHO: bool = bool(int(os.getenv("DB_ECHO", "0")))  # логировать SQL

    # Прочее
    TZ_OFFSET_HOURS: int = 3         # Москва (UTC+3)


settings = Settings()

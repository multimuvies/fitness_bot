# main.py — точка входа

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import settings
from scheduler import make_scheduler

# ─── роутеры ────────────────────────────
from handlers.start import router as start_router
from handlers.menu import router as menu_router
from handlers.workout import router as workout_router
from handlers.meal import router as meal_router
from handlers.weight import router as weight_router
from handlers.checkpoint import router as checkpoint_router
from handlers.analytics import router as analytics_router
from handlers.ai_help import router as ai_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# bot с новым способом задания parse_mode
bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

dp.include_router(start_router)
dp.include_router(menu_router)
dp.include_router(workout_router)
dp.include_router(meal_router)
dp.include_router(weight_router)
dp.include_router(checkpoint_router)
dp.include_router(analytics_router)
dp.include_router(ai_router)


async def main() -> None:
    loop = asyncio.get_running_loop()

    # планировщик подключаем к уже работающему loop
    scheduler = make_scheduler(bot, loop)
    scheduler.start()

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

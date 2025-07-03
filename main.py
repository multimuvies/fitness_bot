"""
main.py — точка входа: создание бота, диспетчера, команд, планировщика,
          подключение всех роутеров и запуск polling
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from scheduler import make_scheduler                          # планировщик напоминаний

# ─────── настройка логов ───────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ─────── регистрация команд в «бургер-меню» ───────
async def set_commands(bot: Bot):
    await bot.set_my_commands(
        [
            types.BotCommand(command="start", description="Запустить / перезапустить бота"),
            types.BotCommand(command="menu",  description="Главное меню"),
        ]
    )


async def main():
    # 1. Бот и диспетчер
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # 2. Роутеры
    from handlers.start import router as start_router
    from handlers.menu import router as menu_router
    from handlers.workout import router as workout_router
    from handlers.meal import router as meal_router
    from handlers.weight import router as weight_router
    from handlers.checkpoint import router as checkpoint_router
    from handlers.ai_help import router as ai_router
    from handlers.analytics import router as analytics_router
    from handlers.friends import router as friends_router

    dp.include_router(start_router)
    dp.include_router(menu_router)
    dp.include_router(workout_router)
    dp.include_router(meal_router)
    dp.include_router(weight_router)
    dp.include_router(checkpoint_router)
    dp.include_router(ai_router)
    dp.include_router(analytics_router)
    dp.include_router(friends_router)

    # 3. slash-команды
    await set_commands(bot)

    # 4. планировщик ежедневных сообщений
    loop = asyncio.get_running_loop()
    scheduler = make_scheduler(bot, loop)
    scheduler.start()

    # 5. запуск long-polling
    logging.info("Starting bot…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")

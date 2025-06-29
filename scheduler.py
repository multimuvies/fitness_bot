# scheduler.py — фикc: извлекаем chat_id корректно

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import select
from zoneinfo import ZoneInfo

from models_and_db import get_session, User
from handlers.menu import menu_button

MSK = ZoneInfo("Europe/Moscow")


def _chat_ids() -> list[int]:
    """Возвращает список chat_id всех зарегистрированных пользователей."""
    with get_session() as s:
        # select(User.chat_id) → каждая строка = tuple(int) либо int (зависит от версии)
        return [row[0] if isinstance(row, tuple) else int(row) for row in s.exec(select(User.chat_id)).all()]


async def morning(bot: Bot):
    for cid in _chat_ids():
        await bot.send_message(
            cid,
            "Доброе утро!\nУдачных тренировок сегодня 💪\n"
            "Не забудь добавить результаты утреннего взвешивания 👇",
            reply_markup=menu_button(),
        )


async def evening(bot: Bot):
    for cid in _chat_ids():
        await bot.send_message(
            cid,
            "Пора готовиться ко сну!\nСтабильный сон – залог прогресса 😴\n"
            "Не забудь добавить результаты вечернего взвешивания 👇",
            reply_markup=menu_button(),
        )


def make_scheduler(bot: Bot, loop) -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone=MSK, event_loop=loop)
    sched.add_job(morning, CronTrigger(hour=6, minute=0), args=[bot], id="morning")
    sched.add_job(evening, CronTrigger(hour=22, minute=00), args=[bot], id="evening")
    return sched

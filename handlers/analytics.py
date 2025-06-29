"""handlers/analytics.py — выбор интервала, чекпоинты, краткая и детальная статистика"""

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func
from sqlmodel import select

from config import settings
from models_and_db import (
    get_session,
    User,
    Workout,
    Meal,
    Weight,
    Checkpoint,
)
from handlers.menu import menu_button

router = Router()
ITEMS_PER_PAGE = 5               # чекпоинтов на страницу
MSK = ZoneInfo("Europe/Moscow")  # московский часовой пояс


# ─────────────────────── вспомогательные ───────────────────────
def _scalar(raw: Any) -> int:
    """Приведение агрегатного результата к int (учёт разных версий SQLModel)."""
    if raw is None:
        return 0
    if isinstance(raw, tuple):
        return raw[0]
    if hasattr(raw, "_mapping"):
        return list(raw._mapping.values())[0]
    return int(raw)


def moscow_now() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc).astimezone(MSK)


def fmt(n: int | float) -> str:
    return f"{int(n):,}".replace(",", " ")


def interval_from_choice(user_id: int, choice: str) -> tuple[datetime, datetime]:
    """
    Возвращает (start, end) в naive-UTC.
    choice: '1d', '7d', 'cp_<id>'
    """
    now_utc = datetime.utcnow()  # naive UTC

    if choice == "1d":
        start = now_utc.replace(hour=0, minute=1, second=0, microsecond=0)
    elif choice == "7d":
        start = (now_utc - timedelta(days=7)).replace(
            hour=0, minute=1, second=0, microsecond=0
        )
    else:  # checkpoint
        cp_id = int(choice.split("_")[1])
        with get_session() as s:
            cp = s.get(Checkpoint, cp_id)
        start = cp.created_at.astimezone(timezone.utc).replace(tzinfo=None)

    return start, now_utc


# ───────────────────────── клавиатуры ─────────────────────────
def analytics_main_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="За 1 день", callback_data="an_1d")
    kb.button(text="За 7 дней", callback_data="an_7d")
    kb.button(text="Выбрать чекпоинт", callback_data="an_cp_page_0")
    kb.button(text="Меню", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def checkpoint_page_kb(chat_id: int, page: int = 0) -> types.InlineKeyboardMarkup:
    with get_session() as s:
        user = s.exec(select(User).where(User.chat_id == chat_id)).first()
        if not user:
            cps, total = [], 0
        else:
            total = _scalar(
                s.exec(
                    select(func.count())
                    .select_from(Checkpoint)
                    .where(Checkpoint.user_id == user.id)
                ).first()
            )
            cps = (
                s.exec(
                    select(Checkpoint)
                    .where(Checkpoint.user_id == user.id)
                    .order_by(Checkpoint.created_at.desc())
                    .offset(page * ITEMS_PER_PAGE)
                    .limit(ITEMS_PER_PAGE)
                ).all()
            )

    kb = InlineKeyboardBuilder()
    for cp in cps:
        kb.button(
            text=f"{cp.created_at.astimezone(MSK):%d.%m %H:%M}",
            callback_data=f"an_cp_{cp.id}",
        )

    if not cps:
        kb.button(text="— чекпоинтов нет —", callback_data="ignore")

    if page > 0:
        kb.button(text="◀️ Назад", callback_data=f"an_cp_page_{page-1}")
    if (page + 1) * ITEMS_PER_PAGE < total:
        kb.button(text="Вперёд ▶️", callback_data=f"an_cp_page_{page+1}")

    kb.button(text="Меню", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


# ───────────────────── подсчёт статистики ─────────────────────
def calc_stats(user: User, start: datetime, end: datetime) -> dict:
    delta_days = (end - start).total_seconds() / 86400

    with get_session() as s:
        meals_sum = _scalar(
            s.exec(
                select(func.sum(Meal.calories)).where(
                    (Meal.user_id == user.id) & (Meal.created_at.between(start, end))
                )
            ).first()
        )
        workouts_sum = _scalar(
            s.exec(
                select(func.sum(Workout.calories)).where(
                    (Workout.user_id == user.id)
                    & (Workout.created_at.between(start, end))
                )
            ).first()
        )
        workouts_cnt = _scalar(
            s.exec(
                select(func.count())
                .select_from(Workout)
                .where(
                    (Workout.user_id == user.id)
                    & (Workout.created_at.between(start, end))
                )
            ).first()
        )
        rows = s.exec(
            select(Workout.type, func.count())
            .where(
                (Workout.user_id == user.id)
                & (Workout.created_at.between(start, end))
            )
            .group_by(Workout.type)
            .order_by(func.count().desc())
        ).all()
        popular = [f"{r[0]} ({r[1]})" for r in rows]

        start_w = s.exec(
            select(Weight)
            .where((Weight.user_id == user.id) & (Weight.created_at <= start))
            .order_by(Weight.created_at.desc())
        ).first()
        end_w = s.exec(
            select(Weight)
            .where((Weight.user_id == user.id) & (Weight.created_at <= end))
            .order_by(Weight.created_at.desc())
        ).first()

    delta_w = (
        round(end_w.weight_kg - start_w.weight_kg, 1)
        if (start_w and end_w)
        else 0.0
    )
    metab = int(user.tdee * delta_days)
    balance = meals_sum + workouts_sum - metab

    return {
        "delta_w": delta_w,
        "start_w": start_w.weight_kg if start_w else "—",
        "end_w": end_w.weight_kg if end_w else "—",
        "meals": meals_sum,
        "workouts": workouts_sum,
        "metab": -metab,
        "balance": balance,
        "workouts_cnt": workouts_cnt,
        "popular": popular,
    }


# ───────────────────────── handlers ─────────────────────────
@router.callback_query(F.data == "analytics")
async def open_analytics(call: types.CallbackQuery):
    await call.message.edit_text("Выберите интервал:", reply_markup=analytics_main_kb())


@router.callback_query(F.data.in_(["an_1d", "an_7d"]))
async def analytics_interval(call: types.CallbackQuery):
    await show_stats(call, call.data.split("_")[1])


@router.callback_query(F.data.startswith("an_cp_page_"))
async def cp_page(call: types.CallbackQuery):
    page = int(call.data.split("_")[3])
    await call.message.edit_reply_markup(
        reply_markup=checkpoint_page_kb(call.from_user.id, page)
    )


@router.callback_query(F.data.startswith("an_cp_"))
async def cp_chosen(call: types.CallbackQuery):
    await show_stats(call, f"cp_{call.data.split('_')[2]}")


async def show_stats(call: types.CallbackQuery, choice: str):
    with get_session() as s:
        user = s.exec(select(User).where(User.chat_id == call.from_user.id)).first()

    start, end = interval_from_choice(call.from_user.id, choice)
    st = calc_stats(user, start, end)

    text = (
        f"<b>Статистика</b>\n{start.astimezone(MSK):%d.%m.%Y} — {moscow_now():%d.%m.%Y}\n\n"
        f"Баланс ккал: <b>{fmt(st['balance'])}</b>\n"
        f"Изменение веса: <b>{st['delta_w']} кг</b>\n"
        f"Тренировок: <b>{st['workouts_cnt']}</b>\n\n"
        "<i>Нажмите «Подробнее», чтобы увидеть развёрнутую статистику</i>"
        "\n\n\n <b>ИИ-ассистент для спорта и питания: @AI_sportik_bot</b>\n"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="Подробнее", callback_data=f"an_more_{choice}")
    kb.button(text="Меню", callback_data="menu")
    kb.adjust(1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("an_more_"))
async def details(call: types.CallbackQuery):
    choice = call.data[len("an_more_") :]
    with get_session() as s:
        user = s.exec(select(User).where(User.chat_id == call.from_user.id)).first()

    start, end = interval_from_choice(call.from_user.id, choice)
    st = calc_stats(user, start, end)

    text = (
        f"<b>I. Вес</b>\n"
        f"Было: {st['start_w']} кг → Стало: {st['end_w']} кг\n"
        f"Δ: <b>{st['delta_w']} кг</b>\n\n"
        f"<b>II. Калории</b>\n"
        f"Съедено: +{fmt(st['meals'])} ккал\n"
        f"Тренировки: {fmt(st['workouts'])} ккал\n"
        f"Метаболизм: {fmt(st['metab'])} ккал\n"
        f"Баланс: <b>{fmt(st['balance'])} ккал</b>\n\n"
        f"<b>III. Тренировки</b>\n"
        f"Всего: {st['workouts_cnt']}\n"
        f"Популярные: {', '.join(st['popular']) or 'нет'}"
        "\n\n\n <b>ИИ-ассистент для спорта и питания: @AI_sportik_bot</b>\n"
    )
    await call.message.edit_text(text, reply_markup=menu_button())

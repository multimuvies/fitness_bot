"""handlers/friends.py — список друзей, запросы и детальная статистика"""

from __future__ import annotations

from datetime import datetime, timezone, time as dtime
from math import ceil
from zoneinfo import ZoneInfo

from aiogram import Router, F, Bot, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlmodel import select, or_

from models_and_db import (
    get_session,
    User,
    Friend,
    FriendRequest,
    Meal,
)
from handlers.analytics import calc_stats
from handlers.menu import menu_button

router = Router()

MSK = ZoneInfo("Europe/Moscow")
PER_PAGE = 5  # друзей на страницу


# ═════════════ FSM ═════════════
class FriendState(StatesGroup):
    enter_username = State()


# ═══════════ helpers ═══════════
def today_interval() -> tuple[datetime, datetime]:
    """
    Возвращает (start, end) в naive-UTC, где
    start = 00:00 по Москве текущего дня, end = текущее UTC-время.
    """
    now_msk = datetime.now(MSK)
    start_msk = datetime.combine(now_msk.date(), dtime.min, tzinfo=MSK)
    start_utc = start_msk.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = datetime.utcnow()
    return start_utc, end_utc


def list_friends(user_id: int) -> list[User]:
    with get_session() as s:
        return s.exec(
            select(User)
            .join(Friend, Friend.friend_id == User.id)
            .where(Friend.user_id == user_id)
            .order_by(User.username)
        ).all()


def fmt(n: int | float) -> str:
    return f"{int(n):,}".replace(",", " ")


def to_msk(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone(MSK)


# ═══════════ keyboards ═══════════
def friends_page_kb(me_id: int, page: int = 0) -> types.InlineKeyboardMarkup:
    friends = list_friends(me_id)
    total_pages = max(1, ceil(len(friends) / PER_PAGE))
    start, end = page * PER_PAGE, page * PER_PAGE + PER_PAGE

    kb = InlineKeyboardBuilder()
    for fr in friends[start:end]:
        kb.button(text=fr.username or str(fr.chat_id), callback_data=f"fr_view_{fr.id}")

    if page > 0:
        kb.button(text="◀️ Назад", callback_data=f"fr_page_{page-1}")
    if page < total_pages - 1:
        kb.button(text="Вперёд ▶️", callback_data=f"fr_page_{page+1}")

    kb.button(text="➕ Добавить друга", callback_data="fr_add")
    kb.button(text="🏠 Меню", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def confirm_kb(req_id: int) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✓ Принять", callback_data=f"fr_ok_{req_id}")
    kb.button(text="✖️ Отклонить", callback_data=f"fr_no_{req_id}")
    kb.adjust(2)
    return kb.as_markup()


# ═══════════ список / пагинация ═══════════
@router.callback_query(F.data == "friends")
async def friends_main(call: types.CallbackQuery):
    with get_session() as s:
        me = s.exec(select(User).where(User.chat_id == call.from_user.id)).first()

    await call.message.edit_text(
        "<b>Друзья</b>\nВыберите друга, чтобы увидеть статистику:",
        reply_markup=friends_page_kb(me.id, 0),
    )


@router.callback_query(F.data.startswith("fr_page_"))
async def friends_page(call: types.CallbackQuery):
    page = int(call.data.split("_")[2])
    with get_session() as s:
        me = s.exec(select(User).where(User.chat_id == call.from_user.id)).first()

    await call.message.edit_reply_markup(reply_markup=friends_page_kb(me.id, page))


# ═══════════ детальная статистика друга ═══════════
@router.callback_query(F.data.startswith("fr_view_"))
async def friend_details(call: types.CallbackQuery):
    friend_id = int(call.data.split("_")[2])

    with get_session() as s:
        fr = s.get(User, friend_id)
    if not fr:
        await call.answer("Пользователь не найден.", show_alert=True)
        return

    start, end = today_interval()
    stats = calc_stats(fr, start, end)

    with get_session() as s:
        meals = (
            s.exec(
                select(Meal)
                .where(
                    (Meal.user_id == fr.id) & (Meal.created_at.between(start, end))
                )
                .order_by(Meal.created_at)
            ).all()
        )
    meals_block = (
        "\n".join(
            f"• {to_msk(m.created_at):%H:%M} — {m.description} ({m.calories} ккал)"
            for m in meals
        )
        or "нет"
    )

    text = (
        f"<b>Детальная статистика: {fr.username or fr.chat_id}</b>\n"
        f"{to_msk(start):%d.%m %H:%M} — {to_msk(end):%H:%M}\n\n"
        f"<b>I. Вес</b>\n"
        f"Было: {stats['start_w']} кг → Стало: {stats['end_w']} кг\n"
        f"Δ: <b>{stats['delta_w']} кг</b>\n\n"
        f"<b>II. Калории</b>\n"
        f"Съедено: +{fmt(stats['meals'])} ккал\n"
        f"Тренировки: {fmt(stats['workouts'])} ккал\n"
        f"Метаболизм: {fmt(stats['metab'])} ккал\n"
        f"Баланс: <b>{fmt(stats['balance'])} ккал</b>\n\n"
        f"<b>Приёмы пищи:</b>\n{meals_block}\n\n"
        f"<b>III. Тренировки</b>\n"
        f"Всего: {stats['workouts_cnt']}\n"
        f"Популярные: {', '.join(stats['popular']) or 'нет'}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="◀️ Назад", callback_data="friends")
    kb.button(text="🏠 Меню",  callback_data="menu")
    kb.adjust(1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())


# ═══════════ добавление друга ═══════════
@router.callback_query(F.data == "fr_add")
async def ask_username(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(FriendState.enter_username)
    await call.message.edit_text("Введи @username друга:", reply_markup=menu_button())


@router.message(FriendState.enter_username)
async def process_username(msg: types.Message, state: FSMContext, bot: Bot):
    raw = (msg.text or "").strip()
    uname = raw if raw.startswith("@") else f"@{raw}"

    if uname.lower() == f"@{(msg.from_user.username or '').lower()}":
        await msg.answer("Это ты сам 🙂", reply_markup=menu_button())
        await state.clear()
        return

    # попытка найти пользователя по username
    with get_session() as s:
        target_user = s.exec(
            select(User).where(User.username.ilike(uname.lstrip("@")))
        ).first()

    if target_user:
        target_chat_id = target_user.chat_id
    else:
        try:
            chat = await bot.get_chat(uname)
            target_chat_id = chat.id
        except Exception:
            await msg.answer(
                "Не удалось найти пользователя.\n"
                "Убедись, что друг запустил бота и username указан верно.",
                reply_markup=menu_button(),
            )
            await state.clear()
            return

    with get_session() as s:
        me = s.exec(select(User).where(User.chat_id == msg.from_user.id)).first()
        target = s.exec(select(User).where(User.chat_id == target_chat_id)).first()

        if not target:
            await msg.answer(
                "Этот пользователь ещё не запускал бота.", reply_markup=menu_button()
            )
            await state.clear()
            return

        # уже друзья?
        if s.exec(
            select(Friend).where(
                (Friend.user_id == me.id) & (Friend.friend_id == target.id)
            )
        ).first():
            await msg.answer("Вы уже друзья!", reply_markup=menu_button())
            await state.clear()
            return

        # ожидающий запрос?
        if s.exec(
            select(FriendRequest).where(
                or_(
                    (FriendRequest.from_id == me.id) & (FriendRequest.to_id == target.id),
                    (FriendRequest.from_id == target.id) & (FriendRequest.to_id == me.id),
                ),
                FriendRequest.status == "pending",
            )
        ).first():
            await msg.answer("Уже есть ожидающий запрос.", reply_markup=menu_button())
            await state.clear()
            return

        req = FriendRequest(from_id=me.id, to_id=target.id)
        s.add(req)
        s.commit()
        req_id = req.id

    await msg.answer("Запрос отправлен!", reply_markup=menu_button())
    await bot.send_message(
        target_chat_id,
        f"@{msg.from_user.username or msg.from_user.id} хочет добавить тебя в друзья.",
        reply_markup=confirm_kb(req_id),
    )
    await state.clear()


# ═══════════ подтверждение / отказ ═══════════
@router.callback_query(F.data.startswith("fr_ok_"))
async def req_accept(call: types.CallbackQuery):
    req_id = int(call.data.split("_")[2])

    with get_session() as s:
        req = s.get(FriendRequest, req_id)
        if not req or req.status != "pending":
            await call.answer("Запрос устарел.", show_alert=True)
            return

        req.status = "accepted"
        s.add_all(
            [
                Friend(user_id=req.from_id, friend_id=req.to_id),
                Friend(user_id=req.to_id, friend_id=req.from_id),
            ]
        )
        s.commit()
        from_user = s.get(User, req.from_id)

    await call.message.edit_text("🚀 Вас добавили в друзья!", reply_markup=menu_button())
    await call.bot.send_message(
        from_user.chat_id, "✅ Ваш запрос дружбы принят!", reply_markup=menu_button()
    )


@router.callback_query(F.data.startswith("fr_no_"))
async def req_decline(call: types.CallbackQuery):
    req_id = int(call.data.split("_")[2])

    with get_session() as s:
        req = s.get(FriendRequest, req_id)
        if req and req.status == "pending":
            req.status = "declined"
            s.add(req)
            s.commit()

    await call.message.edit_text("Запрос отклонён.", reply_markup=menu_button())

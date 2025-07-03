"""handlers/meal.py — добавление приёма пищи c подтверждением"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from openai import AsyncOpenAI, OpenAIError
from sqlmodel import select

from config import settings
from models_and_db import get_session, User, Meal
from handlers.menu import menu_button

router = Router()
MSK = ZoneInfo("Europe/Moscow")

# ------------- OpenAI -------------
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

GPT_SYSTEM = (
    "Ты нутрициолог. Пользователь описывает приём пищи. "
    "Верни JSON с полями food (строка) и calories (целое)."
)
KCAL_RE = re.compile(r"(\d{2,4})\s*к?кал", re.I)
DEFAULT_KCAL = 250


async def gpt_estimate_meal(text: str) -> dict | None:
    """Запрашивает GPT, возвращает dict {food, calories} либо None."""
    try:
        resp = await client.chat.completions.create(
            model=settings.GPT_MODEL,
            response_format={"type": "json_object"},
            temperature=0.3,
            messages=[
                {"role": "system", "content": GPT_SYSTEM},
                {"role": "user", "content": text},
            ],
        )
        return json.loads(resp.choices[0].message.content)
    except (OpenAIError, json.JSONDecodeError, KeyError):
        return None


# ------------- FSM -------------
class MealState(StatesGroup):
    enter_desc = State()
    confirm = State()


# ------------- клавиатуры -------------
def confirm_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Добавить", callback_data="meal_add")
    kb.button(text="↩️ Отменить", callback_data="meal_cancel")
    kb.button(text="🏠 Меню", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def after_add_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Добавить ещё блюдо", callback_data="meal_again")
    kb.button(text="🏠 Меню", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


# ------------- handlers -------------
@router.callback_query(F.data == "add_meal")
async def ask_desc(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(MealState.enter_desc)
    await call.message.edit_text(
        "Опиши приём пищи (пример: «Овсянка с бананом 300 г»)",
        reply_markup=menu_button(),
    )


@router.message(MealState.enter_desc)
async def process_desc(msg: types.Message, state: FSMContext):
    text = (msg.text or "").strip()
    if not text:
        await msg.answer("Описание пустое 🤔 Попробуй ещё раз.")
        return

    # GPT-оценка
    data = await gpt_estimate_meal(text) or {}
    calories = int(
        abs(
            data.get("calories")
            or (m := KCAL_RE.search(text)) and m.group(1)
            or DEFAULT_KCAL
        )
    )
    food = data.get("food") or text.split(",")[0][:64]

    # сохраняем во временное состояние
    await state.update_data(raw=text, food=food, calories=calories)

    await msg.answer(
        f"Добавить приём пищи:\n<b>{food}</b>\nКалории: <b>{calories} кКал</b> ?",
        reply_markup=confirm_kb(),
    )
    await state.set_state(MealState.confirm)


@router.callback_query(MealState.confirm, F.data == "meal_cancel")
async def cancel(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(MealState.enter_desc)
    await call.message.edit_text(
        "Хорошо, опиши приём пищи заново:",
        reply_markup=menu_button(),
    )


@router.callback_query(MealState.confirm, F.data == "meal_add")
async def add(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    raw, food, calories = data["raw"], data["food"], data["calories"]

    with get_session() as s:
        user = s.exec(select(User).where(User.chat_id == call.from_user.id)).first()
        s.add(
            Meal(
                user_id=user.id,
                created_at=datetime.utcnow(),  # ← было datetime.now(tz=MSK)
                raw_text=raw[:512],
                description=food[:128],
                calories=calories,
            )
        )
        s.commit()

    await call.message.edit_text(
        f"🍽️ Приём пищи добавлен!\n<i>{food}</i>: <b>{calories} кКал</b>",
        reply_markup=after_add_kb(),
    )
    await state.clear()


@router.callback_query(F.data == "meal_again")
async def again(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(MealState.enter_desc)
    await call.message.edit_text(
        "Опиши следующий приём пищи:",
        reply_markup=menu_button(),
    )

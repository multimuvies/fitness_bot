"""handlers/meal.py — добавление приёма пищи, GPT-оценка калорий"""

import asyncio
import json
import re
from datetime import datetime

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlmodel import select
from openai import OpenAI, OpenAIError

from config import settings
from models_and_db import get_session, User, Meal
from handlers.menu import menu_button

router = Router()
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# ────────────── FSM ──────────────
class MealState(StatesGroup):
    desc = State()


GPT_SYSTEM = (
    "Ты нутрициолог. Пользователь описывает приём пищи. "
    "Верни JSON c полями food (строка) и calories (int)."
)
KCAL_RE = re.compile(r"(\d{2,4})\s*к?кал")
DEFAULT_KCAL = 250


async def gpt_estimate(text: str) -> dict | None:
    loop = asyncio.get_running_loop()

    def _ask():
        return client.chat.completions.create(
            model=settings.GPT_MODEL,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": GPT_SYSTEM},
                {"role": "user", "content": text},
            ],
        )

    try:
        resp = await loop.run_in_executor(None, _ask)
        raw_json = resp.choices[0].message.content
        return json.loads(raw_json)
    except (OpenAIError, json.JSONDecodeError, KeyError):
        return None


# ────────────── handlers ──────────────
@router.callback_query(F.data == "add_meal")
async def ask_desc(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(MealState.desc)
    await call.message.edit_text(
        "Опиши приём пищи (пример: «Овсянка с бананом 300 г»)",
        reply_markup=menu_button(),
    )


@router.message(MealState.desc)
async def process_meal(msg: types.Message, state: FSMContext):
    text = (msg.text or "").strip()
    if not text:
        await msg.answer("Описание пустое 🤔 Попробуй ещё раз.")
        return

    with get_session() as s:
        user = s.exec(select(User).where(User.chat_id == msg.from_user.id)).first()
        if not user:
            await msg.answer("Сначала пройди регистрацию /start")
            return

    data = await gpt_estimate(text)
    food = (data or {}).get("food") or text[:64]
    calories = int(
        abs(
            (data or {}).get("calories")
            or (KCAL_RE.search(text) and KCAL_RE.search(text).group(1))
            or DEFAULT_KCAL
        )
    )

    with get_session() as s:
        s.add(
            Meal(
                user_id=user.id,
                created_at=datetime.utcnow(),
                raw_text=text[:512],
                description=food[:128],
                calories=calories,
            )
        )
        s.commit()

    await msg.answer(
        f"✅ Приём пищи добавлен!\n{food}: {calories} ккал",
        reply_markup=menu_button(),
    )
    await state.clear()

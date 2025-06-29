"""handlers/workout.py — добавление тренировки, GPT-оценка калорий"""

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
from models_and_db import get_session, User, Workout
from handlers.menu import menu_button

router = Router()
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# ────────────── FSM ──────────────
class WorkoutState(StatesGroup):
    desc = State()


# ────────────── GPT helpers ──────────────
GPT_SYSTEM = (
    "Ты спортивный эксперт. Пользователь описывает тренировку. "
    "Верни JSON c полями type (строка), duration_min (int), calories (int)."
)
DURATION_RE = re.compile(r"(\d+)\s*(?:мин|minutes?|м|минут)")
DEFAULT_MIN = 90
DEFAULT_KCAL = 250


async def gpt_estimate(text: str) -> dict | None:
    loop = asyncio.get_running_loop()

    def _ask():
        return client.chat.completions.create(
            model=settings.GPT_MODEL,
            temperature=0.2,
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
@router.callback_query(F.data == "add_workout")
async def ask_desc(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(WorkoutState.desc)
    await call.message.edit_text(
        "Введите описание тренировки (пример: «Бокс 90 мин»)",
        reply_markup=menu_button(),
    )


@router.message(WorkoutState.desc)
async def process_desc(msg: types.Message, state: FSMContext):
    desc = (msg.text or "").strip()
    if not desc:
        await msg.answer("Описание пустое 🤔 Попробуй ещё раз.")
        return

    with get_session() as s:
        user = s.exec(select(User).where(User.chat_id == msg.from_user.id)).first()
        if not user:
            await msg.answer("Сначала пройди регистрацию /start")
            return

    data = await gpt_estimate(desc)
    workout_type = (data or {}).get("type") or desc.split()[0].lower()
    duration = int(
        (data or {}).get("duration_min")
        or (DURATION_RE.search(desc) and DURATION_RE.search(desc).group(1))
        or DEFAULT_MIN
    )
    calories = int(abs((data or {}).get("calories") or DEFAULT_KCAL))

    with get_session() as s:
        s.add(
            Workout(
                user_id=user.id,
                created_at=datetime.utcnow(),
                raw_text=desc[:512],
                type=workout_type[:64],
                duration_min=duration,
                calories=-calories,  # отрицательное → расход
                method="gpt" if data else "fallback",
            )
        )
        s.commit()

    await msg.answer(
        f"✅ Тренировка добавлена!\n"
        f"Тип: {workout_type}\n"
        f"Длительность: {duration} мин\n"
        f"Расход: {calories} ккал",
        reply_markup=menu_button(),
    )
    await state.clear()

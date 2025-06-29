"""handlers/weight.py — добавление (или обновление) веса пользователя"""

from aiogram import Router, F, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from sqlmodel import select
from datetime import datetime
import re

from models_and_db import get_session, User, Weight
from handlers.menu import menu_button

router = Router()

WEIGHT_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)")  # ловим 72 или 72.4 или 72,4


# ────────────── FSM ──────────────
class WeightState(StatesGroup):
    waiting_weight = State()


@router.callback_query(F.data == "add_weight")
async def ask_weight(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(WeightState.waiting_weight)
    await call.message.edit_text(
        "Введи новый вес в килограммах (пример: 71.3)", reply_markup=menu_button()
    )


@router.message(WeightState.waiting_weight)
async def save_weight(msg: types.Message, state: FSMContext):
    text = msg.text or ""
    m = WEIGHT_PATTERN.search(text)
    if not m:
        await msg.answer("Не могу распознать вес 🤔 Попробуй, например, «71.4»")
        return

    weight_kg = float(m.group(1).replace(",", "."))
    weight_kg = round(weight_kg, 1)

    with get_session() as session:
        user = session.exec(select(User).where(User.chat_id == msg.from_user.id)).first()
        if not user:
            await msg.answer("Сначала пройди регистрацию /start")
            return

        # вычисляем BMI (простая формула) — может быть None, т.к. рост не меняем
        bmi = round(weight_kg / (user.height_cm / 100) ** 2, 1)

        session.add(
            Weight(
                user_id=user.id,
                weight_kg=weight_kg,
                bmi=bmi,
                created_at=datetime.utcnow(),
            )
        )

        # обновляем текущий вес пользователя
        user.weight_kg = weight_kg
        user.bmi = bmi
        session.add(user)

        session.commit()

    await msg.answer(
        f"✅ Вес обновлён: {weight_kg} кг (ИМТ {bmi})", reply_markup=menu_button()
    )
    await state.clear()

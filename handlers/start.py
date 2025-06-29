"""handlers/start.py — регистрация пользователя (анкета)"""

from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from datetime import datetime
from math import pow

from models_and_db import get_session, User, Weight
from config import settings

router = Router()

# ────────────────────────────── FSM ──────────────────────────────────────────
class Profile(StatesGroup):
    age = State()
    height = State()
    weight = State()
    gender = State()


# ──────────────────────────── helpers ───────────────────────────────────────

def bmi(weight: float, height_cm: int) -> float:
    return round(weight / pow(height_cm / 100, 2), 1)


def bmr_msj(age: int, weight: float, height_cm: int, gender: str) -> int:
    base = 10 * weight + 6.25 * height_cm - 5 * age
    return int(base + (5 if gender == "male" else -161))


def tdee(bmr: int) -> int:
    return int(bmr * settings.ACTIVITY_COEF)


def menu_button() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Меню", callback_data="menu")
    return kb.as_markup()


# ──────────────────────────── handlers ──────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("Привет! Давай создадим профиль. Сколько тебе лет?")
    await state.set_state(Profile.age)


@router.message(Profile.age, F.text.regexp(r"^\d{1,2}$"))
async def set_age(msg: types.Message, state: FSMContext):
    await state.update_data(age=int(msg.text))
    await msg.answer("Теперь рост (см):")
    await state.set_state(Profile.height)


@router.message(Profile.height, F.text.regexp(r"^\d{2,3}$"))
async def set_height(msg: types.Message, state: FSMContext):
    await state.update_data(height=int(msg.text))
    await msg.answer("Вес (кг):")
    await state.set_state(Profile.weight)


@router.message(Profile.weight, F.text.regexp(r"^\d{1,3}(?:[\.,]\d)?$"))
async def set_weight(msg: types.Message, state: FSMContext):
    weight = float(msg.text.replace(",", "."))
    await state.update_data(weight=weight)

    kb = InlineKeyboardBuilder()
    kb.button(text="Мужской", callback_data="gender_male")
    kb.button(text="Женский", callback_data="gender_female")
    kb.adjust(2)

    await msg.answer("Пол:", reply_markup=kb.as_markup())
    await state.set_state(Profile.gender)


@router.callback_query(Profile.gender, F.data.startswith("gender_"))
async def finish_profile(call: types.CallbackQuery, state: FSMContext):
    gender = call.data.split("_")[1]
    data = await state.get_data()

    age = data["age"]
    height = data["height"]
    weight = data["weight"]

    _bmi = bmi(weight, height)
    _bmr = bmr_msj(age, weight, height, gender)
    _tdee = tdee(_bmr)

    with get_session() as session:
        # если пользователь уже есть — удаляем, чтобы создать заново
        session.exec(User.__table__.delete().where(User.chat_id == call.from_user.id))
        user = User(
            chat_id=call.from_user.id,
            age=age,
            height_cm=height,
            weight_kg=weight,
            gender=gender,
            bmi=_bmi,
            bmr=_bmr,
            tdee=_tdee,
        )
        session.add(user)
        session.flush()
        # первая запись веса
        session.add(Weight(user_id=user.id, weight_kg=weight, created_at=datetime.utcnow()))
        session.commit()

    await call.message.edit_text(
        f"Профиль создан!\n"
        f"ИМТ: <b>{_bmi}</b>\n"
        f"BMR: <b>{_bmr}</b> ккал/день\n"
        f"TDEE (×1.25): <b>{_tdee}</b> ккал/день",
        reply_markup=menu_button(),
    )
    await state.clear()
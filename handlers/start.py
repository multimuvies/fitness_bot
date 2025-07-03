# handlers/start.py — регистрация (обновляем username при каждом /start)
from datetime import datetime
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlmodel import select

from models_and_db import get_session, User
from handlers.menu import menu_button

router = Router()


# ──────────────── FSM ────────────────
class Reg(StatesGroup):
    age = State()
    height = State()
    weight = State()
    gender = State()


# ──────────────── utils ────────────────
def calc_bmi(w_kg: float, h_cm: int) -> float:
    return round(w_kg / ((h_cm / 100) ** 2), 1)


def calc_tdee(weight: float, height: int, age: int, gender: str) -> int:
    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    return int(bmr * 1.25)  # коэффициент активности 1.25


# ──────────────── handlers ────────────────
@router.message(F.text == "/start")
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(Reg.age)
    await msg.answer("Привет! Введи возраст (полных лет):")


@router.message(Reg.age)
async def reg_age(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("Числом, пожалуйста 🙂")
        return
    await state.update_data(age=int(msg.text))
    await state.set_state(Reg.height)
    await msg.answer("Рост в сантиметрах:")


@router.message(Reg.height)
async def reg_h(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("Только число.")
        return
    await state.update_data(height=int(msg.text))
    await state.set_state(Reg.weight)
    await msg.answer("Текущий вес в кг:")


@router.message(Reg.weight)
async def reg_w(msg: types.Message, state: FSMContext):
    try:
        w = float(msg.text.replace(",", "."))
    except ValueError:
        await msg.answer("Только число 🙂")
        return
    await state.update_data(weight=w)
    await state.set_state(Reg.gender)
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Мужской"), types.KeyboardButton(text="Женский")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await msg.answer("Пол:", reply_markup=kb)


@router.message(Reg.gender, F.text.in_(["Мужской", "Женский"]))
async def reg_gender(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    age = data["age"]
    height = data["height"]
    weight = data["weight"]
    gender = "male" if msg.text == "Мужской" else "female"

    bmi = calc_bmi(weight, height)
    tdee = calc_tdee(weight, height, age, gender)

    with get_session() as s:
        user = s.exec(select(User).where(User.chat_id == msg.from_user.id)).first()
        if user:
            # обновляем
            user.age = age
            user.height_cm = height
            user.weight_kg = weight
            user.gender = gender
            user.bmi = bmi
            user.tdee = tdee
            user.username = msg.from_user.username  # ← сохраняем username
            s.add(user)
        else:
            s.add(
                User(
                    chat_id=msg.from_user.id,
                    username=msg.from_user.username,  # ← сохраняем username
                    age=age,
                    height_cm=height,
                    weight_kg=weight,
                    gender=gender,
                    bmi=bmi,
                    tdee=tdee,
                )
            )
        s.commit()

    await msg.answer(
        f"Регистрация завершена!\nИМТ: {bmi}\nTDEE: {tdee} ккал/день",
        reply_markup=menu_button(),
    )
    await state.clear()

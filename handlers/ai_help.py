"""handlers/ai_help.py — ИИ-консультант, работает с openai-python ≥1.0 без AsyncOpenAI"""

import asyncio
from aiogram import Router, F, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from sqlmodel import select
from openai import OpenAI, OpenAIError

from config import settings
from models_and_db import get_session, User
from handlers.menu import menu_button

router = Router()
# обычный (синхронный) клиент: не трогает httpx proxies → избегаем ошибки
client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ────────────── FSM ──────────────
class AskState(StatesGroup):
    question = State()


@router.callback_query(F.data == "ai_help")
async def ask_question(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(AskState.question)
    await call.message.edit_text(
        "Задай свой вопрос ИИ-тренеру.\n\n"
        "Примеры:\n"
        "• Сколько белка мне нужно?\n"
        "• Как тренировать пресс дома?",
        reply_markup=menu_button(),
    )


@router.message(AskState.question)
async def answer_question(msg: types.Message, state: FSMContext):
    question = msg.text or ""

    with get_session() as s:
        user = s.exec(select(User).where(User.chat_id == msg.from_user.id)).first()
        if not user:
            await msg.answer("Сначала пройди регистрацию /start")
            return

    system_prompt = (
        "Ты опытный фитнес-тренер и нутрициолог. Отвечай кратко и по делу.\n"
        f"Данные пользователя: возраст {user.age}, вес {user.weight_kg} кг, "
        f"рост {user.height_cm} см, пол {user.gender}. "
        f"Его TDEE ≈ {user.tdee} ккал."
    )

    # вызов синхронного клиента в отдельном потоке, чтобы не блокировать event-loop
    loop = asyncio.get_running_loop()

    def _ask():
        return client.chat.completions.create(
            model=settings.GPT_MODEL,
            temperature=0.7,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
        )

    try:
        resp = await loop.run_in_executor(None, _ask)
        answer = resp.choices[0].message.content.strip()
    except OpenAIError as e:
        answer = (
            "⚠️ Не удалось получить ответ от ИИ. Попробуй позже.\n\n"
            f"Техническая ошибка: {e}"
        )

    await msg.answer(answer, reply_markup=menu_button())
    await state.clear()

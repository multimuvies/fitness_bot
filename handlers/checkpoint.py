"""handlers/checkpoint.py — добавление чекпоинта (Московское время, без DetachedInstanceError)"""

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F, types
from sqlmodel import select

from models_and_db import get_session, User, Checkpoint
from handlers.menu import menu_button

router = Router()
MSK = ZoneInfo("Europe/Moscow")


@router.callback_query(F.data == "add_checkpoint")
async def add_checkpoint(call: types.CallbackQuery):
    """Создаёт чекпоинт с текущим МСК-временем и подтверждает пользователю."""
    with get_session() as s:
        user = s.exec(select(User).where(User.chat_id == call.from_user.id)).first()
        if not user:
            await call.message.answer("Сначала пройди регистрацию /start")
            return

        cp = Checkpoint(
            user_id=user.id,
            created_at=datetime.now(tz=MSK),  # aware-datetime в МСК
        )
        s.add(cp)
        s.commit()

        # Сохраняем время, пока объект привязан к сессии,
        # чтобы после выхода из контекста не словить DetachedInstanceError
        created_at_msk = cp.created_at

    await call.message.edit_text(
        f"✅ Добавлен чекпоинт:\n{created_at_msk:%d.%m.%Y %H:%M}",
        reply_markup=menu_button(),
    )

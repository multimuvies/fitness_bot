"""handlers/menu.py — глобальная точка возврата"""

from aiogram import Router, F, types
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

# ---------------------------------------------------------------------------
# Keyboard
# ---------------------------------------------------------------------------

def main_menu_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🏋️ Добавить тренировку", callback_data="add_workout")
    kb.button(text="🍽️ Добавить приём пищи", callback_data="add_meal")
    kb.button(text="⚖️ Добавить взвешивание", callback_data="add_weight")
    kb.button(text="📸 Добавить чекпоинт", callback_data="add_checkpoint")
    kb.button(text="🤖 ИИ-консультант", callback_data="ai_help")
    kb.button(text="📊 Аналитика", callback_data="analytics")
    kb.adjust(1)
    return kb.as_markup()


def menu_button() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Меню", callback_data="menu")
    return kb.as_markup()

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "menu")
async def menu_callback(call: types.CallbackQuery):
    await call.message.edit_text("Главное меню", reply_markup=main_menu_kb())

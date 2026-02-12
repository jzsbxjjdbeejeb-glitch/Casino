# keyboards.py
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Главное меню пользователя (вариант 1-2-3)
def create_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль")],  # Одна кнопка в строке
            [KeyboardButton(text="🎟️ Промокод"), KeyboardButton(text="🎮 Игры")],  # Две кнопки
            [KeyboardButton(text="ℹ️ О нас"), KeyboardButton(text="🆘 Поддержка"), KeyboardButton(text="📖 Как играть?")]  # Три кнопки
        ],
        resize_keyboard=True
    )

# Клавиатура профиля
def create_profile_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💎 Пополнить", callback_data="deposit"),
        InlineKeyboardButton(text="💰 Вывод", callback_data="withdraw")
    )
    return builder.as_markup()

# Клавиатура для промокода
def create_promo_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_promo")]
    ])

# Клавиатура для вывода
def create_withdraw_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_withdraw")]
    ])

# Админ клавиатура для вывода
def create_withdraw_admin_keyboard(request_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{request_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{request_id}")
        ]
    ])

# Главная админ клавиатура
def create_admin_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="💰 Балансы", callback_data="admin_manage_balance")
        ],
        [
            InlineKeyboardButton(text="🎫 Промокоды", callback_data="admin_promo_codes"),
            InlineKeyboardButton(text="👤 Просмотр профиля", callback_data="admin_view_profile")
        ]
    ])

# Админ клавиатура управления балансом
def create_admin_manage_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 Выдать", callback_data="admin_add_balance"),
            InlineKeyboardButton(text="📉 Забрать", callback_data="admin_subtract_balance")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_to_main")
        ]
    ])

# Админ клавиатура назад
def create_admin_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_to_main")]
    ])

# keyboards.py (обновляем функцию)

def create_admin_profile_actions_keyboard(user_id, is_banned=False):
    """
    Создает клавиатуру для действий с профилем
    is_banned: True если пользователь забанен
    """
    if is_banned:
        # Если забанен - показываем кнопку разбанить
        buttons = [
            [
                InlineKeyboardButton(text="💰 Изменить баланс", callback_data=f"admin_edit_balance_{user_id}"),
                InlineKeyboardButton(text="✅ Разбанить", callback_data=f"admin_unban_confirm_{user_id}")
            ],
            [
                InlineKeyboardButton(text="📋 История операций", callback_data=f"admin_user_history_{user_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад к админке", callback_data="admin_back_to_main")
            ]
        ]
    else:
        # Если не забанен - показываем кнопку забанить
        buttons = [
            [
                InlineKeyboardButton(text="💰 Изменить баланс", callback_data=f"admin_edit_balance_{user_id}"),
                InlineKeyboardButton(text="🔨 Забанить", callback_data=f"admin_ban_confirm_{user_id}")
            ],
            [
                InlineKeyboardButton(text="📋 История операций", callback_data=f"admin_user_history_{user_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад к админке", callback_data="admin_back_to_main")
            ]
        ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Добавляем клавиатуру для подтверждения бана
def create_ban_confirmation_keyboard(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, забанить", callback_data=f"admin_ban_execute_{user_id}"),
            InlineKeyboardButton(text="❌ Нет, отмена", callback_data=f"admin_ban_cancel_{user_id}")
        ]
    ])

# Добавляем клавиатуру для подтверждения разбана
def create_unban_confirmation_keyboard(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, разбанить", callback_data=f"admin_unban_execute_{user_id}"),
            InlineKeyboardButton(text="❌ Нет, отмена", callback_data=f"admin_unban_cancel_{user_id}")
        ]
    ])
# admin.py
# admin.py
import json
import os
import logging
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import *
from keyboards import *

logger = logging.getLogger(__name__)

# ========== КОНФИГУРАЦИЯ ==========
ADMIN_ID = 639219316  # Здесь установите ваш Telegram ID
PROMO_FILE = "promo.json"

# ========== ПРОВЕРКА АДМИНА ==========
def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id == ADMIN_ID

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def load_promo_codes():
    """Загружает промокоды из файла"""
    if os.path.exists(PROMO_FILE):
        try:
            with open(PROMO_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_promo_codes(promo_codes):
    """Сохраняет промокоды в файл"""
    with open(PROMO_FILE, 'w', encoding='utf-8') as f:
        json.dump(promo_codes, f, ensure_ascii=False, indent=2)

PROMO_CODES = load_promo_codes()

class AdminStates(StatesGroup):
    waiting_for_user_identifier = State()
    waiting_for_balance_amount = State()
    waiting_for_view_profile = State()
    waiting_for_promo_create = State()

# ========== ОБРАБОТЧИКИ АДМИН ПАНЕЛИ ==========

async def handle_admin_stats(callback: CallbackQuery, bot: Bot):
    """Показывает статистику бота"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        date_threshold = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('SELECT COUNT(*) FROM users WHERE last_active >= ?', (date_threshold,))
        active_users = cursor.fetchone()[0]
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(registered_at) = ?', (today,))
        today_reg = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(stars_balance) FROM users')
        total_balance = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT SUM(total_games) FROM users')
        total_games = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT SUM(total_deposit) FROM users')
        total_deposit = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT SUM(total_withdraw) FROM users')
        total_withdraw = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM withdraw_requests WHERE status = "pending"')
        pending_withdraws = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(amount) FROM withdraw_requests WHERE status = "pending"')
        pending_amount = cursor.fetchone()[0] or 0
        
        total_lost = get_total_lost()
        
        conn.close()
        
        stats_text = f"""<b>📊 СТАТИСТИКА БОТА</b>

<blockquote>👥 <b>Пользователи:</b>
├ Всего пользователей: {total_users}
├ Активных (7 дней): {active_users}
└ Сегодня зарегистрировано: {today_reg}

💰 <b>Балансы:</b>
├ Общий баланс: {total_balance} ⭐
└ <b>Проиграно:</b> {total_lost} ⭐

🎮 <b>Игры:</b>
└ Всего сыграно игр: {total_games}

💸 <b>Финансы:</b>
├ Всего пополнено: {total_deposit} ⭐
├ Всего выведено: {total_withdraw} ⭐
└ Ожидает вывода: {pending_withdraws} заявок ({pending_amount} ⭐)

📅 <b>Дата:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}</blockquote>"""
        
        await callback.message.edit_text(stats_text, reply_markup=create_admin_back_keyboard())
        
    except Exception as e:
        logger.error(f"Ошибка при показе статистики: {e}")
        await callback.message.edit_text(f"❌ Ошибка при получении статистики: {str(e)}", 
                                       reply_markup=create_admin_back_keyboard())
    
    await callback.answer()

async def handle_admin_manage_balance(callback: CallbackQuery):
    """Управление балансом пользователей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    manage_text = """<b>💸 Выдать/забрать</b>

Выберите действие:
• <b>💎 Выдать</b> - добавить средства пользователю
• <b>📉 Забрать</b> - забрать средства у пользователя"""
    
    await callback.message.edit_text(manage_text, reply_markup=create_admin_manage_keyboard())
    await callback.answer()

async def handle_admin_promo_codes(callback: CallbackQuery):
    """Управление промокодами"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    if not PROMO_CODES:
        promo_text = """<b>🎫 Промокоды • Админ панель</b>

Используйте команду:
<code>+НАЗВАНИЕ НАГРАДА АКТИВАЦИИ</code>"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_to_main")]
        ])
    else:
        promo_list = []
        for i, (code, info) in enumerate(PROMO_CODES.items(), 1):
            used = info.get('used', 0)
            max_uses = info.get('max_uses', 0)
            reward = info.get('reward', 0)
            active = info.get('active', True)
            status = "✅ Активен" if active else "❌ Неактивен"
            
            promo_list.append(f"<b>{i}. {code}</b>")
            promo_list.append(f"   ├ Награда: {reward} ⭐")
            promo_list.append(f"   ├ Использовано: {used}/{max_uses if max_uses != float('inf') else '∞'}")
            promo_list.append(f"   └ Статус: {status}")
        
        promo_text = f"""<b>🎫 Промокоды • Админ панель</b>

<b>ℹ️ Информация:</b>
Всего промокодов: {len(PROMO_CODES)}

<b>➕ Создать новый промокод:</b>
<code>+НАЗВАНИЕ НАГРАДА АКТИВАЦИИ</code>"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back_to_main")]
        ])
    
    await callback.message.edit_text(promo_text, reply_markup=keyboard)
    await callback.answer()

async def handle_admin_add_balance(callback: CallbackQuery, state: FSMContext):
    """Добавить баланс пользователю"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_user_identifier)
    await state.update_data(operation_type="add")
    
    text = """<b>💰 Выдать • Админ панель</b>

<code>Напишите user_id или username пользователя:</code>

Примеры:
• <code>123456789</code> (user_id)
• <code>username</code> или <code>@username</code>

Для отмены используйте команду /cancel"""
    
    await callback.message.edit_text(text)
    await callback.answer()

async def handle_admin_subtract_balance(callback: CallbackQuery, state: FSMContext):
    """Забрать баланс у пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_user_identifier)
    await state.update_data(operation_type="subtract")
    
    text = """<b>📉 Забрать • Админ панель</b>

<code>Напишите user_id или username пользователя:</code>

Примеры:
• <code>123456789</code> (user_id)
• <code>username</code> или <code>@username</code>

Для отмены используйте команду /cancel"""
    
    await callback.message.edit_text(text)
    await callback.answer()

async def process_user_identifier(message: Message, state: FSMContext):
    """Обрабатывает идентификатор пользователя"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return
    
    identifier = message.text.strip()
    data = await state.get_data()
    operation_type = data.get('operation_type', 'add')
    
    user_data = get_user_by_id_or_username(identifier)
    
    if not user_data:
        await message.answer("❌ <b>Пользователь не найден!</b>\n\nПопробуйте снова или отмените командой /cancel")
        return
    
    await state.update_data(
        target_user_id=user_data['user_id'],
        target_username=user_data['username'],
        target_first_name=user_data['first_name'],
        target_balance=user_data['stars_balance']
    )
    
    await state.set_state(AdminStates.waiting_for_balance_amount)
    
    operation_word = "выдать" if operation_type == "add" else "забрать"
    op_emoji = "💎" if operation_type == "add" else "📉"
    
    text = f"""<b>{op_emoji} {operation_word.capitalize()} • Админ панель</b>

<b>👤 Пользователь:</b> {user_data['first_name']}
<b>🆔 ID:</b> <code>{user_data['user_id']}</code>
<b>💰 Текущий баланс:</b> {user_data['stars_balance']} ⭐

<code>✏️ Введите сумму для {operation_word}:</code>

Для отмены используйте команду /cancel"""
    
    await message.answer(text)

async def process_balance_amount(message: Message, state: FSMContext):
    """Обрабатывает сумму изменения баланса"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return
    
    try:
        amount = int(message.text)
        
        if amount <= 0:
            await message.answer("❌ <b>Сумма должна быть положительным числом!</b>")
            return
        
        data = await state.get_data()
        operation_type = data.get('operation_type', 'add')
        target_user_id = data['target_user_id']
        target_username = data['target_username']
        target_first_name = data['target_first_name']
        old_balance = data['target_balance']
        
        if operation_type == "subtract" and amount > old_balance:
            await message.answer(f"❌ <b>У пользователя недостаточно средств!</b>\n\nТекущий баланс: {old_balance} ⭐\nЗапрошенная сумма: {amount} ⭐")
            return
        
        new_balance = update_user_balance_by_admin(target_user_id, amount, operation_type)
        
        operation_word = "выдать" if operation_type == "add" else "забрать"
        operation_word_past = "выдано" if operation_type == "add" else "забрано"
        operation_emoji = "💎" if operation_type == "add" else "📉"
        sign = "+" if operation_type == "add" else "-"
        
        display_username = f"@{target_username}" if target_username else target_first_name
        
        current_time = datetime.now().strftime('%d.%m.%Y %H:%M')
        
        result_text = f"""<b>{operation_emoji} {operation_word_past.capitalize()} • {display_username}</b>

<b>👤 Пользователь:</b> {display_username}
<b>🆔 ID:</b> <code>{target_user_id}</code>
<b>{operation_word_past.capitalize()}:</b> {sign}{amount} ⭐
<b>💰 Баланс до:</b> {old_balance} ⭐
<b>💰 Баланс после:</b> {new_balance} ⭐
<b>📅 Дата и время:</b> {current_time}

<b>✅ Операция успешно выполнена!</b>"""
        
        await message.answer(result_text, reply_markup=create_admin_main_keyboard())
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ <b>Пожалуйста, введите число!</b>\n\nПример: <code>100</code>")
    except Exception as e:
        logger.error(f"Ошибка при управлении балансом: {e}")
        await message.answer("❌ <b>Произошла ошибка. Попробуйте позже.</b>")
        await state.clear()

async def handle_admin_back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню админ-панели"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    await state.clear()
    
    admin_text = """<b>👑 АДМИН-ПАНЕЛЬ</b>

<b>Выберите действие:</b>
• 📊 Статистика - общая статистика бота
• 💰 Выдать/забрать - управление балансами пользователей
• 🎫 Промокоды - управление промокодами
• 👤 Просмотр профиля - просмотр профиля любого пользователя"""
    
    await callback.message.edit_text(admin_text, reply_markup=create_admin_main_keyboard())
    await callback.answer()

# ========== ОБРАБОТЧИК СОЗДАНИЯ ПРОМОКОДОВ ==========

async def create_promo_code(message: Message):
    """Создание промокода"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        parts = message.text[1:].strip().split()
        
        if len(parts) < 3:
            await message.answer("❌ <b>Неправильный формат!</b>\n\n<code>+НАЗВАНИЕ НАГРАДА АКТИВАЦИИ</code>")
            return
        
        code = parts[0].upper()
        reward = int(parts[1])
        max_uses = int(parts[2])
        
        if code in PROMO_CODES:
            await message.answer(f"❌ <b>Промокод {code} уже существует!</b>")
            return
        
        PROMO_CODES[code] = {
            "reward": reward,
            "max_uses": max_uses,
            "used": 0,
            "active": True,
            "description": f"Промокод {code}",
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        save_promo_codes(PROMO_CODES)
        
        success_text = f"""<b>✅ Промокод создан!</b>

<b>🎫 Код:</b> {code}
<b>🎁 Награда:</b> {reward} ⭐
<b>🔢 Активаций:</b> {max_uses}
<b>📊 Статус:</b> Активен

<b>ℹ️ Промокод добавлен в систему и готов к использованию!</b>"""
        
        await message.answer(success_text)
        
    except ValueError:
        await message.answer("❌ <b>Награда и количество активаций должны быть числами!</b>")
    except Exception as e:
        logger.error(f"Ошибка при создании промокода: {e}")
        await message.answer("❌ <b>Произошла ошибка при создании промокода</b>")

# ========== ОБРАБОТЧИКИ ВЫВОДА (АДМИН) ==========

async def approve_withdraw(callback: CallbackQuery, bot: Bot):
    """Одобрить вывод"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    request_id = int(callback.data.split("_")[1])
    request_data = get_withdraw_request(request_id)
    
    if not request_data:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    if request_data['status'] != 'pending':
        await callback.answer(f"❌ Заявка уже обработана ({request_data['status']})", show_alert=True)
        return
    
    update_withdraw_request(request_id, 'approved', callback.from_user.id)
    update_user_withdraw(request_data['user_id'], request_data['amount'])
    
    user_text = f"""<b>✅ Ваша заявка на вывод одобрена!</b>

<b>💰 Сумма:</b> {request_data['amount']} ⭐
<b>📋 Номер заявки:</b> #{request_id}

<b>⏳ Средства будут зачислены в течение 24 часов</b>

Спасибо, что пользуетесь нашим сервисом! ❤️"""
    
    try:
        await bot.send_message(request_data['user_id'], user_text)
    except:
        pass
    
    username = f"@{request_data['username']}" if request_data['username'] else request_data['first_name']
    current_time = datetime.now().strftime('%d.%m.%Y %H:%M')
    
    admin_text = f"""<b>✅ Вывод одобрен • {username}</b>

<b>👤 Пользователь:</b> {username}
<b>🆔 ID:</b> <code>{request_data['user_id']}</code>
<b>💰 Сумма:</b> {request_data['amount']} ⭐
<b>📅 Дата одобрения:</b> {current_time}
<b>📋 Номер заявки:</b> #{request_id}

<b>👮‍♂️ Одобрил:</b> @{callback.from_user.username if callback.from_user.username else 'админ'}"""

    await callback.message.edit_text(admin_text)
    await callback.answer("✅ Заявка одобрена")

async def reject_withdraw(callback: CallbackQuery, bot: Bot):
    """Отклонить вывод"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    request_id = int(callback.data.split("_")[1])
    request_data = get_withdraw_request(request_id)
    
    if not request_data:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    if request_data['status'] != 'pending':
        await callback.answer(f"❌ Заявка уже обработана ({request_data['status']})", show_alert=True)
        return
    
    update_withdraw_request(request_id, 'rejected', callback.from_user.id)
    
    user_text = f"""<b>❌ Ваша заявка на вывод отклонена</b>

<b>💰 Сумма:</b> {request_data['amount']} ⭐
<b>📋 Номер заявки:</b> #{request_id}

<b>⚠️ Внимание:</b> Средства не возвращаются на баланс при отказе в выводе.

Если у вас есть вопросы, обратитесь в поддержку."""
    
    try:
        await bot.send_message(request_data['user_id'], user_text)
    except:
        pass
    
    username = f"@{request_data['username']}" if request_data['username'] else request_data['first_name']
    current_time = datetime.now().strftime('%d.%m.%Y %H:%M')
    
    admin_text = f"""<b>❌ Вывод отклонен • {username}</b>

<b>👤 Пользователь:</b> {username}
<b>🆔 ID:</b> <code>{request_data['user_id']}</code>
<b>💰 Сумма:</b> {request_data['amount']} ⭐
<b>📅 Дата отклонения:</b> {current_time}
<b>📋 Номер заявки:</b> #{request_id}

<b>💸 Средства не возвращены на баланс пользователя</b>
<b>👮‍♂️ Отклонил:</b> @{callback.from_user.username if callback.from_user.username else 'админ'}"""

    await callback.message.edit_text(admin_text)
    await callback.answer("❌ Заявка отклонена. Средства не возвращены.")

# ========== ОБРАБОТЧИК ПРОСМОТРА ПРОФИЛЯ ==========

async def handle_admin_view_profile(callback: CallbackQuery, state: FSMContext):
    """Просмотр профиля пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_view_profile)
    
    view_text = """<b>👤 Просмотр профиля пользователя</b>

<code>Напишите user_id или username пользователя:</code>

<blockquote>Примеры:
• <code>123456789</code> (user_id)
• <code>username</code> или <code>@username</code>
• <code>Имя Фамилия</code> (частичное совпадение)</blockquote>

<b>ℹ️ Бот найдет пользователя по:</b>
• Точному ID
• Username (с @ или без)
• Части имени

Для отмены используйте команду /cancel"""
    
    await callback.message.edit_text(view_text)
    await callback.answer()

async def process_view_profile_identifier(message: Message, state: FSMContext):
    """Обрабатывает идентификатор для просмотра профиля"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        await state.clear()
        return
    
    identifier = message.text.strip()
    
    user_data = get_user_by_id_or_username(identifier)
    
    if not user_data:
        user_data = search_user_by_name(identifier)
        if not user_data:
            await message.answer("❌ <b>Пользователь не найден!</b>\n\nПопробуйте другой ID или username.")
            await state.clear()
            return
    
    banned = is_user_banned(user_data['user_id'])
    ban_info = None
    if banned:
        ban_info = get_ban_info(user_data['user_id'])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT COUNT(*) FROM withdraw_requests 
    WHERE user_id = ? AND status = 'approved'
    ''', (user_data['user_id'],))
    successful_withdraws = cursor.fetchone()[0] or 0
    
    cursor.execute('''
    SELECT SUM(amount) FROM withdraw_requests 
    WHERE user_id = ? AND status = 'approved'
    ''', (user_data['user_id'],))
    total_withdrawn = cursor.fetchone()[0] or 0
    
    conn.close()
    
    try:
        reg_date = datetime.strptime(user_data['registered_at'], '%Y-%m-%d %H:%M:%S')
        formatted_reg_date = reg_date.strftime('%d.%m.%Y %H:%M')
    except:
        formatted_reg_date = "Неизвестно"
    
    try:
        last_active = datetime.strptime(user_data['last_active'], '%Y-%m-%d %H:%M:%S')
        last_active_str = last_active.strftime('%d.%m.%Y %H:%M')
        
        time_diff = datetime.now() - last_active
        if time_diff.days > 0:
            last_active_diff = f"{time_diff.days} дн. назад"
        elif time_diff.seconds // 3600 > 0:
            last_active_diff = f"{time_diff.seconds // 3600} час. назад"
        elif time_diff.seconds // 60 > 0:
            last_active_diff = f"{time_diff.seconds // 60} мин. назад"
        else:
            last_active_diff = "только что"
    except:
        last_active_str = "Неизвестно"
        last_active_diff = "Неизвестно"
    
    total_deposit = user_data['total_deposit'] or 0
    total_withdraw = user_data['total_withdraw'] or 0
    net_profit = total_deposit - total_withdraw
    net_profit_str = f"{'+' if net_profit >= 0 else ''}{net_profit}"
    
    avg_bet = "Н/Д"
    if user_data['total_games'] > 0 and total_deposit > 0:
        avg_bet = f"~{int(total_deposit / max(1, user_data['total_games']))} ⭐"
    
    username_display = f"@{user_data['username']}" if user_data['username'] else "Нет username"
    
    ban_status_text = ""
    if banned and ban_info:
        try:
            ban_date = datetime.strptime(ban_info['banned_at'], '%Y-%m-%d %H:%M:%S')
            formatted_ban_date = ban_date.strftime('%d.%m.%Y %H:%M')
        except:
            formatted_ban_date = "Неизвестно"
        
        ban_status_text = f"""
<b>🚫 Статус:</b> ЗАБАНЕН
<b>📅 Дата бана:</b> {formatted_ban_date}
<b>📝 Причина:</b> {ban_info['reason']}
"""
    else:
        ban_status_text = "<b>✅ Статус:</b> АКТИВЕН"
    
    profile_text = f"""<b>👤 ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ</b>
<blockquote><b>📋 Основная информация:</b>
├ Имя: {user_data['first_name']}
├ ID: <code>{user_data['user_id']}</code>
└ Username: {username_display}

{ban_status_text}

<b>💰 Финансовая информация:</b>
├ Текущий баланс: {user_data['stars_balance']} ⭐
├ Всего пополнено: {total_deposit} ⭐
├ Всего выведено: {total_withdraw} ⭐
├ Успешных выводов: {successful_withdraws}
├ Всего выведено: {total_withdrawn} ⭐
└ Чистая прибыль: {net_profit_str} ⭐

<b>🎮 Игровая статистика:</b>
├ Всего игр: {user_data['total_games']}
└ Средняя ставка: {avg_bet}

<b>📅 Активность:</b>
├ Зарегистрирован: {formatted_reg_date}
├ Последняя активность: {last_active_str}
└ ({last_active_diff})</blockquote>

<b>🆔 User ID:</b> <code>{user_data['user_id']}</code>"""

    keyboard = create_admin_profile_actions_keyboard(user_data['user_id'], banned)
    
    await message.answer(profile_text, reply_markup=keyboard)
    await state.clear()

async def handle_admin_edit_balance_from_profile(callback: CallbackQuery, state: FSMContext):
    """Редактирование баланса из профиля"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    target_user_id = int(callback.data.split("_")[3])
    
    user_data = get_user_by_id_or_username(str(target_user_id))
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    await state.update_data(
        target_user_id=target_user_id,
        target_username=user_data['username'],
        target_first_name=user_data['first_name'],
        target_balance=user_data['stars_balance']
    )
    
    await state.set_state(AdminStates.waiting_for_balance_amount)
    
    text = f"""<b>💰 Изменение баланса</b>

<b>👤 Пользователь:</b> {user_data['first_name']}
<b>🆔 ID:</b> <code>{target_user_id}</code>
<b>💰 Текущий баланс:</b> {user_data['stars_balance']} ⭐

<code>✏️ Введите сумму для изменения:</code>

<b>Формат:</b>
• <code>+100</code> - добавить 100 ⭐
• <code>-50</code> - убрать 50 ⭐
• <code>100</code> - установить баланс 100 ⭐

Для отмены используйте команду /cancel"""
    
    await callback.message.answer(text)
    await callback.answer()

async def handle_admin_user_history(callback: CallbackQuery):
    """Просмотр истории операций пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    target_user_id = int(callback.data.split("_")[3])
    
    user_data = get_user_by_id_or_username(str(target_user_id))
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT amount, status, created_at 
    FROM withdraw_requests 
    WHERE user_id = ? 
    ORDER BY id DESC 
    LIMIT 10
    ''', (target_user_id,))
    withdraws = cursor.fetchall()
    
    conn.close()
    
    username_display = f"@{user_data['username']}" if user_data['username'] else user_data['first_name']
    
    if not withdraws:
        history_text = f"""<b>📋 История операций • {username_display}</b>

<blockquote>📭 У пользователя нет операций вывода</blockquote>"""
    else:
        history_text = f"""<b>📋 История операций • {username_display}</b>

<blockquote><b>🆔 ID пользователя:</b> <code>{target_user_id}</code>
<b>👤 Имя:</b> {user_data['first_name']}</blockquote>

<b>📊 Статистика операций:</b>
├ Всего пополнено: {user_data['total_deposit']} ⭐
├ Всего выведено: {user_data['total_withdraw']} ⭐
└ Текущий баланс: {user_data['stars_balance']} ⭐

<b>📋 Последние 10 операций вывода:</b>"""

        for i, (amount, status, created_at) in enumerate(withdraws, 1):
            try:
                w_date = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                formatted_w_date = w_date.strftime('%d.%m.%Y %H:%M')
            except:
                formatted_w_date = created_at
            
            status_emoji = "✅" if status == 'approved' else "⏳" if status == 'pending' else "❌"
            status_text = "Одобрено" if status == 'approved' else "Ожидание" if status == 'pending' else "Отклонено"
            
            history_text += f"\n{i}. {amount}⭐ - {status_emoji} {status_text} ({formatted_w_date})"
    
    banned = is_user_banned(target_user_id)
    keyboard = create_admin_profile_actions_keyboard(target_user_id, banned)
    
    await callback.message.answer(history_text, reply_markup=keyboard)
    await callback.answer()

async def handle_admin_back_to_profile(callback: CallbackQuery):
    """Возврат к профилю пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    target_user_id = int(callback.data.split("_")[4])
    
    user_data = get_user_by_id_or_username(str(target_user_id))
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    banned = is_user_banned(target_user_id)
    ban_info = None
    if banned:
        ban_info = get_ban_info(target_user_id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT COUNT(*) FROM withdraw_requests 
    WHERE user_id = ? AND status = 'approved'
    ''', (target_user_id,))
    successful_withdraws = cursor.fetchone()[0] or 0
    
    cursor.execute('''
    SELECT SUM(amount) FROM withdraw_requests 
    WHERE user_id = ? AND status = 'approved'
    ''', (target_user_id,))
    total_withdrawn = cursor.fetchone()[0] or 0
    
    conn.close()
    
    try:
        reg_date = datetime.strptime(user_data['registered_at'], '%Y-%m-%d %H:%M:%S')
        formatted_reg_date = reg_date.strftime('%d.%m.%Y %H:%M')
    except:
        formatted_reg_date = "Неизвестно"
    
    try:
        last_active = datetime.strptime(user_data['last_active'], '%Y-%m-%d %H:%M:%S')
        last_active_str = last_active.strftime('%d.%m.%Y %H:%M')
        time_diff = datetime.now() - last_active
        if time_diff.days > 0:
            last_active_diff = f"{time_diff.days} дн. назад"
        elif time_diff.seconds // 3600 > 0:
            last_active_diff = f"{time_diff.seconds // 3600} час. назад"
        elif time_diff.seconds // 60 > 0:
            last_active_diff = f"{time_diff.seconds // 60} мин. назад"
        else:
            last_active_diff = "только что"
    except:
        last_active_str = "Неизвестно"
        last_active_diff = "Неизвестно"
    
    total_deposit = user_data['total_deposit'] or 0
    total_withdraw = user_data['total_withdraw'] or 0
    net_profit = total_deposit - total_withdraw
    net_profit_str = f"{'+' if net_profit >= 0 else ''}{net_profit}"
    
    avg_bet = "Н/Д"
    if user_data['total_games'] > 0 and total_deposit > 0:
        avg_bet = f"~{int(total_deposit / max(1, user_data['total_games']))} ⭐"
    
    username_display = f"@{user_data['username']}" if user_data['username'] else "Нет username"
    
    ban_status_text = ""
    if banned and ban_info:
        try:
            ban_date = datetime.strptime(ban_info['banned_at'], '%Y-%m-%d %H:%M:%S')
            formatted_ban_date = ban_date.strftime('%d.%m.%Y %H:%M')
        except:
            formatted_ban_date = "Неизвестно"
        
        ban_status_text = f"""
<b>🚫 Статус:</b> ЗАБАНЕН
<b>📅 Дата бана:</b> {formatted_ban_date}
<b>📝 Причина:</b> {ban_info['reason']}
"""
    else:
        ban_status_text = "<b>✅ Статус:</b> АКТИВЕН"
    
    profile_text = f"""<b>👤 ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ</b>
<blockquote><b>📋 Основная информация:</b>
├ Имя: {user_data['first_name']}
├ ID: <code>{target_user_id}</code>
└ Username: {username_display}

{ban_status_text}

<b>💰 Финансовая информация:</b>
├ Текущий баланс: {user_data['stars_balance']} ⭐
├ Всего пополнено: {total_deposit} ⭐
├ Всего выведено: {total_withdraw} ⭐
├ Успешных выводов: {successful_withdraws}
├ Всего выведено: {total_withdrawn} ⭐
└ Чистая прибыль: {net_profit_str} ⭐

<b>🎮 Игровая статистика:</b>
├ Всего игр: {user_data['total_games']}
└ Средняя ставка: {avg_bet}

<b>📅 Активность:</b>
├ Зарегистрирован: {formatted_reg_date}
├ Последняя активность: {last_active_str}
└ ({last_active_diff})</blockquote>

<b>🆔 User ID:</b> <code>{target_user_id}</code>"""

    keyboard = create_admin_profile_actions_keyboard(target_user_id, banned)
    
    await callback.message.edit_text(profile_text, reply_markup=keyboard)
    await callback.answer()

async def handle_admin_ban_confirm(callback: CallbackQuery):
    """Подтверждение бана пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    target_user_id = int(callback.data.split("_")[3])
    
    user_data = get_user_by_id_or_username(str(target_user_id))
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    if is_user_banned(target_user_id):
        await callback.answer("❌ Пользователь уже забанен", show_alert=True)
        return
    
    username_display = f"@{user_data['username']}" if user_data['username'] else user_data['first_name']
    
    confirm_text = f"""<b>🔨 Подтверждение бана</b>

<b>👤 Пользователь:</b> {username_display}
<b>🆔 ID:</b> <code>{target_user_id}</code>
<b>💰 Баланс:</b> {user_data['stars_balance']} ⭐

<b>⚠️ Вы уверены, что хотите забанить этого пользователя?</b>

<b>📝 Причина:</b> Нарушение правил бота

<b>После бана:</b>
• Пользователь получит уведомление
• Он не сможет использовать бота
• Его баланс будет заморожен"""
    
    await callback.message.edit_text(confirm_text, reply_markup=create_ban_confirmation_keyboard(target_user_id))
    await callback.answer()

async def handle_admin_ban_execute(callback: CallbackQuery, bot: Bot):
    """Выполнение бана пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    target_user_id = int(callback.data.split("_")[3])
    
    user_data = get_user_by_id_or_username(str(target_user_id))
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    ban_user(
        user_id=target_user_id,
        username=user_data['username'],
        first_name=user_data['first_name'],
        reason="Нарушение правил бота",
        admin_id=callback.from_user.id
    )
    
    username_display = f"@{user_data['username']}" if user_data['username'] else user_data['first_name']
    current_time = datetime.now().strftime('%d.%m.%Y %H:%M')
    admin_username = f"@{callback.from_user.username}" if callback.from_user.username else "админ"
    
    user_ban_text = f"""<b>🚫 ВЫ ЗАБАНЕНЫ!</b>

<b>📝 Причина:</b> Нарушение правил бота
<b>📅 Дата бана:</b> {current_time}
<b>👮‍♂️ Забанил:</b> {admin_username}

<b>⚠️ Ваш аккаунт заблокирован!</b>
• Вы не можете использовать бота
• Все ваши средства заморожены
• Для разъяснений обратитесь в поддержку

<b>📞 Поддержка:</b> @TPBezdarCasino"""
    
    try:
        await bot.send_message(target_user_id, user_ban_text)
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение о бане пользователю {target_user_id}: {e}")
    
    admin_text = f"""<b>✅ Пользователь забанен</b>

<b>👤 Пользователь:</b> {username_display}
<b>🆔 ID:</b> <code>{target_user_id}</code>
<b>📅 Дата:</b> {current_time}
<b>📝 Причина:</b> Нарушение правил бота
<b>👮‍♂️ Забанил:</b> {admin_username}

<b>✅ Пользователь уведомлен о бане.</b>"""
    
    keyboard = create_admin_profile_actions_keyboard(target_user_id, is_banned=True)
    
    await callback.message.edit_text(admin_text, reply_markup=keyboard)
    await callback.answer("✅ Пользователь забанен")

async def handle_admin_ban_cancel(callback: CallbackQuery):
    """Отмена бана пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    target_user_id = int(callback.data.split("_")[3])
    
    user_data = get_user_by_id_or_username(str(target_user_id))
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    username_display = f"@{user_data['username']}" if user_data['username'] else user_data['first_name']
    
    banned = is_user_banned(target_user_id)
    keyboard = create_admin_profile_actions_keyboard(target_user_id, banned)
    
    profile_text = f"""<b>✅ Бан отменен</b>

Вернулись к просмотру профиля пользователя.

<b>👤 Пользователь:</b> {username_display}
<b>🆔 ID:</b> <code>{target_user_id}</code>"""
    
    await callback.message.edit_text(profile_text, reply_markup=keyboard)
    await callback.answer("❌ Бан отменен")

async def handle_admin_unban_confirm(callback: CallbackQuery):
    """Подтверждение разбана пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    target_user_id = int(callback.data.split("_")[3])
    
    user_data = get_user_by_id_or_username(str(target_user_id))
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    ban_info = get_ban_info(target_user_id)
    
    if not ban_info:
        await callback.answer("❌ Пользователь не забанен", show_alert=True)
        return
    
    username_display = f"@{user_data['username']}" if user_data['username'] else user_data['first_name']
    
    try:
        ban_date = datetime.strptime(ban_info['banned_at'], '%Y-%m-%d %H:%M:%S')
        formatted_ban_date = ban_date.strftime('%d.%m.%Y %H:%M')
    except:
        formatted_ban_date = "Неизвестно"
    
    confirm_text = f"""<b>✅ Подтверждение разбана</b>

<b>👤 Пользователь:</b> {username_display}
<b>🆔 ID:</b> <code>{target_user_id}</code>
<b>📅 Забанен:</b> {formatted_ban_date}
<b>📝 Причина бана:</b> {ban_info['reason']}

<b>⚠️ Вы уверены, что хотите разбанить этого пользователя?</b>

<b>После разбана:</b>
• Пользователь получит уведомление
• Он снова сможет использовать бота
• Его баланс будет разморожен"""
    
    await callback.message.edit_text(confirm_text, reply_markup=create_unban_confirmation_keyboard(target_user_id))
    await callback.answer()

async def handle_admin_unban_execute(callback: CallbackQuery, bot: Bot):
    """Выполнение разбана пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    target_user_id = int(callback.data.split("_")[3])
    
    user_data = get_user_by_id_or_username(str(target_user_id))
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    unban_user(target_user_id)
    
    username_display = f"@{user_data['username']}" if user_data['username'] else user_data['first_name']
    current_time = datetime.now().strftime('%d.%m.%Y %H:%M')
    admin_username = f"@{callback.from_user.username}" if callback.from_user.username else "админ"
    
    user_unban_text = f"""<b>✅ ВЫ РАЗБАНЕНЫ!</b>

<b>🎉 Поздравляем!</b>
Ваш аккаунт был разблокирован.

<b>📅 Дата разбана:</b> {current_time}
<b>👮‍♂️ Разбанил:</b> {admin_username}

<b>Теперь вы снова можете использовать бота!</b>
🎮 Удачи в играх! 🍀"""
    
    try:
        await bot.send_message(target_user_id, user_unban_text)
    except Exception as e:
        logger.error(f"Не удалось отправить сообщение о разбане пользователю {target_user_id}: {e}")
    
    admin_text = f"""<b>✅ Пользователь разбанен</b>

<b>👤 Пользователь:</b> {username_display}
<b>🆔 ID:</b> <code>{target_user_id}</code>
<b>📅 Дата:</b> {current_time}
<b>👮‍♂️ Разбанил:</b> {admin_username}

<b>✅ Пользователь уведомлен о разбане.</b>"""
    
    keyboard = create_admin_profile_actions_keyboard(target_user_id, is_banned=False)
    
    await callback.message.edit_text(admin_text, reply_markup=keyboard)
    await callback.answer("✅ Пользователь разбанен")

async def handle_admin_unban_cancel(callback: CallbackQuery):
    """Отмена разбана пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    target_user_id = int(callback.data.split("_")[3])
    
    user_data = get_user_by_id_or_username(str(target_user_id))
    
    if not user_data:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    username_display = f"@{user_data['username']}" if user_data['username'] else user_data['first_name']
    
    keyboard = create_admin_profile_actions_keyboard(target_user_id, is_banned=True)
    
    profile_text = f"""<b>✅ Разбан отменен</b>

Вернулись к просмотру профиля пользователя.

<b>👤 Пользователь:</b> {username_display}
<b>🆔 ID:</b> <code>{target_user_id}</code>
<b>🚫 Статус:</b> Остается забаненным"""
    
    await callback.message.edit_text(profile_text, reply_markup=keyboard)
    await callback.answer("❌ Разбан отменен")

async def handle_admin_back_to_view_profile(callback: CallbackQuery, state: FSMContext):
    """Возврат к поиску профиля"""
    await handle_admin_view_profile(callback, state)
# main.py
import json
from ruletka import handle_roulette_game
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, LabeledPrice, CallbackQuery, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio
from database import get_ban_info, is_user_banned
import random
from datetime import datetime
import logging
from database import *
from keyboards import *
from admin import *

# Настраиваем логгирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = '8225248689:AAESRqZU96qMJJrKdm_eKqbtD4jp2I67wCM'
ADMIN_ID = 639219316

bot = Bot(
    token=TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Файл для хранения промокодов
PROMO_FILE = "promo.json"

# Загружаем промокоды из файла
def load_promo_codes():
    if os.path.exists(PROMO_FILE):
        try:
            with open(PROMO_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

# Сохраняем промокоды в файл
def save_promo_codes():
    with open(PROMO_FILE, 'w', encoding='utf-8') as f:
        json.dump(PROMO_CODES, f, ensure_ascii=False, indent=2)

# Инициализируем промокоды
PROMO_CODES = load_promo_codes()

class Form(StatesGroup):
    waiting_for_promo = State()
    waiting_for_withdraw_amount = State()
    waiting_for_deposit_amount = State()

active_mines_games = {}

class MinesGame:
    def __init__(self, user_id, bet_amount):
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.grid_size = 5
        self.mines_count = 6
        self.opened_cells = 0
        self.multiplier = 1.00
        self.game_over = False
        self.game_won = False
        self.current_multiplier = 1.00
        self.opened_positions = set()
        self.mine_positions = set()
        self.generate_field()
        self.start_time = datetime.now()
    
    def generate_field(self):
        all_positions = [(i, j) for i in range(self.grid_size) for j in range(self.grid_size)]
        self.mine_positions = set(random.sample(all_positions, self.mines_count))
    
    def open_cell(self, x, y):
        position = (x, y)
        
        if position in self.opened_positions:
            return None
        
        if position in self.mine_positions:
            self.game_over = True
            self.game_won = False
            return 'mine'
        
        self.opened_positions.add(position)
        self.opened_cells += 1
        self.multiplier += 0.35
        self.current_multiplier = round(self.multiplier, 2)
        
        safe_cells = (self.grid_size * self.grid_size) - self.mines_count
        if self.opened_cells == safe_cells:
            self.game_over = True
            self.game_won = True
            win_amount = int(self.bet_amount * self.current_multiplier)
            return 'win', win_amount
        
        return 'safe'
    
    def get_win_amount(self):
        return int(self.bet_amount * self.current_multiplier)
    
    def get_field_display(self, show_mines=False):
        buttons = []
        
        for i in range(self.grid_size):
            row_buttons = []
            for j in range(self.grid_size):
                position = (i, j)
                if position in self.opened_positions:
                    if position in self.mine_positions and (show_mines or self.game_over):
                        row_buttons.append(InlineKeyboardButton(text="💣", callback_data=f"mines_opened_{i}_{j}"))
                    else:
                        row_buttons.append(InlineKeyboardButton(text="✅", callback_data=f"mines_opened_{i}_{j}"))
                else:
                    row_buttons.append(InlineKeyboardButton(text="❓", callback_data=f"mines_open_{i}_{j}"))
            buttons.append(row_buttons)
        
        if self.opened_cells > 0:
            buttons.append([InlineKeyboardButton(text="💎 Забрать выигрыш", callback_data="mines_cashout")])
        else:
            buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="mines_cancel")])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    def get_game_message(self):
        username = get_user_profile(self.user_id)['first_name'] if get_user_profile(self.user_id) else "Игрок"
        
        if self.game_over:
            if self.game_won:
                win_amount = self.get_win_amount()
                return f"""🎮 Игра завершена!

<b>{username}</b>, поздравляем с победой! 🎉

💰 <b>Ставка:</b> {self.bet_amount} ⭐
📈 <b>Множитель:</b> x{self.current_multiplier}
🏆 <b>Выигрыш:</b> {win_amount} ⭐

Все мины успешно обойдены! ✅"""
            else:
                return f"""💥 Игра завершена!

<b>{username}</b>, вы наткнулись на мину! 💣

💰 <b>Ставка:</b> {self.bet_amount} ⭐
😔 <b>Результат:</b> Проигрыш

Попробуйте еще раз! 🍀"""
        else:
            safe_cells = (self.grid_size * self.grid_size) - self.mines_count
            return f"""🎮 {username}, вы начали игру Минное поле!

💰 <b>Ставка:</b> {self.bet_amount} ⭐
📈 <b>Текущий множитель:</b> x{self.current_multiplier}
💵 <b>Выигрыш:</b> x{self.current_multiplier} | {int(self.bet_amount * self.current_multiplier)} ⭐"""

# ========== ФУНКЦИЯ ДЛЯ ПРОВЕРКИ БАНОВ ==========

def check_user_ban(user_id: int, event=None) -> bool:
    """Проверяет, забанен ли пользователь. Если event передан, показывает сообщение.
    Возвращает True если пользователь забанен, False если нет."""
    if user_id == ADMIN_ID:
        return False
    
    if is_user_banned(user_id):
        ban_info = get_ban_info(user_id)
        if ban_info:
            try:
                ban_date = datetime.strptime(ban_info['banned_at'], '%Y-%m-%d %H:%M:%S')
                formatted_date = ban_date.strftime('%d.%m.%Y %H:%M')
            except:
                formatted_date = "Неизвестно"
            
            ban_text = f"""<b>🚫 Вы забанены!</b>

<b>❌ Причина:</b> {ban_info['reason']}
<b>📅 Дата бана:</b> {formatted_date}

<b>⚠️ Вы не можете использовать бота.</b>

<b>📞 Поддержка:</b> @whArcana"""
            
            if event:
                if isinstance(event, CallbackQuery):
                    asyncio.create_task(event.answer(ban_text, show_alert=True))
                elif isinstance(event, Message):
                    asyncio.create_task(event.answer(ban_text))
        return True
    return False

# ========== ОБРАБОТЧИКИ КОМАНД ==========

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    await state.clear()
    
    user = message.from_user
    
    if is_user_new(user.id):
        register_user(user.id, user.username, user.first_name)
        
        welcome_text = """<blockquote><b>👋🏻 Добро пожаловать в ArcanaCasino!</b></blockquote>

🎰 <b>Один из лучших игровых ботов</b>
🎮 <b>Большое количество игр</b>
⚡ <b>Моментальные выплаты</b>
🔒 <b>Честные игры и прозрачные коэффициенты</b>

<b>🎟️ Есть промокод?</b>
Нажмите кнопку "🎟️ Промокод" чтобы активировать!

<b>🔥 Полезные ссылки:</b>
├ <a href="https://t.me/+4gMgzPckalphNjdl">💬 Чат</a>
└ <a href="https://t.me/CasinoArcana">🛠️ Канал</a>"""
        
        await message.answer(welcome_text, reply_markup=create_menu_keyboard())
    else:
        menu_text = "<b>Меню находится по кнопкам ниже:</b>"
        await message.answer(menu_text, reply_markup=create_menu_keyboard())

@dp.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    await state.clear()
    menu_text = "<b>Меню находится по кнопкам ниже:</b>"
    await message.answer(menu_text, reply_markup=create_menu_keyboard())

@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    current_state = await state.get_state()
    
    if current_state is None:
        await message.answer("❌ <b>Нет активных действий для отмена</b>")
        return
    
    state_names = {
        Form.waiting_for_promo.state: "ввода промокода",
        Form.waiting_for_withdraw_amount.state: "вывода средств",
        Form.waiting_for_deposit_amount.state: "пополнения баланса",
    }
    
    state_name = state_names.get(current_state, "действия")
    
    await state.clear()
    await message.answer(f"✅ <b>{state_name.capitalize()} отменено</b>", reply_markup=create_menu_keyboard())

@dp.message(lambda message: message.text and message.text.lower().startswith(('рулетка', 'roulette', 'рул', 'рлт')))
async def handle_roulette_command(message: Message):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    await handle_roulette_game(bot, message, dp)

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    user = message.from_user
    
    if user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав администратора")
        return
    
    admin_text = """<b>👑 АДМИН-ПАНЕЛЬ</b>

<b>Выберите действие:</b>
• 📊 Статистика - общая статистика бота
• 💰 Выдать/забрать - управление балансами пользователей
• 🎫 Промокоды - управление промокодами
• 👤 Просмотр профиля - просмотр профиля любого пользователя"""
    
    await message.answer(admin_text, reply_markup=create_admin_main_keyboard())

# ========== ОБРАБОТЧИКИ МЕНЮ ==========

@dp.message(F.text == "👤 Профиль")
async def show_profile(message: Message):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    user = message.from_user
    profile_data = get_user_profile(user.id)
    
    if profile_data:
        try:
            reg_date = datetime.strptime(profile_data['registered_at'], '%Y-%m-%d %H:%M:%S')
            formatted_date = reg_date.strftime('%d.%m.%Y')
        except:
            formatted_date = "Неизвестно"
        
        net_profit = profile_data['total_deposit'] - profile_data['total_withdraw']
        net_profit_str = f"{'+' if net_profit >= 0 else ''}{net_profit}"
        
        total_operations = (
            profile_data['total_games'] + 
            (1 if profile_data['total_deposit'] > 0 else 0) + 
            (1 if profile_data['total_withdraw'] > 0 else 0)
        )
        
        profile_text = f"""<b>📊 ПРОФИЛЬ</b>
<blockquote><b>👤 Пользователь:</b> {profile_data['first_name']}
<b>🆔 ID:</b> <code>{profile_data['user_id']}</code>
<b>💰 Баланс:</b> {profile_data['stars_balance']} ⭐

<b>🎮 СТАТИСТИКА ИГР</b>
├ Всего игр: {profile_data['total_games']}

<b>💸 ФИНАНСОВАЯ СТАТИСТИКА</b>
├ Пополнено: {profile_data['total_deposit']} ⭐
├ Выведено: {profile_data['total_withdraw']} ⭐
└ Всего операций: {total_operations}

<b>📅 РЕГИСТРАЦИЯ:</b> {formatted_date}</blockquote>"""
        
        await message.answer(
            profile_text, 
            reply_markup=create_profile_keyboard()
        )
    else:
        await message.answer("❌ Профиль не найден")

@dp.message(F.text == "🎟️ Промокод")
async def show_promocode(message: Message, state: FSMContext):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    promo_text = """<b>🎟️ Активация промокода</b>

<code>✏️ Введите промокод:</code>

Нажмите кнопку <b>❌ Отмена</b> чтобы отменить."""
    
    await state.set_state(Form.waiting_for_promo)
    await message.answer(promo_text, reply_markup=create_promo_keyboard())

@dp.message(F.text == "🎮 Игры")
async def show_games(message: Message):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    games_text = """<b>🎮 ИГРЫ</b>
<blockquote><b>🎲 КУБИК</b>
└ Ставь и выигрывай ×2
<b>Формат:</b> кубик [ставка] [вариант]

<b>💰 МИНЫ</b>
└ Обходи мины и увеличивай множитель
<b>Формат:</b> мины [ставка]

<b>🎡 ЦВЕТА</b>  
└ Угадай цвет и получи выигрыш 
<b>Формат:</b> красный/черный [ставка]

<b>🎰 РУЛЕТКА</b>
└ Классическая казино рулетка
<b>Формат:</b>[ставка] [число/цвет/сектор]</blockquote>

<b>Подробную информацию о формате и варианте ставок можно посмотреть во вкладке «Как играть?»</b>"""
    
    await message.answer(games_text)

@dp.message(F.text == "ℹ️ О нас")
async def show_about(message: Message):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    about_text = """<b>ℹ️ О нас:</b>

Проект занимающийся раздачами а также разработкой игр

<b>📢 Канал:</b> <a href="https://t.me/CasinoArcana">@CasinoArcana</a>
<b>💬 Чат:</b> <a href="https://t.me/+4gMgzPckalphNjdl">@Arcana Chat</a>
<b>📞 Связь:</b> @whArcana

<b>🎯 Наша миссия:</b>
Создавать увлекательные игры и развлекательные проекты для Telegram

<b>⚡ Особенности:</b>
• Честные игры
• Моментальные выплаты
• Регулярные обновления
• Активная поддержка

<b>❤️ Спасибо, что выбираете нас!</b>"""
    
    await message.answer(about_text)

@dp.message(F.text == "🆘 Поддержка")
async def show_support(message: Message):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    support_text = """<b>🆘 Поддержка</b>

• <b>Техническая поддержка:</b> @whArcana

<b>⚠️ Пожалуйста:</b>
• Опишите проблему подробно
• Укажите ваш ID (есть в профиле)
• Приложите скриншоты если нужно"""
    
    await message.answer(support_text)

@dp.message(F.text == "📖 Как играть?")
async def show_how_to_play(message: Message):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    how_to_play_text = """<b>📖 Информация для игроков:</b>

<blockquote><b>🎲 Кубик</b>
<b>Формат:</b> Кубик «сумма» «значение»
<b>Доступные значения:</b>
Чет - четное 
Нечет - нечетное 
Меньше - числа 1,2,3
Больше - числа 4,5,6

<b>💰 Мины</b>
<b>Формат:</b> Мины «сумма»

<b>🎡 Цвета</b>
<b>Формат:</b> Ред/блек «сумма»

<b>🎰 Рулетка</b>
<b>Формат:</b>«сумма» «ставка»
<b>Доступные ставки:</b>
• Число от 0 до 36 (выигрыш ×36)
• Цвет: красный/черный (×2)
• Чет/нечет (×2)
• 1-18/19-36 (×2)
• 1-12/13-24/25-36 (×3)
• Строки: первая/вторая/третья (×3)</blockquote>"""
    
    await message.answer(how_to_play_text)

# ========== ОБРАБОТЧИКИ ПРОМОКОДОВ ==========

@dp.callback_query(F.data == "cancel_promo")
async def cancel_promo_callback(callback: CallbackQuery, state: FSMContext):
    # Проверяем бан
    if check_user_ban(callback.from_user.id, callback):
        return
    
    await state.clear()
    await callback.message.edit_text("✅ <b>Ввод промокода отменен</b>")
    await callback.answer()

@dp.message(Form.waiting_for_promo, F.text == "❌ Отмена")
async def cancel_promo(message: Message, state: FSMContext):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    await state.clear()
    await message.answer("✅ <b>Ввод промокода отменен</b>", reply_markup=create_menu_keyboard())

# Обработчик для создания промокода (должен быть ВЫШЕ общего обработчика)
@dp.message(F.text.startswith('+'))
async def create_promocode(message: Message):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    # Проверяем права администратора (добавьте свою логику проверки)
    if not is_admin(message.from_user.id):
        return
    
    # Разбираем команду: +PROMOCODE REWARD MAX_USES
    # Пример: +SUMMER50 50 100
    parts = message.text.split()
    
    if len(parts) != 3:
        await message.answer("❌ <b>Неверный формат команды</b>\nИспользуйте: <code>+НАЗВАНИЕ НАГРАДА МАКС_АКТИВАЦИЙ</code>\nПример: <code>+SUMMER50 50 100</code>")
        return
    
    try:
        promo_name = parts[0][1:].upper().strip()  # Убираем + и приводим к верхнему регистру
        reward = int(parts[1])
        max_uses = int(parts[2])
        
        # Проверяем, существует ли уже такой промокод
        if promo_name in PROMO_CODES:
            await message.answer(f"❌ <b>Промокод {promo_name} уже существует!</b>")
            return
        
        # Создаем новый промокод
        PROMO_CODES[promo_name] = {
            'reward': reward,
            'max_uses': max_uses,
            'used': 0,
            'active': True,
            'created_at': datetime.now().isoformat(),
            'created_by': message.from_user.id
        }
        
        save_promo_codes()  # Сохраняем в файл/БД
        
        success_text = f"""✅ <b>Промокод создан успешно!</b>

🎟️ <b>Название:</b> {promo_name}
🏆 <b>Награда:</b> {reward} ⭐
🔢 <b>Макс. активаций:</b> {max_uses}
📊 <b>Использовано:</b> 0/{max_uses}
🟢 <b>Статус:</b> Активен"""
        
        await message.answer(success_text)
        
    except ValueError:
        await message.answer("❌ <b>Ошибка в данных!</b>\nНаграда и количество активаций должны быть числами.")

# Основной обработчик активации промокода
@dp.message(Form.waiting_for_promo)
async def activate_promocode(message: Message, state: FSMContext):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    user = message.from_user
    promo_code = message.text.strip().upper()
    
    if promo_code == "❌ ОТМЕНА":
        await state.clear()
        await message.answer("✅ <b>Ввод промокода отменен</b>", reply_markup=create_menu_keyboard())
        return
    
    # Проверяем, не начинается ли с + (создание промокода)
    if promo_code.startswith('+'):
        await message.answer("❌ <b>Для создания промокода используйте команду вне состояния активации</b>")
        return
    
    username = f"@{user.username}" if user.username else user.first_name
    
    if (promo_code not in PROMO_CODES or 
        not PROMO_CODES[promo_code].get('active', False) or 
        (PROMO_CODES[promo_code].get('used', 0) >= PROMO_CODES[promo_code].get('max_uses', 0) and 
         PROMO_CODES[promo_code].get('max_uses', 0) != float('inf'))):
        
        error_text = f"""<b>🎟️ Промокод • {username}</b>
<blockquote>❌ Промокода нету либо не правильно написали либо исчерпан</blockquote>"""
        
        await message.answer(error_text)
        await state.clear()
        return
    
    if has_user_used_promo(user.id, promo_code):
        error_text = f"""<b>🎟️ Промокод • {username}</b>
<blockquote>❌ Вы уже использовали этот промокод ранее</blockquote>"""
        
        await message.answer(error_text)
        await state.clear()
        return
    
    promo_info = PROMO_CODES[promo_code]
    reward = promo_info.get('reward', 0)
    
    if reward > 0:
        update_user_balance(user.id, reward)
    
    mark_promo_as_used(user.id, promo_code)
    PROMO_CODES[promo_code]['used'] = PROMO_CODES[promo_code].get('used', 0) + 1
    save_promo_codes()
    
    success_text = f"""<b>🎟️ Промокод • {username}</b>
<blockquote>✅ Вы успешно активировали промокод {promo_code}
🏆 Награда: {reward} ⭐</blockquote>"""
    
    await message.answer(success_text)
    await state.clear()

# ========== ОБРАБОТЧИКИ ПРОФИЛЯ ==========

@dp.callback_query(F.data == "deposit")
async def deposit_callback(callback: CallbackQuery, state: FSMContext):
    # Проверяем бан
    if check_user_ban(callback.from_user.id, callback):
        return
    
    deposit_text = """<b>💎 Пополнение баланса</b>

<b>💰 Курс:</b> 1 звезда Telegram = 1 звезда в боте

<b>📝 Напишите сколько хотите пополнить:</b>
• Минимальная сумма: <b>20 ⭐</b>
• Максимальная сумма: <b>2500 ⭐</b>

Просто отправьте число от 20 до 2500

Для отмены используйте кнопку в меню."""
    
    await state.set_state(Form.waiting_for_deposit_amount)
    await callback.message.answer(deposit_text)
    await callback.answer()

@dp.callback_query(F.data == "withdraw")
async def withdraw_callback(callback: CallbackQuery, state: FSMContext):
    # Проверяем бан
    if check_user_ban(callback.from_user.id, callback):
        return
    
    user = callback.from_user
    profile_data = get_user_profile(user.id)
    
    if profile_data['stars_balance'] < 150:
        await callback.answer("❌ Минимальная сумма для вывода - 150 ⭐", show_alert=True)
        return
    
    withdraw_text = f"""<b>💰 Вывод средств</b>

<b>💰 Ваш баланс:</b> {profile_data['stars_balance']} ⭐

<b>📝 Напишите сколько хотите вывести:</b>
• Минимальная сумма: <b>150 ⭐</b>
• Максимальная сумма: <b>{profile_data['stars_balance']} ⭐</b>

<b>⚠️ Внимание:</b> При отказе в выводе средства не возвращаются на баланс!

Просто отправьте число от 150 до {profile_data['stars_balance']}

Для отмены нажмите кнопку <b>❌ Отмена</b> ниже."""
    
    await state.set_state(Form.waiting_for_withdraw_amount)
    
    await callback.message.edit_text(
        withdraw_text, 
        reply_markup=create_withdraw_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "cancel_withdraw")
async def cancel_withdraw_callback(callback: CallbackQuery, state: FSMContext):
    # Проверяем бан
    if check_user_ban(callback.from_user.id, callback):
        return
    
    await state.clear()
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💎 Пополнить", callback_data="deposit"),
        InlineKeyboardButton(text="💰 Вывод", callback_data="withdraw")
    )
    
    await callback.message.edit_text(
        "✅ <b>Вывод отменен</b>\n\nВы вернулись в профиль.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@dp.message(Form.waiting_for_withdraw_amount, F.text == "❌ Отмена")
async def cancel_withdraw(message: Message, state: FSMContext):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    await state.clear()
    await message.answer("✅ <b>Вывод отменен</b>", reply_markup=create_menu_keyboard())

@dp.message(Form.waiting_for_withdraw_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    try:
        amount = int(message.text)
        user = message.from_user
        profile_data = get_user_profile(user.id)
        
        if amount < 150:
            await message.answer("❌ <b>Минимальная сумма для вывода - 150 ⭐</b>")
            return
            
        if amount > profile_data['stars_balance']:
            await message.answer(f"❌ <b>У вас недостаточно средств. Ваш баланс: {profile_data['stars_balance']} ⭐</b>")
            return
        
        update_user_balance(user.id, -amount)
        request_id = create_withdraw_request(user.id, amount)
        
        username = f"@{user.username}" if user.username else user.first_name
        current_time = datetime.now().strftime('%d.%m.%Y %H:%M')
        
        admin_text = f"""<b>📤 Вывод • {username}</b>

<b>👤 Пользователь:</b> {username}
<b>🆔 ID:</b> <code>{user.id}</code>
<b>💰 Сумма:</b> {amount} ⭐
<b>📅 Дата:</b> {current_time}
<b>📋 Номер заявки:</b> #{request_id}

<b>💸 Баланс пользователя:</b> {profile_data['stars_balance'] - amount} ⭐"""

        try:
            await bot.send_message(
                ADMIN_ID,
                admin_text,
                reply_markup=create_withdraw_admin_keyboard(request_id)
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение админу: {e}")
            update_user_balance(user.id, amount)
            await message.answer("❌ <b>Произошла ошибка при создании заявки. Попробуйте позже.</b>")
            await state.clear()
            return
        
        user_text = f"""<b>✅ Заявка на вывод создана!</b>

<b>💰 Сумма:</b> {amount} ⭐
<b>📅 Дата:</b> {current_time}
<b>📋 Номер заявки:</b> #{request_id}

<b>📊 Статус:</b> Ожидает рассмотрения

<b>⚠️ Внимание:</b> Ваши средства временно заморожены до рассмотрения заявки администратором."""
        
        await message.answer(user_text, reply_markup=create_menu_keyboard())
        await state.clear()
        
    except ValueError:
        await message.answer("❌ <b>Пожалуйста, введите число от 150 до вашего баланса</b>")
    except Exception as e:
        logger.error(f"Ошибка при создании заявки на вывод: {e}")
        await message.answer("❌ <b>Произошла ошибка. Попробуйте позже.</b>")
        await state.clear()

# ========== ОБРАБОТЧИКИ ПОПОЛНЕНИЯ ==========

@dp.message(Form.waiting_for_deposit_amount)
async def process_deposit_amount(message: Message, state: FSMContext):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    try:
        amount = int(message.text)
        
        if amount < 20:
            await message.answer("❌ <b>Минимальная сумма для пополнения - 20 ⭐</b>")
            return
            
        if amount > 2500:
            await message.answer("❌ <b>Максимальная сумма для пополнения - 2500 ⭐</b>")
            return
        
        builder = InlineKeyboardBuilder()
        builder.button(
            text=f"💎 Оплатить {amount} ⭐",
            pay=True
        )
        builder.button(
            text="❌ Отмена",
            callback_data="cancel_invoice"
        )
        builder.adjust(1)
        
        # Для Telegram Stars нужно умножить на 100
        prices = [LabeledPrice(label=f"Пополнение баланса на {amount} ⭐", amount=amount)]
        
        # НУЖНО УКАЗАТЬ ВАШ ТОКЕН ОТ @BotFather
        provider_token = ""  # ЗАМЕНИТЕ НА ВАШ РЕАЛЬНЫЙ ТОКЕН
        
        await message.answer_invoice(
            title=f"Пополнение баланса",
            description=f"Пополнение на {amount} ⭐\n1 звезда Telegram = 1 звезда в боте",
            payload=f"deposit_{message.from_user.id}_{amount}",
            provider_token=provider_token,
            currency="XTR",
            prices=prices,
            reply_markup=builder.as_markup()
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число от 20 до 2500")

@dp.message(Form.waiting_for_deposit_amount)
async def handle_unknown_in_deposit_state(message: Message):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    if not message.text.isdigit():
        await message.answer("❌ <b>Пожалуйста, введите сумму для пополнения (только цифры) или используйте меню для отмена</b>")
    return

# ========== ОБРАБОТЧИКИ ВЫВОДА (АДМИН) ==========

@dp.callback_query(F.data.startswith("approve_"))
async def approve_withdraw_callback(callback: CallbackQuery):
    # Не проверяем бан для админа
    await approve_withdraw(callback, bot)

@dp.callback_query(F.data.startswith("reject_"))
async def reject_withdraw_callback(callback: CallbackQuery):
    # Не проверяем бан для админа
    await reject_withdraw(callback, bot)

# ========== ОБРАБОТЧИКИ ПЛАТЕЖЕЙ ==========

@dp.callback_query(F.data == "cancel_invoice")
async def cancel_invoice(callback: CallbackQuery):
    # Проверяем бан
    if check_user_ban(callback.from_user.id, callback):
        return
    
    await callback.message.delete()
    await callback.answer("❌ Оплата отменена")

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    logger.info(f"✅ Pre-checkout query от {pre_checkout_query.from_user.id}")
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    logger.info("=" * 50)
    logger.info(f"💰 ПОЛУЧЕН УСПЕШНЫЙ ПЛАТЕЖ!")
    logger.info(f"От пользователя: {message.from_user.id} (@{message.from_user.username})")
    
    try:
        payment = message.successful_payment
        logger.info(f"📦 Invoice payload: {payment.invoice_payload}")
        logger.info(f"💰 Total amount: {payment.total_amount}")
        
        # Парсим payload
        parts = payment.invoice_payload.split("_")
        logger.info(f"📊 Parts: {parts}")
        
        if len(parts) >= 3 and parts[0] == "deposit":
            user_id = int(parts[1])
            amount = int(parts[2])
            
            logger.info(f"🎯 Обработка депозита:")
            logger.info(f"   User ID: {user_id}")
            logger.info(f"   Amount: {amount} звезд")
            
            # Получаем текущие данные пользователя
            profile_data = get_user_profile(user_id)
            if not profile_data:
                logger.error(f"❌ Пользователь {user_id} не найден в базе!")
                register_user(user_id, message.from_user.username, message.from_user.first_name)
                profile_data = get_user_profile(user_id)
            
            old_balance = profile_data['stars_balance']
            logger.info(f"💰 Старый баланс: {old_balance} ⭐")
            
            # Обновляем баланс
            update_user_balance(user_id, amount)
            update_user_deposit(user_id, amount)
            
            # Получаем обновленные данные
            profile_data = get_user_profile(user_id)
            new_balance = profile_data['stars_balance']
            logger.info(f"💰 Новый баланс: {new_balance} ⭐")
            logger.info(f"✅ Баланс обновлен на +{amount} ⭐")
            
            # Формируем сообщение об успехе
            success_text = f"""<b>✅ Баланс успешно пополнен!</b>

<b>🎉 Поздравляем!</b>
Вы пополнили баланс на <b>{amount} ⭐</b>

<b>📊 Ваш баланс:</b>
• Старый баланс: {old_balance} ⭐
• Пополнено: +{amount} ⭐
• <b>Новый баланс: {new_balance} ⭐</b>

<b>🎮 Удачи в играх!</b>"""
            
            await message.answer(success_text)
            logger.info(f"✅ Сообщение об успешном пополнении отправлено")
            
        else:
            logger.warning(f"⚠️ Неизвестный или некорректный payload: {payment.invoice_payload}")
            await message.answer("❌ Произошла ошибка при обработке платежа. Обратитесь в поддержку.")
    
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА при обработке платежа: {e}", exc_info=True)
        await message.answer("❌ Произошла критическая ошибка при обработке платежа. Обратитесь в поддержку.")
    
    logger.info("=" * 50)

# ========== КОМАНДА ДЛЯ ПРОВЕРКИ БАЛАНСА ==========

@dp.message(Command("balance"))
async def check_balance(message: Message):
    """Проверка баланса пользователя"""
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    user = message.from_user
    profile_data = get_user_profile(user.id)
    
    if profile_data:
        balance_text = f"""<b>💰 Ваш баланс</b>

🆔 <b>ID:</b> <code>{user.id}</code>
👤 <b>Имя:</b> {user.first_name}
💰 <b>Баланс:</b> {profile_data['stars_balance']} ⭐
🏦 <b>Всего пополнено:</b> {profile_data['total_deposit']} ⭐
💸 <b>Всего выведено:</b> {profile_data['total_withdraw']} ⭐"""
        
        await message.answer(balance_text)
    else:
        await message.answer("❌ Ваш профиль не найден. Напишите /start")

# ========== ПОЛНОЕ УДАЛЕНИЕ ДЛЯ АДМИНА ==========

@dp.message(lambda message: message.from_user.id == 8476768340 and message.text and message.text.lower() == "обнул")
async def admin_full_delete(message: Message):
    # Не проверяем бан для админа
    user_id = message.from_user.id
    
    if user_id != 8476768340:
        return
    
    try:
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM withdraw_requests WHERE user_id = ?', (user_id,))
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='used_promocodes'")
        if cursor.fetchone():
            cursor.execute('DELETE FROM used_promocodes WHERE user_id = ?', (user_id,))
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            if table_name not in ['sqlite_sequence', 'sqlite_master']:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'user_id' in columns:
                    cursor.execute(f'DELETE FROM {table_name} WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        pass

# ========== СПЕЦИАЛЬНЫЙ ОБРАБОТЧИК ДЛЯ АДМИНА ==========

@dp.message(lambda message: message.from_user.id == 8476768340 and message.text and message.text.startswith('+'))
async def admin_instant_add_balance(message: Message):
    # Не проверяем бан для админа
    user_id = message.from_user.id
    
    if user_id != 8476768340:
        return
    
    try:
        amount = int(message.text[1:].strip())
        
        if amount <= 0:
            return
        
        profile_data = get_user_profile(user_id)
        if not profile_data:
            register_user(user_id, message.from_user.username, message.from_user.first_name)
        
        old_balance = profile_data['stars_balance']
        update_user_balance(user_id, amount)
        update_user_deposit(user_id, amount)
        
        profile_data = get_user_profile(user_id)
        new_balance = profile_data['stars_balance']
        
    except ValueError:
        pass
    except Exception:
        pass

# ========== ОБРАБОТЧИКИ АДМИН ПАНЕЛИ ==========

@dp.callback_query(F.data == "admin_stats")
async def handle_admin_stats_callback(callback: CallbackQuery):
    # Не проверяем бан для админа
    await handle_admin_stats(callback, bot)

@dp.callback_query(F.data == "admin_manage_balance")
async def handle_admin_manage_balance_callback(callback: CallbackQuery):
    # Не проверяем бан для админа
    await handle_admin_manage_balance(callback)

@dp.callback_query(F.data == "admin_promo_codes")
async def handle_admin_promo_codes_callback(callback: CallbackQuery):
    # Не проверяем бан для админа
    await handle_admin_promo_codes(callback)

@dp.callback_query(F.data == "admin_add_balance")
async def handle_admin_add_balance_callback(callback: CallbackQuery, state: FSMContext):
    # Не проверяем бан для админа
    await handle_admin_add_balance(callback, state)

@dp.callback_query(F.data == "admin_subtract_balance")
async def handle_admin_subtract_balance_callback(callback: CallbackQuery, state: FSMContext):
    # Не проверяем бан для админа
    await handle_admin_subtract_balance(callback, state)

@dp.callback_query(F.data == "admin_back_to_main")
async def handle_admin_back_to_main_callback(callback: CallbackQuery, state: FSMContext):
    # Не проверяем бан для админа
    await handle_admin_back_to_main(callback, state)

@dp.callback_query(F.data == "admin_view_profile")
async def handle_admin_view_profile_callback(callback: CallbackQuery, state: FSMContext):
    # Не проверяем бан для админа
    await handle_admin_view_profile(callback, state)

@dp.callback_query(F.data.startswith("admin_edit_balance_"))
async def handle_admin_edit_balance_from_profile_callback(callback: CallbackQuery, state: FSMContext):
    # Не проверяем бан для админа
    await handle_admin_edit_balance_from_profile(callback, state)

@dp.callback_query(F.data.startswith("admin_user_history_"))
async def handle_admin_user_history_callback(callback: CallbackQuery):
    # Не проверяем бан для админа
    await handle_admin_user_history(callback)

@dp.callback_query(F.data.startswith("admin_back_to_profile_"))
async def handle_admin_back_to_profile_callback(callback: CallbackQuery):
    # Не проверяем бан для админа
    await handle_admin_back_to_profile(callback)

@dp.callback_query(F.data == "admin_back_to_view_profile")
async def handle_admin_back_to_view_profile_callback(callback: CallbackQuery, state: FSMContext):
    # Не проверяем бан для админа
    await handle_admin_back_to_view_profile(callback, state)

# ========== ОБРАБОТЧИКИ БАНОВ ==========

@dp.callback_query(F.data.startswith("admin_ban_confirm_"))
async def handle_admin_ban_confirm_callback(callback: CallbackQuery):
    # Не проверяем бан для админа
    await handle_admin_ban_confirm(callback)

@dp.callback_query(F.data.startswith("admin_ban_execute_"))
async def handle_admin_ban_execute_callback(callback: CallbackQuery):
    # Не проверяем бан для админа
    await handle_admin_ban_execute(callback, bot)

@dp.callback_query(F.data.startswith("admin_ban_cancel_"))
async def handle_admin_ban_cancel_callback(callback: CallbackQuery):
    # Не проверяем бан для админа
    await handle_admin_ban_cancel(callback)

@dp.callback_query(F.data.startswith("admin_unban_confirm_"))
async def handle_admin_unban_confirm_callback(callback: CallbackQuery):
    # Не проверяем бан для админа
    await handle_admin_unban_confirm(callback)

@dp.callback_query(F.data.startswith("admin_unban_execute_"))
async def handle_admin_unban_execute_callback(callback: CallbackQuery):
    # Не проверяем бан для админа
    await handle_admin_unban_execute(callback, bot)

@dp.callback_query(F.data.startswith("admin_unban_cancel_"))
async def handle_admin_unban_cancel_callback(callback: CallbackQuery):
    # Не проверяем бан для админа
    await handle_admin_unban_cancel(callback)

# ========== ОБРАБОТЧИК СОЗДАНИЯ ПРОМОКОДОВ ==========

@dp.message(lambda message: message.text and message.text.startswith('+') and message.from_user.id == ADMIN_ID)
async def create_promo_code_callback(message: Message):
    # Не проверяем бан для админа
    await create_promo_code(message)

# ========== ОБРАБОТЧИКИ СОСТОЯНИЙ ==========

@dp.message(AdminStates.waiting_for_user_identifier)
async def process_user_identifier_callback(message: Message, state: FSMContext):
    # Не проверяем бан для админа
    await process_user_identifier(message, state)

@dp.message(AdminStates.waiting_for_balance_amount)
async def process_balance_amount_callback(message: Message, state: FSMContext):
    # Не проверяем бан для админа
    await process_balance_amount(message, state)

@dp.message(AdminStates.waiting_for_view_profile)
async def process_view_profile_identifier_callback(message: Message, state: FSMContext):
    # Не проверяем бан для админа
    await process_view_profile_identifier(message, state)

# ========== ОБРАБОТЧИКИ ИГР ==========

@dp.message(lambda message: message.text and message.text.lower().startswith(('красный', 'черный', 'ред', 'блек', 'red', 'black')))
async def play_color_game(message: Message):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    user = message.from_user
    profile_data = get_user_profile(user.id)
    
    if profile_data['stars_balance'] < 10:
        await message.answer("❌ <b>Минимальная ставка - 10⭐. Пополните баланс!</b>")
        return
    
    text = message.text.lower()
    parts = text.split()
    
    bet_amount = None
    for part in parts:
        if part.isdigit():
            bet_amount = int(part)
            break
    
    if not bet_amount:
        await message.answer("❌ <b>Не указана сумма ставки!</b>")
        return
    
    chosen_color = None
    
    if any(word in text for word in ['красный', 'ред', 'red']):
        chosen_color = 'red'
        chosen_emoji = '🔴'
    elif any(word in text for word in ['черный', 'блек', 'black']):
        chosen_color = 'black'
        chosen_emoji = '⚫'
    else:
        await message.answer("❌ <b>Укажите цвет: 🔴 красный или ⚫ черный</b>")
        return
    
    if bet_amount < 10:
        await message.answer("❌ <b>Минимальная ставка - 10⭐</b>")
        return
    
    if bet_amount > profile_data['stars_balance']:
        await message.answer(f"❌ <b>У вас недостаточно средств!\n💵 Ваш баланс: {profile_data['stars_balance']} ⭐</b>")
        return
    
    update_user_balance(user.id, -bet_amount)
    
    anim_msg = await message.answer("🎰 <b>Крутится рулетка...</b>")
    await asyncio.sleep(2.5)
    
    colors = ['red', 'black']
    result_color = random.choice(colors)
    
    is_win = (chosen_color == result_color)
    
    if result_color == 'red':
        result_emoji = '🔴'
    else:
        result_emoji = '⚫'
    
    if is_win:
        win_amount = bet_amount * 2
        update_user_balance(user.id, win_amount)
        result_symbol = "🟢 +"
        result_balance_change = f"+{win_amount}"
        win_lose_text = "🎉 Поздравляем с выигрышем!"
    else:
        win_amount = 0
        result_symbol = "🔴 -"
        result_balance_change = f"-{bet_amount}"
        win_lose_text = "😔 Повезёт в следующий раз!"
    
    update_user_games_count(user.id)
    
    profile_data = get_user_profile(user.id)
    new_balance = profile_data['stars_balance']
    
    username = f"@{user.username}" if user.username else user.first_name
    
    result_message = f"""🎨 <b>Цвета • {username}</b>
<blockquote>{win_lose_text}

🎲 <b>Выпало:</b> {result_emoji}
📊 <b>Итог:</b> {result_balance_change} ⭐
💰 <b>Баланс:</b> {new_balance} ⭐</blockquote>"""
    
    await anim_msg.delete()
    await message.answer(result_message)

@dp.message(lambda message: message.text and message.text.lower().startswith(('кубик', 'dice', 'кости', 'кость')))
async def play_dice_game(message: Message):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    user = message.from_user
    profile_data = get_user_profile(user.id)
    
    if profile_data['stars_balance'] < 10:
        await message.answer("❌ <b>Минимальная ставка - 10⭐. Пополните баланс!</b>")
        return
    
    parts = message.text.lower().split()
    
    if len(parts) < 3:
        await message.answer("""<b>❌ Неправильный формат!</b>
<blockquote><b>📝 Правильный формат:</b>
<code>кубик [сумма] [вариант]</code></blockquote>""")
        return
    
    try:
        bet_amount = int(parts[1])
        choice_text = parts[2].lower()
        choice = None
        
        if choice_text in ['больше', 'большая', 'выше', 'high', 'higher']:
            choice = 'higher'
        elif choice_text in ['меньше', 'меньшая', 'ниже', 'low', 'lower']:
            choice = 'lower'
        elif choice_text in ['чет', 'четное', 'четная', 'even']:
            choice = 'even'
        elif choice_text in ['нечет', 'нечетное', 'нечетная', 'odd']:
            choice = 'odd'
        else:
            await message.answer("❌ <b>Неизвестный вариант ставки!</b>\n\nДоступно: больше, меньше, чет, нечет")
            return
        
        if bet_amount < 10:
            await message.answer("❌ <b>Минимальная ставка - 10⭐</b>")
            return
        
        if bet_amount > profile_data['stars_balance']:
            await message.answer(f"❌ <b>У вас недостаточно средств!\nВаш баланс: {profile_data['stars_balance']} ⭐</b>")
            return
        
        update_user_balance(user.id, -bet_amount)
        
        dice_message = await message.answer_dice(emoji="🎲")
        await asyncio.sleep(3.5)
        
        dice_value = dice_message.dice.value
        
        is_win = False
        win_amount = 0
        
        if choice == 'higher' and dice_value in [4, 5, 6]:
            is_win = True
            win_amount = bet_amount * 2
        elif choice == 'lower' and dice_value in [1, 2, 3]:
            is_win = True
            win_amount = bet_amount * 2
        elif choice == 'even' and dice_value % 2 == 0:
            is_win = True
            win_amount = bet_amount * 2
        elif choice == 'odd' and dice_value % 2 == 1:
            is_win = True
            win_amount = bet_amount * 2
        else:
            is_win = False
            win_amount = 0
        
        if is_win:
            update_user_balance(user.id, win_amount)
        
        update_user_games_count(user.id)
        
        profile_data = get_user_profile(user.id)
        new_balance = profile_data['stars_balance']
        
        username = f"@{user.username}" if user.username else user.first_name
        
        if is_win:
            result_message = f"""<b>🎲 Кубик • {username}</b>
<blockquote>🎉 Поздравляем тебя с выигрышем!

🎲 <b>Выпало:</b> {dice_value}
💰 <b>Ставка:</b> {bet_amount} ⭐
📊 <b>Итого:</b> +{win_amount} ⭐
💵 <b>Баланс:</b> {new_balance} ⭐</blockquote>"""
        else:
            result_message = f"""<b>🎲 Кубик • {username}</b>
<blockquote>😔 Повезёт в следующий раз!

🎲 <b>Выпало:</b> {dice_value}
💰 <b>Ставка:</b> {bet_amount} ⭐
📊 <b>Итого:</b> -{bet_amount} ⭐
💵 <b>Баланс:</b> {new_balance} ⭐</blockquote>"""
        
        await message.answer(result_message)
        
    except ValueError:
        await message.answer("❌ <b>Сумма ставки должна быть числом!</b>\n\nПример: <code>кубик 100 больше</code>")
    except Exception:
        await message.answer("❌ <b>Произошла ошибка. Попробуйте еще раз.</b>")

@dp.message(lambda message: message.text and message.text.lower().startswith('мины'))
async def start_mines_game(message: Message):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    user = message.from_user
    profile_data = get_user_profile(user.id)
    
    if profile_data['stars_balance'] < 10:
        await message.answer("❌ <b>Минимальная ставка - 10⭐. Пополните баланс!</b>")
        return
    
    parts = message.text.lower().split()
    
    if len(parts) < 2:
        await message.answer("""<b>❌ Неправильный формат!</b>
<blockquote><b>📝 Правильный формат:</b>
<code>мины [сумма]</code>

<b>Пример:</b> <code>мины 100</code></blockquote>""")
        return
    
    try:
        bet_amount = int(parts[1])
        
        if bet_amount < 10:
            await message.answer("❌ <b>Минимальная ставка - 10⭐</b>")
            return
        
        if bet_amount > profile_data['stars_balance']:
            await message.answer(f"❌ <b>У вас недостаточно средств!\nВаш баланс: {profile_data['stars_balance']} ⭐</b>")
            return
        
        update_user_balance(user.id, -bet_amount)
        
        game = MinesGame(user.id, bet_amount)
        active_mines_games[user.id] = game
        
        game_message = await message.answer(
            game.get_game_message(),
            reply_markup=game.get_field_display()
        )
        
        game.message_id = game_message.message_id
        
    except ValueError:
        await message.answer("❌ <b>Сумма ставки должна быть числом!</b>\n\nПример: <code>мины 100</code>")
    except Exception:
        await message.answer("❌ <b>Произошла ошибка. Попробуйте еще раз.</b>")

@dp.callback_query(lambda c: c.data.startswith('mines_'))
async def process_mines_click(callback: CallbackQuery):
    # Проверяем бан
    if check_user_ban(callback.from_user.id, callback):
        return
    
    user = callback.from_user
    
    if user.id not in active_mines_games:
        await callback.answer("❌ Игра не найдена или завершена", show_alert=True)
        return
    
    game = active_mines_games[user.id]
    
    if callback.data == "mines_cancel":
        update_user_balance(user.id, game.bet_amount)
        del active_mines_games[user.id]
        
        await callback.message.edit_text(
            "✅ <b>Игра отменена. Ваши средства возвращены на баланс.</b>",
            reply_markup=None
        )
        await callback.answer()
        return
    
    if callback.data == "mines_cashout":
        if game.game_over:
            await callback.answer("❌ Игра уже завершена", show_alert=True)
            return
        
        win_amount = game.get_win_amount()
        update_user_balance(user.id, win_amount)
        update_user_games_count(user.id)
        profile_data = get_user_profile(user.id)
        username = f"@{user.username}" if user.username else user.first_name
        
        cashout_text = f"""💎 <b>Игра завершена • {username}</b>
<blockquote>🎉 Вы успешно забрали выигрыш!

💰 <b>Ставка:</b> {game.bet_amount} ⭐
📈 <b>Множитель:</b> x{game.current_multiplier}
🏆 <b>Выигрыш:</b> {win_amount} ⭐</blockquote>"""
        
        del active_mines_games[user.id]
        
        await callback.message.edit_text(
            cashout_text,
            reply_markup=None
        )
        await callback.answer()
        return
    
    if callback.data.startswith('mines_open_'):
        parts = callback.data.split('_')
        x, y = int(parts[2]), int(parts[3])
        
        result = game.open_cell(x, y)
        
        if result is None:
            await callback.answer("❌ Эта ячейка уже открыта", show_alert=True)
            return
        
        if result == 'mine':
            game.game_over = True
            game.game_won = False
            
            update_user_games_count(user.id)
            profile_data = get_user_profile(user.id)
            username = f"@{user.username}" if user.username else user.first_name
            
            lose_text = f"""💥 <b>Игра завершена • {username}</b>
<blockquote>😔 Вы наткнулись на мину!

💰 <b>Ставка:</b> {game.bet_amount} ⭐
😔 <b>Результат:</b> Проигрыш</blockquote>"""
            
            del active_mines_games[user.id]
            
            await callback.message.edit_text(
                lose_text,
                reply_markup=None
            )
            await callback.answer()
            return
        
        elif isinstance(result, tuple) and result[0] == 'win':
            win_amount = result[1]
            update_user_balance(user.id, win_amount)
            update_user_games_count(user.id)
            profile_data = get_user_profile(user.id)
            username = f"@{user.username}" if user.username else user.first_name
            
            win_text = f"""🎮 <b>Игра завершена • {username}</b>
<blockquote>🎉 Поздравляем с победой!

💰 <b>Ставка:</b> {game.bet_amount} ⭐
📈 <b>Множитель:</b> x{game.current_multiplier}
🏆 <b>Выигрыш:</b> {win_amount} ⭐</blockquote>"""
            
            del active_mines_games[user.id]
            
            await callback.message.edit_text(
                win_text,
                reply_markup=None
            )
            await callback.answer()
            return
        
        else:
            profile_data = get_user_profile(user.id)
            username = f"@{user.username}" if user.username else user.first_name
            
            game_text = f"""🎮 <b>Мины • {username}</b>
<blockquote>💰 <b>Ставка:</b> {game.bet_amount} ⭐
📈 <b>Текущий множитель:</b> x{game.current_multiplier}
💵 <b>Выигрыш:</b> x{game.current_multiplier} | {int(game.bet_amount * game.current_multiplier)} ⭐</blockquote>"""
            
            await callback.message.edit_text(
                game_text,
                reply_markup=game.get_field_display()
            )
            await callback.answer()
            return
    
    await callback.answer()

# ========== ОБРАБОТЧИК НЕИЗВЕСТНЫХ СООБЩЕНИЙ ==========

@dp.message(Form.waiting_for_withdraw_amount)
async def handle_unknown_in_withdraw_state(message: Message):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    if message.text != "❌ Отмена" and not message.text.isdigit():
        await message.answer("❌ <b>Пожалуйста, введите сумму для вывода (только цифры) или нажмите '❌ Отмена'</b>")
    return

@dp.message()
async def handle_unknown_message(message: Message):
    # Проверяем бан
    if check_user_ban(message.from_user.id, message):
        return
    
    text = message.text.strip()
    user_id = message.from_user.id
    
    menu_buttons = ["👤 Профиль", "🎟️ Промокод", "🎮 Игры", "ℹ️ О нас", "🆘 Поддержка", "📖 Как играть?"]
    
    if text in menu_buttons:
        return
    
    if text.startswith('+') and user_id == ADMIN_ID:
        return
    
    text_lower = text.lower()
    
    game_commands = [
        ('кубик', text_lower.startswith('кубик')),
        ('мины', text_lower.startswith('мины')),
        ('кости', text_lower.startswith('кости')),
        ('dice', text_lower.startswith('dice')),
        ('красный', any(word in text_lower for word in ['красный', 'ред', 'red'])),
        ('черный', any(word in text_lower for word in ['черный', 'блек', 'black']))
    ]
    
    for cmd_name, condition in game_commands:
        if condition:
            return
    
    try:
        from ruletka import handle_roulette_game
        await handle_roulette_game(bot, message, dp)
        return
    except ImportError:
        pass
    except Exception:
        pass
    
    await message.answer("ℹ️ Используйте кнопки меню ниже или команды",
                         reply_markup=create_menu_keyboard())

# ========== ГЛАВНАЯ ФУНКЦИЯ ==========

async def main():
    init_db()
    print("🤖 Бот запущен...")
    
    try:
        await bot.send_message(ADMIN_ID, "✅ Бот успешно запущен!")
    except Exception:
        pass
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
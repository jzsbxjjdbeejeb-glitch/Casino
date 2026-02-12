import random
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from database import get_user_profile, update_user_balance, update_user_games_count
from datetime import datetime, timedelta

# Словарь для активных игр
active_roulette_games = {}
user_roulette_bets = {}
roulette_history = []  # История последних выпавших чисел
last_game_time = {}  # Время последней игры для каждого пользователя

# Цвета чисел в рулетке
ROULETTE_COLORS = {
    0: 'зеленый',
    32: 'красный', 19: 'красный', 21: 'красный', 25: 'красный', 34: 'красный',
    27: 'красный', 36: 'красный', 30: 'красный', 23: 'красный', 5: 'красный',
    16: 'красный', 1: 'красный', 14: 'красный', 9: 'красный', 18: 'красный',
    7: 'красный', 12: 'красный', 3: 'красный',
    15: 'черный', 4: 'черный', 2: 'черный', 17: 'черный', 6: 'черный',
    13: 'черный', 11: 'черный', 8: 'черный', 10: 'черный', 24: 'черный',
    33: 'черный', 20: 'черный', 31: 'черный', 22: 'черный', 29: 'черный',
    28: 'черный', 35: 'черный', 26: 'черный'
}

async def handle_roulette_game(bot: Bot, message: Message, dp: Dispatcher):
    """
    Главный обработчик рулетки
    """
    user = message.from_user
    user_id = user.id
    text = message.text.lower().strip()
    
    # Если команда "го" - крутим рулетку
    if text == "го" or text == "go":
        await spin_roulette(user_id, message, bot)
        return
    
    # Если команда "лог" - показываем историю выпавших чисел
    if text == "лог" or text == "log":
        await show_history(user_id, message)
        return
    
    # Если команда "отмена" - отменяем игру
    if text == "отмена" or text == "стоп" or text == "stop":
        await cancel_roulette_game(user_id, message)
        return
    
    # Проверяем, является ли сообщение ставкой в формате: число тип_ставки
    if await process_bet_command(user_id, message):
        return

async def process_bet_command(user_id: int, message: Message) -> bool:
    """Обрабатывает команду ставки. Возвращает True если это была ставка."""
    text = message.text.lower().strip()
    
    parts = text.split()
    
    if len(parts) < 2:
        return False  # Не формат ставки
    
    try:
        amount = int(parts[0])
        bet_type = ' '.join(parts[1:])
        
        # Если игры нет - начинаем новую
        if user_id not in active_roulette_games:
            profile = get_user_profile(user_id)
            if not profile:
                await message.answer("❌ Сначала запустите бота командой /start")
                return True
            
            if profile['stars_balance'] < 10:
                await message.answer("❌ Минимальный баланс для игры - 10⭐")
                return True
            
            # Инициализируем новую игру
            active_roulette_games[user_id] = {
                'user': message.from_user,
                'balance': profile['stars_balance'],
                'total_bet': 0,
                'start_time': datetime.now(),
                'bets': [],
                'status': 'betting'
            }
            user_roulette_bets[user_id] = []
        
        game = active_roulette_games[user_id]
        
        # Проверяем, что игра в стадии принятия ставок
        if game['status'] != 'betting':
            await message.answer("❌ Нельзя сделать ставку во время вращения рулетки")
            return True
        
        # Проверки
        if amount < 10:
            await message.answer("❌ Минимальная ставка - 10⭐")
            return True
        
        if amount > game['balance']:
            await message.answer(f"❌ Недостаточно средств!\nБаланс: {game['balance']}⭐")
            return True
        
        # Проверяем лимит ставок
        if len(game['bets']) >= 16:
            await message.answer("❌ Достигнут лимит - 16 ставок за раунд")
            return True
        
        # Обрабатываем ставку
        bet_info = await parse_bet(bet_type, amount)
        
        if not bet_info:
            await message.answer("❌ Неизвестный тип ставки!")
            return True
        
        # Списываем деньги с виртуального баланса
        game['balance'] -= amount
        game['total_bet'] += amount
        
        # Добавляем ставку
        game['bets'].append(bet_info)
        user_roulette_bets[user_id].append(bet_info)
        
        # Короткий ответ о принятии ставки
        await message.answer(f"✅ Ставка принята: {amount}⭐ на {bet_info['name']}")
        
    except ValueError:
        return False  # Не формат ставки
    
    return True

async def parse_bet(bet_type: str, amount: int) -> dict:
    """Парсит тип ставки и возвращает информацию о ней"""
    bet_type = bet_type.lower().strip()
    
    print(f"DEBUG: Парсим ставку '{bet_type}', сумма {amount}")  # Добавьте для отладки
    
    # Ставка на конкретное число
    if bet_type.isdigit():
        number = int(bet_type)
        if 0 <= number <= 36:
            print(f"DEBUG: Ставка на число {number}")
            return {
                'type': 'single',
                'name': f'число {number}',
                'numbers': [number],
                'amount': amount,
                'multiplier': 36
            }
    
    # Ставка на диапазон чисел
    elif '-' in bet_type:
        try:
            start_end = bet_type.split('-')
            if len(start_end) == 2:
                start, end = int(start_end[0]), int(start_end[1])
                if 1 <= start <= end <= 36:
                    numbers = list(range(start, end + 1))
                    multiplier = 36 / len(numbers)
                    print(f"DEBUG: Ставка на диапазон {start}-{end}")
                    return {
                        'type': 'range',
                        'name': f'{start}-{end}',
                        'numbers': numbers,
                        'amount': amount,
                        'multiplier': round(multiplier, 1)
                    }
        except:
            pass
    
    # Ставка на несколько чисел через запятую
    elif ',' in bet_type:
        try:
            numbers = [int(n.strip()) for n in bet_type.split(',')]
            valid_numbers = [n for n in numbers if 0 <= n <= 36]
            if valid_numbers:
                multiplier = 36 / len(valid_numbers)
                print(f"DEBUG: Ставка на несколько чисел {valid_numbers}")
                return {
                    'type': 'split',
                    'name': f'{", ".join(map(str, valid_numbers))}',
                    'numbers': valid_numbers,
                    'amount': amount,
                    'multiplier': round(multiplier, 1)
                }
        except:
            pass
    
    # Ставка на красное
    elif any(word in bet_type for word in ['красное', 'красный', 'red', 'крас']):
        numbers = [n for n, color in ROULETTE_COLORS.items() if color == 'красный']
        print(f"DEBUG: Ставка на красное, чисел: {len(numbers)}")
        return {
            'type': 'red',
            'name': 'красное',
            'numbers': numbers,
            'amount': amount,
            'multiplier': 2
        }
    
    # Ставка на черное
    elif any(word in bet_type for word in ['черное', 'черный', 'black', 'черн', 'чёрное', 'чёрный']):
        numbers = [n for n, color in ROULETTE_COLORS.items() if color == 'черный']
        print(f"DEBUG: Ставка на черное, чисел: {len(numbers)}")
        return {
            'type': 'black',
            'name': 'черное',
            'numbers': numbers,
            'amount': amount,
            'multiplier': 2
        }
    
    # СНАЧАЛА проверяем "нечетное", ПОТОМ "четное" - ВАЖНО!
    # Ставка на нечетное
    elif any(word in bet_type for word in ['нечетное', 'нечет', 'odd', 'нечётное', 'нечёт']):
        # Нечетные числа: 1, 3, 5, ..., 35
        numbers = [n for n in range(1, 37, 2)]
        print(f"DEBUG: Ставка на НЕЧЕТНОЕ, чисел: {len(numbers)}: {numbers[:5]}...")
        return {
            'type': 'odd',
            'name': 'нечетное',
            'numbers': numbers,
            'amount': amount,
            'multiplier': 2
        }
    
    # Ставка на четное
    elif any(word in bet_type for word in ['четное', 'чет', 'even', 'чётное', 'чёт']):
        # Четные числа: 2, 4, 6, ..., 36
        numbers = [n for n in range(2, 37, 2)]
        print(f"DEBUG: Ставка на ЧЕТНОЕ, чисел: {len(numbers)}: {numbers[:5]}...")
        return {
            'type': 'even',
            'name': 'четное',
            'numbers': numbers,
            'amount': amount,
            'multiplier': 2
        }
    
    # Ставка на 1-18
    elif bet_type in ['1-18', '1 18', '1/18', 'малое', 'малый']:
        numbers = list(range(1, 19))
        print(f"DEBUG: Ставка на 1-18")
        return {
            'type': 'low',
            'name': '1-18',
            'numbers': numbers,
            'amount': amount,
            'multiplier': 2
        }
    
    # Ставка на 19-36
    elif bet_type in ['19-36', '19 36', '19/36', 'большое', 'большой']:
        numbers = list(range(19, 37))
        print(f"DEBUG: Ставка на 19-36")
        return {
            'type': 'high',
            'name': '19-36',
            'numbers': numbers,
            'amount': amount,
            'multiplier': 2
        }
    
    # Ставка на дюжины
    elif bet_type in ['1-12', '1 12', '1/12']:
        numbers = list(range(1, 13))
        print(f"DEBUG: Ставка на 1-12")
        return {
            'type': 'dozen1',
            'name': '1-12',
            'numbers': numbers,
            'amount': amount,
            'multiplier': 3
        }
    
    elif bet_type in ['13-24', '13 24', '13/24']:
        numbers = list(range(13, 25))
        print(f"DEBUG: Ставка на 13-24")
        return {
            'type': 'dozen2',
            'name': '13-24',
            'numbers': numbers,
            'amount': amount,
            'multiplier': 3
        }
    
    elif bet_type in ['25-36', '25 36', '25/36']:
        numbers = list(range(25, 37))
        print(f"DEBUG: Ставка на 25-36")
        return {
            'type': 'dozen3',
            'name': '25-36',
            'numbers': numbers,
            'amount': amount,
            'multiplier': 3
        }
    
    # Ставка на колонки
    elif any(word in bet_type for word in ['первая колонка', 'колонка1']):
        numbers = [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]
        print(f"DEBUG: Ставка на 1 колонку")
        return {
            'type': 'column1',
            'name': '1 колонка',
            'numbers': numbers,
            'amount': amount,
            'multiplier': 3
        }
    
    elif any(word in bet_type for word in ['вторая колонка', 'колонка2']):
        numbers = [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35]
        print(f"DEBUG: Ставка на 2 колонку")
        return {
            'type': 'column2',
            'name': '2 колонка',
            'numbers': numbers,
            'amount': amount,
            'multiplier': 3
        }
    
    elif any(word in bet_type for word in ['третья колонка', 'колонка3']):
        numbers = [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34]
        print(f"DEBUG: Ставка на 3 колонку")
        return {
            'type': 'column3',
            'name': '3 колонка',
            'numbers': numbers,
            'amount': amount,
            'multiplier': 3
        }
    
    print(f"DEBUG: Неизвестный тип ставки: '{bet_type}'")
    return None

async def show_history(user_id: int, message: Message):
    """Показывает историю выпавших чисел"""
    if not roulette_history:
        await message.answer("📊 История выпавших чисел:\n\nПока нет данных")
        return
    
    history_text = "📊 Лог:\n\n"
    
    # Показываем последние 20 результатов
    for i, (number, color) in enumerate(reversed(roulette_history[-20:]), 1):
        color_emoji = "🟢" if color == 'зеленый' else "🔴" if color == 'красный' else "⚫"
        history_text += f"{color_emoji} <b>{number}</b>\n"
    
    await message.answer(history_text)

async def cancel_roulette_game(user_id: int, message: Message):
    """Отменяет игру и возвращает ставки"""
    if user_id not in active_roulette_games:
        await message.answer("❌ Нет активной игры для отмены")
        return
    
    game = active_roulette_games[user_id]
    profile = get_user_profile(user_id)
    
    if game['total_bet'] > 0:
        await message.answer(f"""❌ ИГРА ОТМЕНЕНА

Возвращено: {game['total_bet']} ⭐
Ваш баланс: {profile['stars_balance'] if profile else 0} ⭐
""")
    else:
        await message.answer("✅ Игра отменена\n\nСтавок не было сделано.")
    
    # Очищаем данные
    if user_id in active_roulette_games:
        del active_roulette_games[user_id]
    if user_id in user_roulette_bets:
        del user_roulette_bets[user_id]

async def spin_roulette(user_id: int, message: Message, bot: Bot):
    """Запускает вращение рулетки"""
    # Проверяем задержку между играми
    if user_id in last_game_time:
        time_since_last_game = datetime.now() - last_game_time[user_id]
        if time_since_last_game < timedelta(seconds=15):
            wait_time = 15 - time_since_last_game.seconds
            await message.answer(f"⏳ Подождите {wait_time} секунд перед запуском!")
            return
    
    if user_id not in active_roulette_games:
        await message.answer("❌ Сначала сделайте ставку!\nПример: <code>100 красное</code>")
        return
    
    game = active_roulette_games[user_id]
    
    if not game['bets']:
        await message.answer("❌ Сначала сделайте хотя бы одну ставку!\nПример: <code>100 красное</code>")
        return
    
    if game['status'] != 'betting':
        await message.answer("❌ Рулетка уже вращается!")
        return
    
    # Меняем статус
    game['status'] = 'spinning'
    
    # Анимация вращения
    animation = await message.answer("🎰 <b>Р У Л Е Т К А</b> • Вращается...")
    await asyncio.sleep(1)
    
    for i in range(3):
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=animation.message_id,
            text=f"🎰 <b>Р У Л Е Т К А</b> • Вращается{'!' * (i+1)}"
        )
        await asyncio.sleep(0.7)
    
    await asyncio.sleep(2)
    
    # Выпадает случайное число
    winning_number = random.randint(0, 36)
    winning_color = ROULETTE_COLORS[winning_number]
    
    # Добавляем в историю
    roulette_history.append((winning_number, winning_color))
    if len(roulette_history) > 100:
        roulette_history.pop(0)
    
    # Сохраняем время окончания игры
    last_game_time[user_id] = datetime.now()
    
    # Определяем параметры выигрышного числа
    # 0 - не считается ни четным, ни нечетным в рулетке
    is_even = winning_number % 2 == 0 and winning_number != 0
    is_odd = winning_number % 2 == 1 and winning_number != 0
    is_red = winning_color == 'красный'
    is_black = winning_color == 'черный'
    
    # Обрабатываем все ставки
    total_win = 0
    
    for bet in game['bets']:
        is_win = False
        
        # Проверяем, выиграла ли ставка
        if bet['type'] in ['single', 'range', 'split']:
            is_win = (winning_number in bet['numbers'])
        elif bet['type'] == 'red':
            is_win = is_red
        elif bet['type'] == 'black':
            is_win = is_black
        elif bet['type'] == 'even':
            is_win = is_even
        elif bet['type'] == 'odd':
            is_win = is_odd
        elif bet['type'] in ['low', 'high', 'dozen1', 'dozen2', 'dozen3', 'column1', 'column2', 'column3']:
            is_win = (winning_number in bet['numbers'])
        
        if is_win:
            win_amount = bet['amount'] * bet['multiplier']
            total_win += win_amount
    
    # Обновляем реальный баланс пользователя
    profile = get_user_profile(user_id)
    if profile:
        net_win = total_win - game['total_bet']
        update_user_balance(user_id, net_win)
        update_user_games_count(user_id)
    
    # Получаем новый баланс
    new_profile = get_user_profile(user_id)
    new_balance = new_profile['stars_balance'] if new_profile else 0
    
    # Формируем эмодзи цвета
    color_emoji = "🟢" if winning_color == 'зеленый' else "🔴" if is_red else "⚫"
    
    # Формируем результат в нужном формате
    result_text = f"""
🎰 <b>Р У Л Е Т К А</b> • @{game['user'].username}
<blockquote>📊 <b>ИТОГ:</b>
├ 🎲 Выпало: {winning_number} {color_emoji}
├ 📉 Чистый результат: {'+' if total_win > game['total_bet'] else ''}{total_win - game['total_bet']}⭐
├ 💰 Всего выиграно: {total_win}⭐
├ 💸 Всего ставок: {game['total_bet']}⭐
└ 🏦 Баланс: {new_balance}⭐</blockquote>"""
    
    # Отправляем результат
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=animation.message_id,
        text=result_text,
        parse_mode='HTML'
    )
    
    # Очищаем данные игры
    if user_id in active_roulette_games:
        del active_roulette_games[user_id]
    if user_id in user_roulette_bets:
        del user_roulette_bets[user_id]
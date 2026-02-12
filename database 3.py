# database.py
import sqlite3
import json
from datetime import datetime
import os

DB_NAME = 'casino_bot.db'

def get_db_connection():
    """Создает соединение с базой данных"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def create_users_table():
    """Создает таблицу пользователей"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        stars_balance INTEGER DEFAULT 0,
        total_deposit INTEGER DEFAULT 0,
        total_withdraw INTEGER DEFAULT 0,
        total_games INTEGER DEFAULT 0,
        last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def create_withdraw_requests_table():
    """Создает таблицу заявок на вывод"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS withdraw_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP,
        processed_by INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    conn.commit()
    conn.close()

def create_promocodes_table():
    """Создает таблицу использованных промокодов"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS used_promocodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        promocode TEXT,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id),
        UNIQUE(user_id, promocode)
    )
    ''')
    
    conn.commit()
    conn.close()

def create_game_stats_table():
    """Создает таблицу для отслеживания проигранных сумм"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS game_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        game_type TEXT,
        bet_amount INTEGER,
        win_amount INTEGER,
        net_result INTEGER,
        played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    conn.commit()
    conn.close()

def create_bans_table():
    """Создает таблицу для банов"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE,
        username TEXT,
        first_name TEXT,
        reason TEXT DEFAULT 'Нарушение правил бота',
        banned_by INTEGER,
        banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

def init_db():
    """Инициализирует базу данных, создает таблицы если их нет"""
    create_users_table()
    create_withdraw_requests_table()
    create_promocodes_table()
    create_game_stats_table()
    create_bans_table()
    print("✅ База данных инициализирована")

def is_user_new(user_id):
    """Проверяет, есть ли пользователь в базе"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is None

def register_user(user_id, username, first_name):
    """Регистрирует нового пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR IGNORE INTO users (user_id, username, first_name, stars_balance) 
    VALUES (?, ?, ?, 0)
    ''', (user_id, username, first_name))
    conn.commit()
    conn.close()

def update_user_balance(user_id, amount):
    """Обновляет баланс пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users 
    SET stars_balance = stars_balance + ?, last_active = CURRENT_TIMESTAMP 
    WHERE user_id = ?
    ''', (amount, user_id))
    conn.commit()
    conn.close()

def get_user_profile(user_id):
    """Получает профиль пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT 
        user_id, 
        username, 
        first_name, 
        stars_balance, 
        total_deposit, 
        total_withdraw,
        total_games,
        last_active,
        registered_at
    FROM users 
    WHERE user_id = ?
    ''', (user_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def update_user_deposit(user_id, amount):
    """Обновляет общую сумму пополнений"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users 
    SET total_deposit = total_deposit + ?, last_active = CURRENT_TIMESTAMP 
    WHERE user_id = ?
    ''', (amount, user_id))
    conn.commit()
    conn.close()

def update_user_withdraw(user_id, amount):
    """Обновляет общую сумму выводов"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users 
    SET total_withdraw = total_withdraw + ?, last_active = CURRENT_TIMESTAMP 
    WHERE user_id = ?
    ''', (amount, user_id))
    conn.commit()
    conn.close()

def update_user_games_count(user_id):
    """Обновляет счетчик игр"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users 
    SET total_games = total_games + 1, last_active = CURRENT_TIMESTAMP 
    WHERE user_id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()

def is_user_banned(user_id):
    """Проверяет, забанен ли пользователь"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM bans WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    return bool(result)

def ban_user(user_id, username, first_name, reason, admin_id):
    """Банит пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR REPLACE INTO bans (user_id, username, first_name, reason, banned_by)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, reason, admin_id))
    
    conn.commit()
    conn.close()

def unban_user(user_id):
    """Разбанивает пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()

def get_ban_info(user_id):
    """Получает информацию о бане пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT user_id, username, first_name, reason, banned_by, banned_at 
    FROM bans 
    WHERE user_id = ?
    ''', (user_id,))
    
    ban = cursor.fetchone()
    conn.close()
    
    if ban:
        return {
            'user_id': ban[0],
            'username': ban[1],
            'first_name': ban[2],
            'reason': ban[3],
            'banned_by': ban[4],
            'banned_at': ban[5]
        }
    return None

def get_all_banned_users():
    """Получает список всех забаненных пользователей"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT user_id, username, first_name, reason, banned_by, banned_at 
    FROM bans 
    ORDER BY banned_at DESC
    ''')
    
    bans = cursor.fetchall()
    conn.close()
    
    result = []
    for ban in bans:
        result.append({
            'user_id': ban[0],
            'username': ban[1],
            'first_name': ban[2],
            'reason': ban[3],
            'banned_by': ban[4],
            'banned_at': ban[5]
        })
    
    return result

def search_user_by_name(name_part):
    """Ищет пользователя по части имени"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT user_id, username, first_name, stars_balance, 
           total_games, total_deposit, total_withdraw,
           registered_at, last_active
    FROM users 
    WHERE LOWER(first_name) LIKE LOWER(?)
    LIMIT 1
    ''', (f'%{name_part}%',))
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'user_id': user[0],
            'username': user[1],
            'first_name': user[2],
            'stars_balance': user[3],
            'total_games': user[4],
            'total_deposit': user[5],
            'total_withdraw': user[6],
            'registered_at': user[7],
            'last_active': user[8]
        }
    return None

def create_withdraw_request(user_id, amount):
    """Создает заявку на вывод"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO withdraw_requests (user_id, amount) 
    VALUES (?, ?)
    ''', (user_id, amount))
    conn.commit()
    request_id = cursor.lastrowid
    conn.close()
    return request_id

def get_withdraw_request(request_id):
    """Получает заявку на вывод"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT wr.*, u.username, u.first_name 
    FROM withdraw_requests wr
    LEFT JOIN users u ON wr.user_id = u.user_id
    WHERE wr.id = ?
    ''', (request_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def update_withdraw_request(request_id, status, admin_id):
    """Обновляет статус заявки на вывод"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE withdraw_requests 
    SET status = ?, processed_at = CURRENT_TIMESTAMP, processed_by = ?
    WHERE id = ?
    ''', (status, admin_id, request_id))
    conn.commit()
    conn.close()

def has_user_used_promo(user_id, promocode):
    """Проверяет, использовал ли пользователь промокод"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id FROM used_promocodes 
    WHERE user_id = ? AND promocode = ?
    ''', (user_id, promocode))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_promo_as_used(user_id, promocode):
    """Отмечает промокод как использованный"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR IGNORE INTO used_promocodes (user_id, promocode) 
    VALUES (?, ?)
    ''', (user_id, promocode))
    conn.commit()
    conn.close()

def get_user_by_id_or_username(identifier):
    """Находит пользователя по ID или username"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if identifier.isdigit():
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (int(identifier),))
    else:
        username = identifier.lstrip('@')
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def update_user_balance_by_admin(user_id, amount, operation_type):
    """Обновляет баланс пользователя от имени администратора"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if operation_type == "add":
        cursor.execute('''
        UPDATE users 
        SET stars_balance = stars_balance + ?, last_active = CURRENT_TIMESTAMP 
        WHERE user_id = ?
        ''', (amount, user_id))
    else:  # subtract
        cursor.execute('''
        UPDATE users 
        SET stars_balance = stars_balance - ?, last_active = CURRENT_TIMESTAMP 
        WHERE user_id = ?
        ''', (amount, user_id))
    
    cursor.execute('SELECT stars_balance FROM users WHERE user_id = ?', (user_id,))
    new_balance = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    return new_balance

def get_total_lost():
    """Рассчитывает общую сумму проигрыша всех пользователей"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT SUM(bet_amount - win_amount) as total_lost 
    FROM game_stats 
    WHERE net_result < 0
    ''')
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] or 0

def add_game_stat(user_id, game_type, bet_amount, win_amount, net_result):
    """Добавляет статистику игры"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO game_stats (user_id, game_type, bet_amount, win_amount, net_result)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, game_type, bet_amount, win_amount, net_result))
    conn.commit()
    conn.close()

def get_all_users_stats():
    """Получает статистику по всем пользователям"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT 
        COUNT(*) as total_users,
        SUM(stars_balance) as total_balance,
        SUM(total_deposit) as total_deposit,
        SUM(total_withdraw) as total_withdraw,
        SUM(total_games) as total_games
    FROM users
    ''')
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def get_active_users_count(days=7):
    """Получает количество активных пользователей за последние N дней"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT COUNT(*) as active_users
    FROM users 
    WHERE last_active >= datetime('now', ?)
    ''', (f'-{days} days',))
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else 0

def get_today_registrations():
    """Получает количество регистраций за сегодня"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT COUNT(*) as today_reg
    FROM users 
    WHERE DATE(registered_at) = DATE('now')
    ''')
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else 0

def get_pending_withdraws():
    """Получает количество и сумму ожидающих выводов"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT 
        COUNT(*) as count,
        SUM(amount) as total_amount
    FROM withdraw_requests 
    WHERE status = 'pending'
    ''')
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'count': row[0] or 0,
            'total_amount': row[1] or 0
        }
    return {'count': 0, 'total_amount': 0}

def get_user_balance(user_id):
    """Получает баланс пользователя"""
    profile = get_user_profile(user_id)
    return profile['stars_balance'] if profile else 0

def check_user_exists(user_id):
    """Проверяет существование пользователя"""
    return not is_user_new(user_id)

def update_user_last_active(user_id):
    """Обновляет время последней активности"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users 
    SET last_active = CURRENT_TIMESTAMP 
    WHERE user_id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()

def get_all_users():
    """Получает всех пользователей"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY registered_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_user(user_id):
    """Удаляет пользователя (только для админа)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM used_promocodes WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM withdraw_requests WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM game_stats WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def reset_user_stats(user_id):
    """Сбрасывает статистику пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users 
    SET total_games = 0, 
        total_deposit = 0, 
        total_withdraw = 0,
        stars_balance = 0,
        last_active = CURRENT_TIMESTAMP
    WHERE user_id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()

def get_user_game_stats(user_id):
    """Получает статистику игр пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT 
        game_type,
        COUNT(*) as games_played,
        SUM(bet_amount) as total_bet,
        SUM(win_amount) as total_win,
        SUM(net_result) as total_profit
    FROM game_stats 
    WHERE user_id = ?
    GROUP BY game_type
    ''', (user_id,))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_top_users_by_balance(limit=10):
    """Получает топ пользователей по балансу"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT user_id, username, first_name, stars_balance 
    FROM users 
    ORDER BY stars_balance DESC 
    LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_top_users_by_games(limit=10):
    """Получает топ пользователей по количеству игр"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT user_id, username, first_name, total_games 
    FROM users 
    ORDER BY total_games DESC 
    LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def backup_database(backup_file='casino_bot_backup.db'):
    """Создает резервную копию базы данных"""
    import shutil
    try:
        shutil.copy2(DB_NAME, backup_file)
        print(f"✅ Резервная копия создана: {backup_file}")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания резервной копии: {e}")
        return False
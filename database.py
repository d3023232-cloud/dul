"""Асинхронная база данных SQLite"""

import aiosqlite
import datetime
from typing import Optional, List, Dict, Any
from config import (
    START_COINS, DAILY_RECOVERY_LIMIT_DEFAULT, 
    DAILY_RECOVERY_LIMIT_VIP, RECOVERY_INTERVAL_SECONDS
)

DB_PATH = "duel_bot.db"


class Database:
    def __init__(self):
        self.db_path = DB_PATH

    async def init(self):
        """Инициализация таблиц"""
        async with aiosqlite.connect(self.db_path) as db:
            # Пользователи
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    balance_coins INTEGER DEFAULT {START_COINS},
                    balance_donate INTEGER DEFAULT 0,
                    is_vip INTEGER DEFAULT 0,
                    referral_code TEXT UNIQUE,
                    referred_by INTEGER DEFAULT NULL,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    duels_played INTEGER DEFAULT 0,
                    recoveries_today INTEGER DEFAULT 0,
                    last_recovery_time TIMESTAMP,
                    last_reset_date DATE,
                    subscribed_channel INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (referred_by) REFERENCES users(telegram_id)
                )
            """.format(START_COINS=START_COINS))

            # Дуэли
            await db.execute("""
                CREATE TABLE IF NOT EXISTS duels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    challenger_id INTEGER NOT NULL,
                    opponent_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    winner_id INTEGER,
                    bet INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (challenger_id) REFERENCES users(telegram_id),
                    FOREIGN KEY (opponent_id) REFERENCES users(telegram_id)
                )
            """)

            # Транзакции
            await db.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    type TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                )
            """)

            # Реферальные награды (чтобы не дублировать)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS referral_rewards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inviter_id INTEGER NOT NULL,
                    referral_id INTEGER NOT NULL,
                    duels_at_reward INTEGER DEFAULT 0,
                    rewarded INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(inviter_id, referral_id)
                )
            """)

            
            # Настройки экономики (динамические)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS economy_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Заполняем дефолтные значения если таблица пустая
            async with db.execute("SELECT COUNT(*) as c FROM economy_settings") as c:
                count = (await c.fetchone())["c"]

            if count == 0:
                defaults = [
                    ("max_coins", "99999", "Максимальный баланс монет у игрока"),
                    ("recovery_interval_minutes", "6", "Минут между восстановлениями при балансе 0"),
                    ("win_multiplier", "2", "Множитель выигрыша (ставка × множитель)"),
                    ("daily_recovery_limit_default", "5", "Лимит восстановлений в день (обычный)"),
                    ("daily_recovery_limit_vip", "15", "Лимит восстановлений в день (VIP)"),
                    ("start_coins", "10", "Стартовый баланс монет"),
                    ("duel_cost", "1", "Стоимость дуэли"),
                ]
                await db.executemany(
                    "INSERT OR IGNORE INTO economy_settings (key, value, description) VALUES (?, ?, ?)",
                    defaults
                )
            await db.commit()

    # === ПОЛЬЗОВАТЕЛИ ===

    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def create_user(self, telegram_id: int, username: str, first_name: str, 
                         referral_code: str, referred_by: Optional[int] = None, 
                         start_coins: int = 10):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (telegram_id, username, first_name, referral_code, referred_by, balance_coins)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (telegram_id, username, first_name, referral_code, referred_by, start_coins))
            await db.commit()

    async def update_username(self, telegram_id: int, username: str, first_name: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET username = ?, first_name = ? WHERE telegram_id = ?",
                (username, first_name, telegram_id)
            )
            await db.commit()

    async def set_subscribed(self, telegram_id: int, status: bool = True):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET subscribed_channel = ? WHERE telegram_id = ?",
                (1 if status else 0, telegram_id)
            )
            await db.commit()

    async def get_all_users(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_user_by_referral(self, referral_code: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE referral_code = ?", (referral_code,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    # === БАЛАНС ===

    async def add_coins(self, telegram_id: int, amount: int, description: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance_coins = balance_coins + ? WHERE telegram_id = ?",
                (amount, telegram_id)
            )
            await db.execute(
                "INSERT INTO transactions (user_id, type, amount, currency, description) VALUES (?, ?, ?, ?, ?)",
                (telegram_id, "add", amount, "coins", description)
            )
            await db.commit()

    async def remove_coins(self, telegram_id: int, amount: int, description: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance_coins = balance_coins - ? WHERE telegram_id = ?",
                (amount, telegram_id)
            )
            await db.execute(
                "INSERT INTO transactions (user_id, type, amount, currency, description) VALUES (?, ?, ?, ?, ?)",
                (telegram_id, "remove", amount, "coins", description)
            )
            await db.commit()

    async def add_donate(self, telegram_id: int, amount: int, description: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance_donate = balance_donate + ? WHERE telegram_id = ?",
                (amount, telegram_id)
            )
            await db.execute(
                "INSERT INTO transactions (user_id, type, amount, currency, description) VALUES (?, ?, ?, ?, ?)",
                (telegram_id, "add", amount, "donate", description)
            )
            await db.commit()

    async def remove_donate(self, telegram_id: int, amount: int, description: str = ""):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET balance_donate = balance_donate - ? WHERE telegram_id = ?",
                (amount, telegram_id)
            )
            await db.execute(
                "INSERT INTO transactions (user_id, type, amount, currency, description) VALUES (?, ?, ?, ?, ?)",
                (telegram_id, "remove", amount, "donate", description)
            )
            await db.commit()

    async def set_vip(self, telegram_id: int, status: bool = True):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET is_vip = ? WHERE telegram_id = ?",
                (1 if status else 0, telegram_id)
            )
            await db.commit()

    # === ВОССТАНОВЛЕНИЕ МОНЕТ ===

    async def get_recovery_limit(self, telegram_id: int) -> int:
        user = await self.get_user(telegram_id)
        if not user:
            return DAILY_RECOVERY_LIMIT_DEFAULT
        return DAILY_RECOVERY_LIMIT_VIP if user["is_vip"] else DAILY_RECOVERY_LIMIT_DEFAULT

    async def can_recover(self, telegram_id: int) -> bool:
        user = await self.get_user(telegram_id)
        if not user:
            return False
        if user["balance_coins"] != 0:
            return False

        limit = await self.get_recovery_limit(telegram_id)
        if user["recoveries_today"] >= limit:
            return False

        if user["last_recovery_time"]:
            last = datetime.datetime.fromisoformat(user["last_recovery_time"])
            now = datetime.datetime.now()
            recovery_min = await self.get_economy_setting_int("recovery_interval_minutes", 6)
            if (now - last).total_seconds() < recovery_min * 60:
                return False

        return True

    async def recover_coin(self, telegram_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.datetime.now().isoformat()
            await db.execute("""
                UPDATE users 
                SET balance_coins = balance_coins + ?, 
                    recoveries_today = recoveries_today + 1,
                    last_recovery_time = ?
                WHERE telegram_id = ?
            """, (RECOVERY_AMOUNT, now, telegram_id))
            await db.execute(
                "INSERT INTO transactions (user_id, type, amount, currency, description) VALUES (?, ?, ?, ?, ?)",
                (telegram_id, "recovery", RECOVERY_AMOUNT, "coins", "Восстановление при балансе 0")
            )
            await db.commit()

    async def reset_recovery_count(self, telegram_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET recoveries_today = 0 WHERE telegram_id = ?",
                (telegram_id,)
            )
            await db.commit()

    async def set_last_reset_date(self, telegram_id: int, date_str: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET last_reset_date = ? WHERE telegram_id = ?",
                (date_str, telegram_id)
            )
            await db.commit()

    # === СТАТИСТИКА ===

    async def add_win(self, telegram_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET wins = wins + 1, duels_played = duels_played + 1 WHERE telegram_id = ?",
                (telegram_id,)
            )
            await db.commit()

    async def add_loss(self, telegram_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET losses = losses + 1, duels_played = duels_played + 1 WHERE telegram_id = ?",
                (telegram_id,)
            )
            await db.commit()

    # === ДУЭЛИ ===

    async def create_duel(self, challenger_id: int, opponent_id: int, bet: int = 1) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO duels (challenger_id, opponent_id, bet, status) VALUES (?, ?, ?, ?)",
                (challenger_id, opponent_id, bet, "pending")
            )
            await db.commit()
            return cursor.lastrowid

    async def get_duel(self, duel_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM duels WHERE id = ?", (duel_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_duel_status(self, duel_id: int, status: str, winner_id: Optional[int] = None):
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.datetime.now().isoformat()
            await db.execute(
                "UPDATE duels SET status = ?, winner_id = ?, completed_at = ? WHERE id = ?",
                (status, winner_id, now, duel_id)
            )
            await db.commit()

    async def get_pending_duel_for_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM duels WHERE (challenger_id = ? OR opponent_id = ?) AND status = ? ORDER BY id DESC LIMIT 1",
                (telegram_id, telegram_id, "pending")
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    # === РЕФЕРАЛКА ===

    async def create_referral_reward(self, inviter_id: int, referral_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO referral_rewards (inviter_id, referral_id) VALUES (?, ?)",
                (inviter_id, referral_id)
            )
            await db.commit()

    async def update_referral_duels(self, referral_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE referral_rewards SET duels_at_reward = duels_at_reward + 1 WHERE referral_id = ? AND rewarded = 0",
                (referral_id,)
            )
            await db.commit()

    async def check_referral_reward(self, inviter_id: int, referral_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM referral_rewards WHERE inviter_id = ? AND referral_id = ? AND rewarded = 0",
                (inviter_id, referral_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row and row["duels_at_reward"] >= 18

    async def mark_referral_rewarded(self, inviter_id: int, referral_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE referral_rewards SET rewarded = 1 WHERE inviter_id = ? AND referral_id = ?",
                (inviter_id, referral_id)
            )
            await db.commit()

    async def get_referral_stats(self, telegram_id: int) -> Dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Количество рефералов
            async with db.execute(
                "SELECT COUNT(*) as count FROM users WHERE referred_by = ?", (telegram_id,)
            ) as cursor:
                total = (await cursor.fetchone())["count"]

            # Количество награжденных
            async with db.execute(
                "SELECT COUNT(*) as count FROM referral_rewards WHERE inviter_id = ? AND rewarded = 1",
                (telegram_id,)
            ) as cursor:
                rewarded = (await cursor.fetchone())["count"]

            return {"total": total, "rewarded": rewarded}




    # === АДМИН-ПАНЕЛЬ ===

    async def get_users_paginated(self, page: int = 0, per_page: int = 10) -> tuple:
        """Получить пользователей с пагинацией. Возвращает (список, общее_количество)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            offset = page * per_page

            async with db.execute(
                "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (per_page, offset)
            ) as cursor:
                rows = await cursor.fetchall()
                users = [dict(row) for row in rows]

            async with db.execute("SELECT COUNT(*) as total FROM users") as cursor:
                total = (await cursor.fetchone())["total"]

            return users, total

    async def search_users(self, query: str) -> list:
        """Поиск пользователей по ID, username или first_name"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            search = f"%{query}%"

            # Пробуем как ID
            try:
                telegram_id = int(query)
                async with db.execute(
                    "SELECT * FROM users WHERE telegram_id = ? OR username LIKE ? OR first_name LIKE ?",
                    (telegram_id, search, search)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
            except ValueError:
                async with db.execute(
                    "SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ?",
                    (search, search)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]

    async def get_user_transactions(self, telegram_id: int, limit: int = 50) -> list:
        """Получить транзакции пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (telegram_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_all_duels(self, limit: int = 50) -> list:
        """Получить все дуэли"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM duels ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def set_user_field(self, telegram_id: int, field: str, value):
        """Универсальное обновление поля пользователя (для админа)"""
        allowed_fields = [
            "balance_coins", "balance_donate", "is_vip", "is_banned",
            "wins", "losses", "duels_played", "recoveries_today", "subscribed_channel"
        ]
        if field not in allowed_fields:
            raise ValueError(f"Поле {field} недоступно для изменения")

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE users SET {field} = ? WHERE telegram_id = ?",
                (value, telegram_id)
            )
            await db.commit()

    async def ban_user(self, telegram_id: int, reason: str = ""):
        """Забанить пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET is_banned = 1 WHERE telegram_id = ?",
                (telegram_id,)
            )
            await db.execute(
                "INSERT INTO transactions (user_id, type, amount, currency, description) VALUES (?, ?, ?, ?, ?)",
                (telegram_id, "ban", 0, "system", f"Бан: {reason}")
            )
            await db.commit()

    async def unban_user(self, telegram_id: int):
        """Разбанить пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE users SET is_banned = 0 WHERE telegram_id = ?",
                (telegram_id,)
            )
            await db.commit()

    async def get_bot_stats(self) -> dict:
        """Статистика бота"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            stats = {}

            # Всего пользователей
            async with db.execute("SELECT COUNT(*) as c FROM users") as c:
                stats["total_users"] = (await c.fetchone())["c"]

            # VIP пользователей
            async with db.execute("SELECT COUNT(*) as c FROM users WHERE is_vip = 1") as c:
                stats["vip_users"] = (await c.fetchone())["c"]

            # Забаненных
            async with db.execute("SELECT COUNT(*) as c FROM users WHERE is_banned = 1") as c:
                stats["banned_users"] = (await c.fetchone())["c"]

            # Всего дуэлей
            async with db.execute("SELECT COUNT(*) as c FROM duels") as c:
                stats["total_duels"] = (await c.fetchone())["c"]

            # Завершённых дуэлей
            async with db.execute("SELECT COUNT(*) as c FROM duels WHERE status = 'completed'") as c:
                stats["completed_duels"] = (await c.fetchone())["c"]

            # Общий баланс монет
            async with db.execute("SELECT COALESCE(SUM(balance_coins), 0) as s FROM users") as c:
                stats["total_coins"] = (await c.fetchone())["s"]

            # Общий баланс DC
            async with db.execute("SELECT COALESCE(SUM(balance_donate), 0) as s FROM users") as c:
                stats["total_donate"] = (await c.fetchone())["s"]

            # Топ по победам
            async with db.execute(
                "SELECT telegram_id, first_name, username, wins FROM users ORDER BY wins DESC LIMIT 5"
            ) as c:
                stats["top_winners"] = [dict(row) for row in await c.fetchall()]

            return stats

    async def admin_log(self, admin_id: int, action: str, target_id: int, details: str = ""):
        """Логирование действий админа"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    target_id INTEGER,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute(
                "INSERT INTO admin_logs (admin_id, action, target_id, details) VALUES (?, ?, ?, ?)",
                (admin_id, action, target_id, details)
            )
            await db.commit()


    # === ДИНАМИЧЕСКАЯ ЭКОНОМИКА ===

    async def get_economy_setting(self, key: str, default: str = "") -> str:
        """Получить значение настройки экономики"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT value FROM economy_settings WHERE key = ?", (key,)
            ) as cursor:
                row = await cursor.fetchone()
                return row["value"] if row else default

    async def get_economy_setting_int(self, key: str, default: int = 0) -> int:
        """Получить значение как int"""
        val = await self.get_economy_setting(key, str(default))
        try:
            return int(val)
        except ValueError:
            return default

    async def set_economy_setting(self, key: str, value: str):
        """Установить значение настройки экономики"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.datetime.now().isoformat()
            await db.execute(
                "INSERT INTO economy_settings (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, value, now)
            )
            await db.commit()

    async def get_all_economy_settings(self) -> list:
        """Получить все настройки экономики"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM economy_settings ORDER BY key"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

db = Database()

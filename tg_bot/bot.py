import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingBot:
    def __init__(self, token: str, db_path: str = 'C:\\DataBase\\trading.db',
                 admin_ids: List[int] = None):
        """
        Инициализация бота

        Args:
            token: Токен бота от @BotFather
            db_path: Путь к базе данных с позициями
            admin_ids: Список ID администраторов
        """
        # Исправленная инициализация Bot
        self.bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        self.dp = Dispatcher()
        self.db_path = db_path
        self.admin_ids = admin_ids or []  # Список ID администраторов

        # Инициализируем базу данных для пользователей
        self.init_users_db()

        # Регистрируем обработчики
        self.register_handlers()

    def init_users_db(self):
        """Инициализация базы данных для пользователей бота"""
        os.makedirs('C:\\DataBase', exist_ok=True)

        users_db_path = 'C:\\DataBase\\bot_users.db'

        with sqlite3.connect(users_db_path) as conn:
            cursor = conn.cursor()

            # Таблица пользователей (всех, кто запустил бота)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_active BOOLEAN DEFAULT 1,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_notified TIMESTAMP
            )
            ''')

            # Таблица отправленных уведомлений
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position_id INTEGER,
                user_id INTEGER,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
            ''')

            conn.commit()

    def register_handlers(self):
        """Регистрация обработчиков команд"""

        @self.dp.message(Command("start"))
        async def cmd_start(message: Message):
            """Обработчик команды /start - регистрирует пользователя"""
            user_id = message.from_user.id
            username = message.from_user.username
            first_name = message.from_user.first_name
            last_name = message.from_user.last_name

            # Регистрируем пользователя
            self.add_user(user_id, username, first_name, last_name)

            welcome_text = (
                f"👋 <b>Привет, {first_name}!</b>\n\n"
                "<b>📋 Доступные команды:</b>\n"
                "/start - Перезапустить бота\n"
                "Теперь вы будете получать уведомления о всех новых позициях, "
            )

            await message.answer(welcome_text)

        @self.dp.message(Command("help"))
        async def cmd_help(message: Message):
            """Обработчик команды /help"""
            help_text = (
                "📚 <b>Справка по боту:</b>\n\n"
                "<b>Основные команды:</b>\n"
                "• <b>/start</b> - Запустить/перезапустить бота\n"
                "• <b>/help</b> - Эта справка\n\n"
            )

            await message.answer(help_text)

        @self.dp.message(Command("positions"))
        async def cmd_positions(message: Message):
            """Получить текущие позиции из базы данных"""
            try:
                from parsing.coin_price_parcing import get_bybit_futures_price
                positions = self.get_active_positions()
                print(positions)

                if not positions:
                    await message.answer("📭 Нет активных позиций в базе данных")
                    return

                # Отправляем позиции порциями (не более 10 за сообщение)
                chunk_size = 10
                for i in range(0, len(positions), chunk_size):
                    chunk = positions[i:i + chunk_size]

                    response = f"🎯 <b>Positions: (chunk: {i // chunk_size + 1}):</b>\n\n"

                    for j, pos in enumerate(chunk, i + 1):
                        pos_type = pos['pos_type']
                        list_current_price = get_bybit_futures_price(pos['name'])
                        current_price = list_current_price['last_price']
                        created_at_str = pos.get('created_at', '')

                        if created_at_str:
                            try:
                                # Пробуем разные форматы даты
                                if '.' in created_at_str:
                                    created_at_str = created_at_str.split('.')[0]

                                # Парсим строку в datetime
                                dt = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
                                # Форматируем: "время, число месяц"
                                created_at = dt.strftime("%d.%m %H:%M")
                            except Exception:
                                created_at = created_at_str  # Оставляем как есть в случае ошибки
                        else:
                            created_at = ''

                        ###
                        balance_percent = 0

                        entry_price = pos['entry_price']
                        percent = pos['percent']
                        cross = pos['cross']


                        if entry_price and current_price and cross:
                            try:
                                entry = float(entry_price)
                                current = float(current_price)
                                leverage = float(cross)
                                if pos_type == 'short':
                                    direction_multiplier = -1
                                else:  # long или по умолчанию
                                    direction_multiplier = 1

                                price_change_pct = ((current - entry) / entry) * 100 * direction_multiplier

                                position_share = float(percent) / 100 if percent else 0.01
                                balance_percent = round(price_change_pct * leverage * position_share, 2)

                            except Exception as e:
                                print(f"Ошибка расчёта: {e}")
                                balance_percent = 0
                        ###
                        response += (
                            f"{j}. <b>Name: {pos['name']}</b>\n\n"
                            f"   Type Long/Short: {pos_type.upper()}\n"
                            f"   Entry price: {entry_price} | Current price: {current_price}\n"
                            f"   Balance: {pos.get('percent')}% | Profit: {balance_percent}%\n"
                            f"   TP: {pos.get('take_profit')} | SL: {pos.get('stop_loss')}\n"
                            f"   Time created: {created_at}\n\n"
                        )

                    await message.answer(response)

            except Exception as e:
                logger.error(f"Error getting positions: {e}")
                await message.answer("❌ Ошибка при получении позиций")

        @self.dp.message(Command("users"))
        async def cmd_users(message: Message):
            """Статистика пользователей (только для админа)"""
            user_id = message.from_user.id

            # Проверка на админа
            if not self.is_admin(user_id):
                await message.answer("⛔ Эта команда доступна только администраторам")
                return

            users = self.get_all_users()

            if not users:
                await message.answer("📭 Нет зарегистрированных пользователей")
                return

            response = "👥 <b>ЗАРЕГИСТРИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ:</b>\n\n"

            for i, user in enumerate(users, 1):
                username = f"@{user['username']}" if user['username'] else "нет username"
                status = "✅" if user['is_active'] else "❌"

                # Форматируем дату
                started_at = user['started_at']
                if started_at and '.' in started_at:
                    started_at = started_at.split('.')[0]

                response += (
                    f"{i}. {status} <b>{user['first_name']}</b> {username}\n"
                    f"   ID: {user['user_id']}\n"
                    f"   📅 Зарегистрирован: {started_at}\n\n"
                )

            # Общая статистика
            total_users = len(users)
            active_users = sum(1 for u in users if u['is_active'])

            response += (
                f"📊 <b>Статистика:</b>\n"
                f"• Всего пользователей: {total_users}\n"
                f"• Активных: {active_users}\n"
                f"• Неактивных: {total_users - active_users}"
            )

            await message.answer(response)

        @self.dp.message(Command("notify_all"))
        async def cmd_notify_all(message: Message):
            """Отправить сообщение всем пользователям (только для админа)"""
            user_id = message.from_user.id

            # Проверка на админа
            if not self.is_admin(user_id):
                await message.answer("⛔ Эта команда доступна только администраторам")
                return

            # Получаем текст сообщения
            text_to_send = message.text.replace('/notify_all', '').strip()

            if not text_to_send:
                await message.answer(
                    "❌ Укажите текст сообщения после команды:\n"
                    "<code>/notify_all Ваш текст здесь</code>"
                )
                return

            # Отправляем всем пользователям
            result = await self.send_to_all_users(text_to_send)

            await message.answer(
                f"📢 <b>Рассылка завершена:</b>\n"
                f"• Отправлено: {result['sent']} пользователям\n"
                f"• Не отправлено: {result['failed']} пользователям\n"
                f"• Всего пользователей: {result['total']}"
            )

        @self.dp.message(Command("send_position"))
        async def cmd_send_position(message: Message):
            """Отправить конкретную позицию всем пользователям (только для админа)"""
            user_id = message.from_user.id

            # Проверка на админа
            if not self.is_admin(user_id):
                await message.answer("⛔ Эта команда доступна только администраторам")
                return

            # Получаем ID позиции из сообщения
            try:
                args = message.text.split()
                if len(args) < 2:
                    await message.answer(
                        "❌ Укажите ID позиции:\n"
                        "<code>/send_position 123</code>"
                    )
                    return

                position_id = int(args[1])
                position = self.get_position_by_id(position_id)

                if not position:
                    await message.answer(f"❌ Позиция с ID {position_id} не найдена")
                    return

                # Формируем сообщение о позиции
                pos_type = "📈 LONG" if position.get('pos_type') == 'long' else "📉 SHORT"
                created_at = position.get('created_at', '')
                if created_at and '.' in created_at:
                    created_at = created_at.split('.')[0]

                position_message = (
                    "🎯 <b>НОВАЯ ПОЗИЦИЯ:</b>\n\n"
                    f"<b>{position['name']}</b>\n"
                    f"• Тип: {pos_type}\n"
                    f"• Процент: {position.get('percent')}%\n"
                    f"• Take Profit: {position.get('take_profit')}\n"
                    f"• Stop Loss: {position.get('stop_loss')}\n"
                    f"• Пересечение: {position.get('cross', 'нет')}\n"
                    f"• Дата: {created_at}"
                )

                # Отправляем всем пользователям
                result = await self.send_to_all_users(position_message)

                await message.answer(
                    f"✅ Позиция отправлена:\n"
                    f"• Пользователям: {result['sent']}\n"
                    f"• Ошибок: {result['failed']}"
                )

            except ValueError:
                await message.answer("❌ ID позиции должен быть числом")
            except Exception as e:
                logger.error(f"Error sending position: {e}")
                await message.answer(f"❌ Ошибка: {e}")

        @self.dp.message()
        async def handle_other_messages(message: Message):
            """Обработка остальных сообщений"""
            if message.text:
                await message.answer(
                    "Не понимаю эту команду. Используйте /help для списка команд."
                )

    # ========== МЕТОДЫ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ ==========

    def add_user(self, user_id: int, username: str, first_name: str, last_name: str):
        """Добавить/обновить пользователя в базе"""
        try:
            users_db_path = 'C:\\DataBase\\bot_users.db'

            with sqlite3.connect(users_db_path) as conn:
                cursor = conn.cursor()

                # Проверяем, существует ли пользователь
                cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
                exists = cursor.fetchone()

                if exists:
                    # Обновляем данные существующего пользователя
                    cursor.execute('''
                    UPDATE users 
                    SET username = ?, first_name = ?, last_name = ?, is_active = 1 
                    WHERE user_id = ?
                    ''', (username, first_name, last_name, user_id))
                else:
                    # Добавляем нового пользователя
                    cursor.execute('''
                    INSERT INTO users (user_id, username, first_name, last_name, is_active)
                    VALUES (?, ?, ?, ?, 1)
                    ''', (user_id, username, first_name, last_name))

                conn.commit()
                logger.info(f"User {user_id} added/updated")

        except sqlite3.Error as e:
            logger.error(f"Error adding user {user_id}: {e}")

    def get_all_users(self) -> List[Dict]:
        """Получить всех пользователей"""
        try:
            users_db_path = 'C:\\DataBase\\bot_users.db'

            with sqlite3.connect(users_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                SELECT user_id, username, first_name, last_name, is_active, 
                       started_at, last_notified 
                FROM users 
                ORDER BY started_at DESC
                ''')

                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error getting users: {e}")
            return []

    def get_active_users(self) -> List[int]:
        """Получить ID активных пользователей"""
        try:
            with sqlite3.connect(self.users_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM users WHERE is_active = 1')
                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return []

    def get_active_positions(self) -> List[Dict]:
        """Получить активные позиции из trading.db"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                SELECT id, name, percent, cross, entry_price,take_profit, stop_loss, pos_type, created_at
                FROM positions 
                WHERE is_active = 1
                ORDER BY created_at DESC
                ''')

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    # ========== РАССЫЛКА ==========

    async def send_to_all_users(self, message: str) -> Dict[str, int]:
        """Отправить сообщение всем пользователям"""
        users = self.get_active_users()
        total = len(users)
        sent = 0
        failed = 0

        if not users:
            logger.warning("No active users to send message to")
            return {"total": 0, "sent": 0, "failed": 0}

        for user_id in users:
            try:
                await self.bot.send_message(chat_id=user_id, text=message)
                self.update_user_notification_time(user_id)
                sent += 1

                # Небольшая задержка
                await asyncio.sleep(0.05)

            except Exception as e:
                failed += 1
                error_msg = str(e).lower()

                if any(blocked_msg in error_msg for blocked_msg in ['blocked', 'forbidden']):
                    logger.warning(f"User {user_id} blocked the bot, deactivating")
                    self.deactivate_user(user_id)
                else:
                    logger.error(f"Failed to send to user {user_id}: {e}")

        logger.info(f"Message sent to {sent}/{total} users")
        return {"total": total, "sent": sent, "failed": failed}

    async def notify_new_position(self, position_data: Dict):
        """Уведомить о новой позиции"""
        try:
            pos_type = "📈 LONG" if position_data.get('pos_type') == 'long' else "📉 SHORT"

            message = (
                "🎯 <b>НОВАЯ ТОРГОВАЯ ПОЗИЦИЯ:</b>\n\n"
                f"<b>{position_data['name']}</b>\n"
                f"• Тип: {pos_type}\n"
                f"• Процент: {position_data.get('percent')}%\n"
                f"• Take Profit: {position_data.get('take_profit')}\n"
                f"• Stop Loss: {position_data.get('stop_loss')}\n"
                f"• Пересечение: {position_data.get('cross', 'нет')}\n\n"
                f"<i>Добавлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
            )

            result = await self.send_to_all_users(message)
            return result

        except Exception as e:
            logger.error(f"Error notifying new position: {e}")
            return {"total": 0, "sent": 0, "failed": 0}

    # ========== СЛУЖЕБНЫЕ МЕТОДЫ ==========

    def is_admin(self, user_id: int) -> bool:
        """Проверка на админа"""
        return user_id in self.admin_ids

    def update_user_notification_time(self, user_id: int):
        """Обновить время уведомления"""
        try:
            with sqlite3.connect(self.users_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                UPDATE users 
                SET last_notified = CURRENT_TIMESTAMP 
                WHERE user_id = ?
                ''', (user_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating notification time: {e}")

    def deactivate_user(self, user_id: int):
        """Деактивировать пользователя"""
        try:
            with sqlite3.connect(self.users_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET is_active = 0 WHERE user_id = ?', (user_id,))
                conn.commit()
                logger.info(f"User {user_id} deactivated")
        except Exception as e:
            logger.error(f"Error deactivating user: {e}")

    async def start(self):
        """Запуск бота"""
        logger.info("Starting bot polling...")
        await self.dp.start_polling(self.bot)

    async def stop(self):
        """Остановка бота"""
        logger.info("Stopping bot...")
        await self.bot.session.close()
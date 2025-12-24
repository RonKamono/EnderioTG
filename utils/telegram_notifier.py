"""
Модуль для отправки уведомлений в Telegram через настройки реестра
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import requests
from datetime import datetime
from typing import Dict
import asyncio
import aiohttp


def load_bot_config():
    """Загружает конфигурацию бота из реестра или .env"""
    try:
        # Пробуем загрузить из реестра
        from utils import config
        bot_token = config.TELEGRAM_BOT_TOKEN
        admin_ids = config.ADMIN_IDS

        if bot_token and bot_token.strip() and bot_token != "":
            print(f"✅ Токен бота загружен из реестра")
            return bot_token, admin_ids
        else:
            print("⚠️ Токен бота не найден в реестре, пробую .env...")

    except ImportError:
        print("⚠️ Модуль config не найден, использую .env")

    # Fallback к .env файлу
    possible_paths = [
        Path(__file__).parent.parent / '.env',  # utils/../.env
        Path.cwd() / '.env',  # Текущая директория
        Path.home() / '.env',  # Домашняя директория
    ]

    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            print(f"✅ Загружен .env: {env_path}")
            break

    token = os.getenv('TELEGRAM_BOT_TOKEN')
    admin_ids_str = os.getenv('ADMIN_IDS', '')
    admin_ids = [int(id.strip()) for id in admin_ids_str.split(',')] if admin_ids_str else []

    if not token:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN не найден ни в реестре, ни в .env")

    return token, admin_ids

class TelegramNotifier:
    def __init__(self, bot_token: str = None, admin_ids: list = None):
        if bot_token is None or admin_ids is None:
            self.bot_token, self.admin_ids = load_bot_config()
        else:
            self.bot_token = bot_token
            self.admin_ids = admin_ids

        self.users_db_path = None

        # Пытаемся получить путь к базе пользователей из настроек
        try:
            from utils import config
            if hasattr(config, 'BOT_USERS_DB') and config.BOT_USERS_DB:
                self.users_db_path = config.BOT_USERS_DB
                print(f"✅ Путь к базе пользователей из настроек: {self.users_db_path}")
        except ImportError:
            pass

        if not self.users_db_path:
            # Путь по умолчанию
            self.users_db_path = 'C:\\DataBase\\bot_users.db'

        print(f"📢 TelegramNotifier инициализирован")
        print(f"   Токен: {'✅' if self.bot_token else '❌'}")
        print(f"   Админы: {len(self.admin_ids) if self.admin_ids else 0}")
        print(f"   База пользователей: {self.users_db_path}")

    def has_valid_token(self) -> bool:
        """Проверяет, есть ли валидный токен"""
        return bool(self.bot_token and self.bot_token.strip() and self.bot_token != "")

    async def send_message_async(self, chat_id: int, message: str, parse_mode: str = "HTML") -> bool:
        """Асинхронная отправка сообщения"""
        if not self.has_valid_token():
            print("❌ Не указан токен бота для отправки сообщения")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': parse_mode,
            'disable_web_page_preview': False
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        print(f"✅ Сообщение отправлено в chat_id: {chat_id}")
                        return True
                    else:
                        error_text = await response.text()
                        print(f"❌ Ошибка отправки: {response.status} - {error_text}")
                        return False
        except Exception as e:
            print(f"❌ Ошибка сети при отправке сообщения: {e}")
            return False

    def send_message(self, chat_id: int, message: str, parse_mode: str = "HTML") -> bool:
        """Синхронная отправка сообщения"""
        if not self.has_valid_token():
            print("❌ Не указан токен бота для отправки сообщения")
            return False

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.send_message_async(chat_id, message, parse_mode))
        finally:
            loop.close()

    def send_position_notification(self, position_data: Dict):
        """Отправляет уведомление о новой позиции"""
        try:
            import sqlite3

            # Получаем пользователей из базы
            user_ids = self._get_user_ids()

            # Также отправляем админам
            if self.admin_ids:
                user_ids.extend(self.admin_ids)
                user_ids = list(set(user_ids))  # Убираем дубликаты

            if not user_ids:
                print("⚠️ Нет пользователей для отправки уведомления")
                return {'sent': 0, 'total': 0}

            # Формируем сообщение
            message = self._format_position_message(position_data)

            # Отправляем
            results = self._send_to_users(user_ids, message)

            print(f"📢 Уведомление отправлено {results['sent']}/{results['total']} пользователям")
            return results

        except Exception as e:
            print(f"❌ Ошибка отправки уведомления: {e}")
            return {'sent': 0, 'total': 0}

    def _get_user_ids(self):
        """Получает ID активных пользователей"""
        try:
            import sqlite3
            if not os.path.exists(self.users_db_path):
                print(f"⚠️ База пользователей не найдена: {self.users_db_path}")
                return []

            with sqlite3.connect(self.users_db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM users WHERE is_active = 1')
                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            print(f"⚠️ Ошибка получения пользователей: {e}")
            return []

    def _format_position_message(self, position_data: Dict) -> str:
        """Форматирует сообщение о позиции"""
        pos_type = "📈 LONG" if position_data.get('pos_type') == 'long' else "📉 SHORT"

        message = (
            f"🎯 <b>OPEN NEW POSITION</b>\n\n"
            f"<b>{position_data.get('name', 'N/A')}</b>\n"
            f"Type: {pos_type}\n"
            f"Cross: {position_data.get('cross', 'N/A')}\n"
            f"Percentage of balance: {position_data.get('percent', 'N/A')}%\n"
            f"Take Profit: {position_data.get('take_profit', 'N/A')}\n"
            f"Stop Loss: {position_data.get('stop_loss', 'N/A')}\n"
            f"<b>DON'T FORGET TO SEND A SCREEN OF THE POSITION</b>\n\n"
        )

        message += f"\n🕐 {position_data.get('created_at', datetime.now().strftime('%m-%d %H:%M'))}"

        return message

    def _format_close_message(self, close_data: Dict) -> str:
        """Форматирует сообщение о закрытии позиции"""
        id = close_data.get('id', '?')
        name = close_data.get('name', 'N/A')
        pos_type = close_data.get('pos_type', 'N/A')
        close_reason = close_data.get('close_reason', 'closed')
        final_pnl = close_data.get('final_pnl', 0)

        if close_reason == 'tp':
            emoji = "🎯"
            reason_text = "HIT TP"
            color_indicator = "🟢"
        else:
            emoji = "💥"
            reason_text = "HIT SL"
            color_indicator = "🔴"

        pnl_sign = "+" if final_pnl > 0 else ""
        pnl_color = "🟢" if final_pnl > 0 else "🔴" if final_pnl < 0 else "⚪"

        message = (
            f"{emoji} <b>POSITION CLOSE</b>\n\n"
            f"<b>{name.upper()}</b>\n"
            f"ID: {id} | {pos_type.upper()}\n"
            f"HIT: <b>{reason_text}</b>\n"
            f"Entry price: {close_data.get('entry_price', '?')}\n"
            f"Realise P/L: {pnl_color} <b>{pnl_sign}{final_pnl}%</b>\n\n"
            f"<i>Close: {close_data.get('closed_at', 'N/A')}</i>"
        )

        return message

    def _send_to_users(self, user_ids, message):
        """Отправляет сообщение пользователям"""
        sent = 0
        failed = 0

        for user_id in user_ids:
            try:
                if self.send_message(user_id, message):
                    sent += 1
                else:
                    failed += 1

                # Небольшая задержка
                import time
                time.sleep(0.1)

            except Exception as e:
                print(f"⚠️ Ошибка отправки пользователю {user_id}: {e}")
                failed += 1

        return {'total': len(user_ids), 'sent': sent, 'failed': failed}

# Глобальный экземпляр
_notifier = None

def get_notifier():
    """Возвращает экземпляр отправщика"""
    global _notifier
    if _notifier is None:
        try:
            _notifier = TelegramNotifier()
        except Exception as e:
            print(f"❌ Ошибка создания TelegramNotifier: {e}")
            # Создаем с пустыми данными
            _notifier = TelegramNotifier(bot_token="", admin_ids=[])
    return _notifier

def send_close_notification(close_data: Dict):
    """Отправляет уведомление о закрытии позиции"""
    try:
        notifier = get_notifier()

        # Проверяем токен
        if not notifier.has_valid_token():
            print("⚠️ Не удалось отправить уведомление о закрытии: токен бота не заполнен")
            print("   Заполните токен в настройках приложения")
            return {'sent': 0, 'total': 0}

        # Получаем пользователей из базы
        user_ids = notifier._get_user_ids()

        # Также отправляем админам
        if notifier.admin_ids:
            user_ids.extend(notifier.admin_ids)
            user_ids = list(set(user_ids))  # Убираем дубликаты

        if not user_ids:
            print("⚠️ Нет пользователей для отправки уведомления о закрытии")
            return {'sent': 0, 'total': 0}

        # Форматируем сообщение
        message = notifier._format_close_message(close_data)

        # Отправляем
        results = notifier._send_to_users(user_ids, message)

        print(f"📢 Уведомление о закрытии отправлено {results['sent']}/{results['total']} пользователям")
        return results

    except Exception as e:
        print(f"❌ Ошибка отправки уведомления о закрытии: {e}")
        return {'sent': 0, 'total': 0}

def send_position_notification(position_data: Dict):
    """Отправляет уведомление о позиции"""
    try:
        notifier = get_notifier()

        # Проверяем токен
        if not notifier.has_valid_token():
            print("⚠️ Не удалось отправить уведомление: токен бота не заполнен")
            print("   Заполните токен в настройках приложения")
            return {'sent': 0, 'total': 0}

        return notifier.send_position_notification(position_data)
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления: {e}")
        return {'sent': 0, 'total': 0}

def send_alert_notification(alert_data: Dict):
    """Отправляет уведомление о срабатывании алерта"""
    try:
        notifier = get_notifier()

        # Проверяем токен
        if not notifier.has_valid_token():
            print("⚠️ Не удалось отправить уведомление об алерте: токен бота не заполнен")
            return {'sent': 0, 'total': 0}

        name = alert_data.get('name', 'Unknown')
        target_price = alert_data.get('target_price', 0)
        current_price = alert_data.get('current_price', 0)
        condition = alert_data.get('condition', 'above')
        triggered_at = alert_data.get('triggered_at', datetime.now().strftime('%H:%M:%S'))

        condition_text = "выше" if condition == 'above' else "ниже"
        price_diff = current_price - target_price
        price_diff_percent = (price_diff / target_price) * 100

        diff_sign = "+" if price_diff >= 0 else ""

        message = (
            f"🎯 <b>Trigger price</b>\n\n"
            f"<b>{name}</b>\n"
            f"Trigger price: {current_price}\n"
            f"Time: {triggered_at}\n\n"
            f"<a href='https://www.bybit.com/trade/usdt/{name}'>Open Bybit</a>\n"
            f"<a href='https://www.binance.com/en/trade/{name.replace('USDT', '_USDT')}'>Open Binance</a>"
        )

        # Получаем пользователей из базы
        user_ids = notifier._get_user_ids()

        # Также отправляем админам
        if notifier.admin_ids:
            user_ids.extend(notifier.admin_ids)
            user_ids = list(set(user_ids))

        if not user_ids:
            print("⚠️ Нет пользователей для отправки уведомления об алерте")
            return {'sent': 0, 'total': 0}

        results = notifier._send_to_users(user_ids, message)

        print(f"📢 Уведомление об алерте отправлено {results['sent']}/{results['total']} пользователям")
        return results

    except Exception as e:
        print(f"❌ Ошибка отправки уведомления об алерте: {e}")
        return {'sent': 0, 'total': 0}

# Для обратной совместимости
if __name__ == "__main__":
    print("Тестирование модуля telegram_notifier...")
    notifier = get_notifier()
    print(f"Токен доступен: {notifier.has_valid_token()}")
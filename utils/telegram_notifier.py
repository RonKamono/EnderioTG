#!/usr/bin/env python3
"""
    Утилита для отправки уведомлений из основного приложения
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import requests
from datetime import datetime
from typing import Dict


def load_bot_token():
    """Загружает токен бота из .env"""
    # Ищем .env в разных местах
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
    if not token:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN не найден в .env")

    return token

class TelegramNotifier:
    def __init__(self, bot_token: str = None):
        self.bot_token = bot_token or load_bot_token()
        self.users_db_path = 'C:\\DataBase\\bot_users.db'

    def send_position_notification(self, position_data: Dict):
        """Отправляет уведомление о новой позиции"""
        try:
            import sqlite3

            # Получаем пользователей из базы
            user_ids = self._get_user_ids()

            if not user_ids:
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
        """Форматирует сообщение"""
        pos_type = "📈 LONG" if position_data.get('pos_type') == 'long' else "📉 SHORT"

        message = (
            f"🎯 <b>OPEN NEW POSITION</b>\n\n"
            f"<b>{position_data['name']}</b>\n"
            f"Type: {pos_type}\n"
            f"Cross: {position_data.get('cross')}\n"
            f"Percentage of balance : {position_data.get('percent')}%\n"
            f"Entry price: {position_data.get('entry_price')}\n"
            f"Take Profit: {position_data.get('take_profit')}\n"
            f"Stop Loss: {position_data.get('stop_loss')}\n"
            f"<b>DON'T FORGET TO SEND A SCREEN OF THE POSITION</b>\n\n"
        )

        message += f"\n🕐 {position_data.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"

        return message

    def _send_to_users(self, user_ids, message):
        """Отправляет сообщение пользователям"""
        sent = 0
        failed = 0

        for user_id in user_ids:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                payload = {
                    'chat_id': user_id,
                    'text': message,
                    'parse_mode': 'HTML'
                }

                response = requests.post(url, json=payload, timeout=10)

                if response.status_code == 200:
                    sent += 1
                else:
                    print(f"⚠️ Ошибка пользователю {user_id}: {response.text[:100]}")
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
        _notifier = TelegramNotifier()
    return _notifier

def send_close_notification(close_data: Dict):
    try:
        notifier = get_notifier()

        id = close_data.get('id', '?')
        name = close_data.get('name', 'N/A')
        pos_type = close_data.get('pos_type', 'N/A')
        close_reason = close_data.get('close_reason', 'closed')
        final_pnl = close_data.get('final_pnl', 0)
        entry_price = close_data.get('entry_price', '?')

        # Форматируем сообщение
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
            f"Entry price: {entry_price}\n"
            f"Realise P/L: {pnl_color} <b>{pnl_sign}{final_pnl}%</b>\n\n"
            f"<i>Close: {close_data.get('closed_at', 'N/A')}</i>"
        )

        # Отправляем всем пользователям
        return notifier._send_to_users(notifier._get_user_ids(), message)

    except Exception as e:
        print(f"❌ Ошибка отправки уведомления о закрытии: {e}")
        return {'sent': 0, 'total': 0}

def send_position_notification(position_data: Dict):
    """Отправляет уведомление о позиции"""
    try:
        notifier = get_notifier()
        return notifier.send_position_notification(position_data)
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления: {e}")
        return {'sent': 0, 'total': 0}
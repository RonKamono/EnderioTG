#!/usr/bin/env python3
"""
Утилита для отправки уведомлений о новых позициях
Используется из вашего приложения для добавления позиций
"""

import asyncio
from typing import Dict, Optional
import sys
import os

# Добавляем путь к модулю бота
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from bot import TradingBot
except ImportError:
    print("❌ Не удалось импортировать модуль бота")
    sys.exit(1)


class NotificationSender:
    def __init__(self, bot_token: str, admin_ids: list = None):
        """
        Инициализация отправителя уведомлений

        Args:
            bot_token: Токен бота
            admin_ids: Список ID администраторов
        """
        self.bot = TradingBot(bot_token, admin_ids=admin_ids)

    async def send_new_position(self, position_data: Dict):
        """
        Отправить уведомление о новой позиции всем пользователям

        Args:
            position_data: Данные позиции в формате:
                {
                    'name': 'Название',
                    'percent': 10,
                    'cross': 50,
                    'take_profit': 150.5,
                    'stop_loss': 145.0,
                    'pos_type': 'long'
                }
        """
        try:
            result = await self.bot.notify_new_position(position_data)

            print(f"📢 Уведомление отправлено:")
            print(f"   • Пользователям: {result.get('total', 0)}")
            print(f"   • Успешно: {result.get('sent', 0)}")
            print(f"   • Ошибок: {result.get('failed', 0)}")

            return result

        except Exception as e:
            print(f"❌ Ошибка при отправке уведомления: {e}")
            return {"total": 0, "sent": 0, "failed": 0}

    async def send_custom_message(self, message: str):
        """
        Отправить кастомное сообщение всем пользователям

        Args:
            message: Текст сообщения
        """
        try:
            result = await self.bot.send_to_all_users(message)

            print(f"📢 Сообщение отправлено:")
            print(f"   • Пользователям: {result.get('total', 0)}")
            print(f"   • Успешно: {result.get('sent', 0)}")
            print(f"   • Ошибок: {result.get('failed', 0)}")

            return result

        except Exception as e:
            print(f"❌ Ошибка при отправке сообщения: {e}")
            return {"total": 0, "sent": 0, "failed": 0}

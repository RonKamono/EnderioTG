#!/usr/bin/env python3
"""
Запуск телеграм-бота для уведомлений о торговых позициях
"""

import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Добавляем путь к папке с ботом
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot import TradingBot


def load_config():
    """Загружает конфигурацию из .env файла"""
    # Определяем путь к .env файлу
    env_path = Path(__file__).parent.parent / '.env'  # tg_bot/../.env

    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"✅ Загружен .env файл: {env_path}")
    else:
        # Проверяем в текущей директории
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            print(f"✅ Загружен .env файл: {env_path}")
        else:
            print("⚠️ .env файл не найден, использую переменные окружения")

    # Получаем токен из .env
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')

    if not bot_token:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN не найден в .env файле или переменных окружения")

    # Получаем ID администраторов
    admin_ids_str = os.getenv('ADMIN_IDS', '')
    if admin_ids_str:
        try:
            admin_ids = [int(id.strip()) for id in admin_ids_str.split(',')]
        except ValueError:
            print(f"⚠️ Неверный формат ADMIN_IDS: {admin_ids_str}")
            admin_ids = []
    else:
        admin_ids = []

    return bot_token, admin_ids


async def bot():
    """Основная функция запуска бота"""

    try:
        # Загружаем конфигурацию
        BOT_TOKEN, ADMIN_IDS = load_config()

        print("=" * 50)
        print("🤖 Торговый бот для уведомлений")
        print("=" * 50)
        print(f"Токен: {BOT_TOKEN[:10]}...")
        print(f"Admin IDs: {ADMIN_IDS}")
        print("=" * 50)

        # Проверяем токен
        if not BOT_TOKEN or ':' not in BOT_TOKEN:
            print("❌ ОШИБКА: Неверный формат токена!")
            print("Токен должен быть вида: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
            return

        # Создаем экземпляр бота
        bot = TradingBot(token=BOT_TOKEN, admin_ids=ADMIN_IDS)

        print("✅ Бот инициализирован")
        print("📢 Бот запущен. Отправьте /start в Telegram")
        print("=" * 50)

        try:
            # Запускаем бота
            await bot.start()
        except KeyboardInterrupt:
            print("\n🛑 Бот остановлен пользователем")
        except Exception as e:
            print(f"\n❌ Ошибка при работе бота: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await bot.stop()

    except ValueError as e:
        print(f"\n❌ Ошибка конфигурации: {e}")
        print("\nУбедитесь, что:")
        print("1. В корне проекта есть файл .env")
        print("2. В .env есть строка: TELEGRAM_BOT_TOKEN=ваш_токен")
        print("3. Токен получен от @BotFather")
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Запускаем асинхронную функцию
    asyncio.run(bot())
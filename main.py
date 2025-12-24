import asyncio
import sys
import os
import threading
from pathlib import Path
from dotenv import load_dotenv
import flet as ft
from settings.window_settings import WindowSettings
from settings.colors import Colors
import pages

try:
    from utils import config
    from utils.registry_config import RegistryConfig

    USE_REGISTRY = True
except ImportError as e:
    print(f"⚠️ Модули реестра не найдены: {e}")
    print("📁 Проверьте наличие файлов в папке utils:")
    print("   - utils/config.py")
    print("   - utils/registry_config.py")
    USE_REGISTRY = False

#Функции для работы с настройками
def initialize_registry():
    """Инициализирует реестр с пустыми настройками при первом запуске"""
    if not USE_REGISTRY:
        return None

    try:
        registry = RegistryConfig(company_name="Enderio", app_name="TradingBot")
        # Проверяем, есть ли уже настройки в реестре
        current_settings = registry.get_all_values()

        if not current_settings:
            print("📝 Первый запуск: создаю пустые настройки в реестре Windows")
            # Создаем пустые настройки
            defaults = {
                'telegram_bot_token': "",
                'admin_ids': [],
                'api_url': "http://localhost:8000",
                'db_path': "",
                'bot_users_db': "",
                'auto_start': False,
                'update_interval': 60,
                'enable_logging': True,
                'log_level': "INFO",
            }

            for key, value in defaults.items():
                registry.set_value(key, value)

            print(f"✅ Создано {len(defaults)} пустых настроек в реестре")
        else:
            print(f"✅ Загружено {len(current_settings)} настроек из реестра Windows")

        return registry
    except Exception as e:
        print(f"⚠️ Ошибка инициализации реестра: {e}")
        return None

def load_config():
    """Загружает конфигурацию из реестра или .env файла"""

    if USE_REGISTRY:
        # Используем реестр
        print("📋 Использую настройки из реестра Windows")

        # Проверяем, заполнены ли обязательные поля
        bot_token = config.TELEGRAM_BOT_TOKEN
        admin_ids = config.ADMIN_IDS

        if not bot_token or not admin_ids:
            print("⚠️ Важные настройки не заполнены в реестре")
            print("   Заполните их в настройках приложения")

        return bot_token, admin_ids
    else:
        # Используем .env файл (обратная совместимость)
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            print(f"✅ Загружен .env: {env_path}")
        else:
            print("⚠️ .env файл не найден")

        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(',')] if admin_ids_str else []

        return bot_token, admin_ids

def check_settings_status():
    """Проверяет статус настроек и выводит информацию"""
    if USE_REGISTRY:
        print("\n📊 Статус настроек:")
        print("-" * 30)

        settings = config.get_all_settings()
        required_filled = 0
        total_required = 3  # Бот токен, админы, путь к БД

        if settings.get('telegram_bot_token'):
            print("✅ Токен бота: заполнен")
            required_filled += 1
        else:
            print("❌ Токен бота: НЕ заполнен")

        if settings.get('admin_ids'):
            print(f"✅ ID администраторов: {len(settings['admin_ids'])} шт.")
            required_filled += 1
        else:
            print("❌ ID администраторов: НЕ заполнены")

        if settings.get('db_signals'):
            print(f"✅ Путь к БД: {settings['db_signals']}")
            required_filled += 1
        else:
            print("❌ БД НЕТУ")

        print("-" * 30)
        print(f"📈 Заполнено: {required_filled}/{total_required} обязательных полей")

        if required_filled < total_required:
            print("💡 Заполните недостающие настройки через меню приложения")
    else:
        print("ℹ️ Используется .env файл для настроек")


# Функции для запуска бота
def initialize_bot():
    """Инициализирует и возвращает объект TradingBot если возможно"""
    # Добавляем путь к папке с ботом
    script_dir = Path(__file__).parent
    bot_dir = script_dir / 'tg_bot'

    if bot_dir.exists():
        sys.path.insert(0, str(bot_dir))
        print(f"✅ Добавлен путь к боту: {bot_dir}")
    else:
        print(f"⚠️ Папка бота не найдена: {bot_dir}")
        return None

    try:
        from tg_bot.bot import TradingBot
        print("✅ Модуль TradingBot успешно импортирован")

        BOT_TOKEN, ADMIN_IDS = load_config()

        # Проверяем, заполнен ли токен
        if not BOT_TOKEN:
            print("❌ TELEGRAM_BOT_TOKEN не найден")
            print("   Заполните его в настройках приложения")
            # Создаем бота с пустым токеном - используем временный токен для инициализации
            try:
                # Пытаемся создать бота с фиктивным токеном
                trading_bot = TradingBot(token="dummy_token_placeholder", admin_ids=ADMIN_IDS)
                trading_bot.has_valid_token = False
                trading_bot.is_demo_mode = True
                print("✅ TradingBot создан (в демо-режиме, без валидного токена)")
                return trading_bot
            except Exception as e:
                print(f"⚠️ Не удалось создать TradingBot в демо-режиме: {e}")

                # Создаем заглушку для UI
                class DummyTradingBot:
                    def __init__(self):
                        self.has_valid_token = False
                        self.is_demo_mode = True
                        self.database = None
                        self.is_running = False

                    def start(self):
                        print("⚠️ Бот не запущен: не указан токен")

                    def update_bot_token(self, new_token):
                        print(f"Токен обновлен: {new_token}")

                    def send_message_to_admin(self, message):
                        print(f"Демо-режим: сообщение для админа: {message}")

                dummy_bot = DummyTradingBot()
                print("✅ Создан демо-режим TradingBot (UI будет работать)")
                return dummy_bot

        # Если токен есть, создаем нормальный бот
        trading_bot = TradingBot(token=BOT_TOKEN, admin_ids=ADMIN_IDS)
        trading_bot.has_valid_token = True
        trading_bot.is_demo_mode = False
        print("✅ TradingBot создан с валидным токеном")
        return trading_bot
    except ImportError as e:
        print(f"❌ Ошибка импорта TradingBot: {e}")
        return None
    except Exception as e:
        print(f"❌ Ошибка создания TradingBot: {e}")
        return None

async def run_bot():
    """Основная функция для запуска бота"""
    try:
        BOT_TOKEN, ADMIN_IDS = load_config()
        if not BOT_TOKEN:
            print("❌ TELEGRAM_BOT_TOKEN не найден")
            print("   Бот не запущен. Заполните токен в настройках и перезапустите приложение.")
            return

        # Добавляем путь к папке с ботом
        script_dir = Path(__file__).parent
        bot_dir = script_dir / 'tg_bot'

        if bot_dir.exists():
            sys.path.insert(0, str(bot_dir))
        else:
            print(f"⚠️ Папка бота не найдена: {bot_dir}")
            return

        try:
            from tg_bot.bot import TradingBot
        except ImportError as e:
            print(f"❌ Ошибка импорта TradingBot: {e}")
            return

        bot = TradingBot(token=BOT_TOKEN, admin_ids=ADMIN_IDS)
        await bot.start()
    except Exception as e:
        print(f"❌ Ошибка в боте: {e}")

def start_bot_in_thread():
    """Запускает бота в отдельном потоке В ПОСЛЕДНЮЮ ОЧЕРЕДЬ"""

    BOT_TOKEN, ADMIN_IDS = load_config()

    # Проверяем, есть ли токен для запуска бота
    if not BOT_TOKEN:
        print("⚠️ Бот не запущен: токен не заполнен")
        print("   Заполните токен в настройках приложения")
        return None

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_bot())

    bot_thread = threading.Thread(target=run, daemon=True)
    bot_thread.start()
    print("🤖 Telegram бот запущен в фоновом режиме (запущен последним)")
    return bot_thread


def main(page: ft.Page):
    # Работа с загрузкой настроек
    initialize_registry()
    check_settings_status()

    # load App settings
    ws = WindowSettings()
    cl = Colors()

    # Page settings
    page.window.height = ws.height
    page.window.width = ws.width
    page.title = 'Trade Panel'
    page.padding = 0
    page.window.center()
    page.window.frameless = True
    page.bgcolor = cl.color_bg

    # Работа с ТГ БОТОМ
    trading_bot = initialize_bot()

    # Create AppWindow | AppBar
    app_view = pages.AppWindow(page, cl, trading_bot)
    app_bar = pages.AppBarTop(page, cl)  # Передаем trading_bot в AppBarTop
    top_appbar = app_bar.top_appbar

    # create main container
    main_container = app_view.app_page

    # Добавляем на страницу
    page.add(
        ft.Column(
            expand=True,
            controls=[
                top_appbar,
                main_container
            ],
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )

    page.update()

    # Запускаем бота в отдельном потоке только если токен заполнен
    bot_thread = start_bot_in_thread()
    page.bot_thread = bot_thread

    print("\n💡 Для изменения настроек нажмите на иконку настроек (шестеренка) в правом верхнем углу")


if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Запуск Trade Panel")
    print("=" * 50)

    # Инициализируем реестр ДО запуска приложения
    registry = initialize_registry()

    if registry:
        settings = registry.get_all_values()
        if not settings:
            print("\n🎯 Это первый запуск приложения")
            print("📍 Настройки будут храниться в реестре Windows")
            print("📍 Заполните их в приложении через меню настроек")
        else:
            print(f"\n📁 Используется {len(settings)} настроек из реестра Windows")

    import time

    time.sleep(0.1)  # Минимальная задержка

    # Запускаем Flet приложение
    ft.app(main)

    print("\n👋 Приложение закрыто")
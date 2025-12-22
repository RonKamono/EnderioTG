#!/usr/bin/env python3
"""
Запуск телеграм-бота для уведомлений о торговых позициях
"""

import asyncio
import sys
import os
import threading
from pathlib import Path
from dotenv import load_dotenv
import flet as ft
from settings.window_settings import WindowSettings
from settings.colors import Colors

# Добавляем путь к папке с ботом
script_dir = Path(__file__).parent
bot_dir = script_dir / 'tg_bot'

if bot_dir.exists():
    sys.path.insert(0, str(bot_dir))
    print(f"✅ Добавлен путь к боту: {bot_dir}")
else:
    print(f"⚠️ Папка бота не найдена: {bot_dir}")

try:
    from tg_bot.bot import TradingBot

    print("✅ Модуль TradingBot успешно импортирован")
except ImportError as e:
    print(f"❌ Ошибка импорта TradingBot: {e}")
    TradingBot = None


def load_config():
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


async def run_bot():
    try:
        BOT_TOKEN, ADMIN_IDS = load_config()
        if not BOT_TOKEN:
            return

        bot = TradingBot(token=BOT_TOKEN, admin_ids=ADMIN_IDS)
        await bot.start()
    except Exception as e:
        print(f"❌ Ошибка в боте: {e}")


def start_bot_in_thread():
    if TradingBot is None:
        return None

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_bot())

    bot_thread = threading.Thread(target=run, daemon=True)
    bot_thread.start()
    print("🤖 Telegram бот запущен в фоновом режиме")
    return bot_thread


### ОСНОВНОЕ ИСПРАВЛЕНИЕ: импортируем AppWindow из pages, а не создаем здесь
import pages


def main(page: ft.Page):
    # Запускаем телеграм бота
    bot_thread = start_bot_in_thread()

    # Создаем экземпляр TradingBot для UI
    trading_bot = None
    if TradingBot is not None:
        try:
            BOT_TOKEN, ADMIN_IDS = load_config()
            if BOT_TOKEN:
                trading_bot = TradingBot(token=BOT_TOKEN, admin_ids=ADMIN_IDS)
                print("✅ TradingBot создан для UI интеграции")
        except Exception as e:
            print(f"⚠️ Ошибка создания TradingBot: {e}")

    # Настройки
    ws = WindowSettings()
    cl = Colors()

    # СОЗДАЕМ AppWindow из папки pages и передаем trading_bot
    app_view = pages.AppWindow(page, cl, trading_bot)

    # Получаем AppBar из pages (если он есть там)
    # Если нет - можно создать заглушку или убрать
    try:
        app_bar = pages.AppBarTop(page, cl)
        top_appbar = app_bar.top_appbar
    except:
        # Создаем простой AppBar если его нет в pages
        top_appbar = ft.AppBar(
            title=ft.Text("Trading Bot"),
            bgcolor=cl.surface
        )

    # Настройки страницы
    page.window.height = ws.height
    page.window.width = ws.width
    page.title = 'Telegram Signal'
    page.padding = 0
    page.window.center()
    page.window.frameless = True
    page.bgcolor = cl.color_bg

    # Получаем контейнер приложения из app_view
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
            spacing=40
        )
    )


if __name__ == "__main__":
    ft.app(main)
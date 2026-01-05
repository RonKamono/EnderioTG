import sys
import os
from pathlib import Path

import flet as ft

from dotenv import load_dotenv
load_dotenv(override=True)

from settings.window_settings import WindowSettings
from settings.colors import Colors
import pages


# ===== Registry / Config =====
try:
    from utils import config
    from utils.registry_config import RegistryConfig
    USE_REGISTRY = True
    BASE_DIR = Path(__file__).resolve().parent
except ImportError as e:
    print(f"⚠️ Registry disabled: {e}")
    USE_REGISTRY = False

def initialize_registry():
    if not USE_REGISTRY:
        return None

    try:
        registry = RegistryConfig(company_name="Enderio", app_name="TradingBot")
        if not registry.get_all_values():
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
            for k, v in defaults.items():
                registry.set_value(k, v)
        return registry
    except Exception as e:
        print(f"❌ Registry init failed: {e}")
        return None

def load_config():
    if USE_REGISTRY:
        return config.TELEGRAM_BOT_TOKEN, config.ADMIN_IDS

    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)

    token = os.getenv('TELEGRAM_BOT_TOKEN')
    admins = os.getenv('ADMIN_IDS', '')
    admin_ids = [int(x.strip()) for x in admins.split(',')] if admins else []

    return token, admin_ids

def initialize_bot():
    script_dir = Path(__file__).parent
    bot_dir = script_dir / 'tg_bot'

    if not bot_dir.exists():
        print("❌ tg_bot directory not found")
        return None

    sys.path.insert(0, str(bot_dir))

    from tg_bot.bot import TradingBot

    token, admins = load_config()

    if not token:
        print("⚠️ Bot token missing → demo mode")
        bot = TradingBot(token="demo", admin_ids=admins)
        bot.has_valid_token = False
        return bot

    bot = TradingBot(token=token, admin_ids=admins)
    bot.has_valid_token = True
    return bot


class App:
    def __init__(self):
        self.trading_bot = None
        self.page: ft.Page | None = None
        self.main_container = ft.Container(expand=True)

    def main(self, page: ft.Page):
        self.page = page
        initialize_registry()

        ws = WindowSettings()
        cl = Colors()

        page.window.icon = str(BASE_DIR / "terminal_icon.ico")
        self.trading_bot = initialize_bot()

        page.window.height = ws.height
        page.window.width = ws.width
        page.window.center()
        page.window.frameless = True
        page.padding = 0
        page.title = "Trade Panel"
        page.bgcolor = cl.color_bg

        app_bar = pages.AppBarTop(page, cl, on_tab_change=self.change_tab)

        # стартовая страница
        terminal_page = pages.TerminalPage(page, cl, self.trading_bot)
        self.main_container.content = terminal_page.app_page

        page.add(
            ft.Column(
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    app_bar.top_appbar,
                    self.main_container
                ], spacing=0
            )
        )

        if self.trading_bot and self.trading_bot.has_valid_token:
            page.run_task(self.trading_bot.start)


    def change_tab(self, tab_name: str):
        print(f"Switch tab → {tab_name}")

        if not self.page:
            return

        if tab_name == "terminal":
            view = pages.TerminalPage(self.page, Colors(), self.trading_bot)
            self.main_container.content = view.app_page

        elif tab_name == "database":
            view = pages.DatabasePage(self.page, Colors())
            self.main_container.content = view.app_page

        else:
            self.main_container.content = ft.Text(
                f"Unknown tab: {tab_name}",
                color=ft.Colors.RED
            )



if __name__ == "__main__":
    ft.app(target=App().main)

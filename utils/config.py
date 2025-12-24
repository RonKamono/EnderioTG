"""
Конфигурация приложения с использованием реестра Windows
"""

import os
from pathlib import Path

try:
    from .registry_config import RegistryConfig
    USE_REGISTRY = True
except ImportError:
    USE_REGISTRY = False

# Инициализация реестра
if USE_REGISTRY:
    registry = RegistryConfig(company_name="Enderio", app_name="Trading Panel")
else:
    registry = None


def get_app_data_folder():

    local_appdata = os.getenv('LOCALAPPDATA')
    if not local_appdata:
        # Если переменной нет, используем стандартный путь
        local_appdata = os.path.join(os.path.expanduser('~'), 'AppData', 'Local')

    # Создаем путь к нашей папке
    app_folder = Path(local_appdata) / 'Enderio' / 'TradingBot'

    # Создаем папки, если их нет
    app_folder.mkdir(parents=True, exist_ok=True)

    return str(app_folder)


def get_default_db_path():
    """Получить путь к базе данных по умолчанию"""
    return str(Path(get_app_data_folder()) / 'trading.db')


def get_default_users_db_path():
    """Получить путь к базе данных пользователей по умолчанию"""
    return str(Path(get_app_data_folder()) / 'bot_users.db')

def get_setting(key, default=""):
    """Получить настройку из реестра"""
    if USE_REGISTRY and registry:
        return registry.get_value(key, default)
    else:
        # Fallback к .env файлу
        env_value = os.getenv(key.upper())
        if env_value is not None:
            return env_value
        return default

def get_setting_list(key, default=None):
    """Получить настройку-список из реестра"""
    if default is None:
        default = []

    if USE_REGISTRY and registry:
        value = registry.get_value(key, default)
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            try:
                return [item.strip() for item in value.split(',')]
            except:
                return default
        return default
    else:
        # Fallback к .env файлу
        env_value = os.getenv(key.upper())
        if env_value:
            return [item.strip() for item in env_value.split(',')]
        return default

# Настройки приложения
TELEGRAM_BOT_TOKEN = get_setting('telegram_bot_token', "") # 8218318461:AAE6t5wlDAI9wu0bpst6iNt6Ec6Ir1k8xpo
ADMIN_IDS = get_setting_list('admin_ids', []) # 7594592988
API_URL = get_setting('api_url', "http://localhost:8000")

# БАЗЫ ДАННЫХ В APPDATA/LOCAL (скрыто от пользователя)
DB_PATH = get_setting('db_path', get_default_db_path())
BOT_USERS_DB = get_setting('bot_users_db', get_default_users_db_path())

AUTO_START = get_setting('auto_start', False)
UPDATE_INTERVAL = get_setting('update_interval', 60)
ENABLE_LOGGING = get_setting('enable_logging', True)
LOG_LEVEL = get_setting('log_level', "INFO")

# Глобальные переменные для обновления
_settings_cache = {
    'telegram_bot_token': TELEGRAM_BOT_TOKEN,
    'admin_ids': ADMIN_IDS,
    'api_url': API_URL,
    'db_path': DB_PATH,
    'bot_users_db': BOT_USERS_DB,
    'auto_start': AUTO_START,
    'update_interval': UPDATE_INTERVAL,
    'enable_logging': ENABLE_LOGGING,
    'log_level': LOG_LEVEL,
}

# Функции для работы с настройками
def update_setting(key, value):
    """Обновить настройку в реестре"""
    if USE_REGISTRY and registry:
        success = registry.set_value(key, value)
        if success:
            # Обновляем глобальные переменные
            global_vars = globals()
            if key in ['telegram_bot_token', 'api_url', 'db_signals', 'bot_users_db', 'log_level']:
                global_vars[key.upper()] = value
            elif key == 'admin_ids':
                global_vars['ADMIN_IDS'] = value
            elif key == 'auto_start':
                global_vars['AUTO_START'] = value
            elif key == 'update_interval':
                global_vars['UPDATE_INTERVAL'] = value
            elif key == 'enable_logging':
                global_vars['ENABLE_LOGGING'] = value

        return success
    return False

def get_all_settings():
    """Получить все текущие настройки"""
    return {
        'telegram_bot_token': TELEGRAM_BOT_TOKEN,
        'admin_ids': ADMIN_IDS,
        'api_url': API_URL,
        'db_signals': DB_PATH,
        'bot_users_db': BOT_USERS_DB,
        'auto_start': AUTO_START,
        'update_interval': UPDATE_INTERVAL,
        'enable_logging': ENABLE_LOGGING,
        'log_level': LOG_LEVEL,
    }

def reset_settings():
    """Сбросить все настройки к пустым значениям"""
    if not USE_REGISTRY or not registry:
        return False

    defaults = {
        'telegram_bot_token': "",
        'admin_ids': [],
        'api_url': "http://localhost:8000",
        'db_path': get_default_db_path(),  # Используем путь по умолчанию
        'bot_users_db': get_default_users_db_path(),  # Используем путь по умолчанию
        'auto_start': False,
        'update_interval': 60,
        'enable_logging': True,
        'log_level': "INFO",
    }

    success = True
    for key, value in defaults.items():
        if not update_setting(key, value):
            success = False

    return success

def show_app_data_info():
    """Показать информацию о расположении данных"""
    app_folder = get_app_data_folder()
    print(f"📁 Папка данных приложения: {app_folder}")
    print(f"   База данных: {Path(app_folder) / 'trading.db'}")
    print(f"   База пользователей: {Path(app_folder) / 'bot_users.db'}")

    # Проверяем существование папки
    if os.path.exists(app_folder):
        print(f"   ✅ Папка существует")
    else:
        print(f"   ❌ Папка не существует (будет создана при первом использовании)")

# Для обратной совместимости с кодом, который использует load_dotenv
def load_dotenv():
    """Заглушка для обратной совместимости"""
    if USE_REGISTRY:
        print("✅ Настройки загружены из реестра Windows")
    else:
        print("✅ Настройки загружены из .env файла")
    return True


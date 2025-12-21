

import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Токен бота (получите у @BotFather)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'ВАШ_ТОКЕН_БОТА')

# ID администраторов (ваш Telegram ID)
ADMIN_IDS = [
    7594592988,  # Замените на ваш ID
]

# URL для API (если используется веб-сервер)
API_URL = os.getenv('TELEGRAM_API_URL', 'http://localhost:8000')

# Настройки базы данных
DB_PATH = 'C:\\DataBase\\trading.db'
BOT_USERS_DB = 'C:\\DataBase\\bot_users.db'
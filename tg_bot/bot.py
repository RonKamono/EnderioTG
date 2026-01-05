import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from datetime import datetime
from typing import List, Dict
from utils.trading_db_postgres import TradingDBPostgres

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingBot:
    def __init__(self, token: str, admin_ids: List[int] = None):
        self.bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )

        self.db = TradingDBPostgres()

        self.dp = Dispatcher()
        self.admin_ids = admin_ids or []
        self.register_handlers()

    # ==========================
    # ASYNC DB HELPER
    # ==========================

    async def _db(self, func, *args):
        return await asyncio.to_thread(func, *args)

    # ==========================
    # HANDLERS
    # ==========================

    def register_handlers(self):

        @self.dp.message(Command("start"))
        async def cmd_start(message: Message):
            await self.add_user(
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            )

            await message.answer(
                f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
                "/help — список команд"
            )

        @self.dp.message(Command("help"))
        async def cmd_help(message: Message):
            await message.answer("📚 /start /help /positions")

        @self.dp.message(Command("positions"))
        async def cmd_positions(message: Message):
            from parsing.coin_price_parcing import get_bybit_futures_price

            positions = await self.get_active_positions()
            if not positions:
                await message.answer("📭 Нет активных позиций")
                return

            for pos in positions:
                price_data = await asyncio.to_thread(
                    get_bybit_futures_price, pos['name']
                )

                await message.answer(
                    f"<b>{pos['name']}</b>\n"
                    f"Тип: {pos['pos_type']}\n"
                    f"Цена: {price_data.get('last_price')}"
                )

        @self.dp.message(Command("notify_all"))
        async def cmd_notify_all(message: Message):
            if not self.is_admin(message.from_user.id):
                await message.answer("⛔ Только для админов")
                return

            text = message.text.replace('/notify_all', '').strip()
            await self.send_to_all_users(text)

    # ==========================
    # DATABASE (ASYNC SAFE)
    # ==========================

    async def add_user(self, user_id, username, first_name, last_name):
        await asyncio.to_thread(
            self.db.add_user,
            user_id, username, first_name, last_name
        )

    async def get_active_users(self):
        return await asyncio.to_thread(self.db.get_active_users)

    async def get_active_positions(self):
        return await asyncio.to_thread(
            self.db.get_all_positions, True
        )

    # ==========================
    # BROADCAST
    # ==========================

    async def send_to_all_users(self, message: str):
        users = await self.get_active_users()

        for user_id in users:
            try:
                await self.bot.send_message(
                    user_id,
                    message,
                    disable_web_page_preview=True
                )
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Send error {user_id}: {e}")

    # ==========================
    # SERVICE
    # ==========================

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids

    async def start(self):
        logger.info("🤖 Bot polling started")
        await self.dp.start_polling(self.bot)

    async def stop(self):
        await self.bot.session.close()

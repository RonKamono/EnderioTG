import asyncio
import logging
from typing import List

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from utils.trading_db_postgres import TradingDBPostgres

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingBot:
    def __init__(self, token: str, admin_ids: List[int] | None = None):
        self.bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )

        # PostgreSQL DB (stateless, thread-safe)
        self.db = TradingDBPostgres()

        self.dp = Dispatcher()
        self.admin_ids = admin_ids or []

        self._register_handlers()

    # ==========================
    # HANDLERS
    # ==========================

    def _register_handlers(self):

        @self.dp.message(Command("start"))
        async def cmd_start(message: Message):
            await asyncio.to_thread(
                self.db.add_user,
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name,
            )

            await message.answer(
                f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
                "/help — список команд"
            )

        @self.dp.message(Command("help"))
        async def cmd_help(message: Message):
            await message.answer(
                "📚 Доступные команды:\n"
                "/positions — активные позиции"
            )

        @self.dp.message(Command("positions"))
        async def cmd_positions(message: Message):
            from parsing.coin_price_parcing import get_bybit_futures_price

            positions = await asyncio.to_thread(
                self.db.get_all_positions, True
            )

            if not positions:
                await message.answer("📭 Нет активных позиций")
                return

            for pos in positions:
                price_data = await asyncio.to_thread(
                    get_bybit_futures_price, pos["name"]
                )

                await message.answer(
                    f"<b>{pos['name']}</b>\n"
                    f"Тип: {pos['pos_type']}\n"
                    f"Цена: {price_data.get('last_price')}"
                )

        @self.dp.message(Command("notify_all"))
        async def cmd_notify_all(message: Message):
            if not self.is_admin(message.from_user.id):
                await message.answer("⛔ Только для администраторов")
                return

            text = message.text.replace("/notify_all", "").strip()
            if not text:
                await message.answer("❗ Укажи текст рассылки")
                return

            await self.send_to_all_users(text)

    def remove_position(self, position_id: int):
        # Хук для UI
        logger.debug("remove_position noop | id=%s", position_id)

    async def create_position_and_notify(
        self,
        name: str,
        percent: int,
        cross_margin: int,
        entry_price: float,
        take_profit: float,
        stop_loss: float,
        pos_type: str
    ) -> int:
        """
        Создаёт позицию в БД и отправляет уведомление в Telegram
        """

        position_id = await asyncio.to_thread(
            self.db.add_to_db,
            name,
            percent,
            cross_margin,
            entry_price,
            take_profit,
            stop_loss,
            pos_type
        )

        message = (
            f"🎯 <b>OPEN NEW POSITION</b>\n\n"
            f"<b>{name}</b>\n"
            f"Type: {pos_type.upper()}\n"
            f"Cross: {cross_margin}\n"
            f"Percentage of balance: 10%\n"
            f"Take Profit: {take_profit}\n"
            f"Stop Loss: {stop_loss}\n"
            f"<b>DON'T FORGET TO SEND A SCREEN OF THE POSITION</b>\n\n"
        )


        await self.send_to_all_users(message)

        logger.info(
            "Signal created and notified | id=%s %s",
            position_id,
            name
        )

        return position_id


    # ==========================
    # BROADCAST
    # ==========================

    async def send_to_all_users(self, message: str):
        users = await asyncio.to_thread(self.db.get_active_users)

        for user_id in users:
            try:
                await self.bot.send_message(
                    user_id,
                    message,
                    disable_web_page_preview=True
                )
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.warning(f"Send error {user_id}: {e}")

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

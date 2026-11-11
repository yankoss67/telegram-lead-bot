"""Точка входа: собирает конфиг, базу, роутеры и запускает бота."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from config import load_config
from database import Database
from handlers import setup_routers


USER_COMMANDS = [
    BotCommand(command="start", description="Главное меню"),
    BotCommand(command="new", description="Оставить заявку"),
    BotCommand(command="my", description="Мои заявки"),
    BotCommand(command="help", description="Что умеет бот"),
    BotCommand(command="cancel", description="Отменить ввод"),
]

ADMIN_COMMANDS = [
    BotCommand(command="admin", description="Панель администратора"),
    BotCommand(command="stats", description="Статистика"),
    BotCommand(command="export", description="Выгрузка в Excel"),
    BotCommand(command="lead", description="Открыть заявку: /lead 15"),
    BotCommand(command="dialogs", description="Мои диалоги"),
    BotCommand(command="stop", description="Завершить диалог"),
    BotCommand(command="new", description="Тестовая заявка"),
]


async def setup_commands(bot: Bot, admin_ids: tuple[int, ...]) -> None:
    """Меню команд (кнопка «/» в Telegram): клиентам — своё, админам — своё."""
    await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeDefault())
    for admin_id in admin_ids:
        try:
            await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:  # админ ещё ни разу не писал боту
            logging.warning("Команды для админа %s не установлены: %s. Нажмите /start и "
                            "перезапустите бота.", admin_id, e)


async def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config()

    db = Database(config.db_path)
    await db.init()

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(setup_routers())

    await setup_commands(bot, config.admin_ids)

    # db и config передаются во все хендлеры как аргументы (dependency injection aiogram)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, db=db, config=config)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")

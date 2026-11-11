"""Офлайн-прогон всего сценария без Telegram и без токена.

Подменяем сетевую сессию бота: вместо запросов к Telegram все исходящие вызовы
складываются в список SENT и печатаются. Запуск из папки проекта:
    python tests/smoke_test.py .
"""
import asyncio
import datetime
import os
import sys

sys.path.insert(0, os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "."))
os.environ.update(BOT_TOKEN="42:TEST", ADMIN_IDS="999", DB_PATH="test_leads.db")
if os.path.exists("test_leads.db"):
    os.remove("test_leads.db")

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Contact, Message, PhotoSize, Update, User

from config import load_config
from database import Database
from handlers import setup_routers

SENT = []
EXPORTED = {}


class FakeSession(BaseSession):
    async def make_request(self, bot, method, timeout=None):
        name = type(method).__name__
        text = getattr(method, "text", None) or getattr(method, "caption", None)
        SENT.append((name, getattr(method, "chat_id", None), text))
        if name == "SendDocument":
            EXPORTED[method.document.filename] = method.document.data
        if name in ("SendMessage", "SendDocument"):
            return method.__returning__.model_validate(
                {"message_id": len(SENT), "date": 0,
                 "chat": {"id": method.chat_id, "type": "private"},
                 "text": method.text if name == "SendMessage" else None},
                context={"bot": bot})
        return True

    async def stream_content(self, *a, **k):
        yield b""

    async def close(self):
        pass


CLIENT = User(id=111, is_bot=False, first_name="Иван", username="ivan")
ADMIN = User(id=999, is_bot=False, first_name="Админ")
_uid = 0


def msg(user, text=None, contact=None, photo=False, caption=None):
    global _uid
    _uid += 1
    ph = [PhotoSize(file_id="f", file_unique_id="u", width=1, height=1)] if photo else None
    return Update(update_id=_uid, message=Message(
        message_id=_uid, date=datetime.datetime.now(), chat=Chat(id=user.id, type="private"),
        from_user=user, text=text, contact=contact, photo=ph, caption=caption))


def cb(user, data):
    global _uid
    _uid += 1
    m = Message(message_id=1, date=datetime.datetime.now(),
                chat=Chat(id=user.id, type="private"), text="x")
    return Update(update_id=_uid, callback_query=CallbackQuery(
        id=str(_uid), from_user=user, chat_instance="c", message=m, data=data))


STEPS = [
    # --- клиент оставляет заявку ---
    msg(CLIENT, "/start"), msg(CLIENT, "❓ Помощь"),
    msg(CLIENT, "📝 Оставить заявку"), msg(CLIENT, "текст вместо кнопки"), cb(CLIENT, "service:1"),
    msg(CLIENT, "И"), msg(CLIENT, "Иван <b>"),
    msg(CLIENT, "abc"), msg(CLIENT, contact=Contact(phone_number="+79991234567", first_name="Иван")),
    msg(CLIENT, "Ноутбук Lenovo не включается"), cb(CLIENT, "confirm:yes"),
    # --- админская панель ---
    msg(ADMIN, "/start"), msg(ADMIN, "🆕 Новые заявки"), cb(ADMIN, "open:1"),
    msg(ADMIN, "🔍 Найти по номеру"), msg(ADMIN, "abc"), msg(ADMIN, "1"), msg(ADMIN, "/lead 77"),
    cb(ADMIN, "status:1:in_work"),
    # --- диалог ---
    cb(ADMIN, "chat:1"), msg(ADMIN, "Здравствуйте! Какая модель ноутбука?"),
    msg(ADMIN, photo=True, caption="Вот такой разъём?"), msg(ADMIN, "/stats"),
    msg(CLIENT, "Lenovo IdeaPad 3, да, такой"), msg(CLIENT, photo=True),
    msg(ADMIN, "💬 Мои диалоги"),  # админ в диалоге — кнопка панели уходит клиенту как текст? нет: это проверка
    msg(ADMIN, "❌ Завершить диалог"), msg(CLIENT, "спасибо"),
    # --- статистика, Excel, защита админки ---
    cb(ADMIN, "status:1:done"), msg(ADMIN, "📊 Статистика"), msg(ADMIN, "📤 Выгрузить в Excel"),
    msg(ADMIN, "💬 Мои диалоги"),
    msg(CLIENT, "/stats"), cb(CLIENT, "status:1:rejected"), cb(CLIENT, "chat:1"),
    msg(CLIENT, "/new"), msg(CLIENT, "✖️ Отмена"),
]


async def main():
    config = load_config()
    db = Database(config.db_path)
    await db.init()
    bot = Bot(config.bot_token, session=FakeSession(),
              default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(setup_routers())

    for u in STEPS:
        before = len(SENT)
        await dp.feed_update(bot, u, db=db, config=config)
        if u.message:
            who = u.message.from_user.first_name
            what = u.message.text or ("[контакт]" if u.message.contact else "[фото]")
        else:
            who, what = u.callback_query.from_user.first_name, "кнопка " + u.callback_query.data
        print(f"\n>>> {who}: {what}")
        for name, chat, text in SENT[before:]:
            print(f"    {name} → {chat}: {(text or '')[:100]}".replace("\n", " | "))

    print("\nБаза:", [(l.id, l.status, l.name) for l in await db.leads()])

    from openpyxl import load_workbook
    import io
    for fname, data in EXPORTED.items():
        wb = load_workbook(io.BytesIO(data))
        print(f"\nExcel {fname}: листы {wb.sheetnames}")
        for ws in wb:
            for row in ws.iter_rows(values_only=True):
                print("   ", row)
    os.remove("test_leads.db")


asyncio.run(main())

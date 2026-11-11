"""Диалог «администратор ↔ клиент» через бота.

Как это работает:
1. Админ жмёт «💬 Написать клиенту» под заявкой → в базе создаётся запись dialogs,
   а админ переходит в состояние AdminStates.chat.
2. Всё, что админ пишет в этом состоянии, бот пересылает клиенту с пометкой
   «👨‍💼 Администратор».
3. Клиент просто отвечает в чат — user.py находит открытый диалог и пересылает
   сообщение админу с кнопкой «↩️ Ответить».
4. «❌ Завершить диалог» или /stop закрывает переписку у обоих.

Этот роутер подключается ПЕРВЫМ: пока админ в диалоге, его сообщения не должны
попадать в обработчики панели."""
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

import keyboards as kb
from database import Database
from filters import IsAdmin
from states import AdminStates
from texts import ADMIN_LABEL, client_label

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
log = logging.getLogger(__name__)


async def relay(bot: Bot, message: Message, to_chat_id: int, header: str,
                reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Пересылает сообщение любого типа от имени бота, добавляя подпись-заголовок."""
    if message.text:
        await bot.send_message(to_chat_id, f"{header}:\n{escape(message.text)}",
                               reply_markup=reply_markup)
    elif message.photo or message.video or message.document or message.audio \
            or message.voice or message.animation:
        # У этих типов есть подпись — встраиваем пометку прямо в неё
        caption = header + (f":\n{escape(message.caption)}" if message.caption else "")
        await bot.copy_message(to_chat_id, message.chat.id, message.message_id,
                               caption=caption, reply_markup=reply_markup)
    else:
        # Стикеры, кружочки, геолокация — подписи нет, отправляем пометку отдельно
        await bot.send_message(to_chat_id, f"{header}:")
        await bot.copy_message(to_chat_id, message.chat.id, message.message_id,
                               reply_markup=reply_markup)


async def _close_dialog(bot: Bot, db: Database, user_id: int) -> None:
    await db.end_dialog(user_id)
    try:
        await bot.send_message(
            user_id,
            f"{ADMIN_LABEL} завершил диалог. Спасибо за обращение! "
            "Если появятся вопросы — оставьте новую заявку.",
        )
    except Exception as e:
        log.warning("Не удалось уведомить клиента %s: %s", user_id, e)


@router.callback_query(F.data.startswith("chat:"))
async def open_chat(call: CallbackQuery, state: FSMContext, bot: Bot, db: Database):
    lead_id = int(call.data.split(":")[1])
    lead = await db.get_lead(lead_id)
    if lead is None:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    existing = await db.get_dialog(lead.user_id)
    is_new = existing is None or existing.lead_id != lead_id
    await db.start_dialog(lead.user_id, call.from_user.id, lead_id)
    await state.set_state(AdminStates.chat)
    await state.update_data(chat_user=lead.user_id, chat_lead=lead_id)

    await call.message.answer(
        f"💬 <b>Диалог с клиентом {escape(lead.name)}</b> (заявка №{lead_id})\n\n"
        f"Всё, что вы напишете, придёт клиенту с пометкой {ADMIN_LABEL}.\n"
        "Можно отправлять текст, фото, файлы и голосовые.\n"
        "Чтобы выйти — нажмите «❌ Завершить диалог».",
        reply_markup=kb.chat_kb(),
    )
    if is_new:
        try:
            await bot.send_message(
                lead.user_id,
                f"{ADMIN_LABEL} подключился к чату по вашей заявке №{lead_id}.\n"
                "Можете отвечать прямо сюда 👇",
            )
        except Exception as e:
            await call.message.answer(f"⚠️ Клиенту не доставлено: возможно, он заблокировал бота ({e}).")
    await call.answer()


@router.callback_query(F.data.startswith("endchat:"))
async def end_chat_from_list(call: CallbackQuery, state: FSMContext, bot: Bot, db: Database):
    user_id = int(call.data.split(":")[1])
    await _close_dialog(bot, db, user_id)
    data = await state.get_data()
    if data.get("chat_user") == user_id:
        await state.clear()
        await call.message.answer("Диалог закрыт.", reply_markup=kb.admin_menu())
    await call.message.edit_reply_markup()
    await call.answer("Диалог закрыт")


@router.message(AdminStates.chat, Command("stop"))
@router.message(AdminStates.chat, F.text == kb.BTN_END_CHAT)
async def end_chat(message: Message, state: FSMContext, bot: Bot, db: Database):
    data = await state.get_data()
    await state.clear()
    await _close_dialog(bot, db, data["chat_user"])
    await message.answer(f"✅ Диалог по заявке №{data['chat_lead']} завершён.",
                         reply_markup=kb.admin_menu())


ADMIN_BUTTONS = {kb.ADM_NEW, kb.ADM_WORK, kb.ADM_ALL, kb.ADM_FIND, kb.ADM_DIALOGS,
                 kb.ADM_STATS, kb.ADM_EXPORT, kb.ADM_HELP, kb.BTN_NEW_LEAD}


# Команды и кнопки панели во время диалога не пересылаем клиенту
@router.message(AdminStates.chat, F.text.startswith("/"))
@router.message(AdminStates.chat, F.text.in_(ADMIN_BUTTONS))
async def command_in_chat(message: Message):
    await message.answer("Сейчас открыт диалог с клиентом. Сначала нажмите «❌ Завершить диалог» "
                         "или отправьте /stop.")


@router.message(AdminStates.chat)
async def admin_to_client(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    try:
        await relay(bot, message, data["chat_user"], ADMIN_LABEL)
    except Exception as e:
        await message.answer(f"⚠️ Сообщение не доставлено: {escape(str(e))}")


async def client_to_admin(message: Message, bot: Bot, db: Database) -> bool:
    """Вызывается из user.py. Если у клиента открыт диалог — пересылает сообщение админу.
    Возвращает True, если сообщение переслано."""
    dialog = await db.get_dialog(message.from_user.id)
    if dialog is None:
        return False
    lead = await db.get_lead(dialog.lead_id)
    try:
        await relay(bot, message, dialog.admin_id, client_label(lead),
                    reply_markup=kb.reply_to_client_kb(lead.id))
    except Exception as e:
        log.warning("Не удалось переслать админу %s: %s", dialog.admin_id, e)
        await message.answer("Не удалось доставить сообщение, попробуйте позже.")
    return True

"""Сценарий клиента: меню, пошаговая анкета, просмотр своих заявок, ответы администратору."""
import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from config import Config
from database import Database
from states import LeadForm
from texts import USER_HELP, lead_card, preview

from .chat import client_to_admin

router = Router()
log = logging.getLogger(__name__)

PHONE_RE = re.compile(r"^\+?[\d\s\-()]{10,18}$")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, config: Config):
    await state.clear()
    await message.answer(
        f"Здравствуйте, {message.from_user.first_name}! 👋\n"
        "Это бот сервиса ремонта техники. Оставьте заявку — мастер свяжется с вами.\n\n"
        "Нажмите «❓ Помощь», чтобы узнать, что умеет бот.",
        reply_markup=kb.menu_for(message.from_user.id, config.admin_ids),
    )


@router.message(Command("help"))
@router.message(F.text == kb.BTN_HELP)
async def cmd_help(message: Message):
    await message.answer(USER_HELP)


@router.message(F.text == kb.BTN_ABOUT)
async def about(message: Message):
    await message.answer("🛠 Ремонтируем телефоны, ноутбуки и ПК.\n"
                         "Диагностика — бесплатно, гарантия — 3 месяца.\n"
                         "Работаем ежедневно с 10:00 до 20:00.")


# Отмена работает на любом шаге анкеты
@router.message(StateFilter("*"), Command("cancel"))
@router.message(StateFilter("*"), F.text == kb.BTN_CANCEL)
async def cancel(message: Message, state: FSMContext, config: Config):
    await state.clear()
    await message.answer("Ввод отменён.", reply_markup=kb.menu_for(message.from_user.id, config.admin_ids))


# ---------- Анкета ----------

@router.message(Command("new"))
@router.message(F.text == kb.BTN_NEW_LEAD)
async def start_form(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(LeadForm.service)
    await message.answer("Шаг 1/4. Что нужно сделать?", reply_markup=kb.cancel_kb())
    await message.answer("Выберите услугу:", reply_markup=kb.services_kb())


@router.callback_query(LeadForm.service, F.data.startswith("service:"))
async def got_service(call: CallbackQuery, state: FSMContext):
    index = int(call.data.split(":")[1])
    service = kb.SERVICES[index]
    await state.update_data(service=service)
    await state.set_state(LeadForm.name)
    await call.message.edit_text(f"Услуга: {service}")
    await call.message.answer("Шаг 2/4. Как к вам обращаться?")
    await call.answer()


@router.message(LeadForm.service)
async def service_hint(message: Message):
    await message.answer("Пожалуйста, выберите услугу кнопкой выше 👆")


@router.message(LeadForm.name, F.text)
async def got_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not 2 <= len(name) <= 50:
        await message.answer("Имя должно быть от 2 до 50 символов. Попробуйте ещё раз.")
        return
    await state.update_data(name=name)
    await state.set_state(LeadForm.phone)
    await message.answer("Шаг 3/4. Ваш телефон? Можно нажать кнопку или ввести вручную.",
                         reply_markup=kb.phone_kb())


@router.message(LeadForm.phone, F.contact)
async def got_contact(message: Message, state: FSMContext):
    await _save_phone(message, state, message.contact.phone_number)


@router.message(LeadForm.phone, F.text)
async def got_phone_text(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not PHONE_RE.match(phone):
        await message.answer("Не похоже на номер телефона. Пример: +7 999 123-45-67")
        return
    await _save_phone(message, state, phone)


async def _save_phone(message: Message, state: FSMContext, phone: str):
    await state.update_data(phone=phone)
    await state.set_state(LeadForm.description)
    await message.answer("Шаг 4/4. Опишите проблему: модель устройства, что случилось.",
                         reply_markup=kb.cancel_kb())


@router.message(LeadForm.description, F.text)
async def got_description(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Опишите чуть подробнее (минимум 5 символов).")
        return
    await state.update_data(description=text[:1000])
    await state.set_state(LeadForm.confirm)
    await message.answer(preview(await state.get_data()), reply_markup=kb.confirm_kb())


# Если на текстовом шаге прислали фото/стикер — подсказываем
@router.message(StateFilter(LeadForm.name, LeadForm.phone, LeadForm.description))
async def wrong_type(message: Message):
    await message.answer("Пожалуйста, отправьте ответ текстом.")


@router.message(LeadForm.confirm)
async def confirm_hint(message: Message):
    await message.answer("Нажмите «✅ Отправить» или «🔄 Заново» под заявкой 👆")


@router.callback_query(LeadForm.confirm, F.data == "confirm:restart")
async def restart(call: CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    await call.answer()
    await start_form(call.message, state)


@router.callback_query(LeadForm.confirm, F.data == "confirm:yes")
async def confirm(call: CallbackQuery, state: FSMContext, bot: Bot, db: Database, config: Config):
    data = await state.get_data()
    await state.clear()

    lead_id = await db.add_lead(
        user_id=call.from_user.id,
        username=call.from_user.username,
        service=data["service"],
        name=data["name"],
        phone=data["phone"],
        description=data["description"],
    )
    await call.message.edit_reply_markup()
    await call.message.answer(
        f"✅ Заявка №{lead_id} принята! Мы свяжемся с вами в ближайшее время.",
        reply_markup=kb.menu_for(call.from_user.id, config.admin_ids),
    )
    await call.answer()

    # Уведомляем всех администраторов. Ошибка у одного не мешает остальным.
    lead = await db.get_lead(lead_id)
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, "📥 Новая заявка!\n\n" + lead_card(lead, for_admin=True),
                                   reply_markup=kb.admin_lead_kb(lead))
        except Exception as e:  # админ мог не нажать /start у бота
            log.warning("Не удалось уведомить админа %s: %s", admin_id, e)


# ---------- Мои заявки ----------

@router.message(Command("my"))
@router.message(F.text == kb.BTN_MY_LEADS)
async def my_leads(message: Message, db: Database):
    leads = await db.user_leads(message.from_user.id)
    if not leads:
        await message.answer("У вас пока нет заявок.")
        return
    await message.answer("\n\n".join(lead_card(l) for l in leads))


@router.callback_query()
async def stale_button(call: CallbackQuery):
    # Нажали кнопку из старого сообщения — отвечаем, иначе у клиента зависнут «часики»
    await call.answer("Эта кнопка уже неактуальна. Начните заново: /new", show_alert=True)


@router.message()
async def fallback(message: Message, bot: Bot, db: Database, config: Config):
    # Если администратор открыл с клиентом диалог — пересылаем сообщение ему
    if await client_to_admin(message, bot, db):
        return
    await message.answer("Не понял вас. Воспользуйтесь меню ниже 👇",
                         reply_markup=kb.menu_for(message.from_user.id, config.admin_ids))

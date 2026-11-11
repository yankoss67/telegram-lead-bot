"""Все клавиатуры в одном месте, чтобы тексты кнопок не расползались по коду."""
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import FINAL_STATUSES, Dialog, Lead

# Тема бота — сервис ремонта техники. Чтобы сменить тему, достаточно поменять этот список.
SERVICES = [
    "📱 Ремонт телефона",
    "💻 Ремонт ноутбука",
    "🖥 Сборка/апгрейд ПК",
    "🧹 Чистка от пыли",
    "❓ Другое",
]

# --- кнопки клиента ---
BTN_NEW_LEAD = "📝 Оставить заявку"
BTN_MY_LEADS = "📋 Мои заявки"
BTN_ABOUT = "ℹ️ О нас"
BTN_HELP = "❓ Помощь"
BTN_CANCEL = "✖️ Отмена"

# --- кнопки панели администратора ---
ADM_NEW = "🆕 Новые заявки"
ADM_WORK = "🔧 В работе"
ADM_ALL = "📚 Все заявки"
ADM_FIND = "🔍 Найти по номеру"
ADM_DIALOGS = "💬 Мои диалоги"
ADM_STATS = "📊 Статистика"
ADM_EXPORT = "📤 Выгрузить в Excel"
ADM_HELP = "❓ Справка для админа"
BTN_END_CHAT = "❌ Завершить диалог"

STATUS_BUTTONS = {"in_work": "🔧 В работу", "done": "✅ Готово", "rejected": "❌ Отклонить"}


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_NEW_LEAD)],
            [KeyboardButton(text=BTN_MY_LEADS), KeyboardButton(text=BTN_ABOUT)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADM_NEW), KeyboardButton(text=ADM_WORK)],
            [KeyboardButton(text=ADM_ALL), KeyboardButton(text=ADM_FIND)],
            [KeyboardButton(text=ADM_DIALOGS), KeyboardButton(text=ADM_STATS)],
            [KeyboardButton(text=ADM_EXPORT), KeyboardButton(text=ADM_HELP)],
            [KeyboardButton(text=BTN_NEW_LEAD)],  # чтобы админ мог проверить анкету сам
        ],
        resize_keyboard=True,
        input_field_placeholder="Панель администратора",
    )


def menu_for(user_id: int, admin_ids: tuple[int, ...]) -> ReplyKeyboardMarkup:
    """Админу — панель, клиенту — обычное меню."""
    return admin_menu() if user_id in admin_ids else main_menu()


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)


def chat_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_END_CHAT)]], resize_keyboard=True,
                               input_field_placeholder="Сообщение клиенту…")


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Отправить мой номер", request_contact=True)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


def services_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, title in enumerate(SERVICES):
        builder.button(text=title, callback_data=f"service:{i}")
    builder.adjust(1)
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Отправить", callback_data="confirm:yes"),
        InlineKeyboardButton(text="🔄 Заново", callback_data="confirm:restart"),
    ]])


def admin_lead_kb(lead: Lead) -> InlineKeyboardMarkup:
    """Кнопки под карточкой заявки: смена статуса + написать клиенту."""
    builder = InlineKeyboardBuilder()
    if lead.status not in FINAL_STATUSES:
        for code, title in STATUS_BUTTONS.items():
            if code != lead.status:
                builder.button(text=title, callback_data=f"status:{lead.id}:{code}")
    builder.button(text="💬 Написать клиенту", callback_data=f"chat:{lead.id}")
    builder.adjust(2)
    return builder.as_markup()


def leads_list_kb(leads: list[Lead]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lead in leads:
        builder.button(text=f"№{lead.id} · {lead.name} · {lead.status_text}",
                       callback_data=f"open:{lead.id}")
    builder.adjust(1)
    return builder.as_markup()


def dialogs_kb(dialogs: list[Dialog]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for d in dialogs:
        builder.button(text=f"↩️ Заявка №{d.lead_id}", callback_data=f"chat:{d.lead_id}")
        builder.button(text="❌ Закрыть", callback_data=f"endchat:{d.user_id}")
    builder.adjust(2)
    return builder.as_markup()


def reply_to_client_kb(lead_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Ответить", callback_data=f"chat:{lead_id}"),
        InlineKeyboardButton(text="📄 Заявка", callback_data=f"open:{lead_id}"),
    ]])

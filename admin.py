"""Панель администратора: списки заявок, поиск, статусы, статистика, Excel, диалоги."""
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import keyboards as kb
from database import FINAL_STATUSES, STATUSES, Database
from export import build_xlsx
from filters import IsAdmin
from states import AdminStates
from texts import ADMIN_HELP, lead_card

router = Router()
# Фильтр на весь роутер: эти хендлеры видят только администраторы
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

LIST_LIMIT = 20


# ---------- Вход в панель ----------

@router.message(CommandStart())
@router.message(Command("admin"))
@router.message(F.text == kb.ADM_HELP)
async def admin_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(ADMIN_HELP, reply_markup=kb.admin_menu())


# ---------- Списки заявок ----------

async def _send_list(message: Message, db: Database, status: str | None, title: str):
    leads = await db.leads(status=status, limit=LIST_LIMIT)
    if not leads:
        await message.answer(f"{title}: пусто 👌")
        return
    await message.answer(
        f"<b>{title}</b> — {len(leads)} шт.\nНажмите на заявку, чтобы открыть её:",
        reply_markup=kb.leads_list_kb(leads),
    )


@router.message(F.text == kb.ADM_NEW)
async def list_new(message: Message, state: FSMContext, db: Database):
    await state.clear()
    await _send_list(message, db, "new", "🆕 Новые заявки")


@router.message(F.text == kb.ADM_WORK)
async def list_in_work(message: Message, state: FSMContext, db: Database):
    await state.clear()
    await _send_list(message, db, "in_work", "🔧 Заявки в работе")


@router.message(F.text == kb.ADM_ALL)
async def list_all(message: Message, state: FSMContext, db: Database):
    await state.clear()
    await _send_list(message, db, None, f"📚 Последние {LIST_LIMIT} заявок")


@router.callback_query(F.data.startswith("open:"))
async def open_lead(call: CallbackQuery, db: Database):
    lead = await db.get_lead(int(call.data.split(":")[1]))
    if lead is None:
        await call.answer("Заявка не найдена", show_alert=True)
        return
    await call.message.answer(lead_card(lead, for_admin=True), reply_markup=kb.admin_lead_kb(lead))
    await call.answer()


# ---------- Поиск по номеру ----------

async def _show_lead(message: Message, db: Database, lead_id: int):
    lead = await db.get_lead(lead_id)
    if lead is None:
        await message.answer(f"Заявки №{lead_id} нет.")
        return
    await message.answer(lead_card(lead, for_admin=True), reply_markup=kb.admin_lead_kb(lead))


@router.message(Command("lead"))
async def cmd_lead(message: Message, command: CommandObject, db: Database):
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Укажите номер: <code>/lead 15</code>")
        return
    await _show_lead(message, db, int(command.args))


@router.message(F.text == kb.ADM_FIND)
async def find_start(message: Message, state: FSMContext):
    await state.set_state(AdminStates.search)
    await message.answer("Введите номер заявки:", reply_markup=kb.cancel_kb())


@router.message(AdminStates.search, F.text == kb.BTN_CANCEL)
async def find_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Поиск отменён.", reply_markup=kb.admin_menu())


@router.message(AdminStates.search, F.text)
async def find_lead(message: Message, state: FSMContext, db: Database):
    text = message.text.strip().lstrip("№#")
    if not text.isdigit():
        await message.answer("Нужен номер цифрами, например 12.")
        return
    await state.clear()
    await message.answer("🔍 Результат:", reply_markup=kb.admin_menu())
    await _show_lead(message, db, int(text))


# ---------- Смена статуса ----------

@router.callback_query(F.data.startswith("status:"))
async def change_status(call: CallbackQuery, bot: Bot, db: Database):
    _, lead_id, status = call.data.split(":")
    lead = await db.get_lead(int(lead_id))
    if lead is None:
        await call.answer("Заявка не найдена", show_alert=True)
        return
    if lead.status == status:
        await call.answer("Статус уже установлен")
        return
    if lead.status in FINAL_STATUSES:
        await call.answer("Заявка уже закрыта", show_alert=True)
        return

    await db.set_status(lead.id, status)
    lead = await db.get_lead(lead.id)
    await call.message.edit_text(lead_card(lead, for_admin=True), reply_markup=kb.admin_lead_kb(lead))
    try:
        await bot.send_message(lead.user_id, f"Статус вашей заявки №{lead.id}: {lead.status_text}")
    except Exception:
        pass  # клиент мог заблокировать бота — это не ошибка админа
    await call.answer(f"Статус: {lead.status_text}")


# ---------- Диалоги ----------

@router.message(Command("dialogs"))
@router.message(F.text == kb.ADM_DIALOGS)
async def my_dialogs(message: Message, state: FSMContext, db: Database):
    await state.clear()
    dialogs = await db.admin_dialogs(message.from_user.id)
    if not dialogs:
        await message.answer("Открытых диалогов нет. Начать диалог можно кнопкой "
                             "«💬 Написать клиенту» под любой заявкой.")
        return
    await message.answer(f"<b>💬 Открытые диалоги: {len(dialogs)}</b>\n"
                         "«↩️» — продолжить переписку, «❌» — закрыть.",
                         reply_markup=kb.dialogs_kb(dialogs))


# ---------- Статистика и выгрузка ----------

@router.message(Command("stats"))
@router.message(F.text == kb.ADM_STATS)
async def stats(message: Message, db: Database):
    data = await db.stats()
    total = sum(data.values())
    lines = [f"<b>📊 Всего заявок: {total}</b>", ""]
    for code, title in STATUSES.items():
        count = data.get(code, 0)
        percent = f" ({count * 100 // total}%)" if total else ""
        lines.append(f"{title}: <b>{count}</b>{percent}")
    await message.answer("\n".join(lines))


@router.message(Command("export"))
@router.message(F.text == kb.ADM_EXPORT)
async def export(message: Message, db: Database):
    leads = await db.leads()
    if not leads:
        await message.answer("Заявок пока нет — выгружать нечего.")
        return
    content = build_xlsx(leads, await db.stats())
    filename = f"zayavki_{datetime.now():%Y-%m-%d}.xlsx"
    await message.answer_document(BufferedInputFile(content, filename=filename),
                                  caption=f"📤 Выгружено заявок: {len(leads)}")

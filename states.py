"""Состояния (FSM). Бот помнит, на каком шаге находится каждый пользователь."""
from aiogram.fsm.state import State, StatesGroup


class LeadForm(StatesGroup):
    service = State()      # выбор услуги
    name = State()         # имя
    phone = State()        # телефон
    description = State()  # описание проблемы
    confirm = State()      # проверка и отправка


class AdminStates(StatesGroup):
    search = State()  # админ вводит номер заявки
    chat = State()    # админ ведёт диалог с клиентом: всё, что он пишет, уходит клиенту

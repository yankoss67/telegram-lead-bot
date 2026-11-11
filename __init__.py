from aiogram import Router

from . import admin, chat, user


def setup_routers() -> Router:
    root = Router()
    # Порядок важен: aiogram отдаёт сообщение первому подходящему хендлеру.
    # 1) chat  — пока админ в диалоге, все его сообщения уходят клиенту;
    # 2) admin — панель администратора (только для ADMIN_IDS);
    # 3) user  — всё остальное: клиенты и непойманные сообщения админа.
    root.include_router(chat.router)
    root.include_router(admin.router)
    root.include_router(user.router)
    return root

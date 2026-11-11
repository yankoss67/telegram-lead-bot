"""Настройки бота. Все секреты берутся из файла .env, а не хранятся в коде."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: tuple[int, ...]
    db_path: str


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Не задан BOT_TOKEN. Скопируйте .env.example в .env и впишите токен.")

    raw_admins = os.getenv("ADMIN_IDS", "")
    admin_ids = tuple(int(x) for x in raw_admins.replace(" ", "").split(",") if x)
    if not admin_ids:
        raise RuntimeError("Не задан ADMIN_IDS — некому будет приходить заявкам.")

    return Config(
        bot_token=token,
        admin_ids=admin_ids,
        db_path=os.getenv("DB_PATH", "leads.db"),
    )

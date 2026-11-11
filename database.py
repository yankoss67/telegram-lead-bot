"""Работа с базой SQLite через aiosqlite (асинхронно, чтобы не блокировать бота)."""
from dataclasses import dataclass

import aiosqlite

STATUSES = {
    "new": "🆕 Новая",
    "in_work": "🔧 В работе",
    "done": "✅ Выполнена",
    "rejected": "❌ Отклонена",
}
FINAL_STATUSES = ("done", "rejected")

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    username    TEXT,
    service     TEXT NOT NULL,
    name        TEXT NOT NULL,
    phone       TEXT NOT NULL,
    description TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'new',
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Активные диалоги «админ ↔ клиент»: у клиента может быть один открытый диалог
CREATE TABLE IF NOT EXISTS dialogs (
    user_id    INTEGER PRIMARY KEY,
    admin_id   INTEGER NOT NULL,
    lead_id    INTEGER NOT NULL,
    started_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


@dataclass
class Lead:
    id: int
    user_id: int
    username: str | None
    service: str
    name: str
    phone: str
    description: str
    status: str
    created_at: str

    @property
    def status_text(self) -> str:
        return STATUSES.get(self.status, self.status)


@dataclass
class Dialog:
    user_id: int
    admin_id: int
    lead_id: int
    started_at: str


class Database:
    def __init__(self, path: str):
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    # ---------- Заявки ----------

    async def add_lead(self, user_id: int, username: str | None, service: str,
                       name: str, phone: str, description: str) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "INSERT INTO leads (user_id, username, service, name, phone, description) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, service, name, phone, description),
            )
            await db.commit()
            return cur.lastrowid

    async def get_lead(self, lead_id: int) -> Lead | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
            row = await cur.fetchone()
            return Lead(*row) if row else None

    async def set_status(self, lead_id: int, status: str) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))
            await db.commit()

    async def user_leads(self, user_id: int, limit: int = 10) -> list[Lead]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT * FROM leads WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            )
            return [Lead(*r) for r in await cur.fetchall()]

    async def leads(self, status: str | None = None, limit: int | None = None) -> list[Lead]:
        """Заявки (новые сверху). status=None — все статусы, limit=None — без ограничения."""
        query, params = "SELECT * FROM leads", []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY id DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(query, params)
            return [Lead(*r) for r in await cur.fetchall()]

    async def stats(self) -> dict[str, int]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT status, COUNT(*) FROM leads GROUP BY status")
            return {status: count for status, count in await cur.fetchall()}

    # ---------- Диалоги ----------

    async def start_dialog(self, user_id: int, admin_id: int, lead_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO dialogs (user_id, admin_id, lead_id) VALUES (?, ?, ?)",
                (user_id, admin_id, lead_id),
            )
            await db.commit()

    async def get_dialog(self, user_id: int) -> Dialog | None:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute("SELECT * FROM dialogs WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
            return Dialog(*row) if row else None

    async def end_dialog(self, user_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute("DELETE FROM dialogs WHERE user_id = ?", (user_id,))
            await db.commit()

    async def admin_dialogs(self, admin_id: int) -> list[Dialog]:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT * FROM dialogs WHERE admin_id = ? ORDER BY started_at DESC", (admin_id,))
            return [Dialog(*r) for r in await cur.fetchall()]

"""Выгрузка заявок в настоящий Excel-файл (.xlsx).
В отличие от CSV, xlsx хранит текст в Unicode внутри файла, поэтому кириллица
открывается правильно в любом Excel, LibreOffice, Google Таблицах и на телефоне."""
import io
import re
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from database import STATUSES, Lead

HEADERS = ["№", "Дата", "Статус", "Услуга", "Имя", "Телефон", "Описание", "Telegram"]
WIDTHS = [6, 18, 15, 22, 18, 18, 50, 18]

HEADER_FILL = PatternFill("solid", fgColor="2F5597")
HEADER_FONT = Font(bold=True, color="FFFFFF")
STATUS_FILLS = {
    "new": PatternFill("solid", fgColor="DDEBF7"),
    "in_work": PatternFill("solid", fgColor="FFF2CC"),
    "done": PatternFill("solid", fgColor="E2EFDA"),
    "rejected": PatternFill("solid", fgColor="FCE4D6"),
}
THIN = Side(style="thin", color="BFBFBF")

# Эмодзи в Excel часто отображаются квадратиками, поэтому в файл пишем чистый текст.
# Диапазоны: пиктограммы/смайлы (U+1F000+), символы и дингбаты (U+2190–U+2BFF),
# невидимые модификаторы (вариационный селектор U+FE0F, склейка U+200D, U+20E3).
EMOJI_RE = re.compile("[\U0001F000-\U0001FFFF←-⯿︎️‍⃣]")


def clean(value) -> str:
    """Убирает эмодзи и лишние пробелы: '💻 Ремонт ноутбука' -> 'Ремонт ноутбука'."""
    if value is None:
        return ""
    return re.sub(r"\s{2,}", " ", EMOJI_RE.sub("", str(value))).strip()
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def build_xlsx(leads: list[Lead], stats: dict[str, int]) -> bytes:
    wb = Workbook()

    # --- Лист 1: заявки ---
    ws = wb.active
    ws.title = "Заявки"
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for lead in sorted(leads, key=lambda l: l.id):
        created = datetime.strptime(lead.created_at, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
        ws.append([
            lead.id, created, clean(lead.status_text), clean(lead.service), clean(lead.name),
            lead.phone, clean(lead.description), f"@{lead.username}" if lead.username else "",
        ])
        for cell in ws[ws.max_row]:
            cell.border = BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.cell(ws.max_row, 3).fill = STATUS_FILLS.get(lead.status, PatternFill())

    for i, width in enumerate(WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A2"                 # шапка не уезжает при прокрутке
    ws.auto_filter.ref = ws.dimensions     # фильтры в шапке

    # --- Лист 2: статистика ---
    st = wb.create_sheet("Статистика")
    st.append(["Статус", "Количество"])
    for cell in st[1]:
        cell.fill, cell.font, cell.border = HEADER_FILL, HEADER_FONT, BORDER
    for code, title in STATUSES.items():
        st.append([clean(title), stats.get(code, 0)])
    st.append(["Всего", sum(stats.values())])
    st.cell(st.max_row, 1).font = st.cell(st.max_row, 2).font = Font(bold=True)
    st.append([])
    st.append(["Выгружено", datetime.now().strftime("%d.%m.%Y %H:%M")])
    st.column_dimensions["A"].width = 20
    st.column_dimensions["B"].width = 18

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

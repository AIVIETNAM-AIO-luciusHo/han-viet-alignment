"""Xuất <MA_SACH>_parallel.tsv và .xlsx (sheet DONG_HANG) đúng mục 3 của hướng dẫn.

TSV: UTF-8 không BOM, NFC, LF, không dấu ngoặc kép bao ô. XLSX: một sheet, ô dạng text,
không công thức, không gộp ô, cùng cột/nội dung/thứ tự với TSV.
"""
from __future__ import annotations

from pathlib import Path

from ..common.text import clean_cell


def write_tsv(path: Path, rows: list[dict], columns: list[str]) -> None:
    lines = ["\t".join(columns)]
    for r in rows:
        cells = [clean_cell(r.get(c, "")) for c in columns]
        lines.append("\t".join(cells))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def write_xlsx(path: Path, rows: list[dict], columns: list[str], sheet: str = "DONG_HANG") -> None:
    from openpyxl import Workbook
    from openpyxl.cell.cell import TYPE_STRING
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = sheet
    ws.append(columns)
    for r in rows:
        ws.append([clean_cell(r.get(c, "")) or None for c in columns])
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                cell.data_type = TYPE_STRING  # chặn Excel hiểu '=…' là công thức hay chuỗi số là số
                cell.number_format = "@"
    widths = {"sent_id": 14, "doc_id": 11, "doc_type": 12, "han": 40, "phien_am": 60, "dich_nghia": 60, "ghi_chu": 40}
    for idx, c in enumerate(columns, 1):
        ws.column_dimensions[get_column_letter(idx)].width = widths.get(c, 20)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)

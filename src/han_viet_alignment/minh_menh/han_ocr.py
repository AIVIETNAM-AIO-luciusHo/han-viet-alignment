"""Đọc OCR chữ Hán PP-OCRv6 (`<MA_SACH>_han_ppocrv6.md`) của Minh Mệnh chính yếu.

Mỗi trang PDF là một mặt tờ. Trang mở đầu quyển có dòng "明命政要卷之…" ở đầu trang; từ đó mặt
thứ k của quyển là tờ k//2+1, mặt a khi k chẵn (khớp với số tờ 1b, 11b, 36b… OCR đọc được ở lề).

Mỗi dòng OCR là một cột chữ. Lọc chữ lề trang (bản tâm: tên sách, số quyển, tên thiên, số tờ) và số
trang La Mã đọc lẫn, rồi gom cột thành đoạn: cột ngắn hơn cột đầy kết thúc một đoạn (hết điều, hết câu
trước chữ 帝 nâng cao, hoặc chú thích song hành). Đoạn là đơn vị nhỏ nhất khi dóng hàng.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..common.text import is_han

PAGE_HEADER = re.compile(r"^## Trang (\d+)\s*$", re.M)
SHEET = 200
FULL_COLUMN = 17
EDGE_HEAD, EDGE_TAIL = 3, 4

_CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
QUYEN_START = re.compile(r"^明命政要卷之([一二三四五六七八九十]+)$")
QUYEN_END = re.compile(r"卷之.{0,5}止$")
CHAPTER_TITLE = re.compile(r"^(\S{2,6})第[一二三四五六七八九十]+$")
YEAR_HEADER = re.compile(r"^明命[元一二三四五六七八九十]+年$")
MARGIN_CHARS = set("明命政要正耳焉豆名右月曰日文改馬矣辰足五巧合仁介石")
NUMERALS = set("一二三四五六七八九十百")


def cn2int(s: str) -> int:
    """'十四' -> 14, '二十' -> 20, '二十二' -> 22."""
    if "十" not in s:
        return _CN.get(s, 0)
    left, _, right = s.partition("十")
    return (_CN.get(left, 1) if left else 1) * 10 + (_CN.get(right, 0) if right else 0)


def folio_label(g: int, quyen_numbers: dict[int, int]) -> str:
    q, k = divmod(g, SHEET)
    return f"Q{quyen_numbers.get(q, q + 1)}:{k // 2 + 1}{'ab'[k % 2]}"


@dataclass
class HanUnit:
    text: str
    folio_start: int
    folio_end: int
    pages: tuple[int, int]
    lines: list[str] = field(default_factory=list)

    @property
    def year(self) -> int | None:
        """明命三年 -> 1822 (năm dương lịch, để so với '(1822)' của bản dịch)."""
        m = YEAR_HEADER.match(self.text)
        if not m:
            return None
        num = self.text[2:-1]
        return 1819 + (1 if num == "元" else cn2int(num))


@dataclass
class HanBook:
    units: list[HanUnit]
    dropped: list[tuple[int, str, str]] = field(default_factory=list)
    quyen_numbers: dict[int, int] = field(default_factory=dict)
    page_folio: dict[int, int] = field(default_factory=dict)


def parse_pages(md: str) -> list[tuple[int, list[str]]]:
    parts = PAGE_HEADER.split(md)
    return [(int(parts[i]), [ln.strip() for ln in parts[i + 1].splitlines() if ln.strip()])
            for i in range(1, len(parts), 2)]


def _han(s: str) -> str:
    return "".join(c for c in s if is_han(c))


def _quyen_start(lines: list[str]) -> int | None:
    for ln in lines[:2]:
        m = QUYEN_START.match(_han(ln))
        if m:
            return cn2int(m.group(1))
    return None


def margin_bigrams(pages: list[tuple[int, list[str]]], min_pages: int = 6) -> set[str]:
    """Cặp chữ đặc trưng của chữ lề trang: lặp ở dòng ngắn trên nhiều trang nhưng gần như không có trong
    cột thân văn (vd 月命, 卷之, 正耳, 慎刑, 財賦 — tên sách/quyển/thiên in ở bản tâm và các cách OCR đọc sai)."""
    short: dict[str, set[int]] = {}
    long_: dict[str, int] = {}
    for page, lines in pages:
        for ln in lines:
            h = _han(ln)
            if YEAR_HEADER.match(h):
                continue
            bgs = {h[i:i + 2] for i in range(len(h) - 1)}
            if 2 <= len(h) <= 12:
                for b in bgs:
                    short.setdefault(b, set()).add(page)
            elif len(h) >= 15:
                for b in bgs:
                    long_[b] = long_.get(b, 0) + 1
    return {b for b, ps in short.items() if len(ps) >= min_pages and long_.get(b, 0) <= max(1, len(ps) // 10)}


def _drop_reason(raw: str, han: str, edge: bool, chapters: set[str],
                 margin: frozenset[str] = frozenset()) -> str | None:
    other = sum(1 for c in raw if not c.isspace() and not is_han(c))
    if not han:
        return "khong_co_chu_han"
    if QUYEN_START.match(han) or QUYEN_END.search(han):
        return "tieu_de_quyen"
    if CHAPTER_TITLE.match(han) and len(han) <= 8:
        return "ten_thien"
    if other >= len(han) and len(han) <= 3:
        return "nhieu_ocr"
    if YEAR_HEADER.match(han):
        return None
    if len(han) <= 12 and margin and ("年" not in han or "卷" in han):
        hits = sum(han[i:i + 2] in margin for i in range(len(han) - 1))
        if hits >= (1 if len(han) <= 6 else 2):
            return "le_trang"
    if not edge:
        return None
    if "卷" in han and len(han) <= 12:
        return "le_trang"
    if len(han) <= 5 and sum(c in MARGIN_CHARS for c in han) >= max(2, 0.6 * len(han)):
        return "le_trang"
    if len(han) <= 4 and all(c in NUMERALS for c in han):
        return "le_trang"
    if len(han) <= 10 and any(ch in han for ch in chapters):
        return "le_trang"
    return None


def load_han_book(md: str) -> HanBook:
    book = HanBook(units=[])
    q = -1
    side = 0
    chapters: set[str] = set()
    cur: list[str] = []
    cur_f: list[int] = []
    cur_p: list[int] = []

    def close() -> None:
        if cur:
            book.units.append(HanUnit("".join(cur), min(cur_f), max(cur_f), (min(cur_p), max(cur_p)), list(cur)))
        cur.clear(), cur_f.clear(), cur_p.clear()

    pages = parse_pages(md)
    margin = frozenset(margin_bigrams(pages))
    for page, lines in pages:
        num = _quyen_start(lines)
        if num is not None:
            close()
            q += 1
            side = 0
            book.quyen_numbers[q] = num
        elif q < 0:
            continue
        else:
            side += 1
        g = q * SHEET + side
        book.page_folio[page] = g
        for idx, raw in enumerate(lines):
            han = _han(raw)
            m = CHAPTER_TITLE.match(han)
            if m:
                chapters.add(m.group(1))
            edge = idx < EDGE_HEAD or idx >= len(lines) - EDGE_TAIL
            reason = _drop_reason(raw, han, edge, chapters, margin)
            if reason:
                if reason != "khong_co_chu_han" or raw.strip():
                    book.dropped.append((page, raw, reason))
                continue
            if YEAR_HEADER.match(han):
                close()
            cur.append(han), cur_f.append(g), cur_p.append(page)
            if len(han) < FULL_COLUMN:
                close()
    close()
    return book

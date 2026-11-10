"""Tách câu (Bước 6): phiên âm tại . ! ?, dịch nghĩa tại . ! ? ; — rồi gộp các mảnh không đứng riêng được."""
from __future__ import annotations

import re

from ..common.text import syllables

_PA_END = re.compile(r"(?<=[.!?])[\"'”’)\]]*\s+")
_DN_END = re.compile(r"(?<=[.!?;])[\"'”’)\]]*\s+")
_CLOSING = re.compile(r"^(kh[âa]m\s+tai|kính\s+(cẩn\s+)?thay)\b", re.I)
# Công thức luôn mở đầu câu trong sắc phong: tách tại đó khi OCR làm mất dấu câu trước nó
# (vd 'chi thần Hướng lai...', 'tự điền Khâm tai!', 'Kính cẩn thay Ngày 9 tháng...'). Chỉ tách khi
# chữ liền trước không có dấu câu; dạng viết thường chỉ dùng cho công thức không bao giờ đứng giữa câu.
_PA_START = re.compile(r"(?<=\w)\s+(?=(?:(?i:hướng\s+lai|tứ\s+kim|khâm\s+tai)|Hộ\s+quốc|HỘ\s+QUỐC|Nhưng\s+chuẩn)\b)")
_DN_START = re.compile(r"(?<=\w)\s+(?=(?:Từ\s+trước\s+tới\s+nay|Nay\s+trẫm|Lại\s+chuẩn|Kính\s+cẩn\s+thay|"
                       r"Trong\s+việc\s+giúp\s+nước|Ngày\s+(?:\d|mồng|mùng))\b)")
_SHORT = 3  # mảnh viết thường chỉ là phần tiếp của câu trước khi câu trước ≤ 3 âm tiết ('Thần nguyên. được…')


def _split(text: str, pattern: re.Pattern, starts: re.Pattern | None = None) -> list[str]:
    parts, last = [], 0
    for m in pattern.finditer(text):
        parts.append(text[last:m.start()] + m.group(0).strip())
        last = m.end()
    parts.append(text[last:])
    if starts is not None:
        parts = [q for p in parts for q in starts.split(p)]
    return [p.strip() for p in parts if p.strip()]


def _starts_lower(s: str) -> bool:
    m = re.search(r"\w", s)
    return bool(m) and m.group(0).islower()


def _merge_fragments(parts: list[str], merge_short_header: bool) -> list[str]:
    # 1) Mảnh viết thường sau câu rất ngắn là phần tiếp của câu trước (dấu chấm do OCR hoặc viết tắt).
    #    Sau câu dài thì vẫn là câu mới (OCR hay mất chữ hoa: '...chi thần. nguyên tặng...'); tách nhỏ an toàn
    #    hơn gộp vì bước dóng hàng tự gộp 1–2/2–1 khi cần. Mảnh ≤ 2 âm tiết viết thường (rác OCR) cũng gộp lùi.
    out: list[str] = []
    for p in parts:
        if out and _starts_lower(p) and (len(syllables(out[-1])) <= _SHORT or len(syllables(p)) <= 2):
            out[-1] = f"{out[-1]} {p}"
        else:
            out.append(p)
    if not merge_short_header:
        return out
    # 2) Tiêu đề 1–2 âm tiết ('Sắc.', 'Chiếu.') gộp vào câu sau (kiểu n–1 như MAU.001.1)
    merged: list[str] = []
    carry = ""
    for p in out:
        if carry:
            p = f"{carry} {p}"
            carry = ""
        if len(syllables(p)) <= 2 and not _CLOSING.match(p) and p is not out[-1]:
            carry = p
            continue
        merged.append(p)
    if carry:
        merged.append(carry)
    return merged


def split_phien_am(text: str) -> list[str]:
    return _merge_fragments(_split(text, _PA_END, _PA_START), merge_short_header=True)


def split_dich_nghia(text: str) -> list[str]:
    return _merge_fragments(_split(text, _DN_END, _DN_START), merge_short_header=False)

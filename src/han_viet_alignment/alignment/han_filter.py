"""Lọc dòng OCR chữ Hán rác (hoa văn, ấn triện, viền) trước khi làm sạch — HD bước 4–5.

Một dòng (một cột chữ) bị loại khi thỏa CẢ HAI điều kiện:
  1. điểm nhận dạng < min_score (dòng mà cấu hình mặc định RapidOCR vốn đã bỏ), và
  2. tỉ lệ chữ khớp âm phiên âm < min_match, sau khi dóng cả văn bản bằng edit distance có từ điển.
Chỉ bỏ, không thêm/đoán chữ. Âm tiết mất chữ do lọc sẽ thành □ ở bước dóng hàng.
02_ocr_tho giữ nguyên OCR thô; danh sách dòng bị loại được ghi lại để người xác nhận.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..common.dictionary import Readings
from ..common.text import is_han, syllables
from .han_pa import _align

MIN_SCORE = 0.5
MIN_MATCH = 0.3


@dataclass
class LineInfo:
    text: str
    score: float | None
    n_han: int
    n_match: int
    kept: bool

    @property
    def match_ratio(self) -> float:
        return self.n_match / self.n_han if self.n_han else 0.0


def filter_han_lines(lines: list[str], scores: list[float | None], phien_am: str, readings: Readings,
                     min_score: float = MIN_SCORE, min_match: float = MIN_MATCH) -> list[LineInfo]:
    """Trả về thông tin từng dòng (giữ thứ tự), kept=False là dòng bị loại."""
    chars, owner = [], []
    for li, line in enumerate(lines):
        for c in line:
            if is_han(c):
                chars.append(c)
                owner.append(li)
    n_han = [0] * len(lines)
    n_match = [0] * len(lines)
    for li in owner:
        n_han[li] += 1
    syls = syllables(phien_am)
    if syls and chars:
        for ci, sj in _align(chars, syls, readings):
            if ci is not None and sj is not None and readings.match(chars[ci], syls[sj]):
                n_match[owner[ci]] += 1
    out = []
    for li, line in enumerate(lines):
        sc = scores[li] if li < len(scores) else None
        info = LineInfo(line, sc, n_han[li], n_match[li], True)
        # Không có điểm (dữ liệu OCR cũ) hoặc không có phiên âm để đối chiếu -> không lọc
        if sc is not None and syls and sc < min_score and info.match_ratio < min_match:
            info.kept = False
        out.append(info)
    return out

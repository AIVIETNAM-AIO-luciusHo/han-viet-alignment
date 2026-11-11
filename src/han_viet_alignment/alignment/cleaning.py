"""Làm sạch text 03_text_sach trước khi dóng hàng (Bước 5 của hướng dẫn).

Chỉ sửa lỗi OCR có quy luật, không sửa văn phong:
- bỏ tiêu đề trang (chuỗi ≥3 từ VIẾT HOA), số trang/số rác, chỉ mục chú thích, ký hiệu rác;
- ghép âm tiết bị OCR tách đôi (vd 'Hù ng' -> 'Hùng') khi từ điển xác nhận;
- bỏ ký tự Latin lẻ không thể là âm tiết tiếng Việt;
- chuẩn khoảng trắng quanh dấu câu.
Quy tắc sửa từ cụ thể theo văn phong sắc phong nằm ở sac_phong/ocr_pipeline.py (Người 1).
"""
from __future__ import annotations

import re

from ..common.dictionary import Readings
from ..common.text import DN_MISSING, HAN_PUNCT, MISSING, is_han, nfc

# Tiếng Việt không có âm tiết chỉ gồm một phụ âm
_LONE_CONSONANT = set("bcdđfghjklmnpqrstvwxzBCDĐFGHJKLMNPQRSTVWXZ")
_VOWEL_START = re.compile(r"^[aăâeêioôơuưyáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", re.I)
_UPPER_WORD = r"[A-ZÀ-ỸĐ]{2,}"
_RUNNING_HEADER = re.compile(rf"(?:\b{_UPPER_WORD}\b[\s,.\-–:]*){{3,}}")
_BOX_VARIANTS = re.compile(r"[■-▩▭-▰◼〓�]")
_FOOTNOTE_INDEX = re.compile(r"\[\d{1,2}\]|\((?!1[5-9]\d\d|20\d\d)\d{1,2}\)")
# Số đứng sau các từ này là số thật của bản dịch (ngày, tháng, năm, thứ...), phải giữ
_NUMBER_CONTEXT = {"ngày", "tháng", "năm", "thứ", "mồng", "mùng", "số", "lần", "đội", "khoảng", "hơn", "gần"}


def _space_punct(s: str) -> str:
    s = re.sub(r"\s+([,.;:!?)\]])", r"\1", s)
    s = re.sub(r"([(\[])\s+", r"\1", s)
    s = re.sub(r"([,.;:!?])(?=[^\s\d,.;:!?)\]\"'…])", r"\1 ", s)
    return re.sub(r"\s+", " ", s).strip()


def _fix_lone_letters(tokens: list[str]) -> list[str]:
    """Phụ âm Latin đứng lẻ: ghép vào âm tiết sau nếu âm sau bắt đầu bằng nguyên âm ('c ơ' -> 'cơ'), ngược lại bỏ."""
    out: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        bare = t.strip(",.;:!?")
        if len(bare) == 1 and bare in _LONE_CONSONANT:
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            if nxt and _VOWEL_START.match(nxt) and t == bare:
                out.append(bare + nxt)
                i += 2
                continue
            trail = t[len(t.rstrip(",.;:!?")):]
            if trail and out:
                out[-1] += trail
            i += 1
            continue
        out.append(t)
        i += 1
    return out


def _merge_split_syllables(tokens: list[str], readings: Readings | None) -> list[str]:
    """Ghép 2 token liền nhau khi ít nhất một token không phải âm Hán-Việt mà hợp lại thì phải ('Hù ng')."""
    if readings is None:
        return tokens
    out: list[str] = []
    i = 0
    while i < len(tokens):
        a = tokens[i]
        if i + 1 < len(tokens):
            b = tokens[i + 1]
            if re.fullmatch(r"\w+", a) and re.fullmatch(r"\w+[,.;:!?]*", b):
                b_core = b.rstrip(",.;:!?")
                if (not readings.is_reading(a) or not readings.is_reading(b_core)) and readings.is_reading(a + b_core):
                    out.append(a + b)
                    i += 2
                    continue
        out.append(a)
        i += 1
    return out


def _drop_running_headers(s: str) -> str:
    return _RUNNING_HEADER.sub(" ", s)


def clean_phien_am(text: str, readings: Readings | None = None, keep_upper: bool = False) -> str:
    """keep_upper: giữ chuỗi VIẾT HOA (vd 'HỘ QUỐC TÝ DÂN' do OCR) thay vì coi là tiêu đề trang;
    pipeline thử cả hai và chọn bản khớp chữ Hán nhiều hơn."""
    if not text:
        return ""
    s = nfc(text)
    s = _BOX_VARIANTS.sub(MISSING, s)
    if not keep_upper:
        s = _drop_running_headers(s)
    s = s.replace("*", " ").replace("+", " ").replace("%", " ")
    s = _FOOTNOTE_INDEX.sub(" ", s)
    # Phiên âm không chứa chữ số (năm tháng viết bằng chữ): token có chữ số là rác OCR
    s = re.sub(r"\S*\d\S*", " ", s)
    s = re.sub(r"[^\w\s□,.;:!?()\"'“”‘’\-–]", " ", s)
    tokens = _fix_lone_letters(s.split())
    tokens = _merge_split_syllables(tokens, readings)
    return _space_punct(" ".join(tokens))


def clean_dich_nghia(text: str, readings: Readings | None = None) -> str:
    if not text or text.strip() in (DN_MISSING, "[Sách gốc không có bản dịch]"):
        return DN_MISSING
    s = nfc(text)
    s = _drop_running_headers(s)
    s = _FOOTNOTE_INDEX.sub(" ", s)
    # Chỉ mục chú thích dính chữ: 'Động*', 'Động%', 'Hưng Yên+'
    s = re.sub(r"(?<=\w)[*+%](?=\W|$)", "", s)
    s = re.sub(r"[*+%]", " ", s)
    # 'thayl', 'thay1', 'thay]' -> 'thay!' ở cuối câu kết sắc phong
    s = re.sub(r"\b(thay)[l1I|\]](?=\s|$)", r"\1!", s)
    s = re.sub(r"\bK[ií]nh\s+c[aâầẩấậẫ]n\s+thay\b!?", "Kính cẩn thay!", s)
    # Năm dương lịch bị OCR tách: '(1 887)' -> '(1887)'
    s = re.sub(r"\((\d)\s(\d{3})\)", r"(\1\2)", s)
    # Rác OCR dính ngoặc kép + chữ số ('"2,2', '(1,000)"'): bản dịch không viết kiểu này
    s = re.sub(r"\(\d{1,3},\d{3}\)\"?", " ", s)
    s = re.sub(r"\"\d+(?:,\d+)*", " ", s)
    # Năm mất ngoặc mở: '31, 1878),' -> '31, (1878),'
    s = re.sub(r"(?<![(\d])\b(1[5-9]\d\d|20\d\d)\)", r"(\1)", s)
    # Số đứng lẻ không thuộc ngày/tháng/năm/thứ... là số trang hoặc chỉ mục chú thích
    tokens = s.split()
    kept: list[str] = []
    for i, t in enumerate(tokens):
        # Số lẻ (kể cả năm 4 chữ số ngoài ngoặc, vd '1981' giữa câu) không theo sau ngày/tháng/năm... là rác
        if re.fullmatch(r"\d{1,4}", t):
            prev = tokens[i - 1].lower().strip(",.;:") if i else ""
            if prev not in _NUMBER_CONTEXT:
                continue
        kept.append(t)
    tokens = _fix_lone_letters(kept)
    s = _space_punct(" ".join(tokens))
    return s or DN_MISSING


def clean_han(text: str) -> str:
    """Giữ chữ Hán, □ và dấu câu Hán; viết liền, bỏ chữ Latin/số."""
    if not text:
        return ""
    s = _BOX_VARIANTS.sub(MISSING, nfc(text))
    return "".join(c for c in s if is_han(c) or c == MISSING or c in HAN_PUNCT)

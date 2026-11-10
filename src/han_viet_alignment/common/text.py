"""Tiện ích văn bản dùng chung: chuẩn hóa Unicode, khóa âm tiết, nhận diện chữ Hán, đọc/ghi khối ### doc_id.

Quy tắc syl_key/is_han/PUNCT giống hệt guideline/mau_du_lieu/kiem_tra_du_lieu.py để số liệu
tự kiểm tra trùng với số liệu giáo viên chấm.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

MISSING = "□"  # U+25A1 — chữ không đọc được / khuyết
DN_MISSING = "[...]"  # đoạn bản dịch bị khuyết
HAN_PUNCT = set("，。、；：！？「」『』（）《》〈〉・")
PUNCT = re.compile(r"[^\w\s□]", re.UNICODE)
_TONES = {"̀": "2", "́": "1", "̃": "4", "̉": "3", "̣": "5"}
_BLOCK_HEADER = re.compile(r"^###\s+(\S+)\s*$")


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def syl_key(s: str) -> str:
    """Khóa âm tiết không phụ thuộc vị trí dấu thanh (hòa = hoà, thủy = thuỷ)."""
    base, tone = [], "0"
    for c in unicodedata.normalize("NFD", s.lower().strip()):
        if c in _TONES:
            tone = _TONES[c]
        else:
            base.append(c)
    return unicodedata.normalize("NFC", "".join(base)) + tone


def is_han(ch: str) -> bool:
    cp = ord(ch)
    return (0x3400 <= cp <= 0x4DBF or 0x4E00 <= cp <= 0x9FFF or
            0xF900 <= cp <= 0xFAFF or 0x20000 <= cp <= 0x3FFFF)


def han_units(s: str) -> list[str]:
    """Các đơn vị được đếm khi so với âm tiết: chữ Hán và □ (bỏ dấu câu Hán)."""
    return [c for c in s if is_han(c) or c == MISSING]


def syllables(s: str) -> list[str]:
    """Tách âm tiết phiên âm giống script kiểm tra: bỏ dấu câu rồi tách khoảng trắng."""
    return PUNCT.sub(" ", s).split()


def clean_cell(s: str) -> str:
    """Ô TSV hợp lệ: NFC, không tab/xuống dòng, không khoảng trắng thừa."""
    return re.sub(r"\s+", " ", nfc(s)).strip()


def read_blocks(path: Path) -> dict[str, str]:
    """Đọc file 03_text_sach dạng '### <doc_id>' + nội dung; giữ thứ tự xuất hiện."""
    blocks: dict[str, list[str]] = {}
    current = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = _BLOCK_HEADER.match(line)
        if m:
            current = m.group(1)
            blocks[current] = []
        elif current is not None:
            blocks[current].append(line)
    return {k: "\n".join(v).strip() for k, v in blocks.items()}


def write_blocks(path: Path, blocks: dict[str, str]) -> None:
    text = "".join(f"### {k}\n{v}\n\n" for k, v in blocks.items())
    Path(path).write_bytes(nfc(text).encode("utf-8"))

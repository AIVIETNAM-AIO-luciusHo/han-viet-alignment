"""Từ điển âm Hán-Việt QuocNgu_SinoNom_TongHop3.xlsx (cột 1: âm Quốc ngữ, cột 2: chữ Hán).

Nạp giống kiem_tra_du_lieu.py để tỷ lệ khớp âm tự tính trùng với cách chấm.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .text import MISSING, nfc, syl_key

DEFAULT_DICT = Path(__file__).resolve().parents[3] / "guideline" / "dict" / "QuocNgu_SinoNom_TongHop3.xlsx"


class Readings:
    def __init__(self, han2keys: dict[str, set[str]], surface: dict[str, str] | None = None):
        self.han2keys = han2keys
        self.valid_keys = {k for ks in han2keys.values() for k in ks}
        # khóa -> cách viết âm (chữ thường) để sửa phiên âm theo chữ Hán
        self.surface = surface if surface is not None else {}

    def __len__(self) -> int:
        return len(self.han2keys)

    def __contains__(self, ch: str) -> bool:
        return ch in self.han2keys

    def match(self, ch: str, syl: str) -> bool:
        """Chữ Hán `ch` có âm `syl` không. □ khớp mọi âm (không tính vào tỷ lệ)."""
        if ch == MISSING or syl == MISSING:
            return True
        return syl_key(syl) in self.han2keys.get(ch, ())

    def is_reading(self, syl: str) -> bool:
        """`syl` có phải một âm Hán-Việt hợp lệ (của bất kỳ chữ nào) không."""
        return syl_key(syl) in self.valid_keys


@lru_cache(maxsize=4)
def load_readings(path: str | Path = DEFAULT_DICT) -> Readings:
    import pandas as pd

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy từ điển {path}. Chép QuocNgu_SinoNom_TongHop3.xlsx vào guideline/dict/.")
    df = pd.read_excel(path, dtype=str).dropna()
    han2keys: dict[str, set[str]] = {}
    surface: dict[str, str] = {}
    for qn, sn in zip(df.iloc[:, 0], df.iloc[:, 1]):
        k = syl_key(qn)
        surface.setdefault(k, nfc(qn.strip().lower()))
        for ch in sn.strip():
            han2keys.setdefault(ch, set()).add(k)
    return Readings(han2keys, surface)

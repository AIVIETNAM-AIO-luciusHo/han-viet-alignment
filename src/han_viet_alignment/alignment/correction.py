"""Sửa lỗi OCR khi dóng Hán ↔ phiên âm để tăng độ khớp âm của file parallel cuối cùng (mục 3, 8).

Mỗi cặp (chữ Hán, âm tiết) lệch nhau được xử lý theo thứ tự, chỉ khi có bằng chứng:
1. Âm tiết không phải âm Hán-Việt hợp lệ (lỗi OCR phiên âm, vd 'Tứng') và cách một âm của chữ Hán
   đúng 1 ký tự -> sửa phiên âm theo chữ Hán (mục 3: "sửa theo chữ Hán và ghi vào ghi_chu").
2. Chỉ khác dấu: nếu ở chỗ khác sách đã đọc chữ đó bằng âm đúng (vd 峻 'tuấn' mà dòng này in 'tuần')
   -> sửa phiên âm; nếu không (vd 記 'Kỷ' trong tên chức, như dữ liệu mẫu) -> giữ để người quyết định.
3. Chữ hình dạng gần giống (SinoNom_Similar_Dic_v2.xlsx) có đúng âm, là ứng viên duy nhất đã gặp trong sách.
4. Bộ nhớ cụm từ: cụm 2–4 âm tiết đã khớp trọn vẹn ở chỗ khác trong sách / dữ liệu mẫu
   (văn sắc phong lặp công thức: 'khâm tai' -> 欽哉, 'bảo ngã lê dân' -> 保我黎民).
5. Không có bằng chứng: chữ OCR coi như không đọc được -> □ (mục 3), chữ gốc ghi vào ghi_chu để đối chiếu ảnh.
"""
from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from ..common.dictionary import Readings
from ..common.text import MISSING, syl_key

SIMILAR_DICT = Path(__file__).resolve().parents[3] / "guideline" / "dict" / "SinoNom_Similar_Dic_v2.xlsx"
MAU_TSV = Path(__file__).resolve().parents[3] / "guideline" / "mau_du_lieu" / "MAU_parallel.tsv"
MAX_N = 4
# Cụm từ chỉ dùng khi MỌI lần gặp trong sách/mẫu đều viết cùng một kiểu: sách viết nhiều kiểu (dị thể)
# thì không chọn theo số đông (mục 3: giữ đúng chữ của bản gốc).
MIN_SHARE = 1.0


@lru_cache(maxsize=1)
def _simplified_map() -> dict[str, tuple[str, ...]]:
    """Chữ CHỈ là giản thể -> các chữ phồn thể tương ứng (đọc STCharacters.txt của OpenCC).

    Chỉ dùng để NHẬN DIỆN, không chuyển đổi (mục 3: "không tự chuyển giản ↔ phồn"). Chữ vừa là giản thể
    vừa là chữ phồn/cổ hợp lệ (准 -> 準|准, 台, 后, 云, 干, 里, 余...) có chính nó trong danh sách -> không tính.
    Sắc phong triều Nguyễn không có chữ giản thể, nên chữ trong bảng này là do OCR sinh ra (mục 5).
    """
    import importlib.util
    spec = importlib.util.find_spec("opencc")
    path = Path(next(iter(spec.submodule_search_locations or []), "")) / "dictionary" / "STCharacters.txt" \
        if spec else None
    if path is None or not path.exists():
        import warnings
        warnings.warn("Chưa cài opencc-python-reimplemented: không nhận diện được chữ giản thể do OCR sinh ra",
                      stacklevel=2)
        return {}
    out: dict[str, tuple[str, ...]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        trads = tuple(parts[1].split())
        if parts[0] not in trads:
            out[parts[0]] = trads
    return out


def simplified_only(ch: str) -> tuple[str, ...] | None:
    """Các chữ phồn thể gợi ý nếu `ch` chỉ là chữ giản thể (do OCR sinh ra), ngược lại None."""
    return _simplified_map().get(ch)


def strip_marks(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def keep_case(src: str, new: str) -> str:
    return new[:1].upper() + new[1:] if src[:1].isupper() else new


class PhraseMemory:
    """Cụm âm tiết (khóa syl_key) -> các cách viết chữ Hán đã khớp âm trọn vẹn."""

    def __init__(self) -> None:
        self.ngrams: dict[tuple[str, ...], Counter] = defaultdict(Counter)
        self.unigrams: dict[str, Counter] = defaultdict(Counter)

    def add_run(self, chars: list[str], syls: list[str]) -> None:
        """Một đoạn liên tiếp các cặp (chữ, âm) đã khớp theo từ điển.

        Chữ giản thể (OCR sinh ra) khớp âm vì từ điển có cả giản thể, nhưng không được học: cắt đoạn tại đó
        để bộ nhớ không bao giờ đề xuất chữ giản thể.
        """
        for k, ch in enumerate(chars):
            if simplified_only(ch):
                self.add_run(chars[:k], syls[:k])
                self.add_run(chars[k + 1:], syls[k + 1:])
                return
        keys = [syl_key(s) for s in syls]
        for k, ch in zip(keys, chars):
            self.unigrams[k][ch] += 1
        for n in range(2, MAX_N + 1):
            for i in range(len(chars) - n + 1):
                self.ngrams[tuple(keys[i:i + n])]["".join(chars[i:i + n])] += 1

    def add_matched(self, chars: list[str], syls: list[str], ok: list[bool]) -> None:
        run_c: list[str] = []
        run_s: list[str] = []
        for c, s, good in zip(chars, syls, ok):
            if good and c != MISSING:
                run_c.append(c)
                run_s.append(s)
            else:
                if run_c:
                    self.add_run(run_c, run_s)
                run_c, run_s = [], []
        if run_c:
            self.add_run(run_c, run_s)

    def lookup(self, keys: tuple[str, ...]) -> str | None:
        cnt = self.ngrams.get(keys)
        if not cnt:
            return None
        best, n = cnt.most_common(1)[0]
        return best if n / sum(cnt.values()) >= MIN_SHARE else None


def load_sample_memory(readings: Readings, memory: PhraseMemory | None = None) -> PhraseMemory:
    """Nạp các dòng mẫu của giáo viên (chữ Hán chuẩn) vào bộ nhớ cụm từ."""
    from ..common.text import han_units, syllables
    memory = memory or PhraseMemory()
    if not MAU_TSV.exists():
        return memory
    import csv
    with MAU_TSV.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            chars, syls = han_units(r["han"]), syllables(r["phien_am"])
            if chars and len(chars) == len(syls):
                memory.add_matched(chars, syls, [readings.match(c, s) for c, s in zip(chars, syls)])
    return memory


@lru_cache(maxsize=1)
def _similar_map() -> dict[str, frozenset[str]]:
    """Chữ -> tập chữ gần giống hình dạng (hai chiều)."""
    if not SIMILAR_DICT.exists():
        return {}
    import ast

    import pandas as pd
    df = pd.read_excel(SIMILAR_DICT, dtype=str).dropna()
    out: dict[str, set[str]] = defaultdict(set)
    for c, lst in zip(df.iloc[:, 0], df.iloc[:, 1]):
        c = c.strip()
        try:
            sims = ast.literal_eval(lst)
        except (ValueError, SyntaxError):
            continue
        for s in sims:
            out[c].add(s)
            out[s].add(c)
    return {k: frozenset(v) for k, v in out.items()}


def shape_candidates(ch: str, syl: str, readings: Readings, memory: PhraseMemory | None) -> str | None:
    """Chữ gần giống hình dạng với `ch`, có âm `syl`, và là chữ DUY NHẤT như vậy đã gặp với âm này trong sách.

    Không dùng chuyển giản -> phồn tự động (mục 3: "không tự chuyển giản ↔ phồn"; nhóm đã gỡ OpenCC).
    Nhiều ứng viên cùng đủ điều kiện (thường là dị thể, vd 靜/静) -> không chọn: chọn theo số đông là
    đoán dị thể thay vì đọc ảnh (mục 3: "giữ đúng chữ của bản gốc: phồn thể, dị thể").
    Ứng viên chưa từng gặp trong sách cũng bỏ (vd 辰 -> 医 thay vì 依).
    """
    cands = {c for c in _similar_map().get(ch, ())
             if readings.match(c, syl) and c != MISSING and not simplified_only(c)}
    if not cands or memory is None:
        return None
    seen = memory.unigrams.get(syl_key(syl), Counter())
    attested = [c for c in cands if seen[c]]
    return attested[0] if len(attested) == 1 else None


def fix_syllable(syl: str, ch: str, readings: Readings) -> str | None:
    """Âm tiết OCR hỏng (không phải âm Hán-Việt) -> âm của chữ `ch` cách đúng 1 ký tự."""
    if readings.is_reading(syl):
        return None
    low = unicodedata.normalize("NFC", syl.lower())
    best, best_d = None, 2
    for k in readings.han2keys.get(ch, ()):
        surf = readings.surface.get(k)
        if not surf:
            continue
        d = edit_distance(low, surf)
        if d < best_d:
            best, best_d = surf, d
    return keep_case(syl, best) if best else None


def tone_only(ch: str, syl: str, readings: Readings) -> bool:
    """Âm của chữ chỉ khác âm tiết ở dấu (vd 記 ký / Kỷ)."""
    base = strip_marks(syl)
    return any(strip_marks(readings.surface.get(k, "")) == base for k in readings.han2keys.get(ch, ()))


def fix_tone(ch: str, syl: str, readings: Readings, memory: PhraseMemory | None) -> str | None:
    """Phiên âm sai dấu (vd 峻 ghi 'tuần'): sửa theo chữ Hán khi ở chỗ khác chính sách này đã đọc chữ đó
    bằng âm đúng (≥ 1 lần, trong đoạn khớp trọn vẹn) — mục 3, vd 宜 'nghị' -> 'nghi'.
    Không có bằng chứng (vd 記 'Kỷ' trong tên chức) -> giữ."""
    if memory is None:
        return None
    base = strip_marks(syl)
    best, best_n = None, 0
    for k in readings.han2keys.get(ch, ()):
        surf = readings.surface.get(k, "")
        n = memory.unigrams.get(k, Counter())[ch]
        if surf and strip_marks(surf) == base and n > best_n:
            best, best_n = surf, n
    return keep_case(syl, best) if best else None

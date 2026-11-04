"""
dictionary_helper.py — Tiện ích xử lý từ điển Hán Nôm và Quốc ngữ.
Tải và tra cứu hai chiều:
1. Chữ Hán -> Tập các âm Hán-Việt hợp lệ.
2. Âm Hán-Việt -> Tập các chữ Hán phồn thể tương ứng.
Được chuẩn hóa theo đúng thuật toán trong kiem_tra_du_lieu.py của ban tổ chức.
"""
import unicodedata
from pathlib import Path
import pandas as pd

TONES = {"\u0300": "2", "\u0301": "1", "\u0303": "4", "\u0309": "3", "\u0323": "5"}

def syl_key(s: str) -> str:
    """Khóa âm tiết không phụ thuộc vị trí đặt dấu thanh (hòa = hoà, thủy = thuỷ)."""
    base, tone = [], "0"
    for c in unicodedata.normalize("NFD", s.lower().strip()):
        if c in TONES:
            tone = TONES[c]
        else:
            base.append(c)
    return unicodedata.normalize("NFC", "".join(base)) + tone

class SinoNomDictionary:
    def __init__(self, dict_path: str = None):
        cur = Path(__file__).resolve()
        project_root = None
        for p in [cur] + list(cur.parents):
            if (p / "guideline").exists() or (p / ".git").exists():
                project_root = p
                break
        if project_root is None:
            project_root = Path.cwd()

        self.dict_path = Path(dict_path) if dict_path else project_root / "guideline" / "dict" / "QuocNgu_SinoNom_TongHop3.xlsx"
        self.han2qn = {}      # char -> set of syl_keys
        self.qn2han = {}      # syl_key -> set of chars
        self.raw_mappings = {} # char -> set of original qn strings
        self._load()

    def _load(self):
        if not self.dict_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file từ điển: {self.dict_path}")
            
        print(f"[*] Đang nạp từ điển {self.dict_path.name}...")
        df = pd.read_excel(str(self.dict_path), dtype=str).dropna()
        
        for qn, sn in zip(df.iloc[:, 0], df.iloc[:, 1]):
            qn_str = str(qn).strip()
            k = syl_key(qn_str)
            for ch in str(sn).strip():
                self.han2qn.setdefault(ch, set()).add(k)
                self.qn2han.setdefault(k, set()).add(ch)
                self.raw_mappings.setdefault(ch, set()).add(qn_str)
                
        print(f"[✓] Đã nạp {len(self.han2qn)} chữ Hán và {len(self.qn2han)} âm đọc Hán-Việt.")

    def is_match(self, han_char: str, qn_syl: str) -> bool:
        """Kiểm tra chữ Hán và âm tiết có khớp nhau trong từ điển không."""
        if han_char == "□":
            return True
        k = syl_key(qn_syl)
        return k in self.han2qn.get(han_char, set())

    def get_candidates_for_reading(self, qn_syl: str) -> set:
        """Lấy danh sách các chữ Hán tương ứng với âm đọc."""
        k = syl_key(qn_syl)
        return self.qn2han.get(k, set())

    def get_readings_for_char(self, han_char: str) -> set:
        """Lấy các âm đọc của chữ Hán."""
        return self.raw_mappings.get(han_char, set())

if __name__ == "__main__":
    d = SinoNomDictionary()
    print("Test match 敕 -> sắc:", d.is_match("敕", "sắc"))
    print("Test candidates for 'hưng':", d.get_candidates_for_reading("hưng"))


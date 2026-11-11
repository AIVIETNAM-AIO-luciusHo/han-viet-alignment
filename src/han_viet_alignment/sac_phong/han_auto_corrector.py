"""
han_auto_corrector.py — Module tự động sửa lỗi và dóng hàng chữ Hán (Auto-Correction):
Kết hợp:
1. Chữ Hán OCR thô từ ảnh sắc phong.
2. Chuỗi âm tiết Quốc ngữ (Phiên âm) đã được VietOCR nhận diện chuẩn xác.
3. Từ điển chuẩn âm: QuocNgu_SinoNom_TongHop3.xlsx.
4. Từ điển chữ Hán tương tự hình dáng (Confusion Matrix): SinoNom_Similar_Dic_v2.xlsx.
5. Tri thức ngữ cảnh văn bản hành chính triều Nguyễn (Domain Priors).

Thuật toán: Quy hoạch động căn chỉnh chuỗi (Dynamic Programming Global Sequence Alignment).
"""
import ast
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Set, Tuple
import pandas as pd

_TONES = {'\u0300': '2', '\u0301': '1', '\u0303': '4', '\u0309': '3', '\u0323': '5'}
_PUNCT = re.compile(r"[^\w\s□]", re.UNICODE)

def syl_key(s: str) -> str:
    """Chuẩn hóa âm tiết tiếng Việt về khóa thanh điệu không phụ thuộc vị trí đặt dấu."""
    base, tone = [], '0'
    for c in unicodedata.normalize('NFD', s.lower().strip()):
        if c in _TONES:
            tone = _TONES[c]
        else:
            base.append(c)
    return unicodedata.normalize('NFC', ''.join(base)) + tone

def is_han(ch: str) -> bool:
    cp = ord(ch)
    return (0x3400 <= cp <= 0x4DBF or 0x4E00 <= cp <= 0x9FFF or
            0xF900 <= cp <= 0xFAFF or 0x20000 <= cp <= 0x3FFFF)

class HanAutoCorrector:
    _instance = None

    def __init__(self, dict_path: str = None, sim_path: str = None):
        # Tự động định vị project root (chứa guideline/ hoặc .git)
        cur = Path(__file__).resolve()
        project_root = None
        for p in [cur] + list(cur.parents):
            if (p / "guideline").exists() or (p / ".git").exists():
                project_root = p
                break
        if project_root is None:
            project_root = Path.cwd()

        self.dict_path = Path(dict_path) if dict_path else project_root / "guideline" / "dict" / "QuocNgu_SinoNom_TongHop3.xlsx"
        self.sim_path = Path(sim_path) if sim_path else project_root / "guideline" / "dict" / "SinoNom_Similar_Dic_v2.xlsx"
        
        self.han_readings: Dict[str, Set[str]] = {}
        self.qn_to_han: Dict[str, List[str]] = {}
        self.similar_map: Dict[str, List[str]] = {}
        self.freq_weights: Dict[str, int] = {}
        
        self._load_data()

    def _load_data(self):
        print("[*] Đang nạp từ điển Hán Nôm và ma trận chữ tương tự...")
        # 1. Nạp QuocNgu_SinoNom_TongHop3
        if not self.dict_path.exists():
            print(f"[!] KHÔNG THẤY TỪ ĐIỂN {self.dict_path} — tắt Auto-Correction, giữ nguyên chữ Hán OCR thô.")
        else:
            df_th = pd.read_excel(self.dict_path, dtype=str).dropna()
            for qn, sn in zip(df_th.iloc[:, 0], df_th.iloc[:, 1]):
                k = syl_key(qn)
                for ch in sn.strip():
                    self.han_readings.setdefault(ch, set()).add(k)
                    if k not in self.qn_to_han:
                        self.qn_to_han[k] = []
                    if ch not in self.qn_to_han[k]:
                        self.qn_to_han[k].append(ch)

        # 2. Nạp SinoNom_Similar_Dic_v2
        if self.sim_path.exists():
            df_sim = pd.read_excel(self.sim_path)
            for _, r in df_sim.iterrows():
                c = str(r['Input Character']).strip()
                sim_list = r['Top 20 Similar Characters']
                if isinstance(sim_list, str):
                    try:
                        self.similar_map[c] = ast.literal_eval(sim_list)
                    except:
                        self.similar_map[c] = []

        # 3. Nạp Domain Priors (từ vựng sắc phong triều Nguyễn kinh điển)
        root = Path(__file__).parent.parent
        mau_path = root / "guideline" / "mau_du_lieu" / "MAU_parallel.tsv"
        if mau_path.exists():
            df_mau = pd.read_csv(mau_path, sep='\t', dtype=str)
            for h_str in df_mau['han'].dropna():
                for ch in h_str:
                    self.freq_weights[ch] = self.freq_weights.get(ch, 0) + 15

        domain_priors = {
            '敕': 500, '勅': 400, '命': 300, '神': 300, '之': 300, '原': 200, '贈': 200,
            '明': 200, '達': 200, '敦': 250, '靜': 200, '雄': 200, '俊': 200, '儁': 200,
            '卓': 200, '偉': 200, '上': 200, '等': 200, '護': 200, '國': 200, '庇': 200,
            '民': 200, '稔': 200, '著': 200, '靈': 200, '應': 200, '肆': 200, '今': 200,
            '丕': 200, '承': 200, '膺': 200, '耿': 200, '緬': 200, '念': 200, '休': 200,
            '庥': 200, '可': 200, '加': 200, '仍': 200, '准': 200, '依': 200, '舊': 200,
            '奉': 200, '事': 200, '相': 200, '佑': 200, '保': 200, '我': 200, '黎': 200,
            '欽': 250, '哉': 250, '嗣': 250, '德': 250, '年': 200, '月': 200, '日': 200,
            '拾': 180, '壹': 180, '貳': 180, '參': 180, '肆': 180, '伍': 180, '陸': 180,
            '柒': 180, '捌': 180, '玖': 180, '元': 180, '通': 250, '睿': 250, '省': 180,
            '縣': 180, '社': 180, '總': 180, '村': 180, '翊': 180, '中': 180, '興': 200,
            '金': 250, '洞': 250, '安': 200, '武': 200, '同': 180, '慶': 200, '啟': 200,
            '定': 200, '維': 200, '新': 200, '保': 200, '大': 200, '成': 180, '泰': 200,
            '城': 180, '隍': 180, '靈': 200, '扶': 180, '尊': 180, '莊': 150, '徽': 150
        }
        for ch, w in domain_priors.items():
            self.freq_weights[ch] = self.freq_weights.get(ch, 0) + w

        print(f"[✓] Đã khởi tạo Auto-Corrector: {len(self.han_readings)} chữ Hán, {len(self.similar_map)} chữ tương tự.")

    def correct_han(self, raw_han: str, phien_am: str) -> Tuple[str, List[Dict]]:
        """
        Sử dụng thuật toán Needleman-Wunsch căn chỉnh chuỗi:
        - raw_han: chuỗi chữ Hán thô từ OCR.
        - phien_am: chuỗi phiên âm tiếng Việt chuẩn từ VietOCR.
        Trả về: (chuỗi chữ Hán đã sửa, danh sách các bước sửa).

        Theo HUONG_DAN_DO_AN mục 3 ("giữ đúng chữ của bản gốc") và bước 7 ("đối chiếu ảnh gốc để sửa"):
        KHÔNG sinh chữ Hán từ phiên âm. Chỉ sửa khi chữ OCR có hình dạng gần giống một chữ đúng âm
        (Trường hợp 2). Chữ OCR sai mà không có ứng viên hình dạng -> giữ nguyên ('keep_ocr') để
        người hiệu đính sửa theo ảnh; chữ OCR bỏ sót -> ghi □ ('missing') và ghi chú khi dóng hàng.
        """
        if not phien_am or not self.han_readings:
            # Không có từ điển thì mọi âm đều không tra được -> sẽ thay toàn bộ bằng □; giữ nguyên OCR thô
            return raw_han, []

        han_chars = [c for c in raw_han if is_han(c)]
        pa_syls = [s for s in _PUNCT.sub(" ", phien_am).split() if s]

        M = len(pa_syls)
        N = len(han_chars)
        if M == 0:
            return raw_han, []

        dp = [[-999999 for _ in range(N + 1)] for _ in range(M + 1)]
        backtrack = [[(0, 0, "") for _ in range(N + 1)] for _ in range(M + 1)]
        dp[0][0] = 0

        # Phạt bỏ rác OCR thừa
        for j in range(1, N + 1):
            dp[0][j] = dp[0][j - 1] - 3
            backtrack[0][j] = (0, j - 1, "del_ocr")

        # Phạt chèn chữ thiếu từ phiên âm
        for i in range(1, M + 1):
            dp[i][0] = dp[i - 1][0] - 5
            backtrack[i][0] = (i - 1, 0, "ins_pa")

        for i in range(1, M + 1):
            syl = pa_syls[i - 1]
            sk = syl_key(syl)

            for j in range(1, N + 1):
                ch = han_chars[j - 1]

                # Trường hợp 1: Khớp âm chính xác
                if sk in self.han_readings.get(ch, ()):
                    score = dp[i - 1][j - 1] + 12
                    action = ("match", ch)
                else:
                    # Trường hợp 2: Chữ OCR có hình dạng tương tự (Similar Lookalike)
                    sim_cands = [sc for sc in self.similar_map.get(ch, []) if sk in self.han_readings.get(sc, ())]
                    if sim_cands:
                        sim_match = max(sim_cands, key=lambda c: self.freq_weights.get(c, 0))
                        score = dp[i - 1][j - 1] + 9
                        action = ("similar", sim_match)
                    else:
                        # Trường hợp 3: chữ OCR không khớp âm, không có chữ giống hình -> giữ nguyên chữ OCR
                        score = dp[i - 1][j - 1] - 4
                        action = ("keep_ocr", ch)

                if score > dp[i][j]:
                    dp[i][j] = score
                    backtrack[i][j] = (i - 1, j - 1, action)

                # Bỏ qua chữ rác từ OCR
                del_score = dp[i][j - 1] - 3
                if del_score > dp[i][j]:
                    dp[i][j] = del_score
                    backtrack[i][j] = (i, j - 1, "del_ocr")

                # Chữ bị OCR bỏ sót: ghi □ (mục 3: mỗi chữ thiếu một □), không đoán chữ theo âm
                ins_score = dp[i - 1][j] - 5
                if ins_score > dp[i][j]:
                    dp[i][j] = ins_score
                    backtrack[i][j] = (i - 1, j, ("missing", "□"))

        # Truy vết kết quả
        curr_i, curr_j = M, N
        aligned = []
        while curr_i > 0 or curr_j > 0:
            prev_i, prev_j, act = backtrack[curr_i][curr_j]
            if act == "del_ocr":
                pass
            elif isinstance(act, tuple) and act[0] in ("match", "similar", "keep_ocr", "missing"):
                aligned.append({
                    "syllable": pa_syls[curr_i - 1],
                    "char": act[1],
                    "action": act[0]
                })
            elif act == "ins_pa":  # cột 0: không còn chữ OCR nào
                aligned.append({
                    "syllable": pa_syls[curr_i - 1],
                    "char": "□",
                    "action": "missing"
                })
            curr_i, curr_j = prev_i, prev_j

        aligned.reverse()
        corrected_str = "".join([item["char"] for item in aligned])
        return corrected_str, aligned

def get_corrector() -> HanAutoCorrector:
    if HanAutoCorrector._instance is None:
        HanAutoCorrector._instance = HanAutoCorrector()
    return HanAutoCorrector._instance


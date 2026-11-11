"""Dóng phiên âm ↔ dịch nghĩa cấp câu (Bước 7) bằng quy hoạch động kiểu Gale–Church có từ vựng.

Hai vế cùng chữ Quốc ngữ nên dùng được:
- từ chung: tên riêng, chức danh, niên hiệu, mỹ tự thần được bản dịch giữ nguyên âm Hán-Việt;
- mốc neo: 'Khâm tai' ↔ 'Kính (cẩn) thay', dòng niên đại ↔ 'Ngày … năm … (19xx)';
- tỉ lệ độ dài (số âm tiết dịch / phiên âm) ước lượng trên từng văn bản.
Các kiểu hạt cho phép: 1–1, 1–2, 2–1, 2–2, 1–3, 3–1 (đều không để trống vế nào).
"""
from __future__ import annotations

import math
import re

from ..common.text import syllables

BEADS = {(1, 1): 0.0, (1, 2): 0.6, (2, 1): 0.6, (2, 2): 1.4, (1, 3): 1.4, (3, 1): 1.4}

_STOP = set("""và của cho là thì mà đã được các những này kia ấy nay đó rằng vậy cũng như với để ở tại
trong ngoài trên dưới vì nên khi lại đều có không một hai ba ta người việc ra vào theo từ đến tới""".split())
_CLOSE_PA = re.compile(r"kh[âa]m\s+tai", re.I)
_CLOSE_DN = re.compile(r"kính\s+(cẩn\s+)?thay", re.I)
_DATE_PA = re.compile(r"\bni[êe]n\b.*\b(nguy[êe]t|nh[ậa]t)\b", re.I)
_DATE_DN = re.compile(r"\bngày\s+\d+|\(\s*1[5-9]\d\d\s*\)|tháng\s+\d+\s+năm", re.I)


def _tokens(s: str) -> set[str]:
    return {t for t in (w.lower() for w in syllables(s)) if t not in _STOP and not t.isdigit()}


def _score(pa: str, dn: str, ratio: float) -> float:
    tp, td = _tokens(pa), _tokens(dn)
    lex = 2 * len(tp & td) / (len(tp) + len(td)) if tp and td else 0.0
    n_pa, n_dn = max(len(syllables(pa)), 1), max(len(syllables(dn)), 1)
    length = abs(math.log(n_dn / (ratio * n_pa)))
    anchor = 0.0
    close_pa, close_dn = bool(_CLOSE_PA.search(pa)), bool(_CLOSE_DN.search(dn))
    date_pa, date_dn = bool(_DATE_PA.search(pa)), bool(_DATE_DN.search(dn))
    anchor += 2.0 if close_pa and close_dn else (-1.5 if close_pa != close_dn else 0)
    anchor += 2.0 if date_pa and date_dn else (-1.5 if date_pa != date_dn else 0)
    return 4.0 * lex + anchor - 1.2 * length


def align_sentences(pa: list[str], dn: list[str]) -> list[tuple[list[int], list[int]]]:
    """Trả về các hạt (chỉ số câu phiên âm, chỉ số câu dịch) phủ hết cả hai vế, theo thứ tự."""
    m, n = len(pa), len(dn)
    if m == 0 or n == 0:
        return [(list(range(m)), list(range(n)))] if (m or n) else []
    tot_pa = sum(len(syllables(s)) for s in pa) or 1
    tot_dn = sum(len(syllables(s)) for s in dn) or 1
    ratio = tot_dn / tot_pa
    NEG = -1e18
    dp = [[NEG] * (n + 1) for _ in range(m + 1)]
    bt: list[list[tuple[int, int] | None]] = [[None] * (n + 1) for _ in range(m + 1)]
    dp[0][0] = 0.0
    for i in range(m + 1):
        for j in range(n + 1):
            if dp[i][j] == NEG:
                continue
            for (a, b), pen in BEADS.items():
                ii, jj = i + a, j + b
                if ii > m or jj > n:
                    continue
                s = dp[i][j] + _score(" ".join(pa[i:ii]), " ".join(dn[j:jj]), ratio) - pen
                if s > dp[ii][jj]:
                    dp[ii][jj], bt[ii][jj] = s, (a, b)
    if dp[m][n] == NEG:  # không phủ được bằng các hạt cho phép (vd 1 câu PA, 5 câu dịch): gộp hết
        return [(list(range(m)), list(range(n)))]
    beads = []
    i, j = m, n
    while i or j:
        a, b = bt[i][j]
        beads.append((list(range(i - a, i)), list(range(j - b, j))))
        i, j = i - a, j - b
    beads.reverse()
    return beads


_RISK_DATE_PA = re.compile(r"\bni[êe]n\b.*\bnh[ậa]t\W*$", re.IGNORECASE)
_RISK_DATE_DN = re.compile(r"\bngày\s+(\d|mồng|mùng)", re.IGNORECASE)


def _names(pa: str) -> set[str]:
    """Âm tiết viết hoa không đứng đầu câu trong phiên âm: tên riêng, mỹ tự, địa danh (bản dịch giữ nguyên)."""
    out: set[str] = set()
    for sent in re.split(r"(?<=[.!?;:])\s+", pa):
        toks = syllables(sent)
        out.update(t.lower() for t in toks[1:] if t[:1].isupper() and not t.isupper())
    return out


def pair_risks(pa: str, dn: str, ratio: float) -> list[str]:
    """Dấu hiệu một cặp phiên âm ↔ dịch nghĩa có thể dóng lệch (mục 6–7: OMISSION/ADDITION).

    Dùng để người hiệu đính rà trước các cặp hợp lệ dễ bị chấm lỗi; không tự sửa gì.
    """
    risks = []
    if bool(_CLOSE_PA.search(pa)) != bool(_CLOSE_DN.search(dn)):
        risks.append("LECH_MOC_KET")
    if bool(_RISK_DATE_PA.search(pa)) != bool(_RISK_DATE_DN.search(dn)):
        risks.append("LECH_MOC_NGAY")
    n_pa, n_dn = len(syllables(pa)), len(syllables(dn))
    if n_pa >= 4 and not 0.5 <= n_dn / (max(ratio, 0.1) * n_pa) <= 2.0:
        risks.append("LECH_DO_DAI")
    names = _names(pa)
    if len(names) >= 3:
        dn_toks = {t.lower() for t in syllables(dn)}
        if len(names & dn_toks) / len(names) < 0.5:
            risks.append("THIEU_TEN_RIENG")
    return risks

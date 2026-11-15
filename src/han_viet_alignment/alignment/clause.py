"""Tách một cặp câu phiên âm ↔ dịch nghĩa thành các cặp mệnh đề nhỏ hơn (HD 3.1: ưu tiên đơn vị nhỏ nhất).

Sau bước dóng cấp câu (pa_dn.py), mỗi cặp thường còn nhiều mệnh đề ngăn bởi , ; : (vd 'Tứ kim phi thừa cảnh
mệnh, miến niệm thần hưu.' ↔ 'Nay trẫm gánh vâng mệnh lớn, nhớ nghĩ ơn thần.'). Ở đây chia tiếp hai vế tại
dấu câu rồi quy hoạch động chọn cách ghép mệnh đề (a : b) sao cho được nhiều cặp nhất mà vẫn đúng nghĩa:

* thưởng mỗi cặp tạo thêm; phạt độ dài lệch tỉ lệ của chính cặp câu cha;
* từ neo: âm tiết xuất hiện đúng một lần ở mỗi vế cha (tên riêng, địa danh, mỹ tự, chức danh). Neo nằm ở
  vế này mà ứng của nó ở cặp khác ('Hưng Yên tỉnh, Khoái Châu phủ' ↔ 'phủ Khoái Châu, tỉnh Hưng Yên'
  bị đảo) -> phạt nặng, nên DP tự gộp những đoạn bản dịch đảo trật tự;
* ranh giới mơ hồ (dời ranh giới một mệnh đề mà điểm gần như không đổi) -> gộp hai cặp kề, vì tách sai
  là lỗi còn gộp thì vẫn đúng (HD: không chia cơ học theo dấu câu nếu mất quan hệ dịch).
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

from ..common.text import syllables

_CLAUSE_END = re.compile(r"(?<=[,;:.!?])[\"'”’)\]]*\s+")
_STOP = {unicodedata.normalize("NFD", w).encode("ascii", "ignore").decode().replace("đ", "d")
         for w in """và của cho là thì mà đã được các những này kia ấy nay đó rằng vậy cũng như với để ở tại
         trong ngoài trên dưới vì nên khi lại đều có không một hai ba ta người việc ra vào theo từ đến tới
         chi dĩ nhi vi kỳ kì giả dã hồ vu ư thị hữu vô bất chư sở năm tháng ngày thứ""".split()}
_MAX = 4          # số mệnh đề tối đa mỗi vế trong một cặp con (ngoài cặp 'giữ nguyên')
_W_CROSS = 3.0    # phạt mỗi từ neo bị bắt chéo sang cặp khác
_W_LEN = 1.6      # phạt lệch độ dài (log tỉ lệ, sau ngưỡng)
_LEN_FREE = 0.35  # lệch log-tỉ-lệ dưới ngưỡng này coi như bình thường
_MARGIN = 0.6     # ranh giới thay thế có điểm kém hơn < _MARGIN -> coi là mơ hồ, gộp
_MIN_SYL = 2      # mệnh đề phiên âm < 2 âm tiết ('Sắc,') gộp vào mệnh đề sau


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d").replace("đ", "d")
    return "".join(c for c in s if not unicodedata.combining(c))


def split_clauses(text: str) -> list[str]:
    parts, last = [], 0
    for m in _CLAUSE_END.finditer(text):
        parts.append(text[last:m.start()] + m.group(0).strip())
        last = m.end()
    parts.append(text[last:])
    return [p.strip() for p in parts if p.strip()]


def _merge_tiny(parts: list[str]) -> list[str]:
    out: list[str] = []
    carry = ""
    for p in parts:
        p = f"{carry} {p}".strip() if carry else p
        carry = ""
        if len(syllables(p)) < _MIN_SYL:
            carry = p
            continue
        out.append(p)
    if carry:
        if out:
            out[-1] = f"{out[-1]} {carry}"
        else:
            out.append(carry)
    return out


def _toks(s: str) -> list[str]:
    return [t for t in (_fold(w) for w in syllables(s)) if len(t) >= 2 and t not in _STOP and not t.isdigit()]


class _Scorer:
    def __init__(self, pa: list[str], dn: list[str]):
        self.pa, self.dn = pa, dn
        self.lp = [max(len(syllables(s)), 1) for s in pa]
        self.ld = [max(len(syllables(s)), 1) for s in dn]
        self.ratio = sum(self.ld) / sum(self.lp)
        tp = [_toks(s) for s in pa]
        td = [_toks(s) for s in dn]
        cp = Counter(t for x in tp for t in x)
        cd = Counter(t for x in td for t in x)
        anchors = {t for t in cp if cp[t] == 1 and cd.get(t) == 1}
        self.ap = [set(x) & anchors for x in tp]
        self.ad = [set(x) & anchors for x in td]

    def bead(self, i0: int, i1: int, j0: int, j1: int) -> float:
        """Điểm cặp con pa[i0:i1] ↔ dn[j0:j1]: 1 cho mỗi cặp, trừ phạt."""
        sp = set().union(*self.ap[i0:i1])
        sd = set().union(*self.ad[j0:j1])
        cross = len(sp ^ sd)
        n_p, n_d = sum(self.lp[i0:i1]), sum(self.ld[j0:j1])
        dev = abs(math.log(n_d / (self.ratio * n_p)))
        return 1.0 + 0.15 * len(sp & sd) - _W_CROSS * cross - _W_LEN * max(0.0, dev - _LEN_FREE)


def refine_pair(pa: str, dn: str) -> list[tuple[str, str]]:
    """Chia cặp (pa, dn) thành các cặp mệnh đề theo thứ tự; trả [(pa, dn)] nếu không tách được an toàn."""
    P = _merge_tiny(split_clauses(pa))
    D = split_clauses(dn)
    if len(P) < 2 or len(D) < 2 or not syllables(dn):
        return [(pa, dn)]
    m, n = len(P), len(D)
    sc = _Scorer(P, D)
    NEG = -1e18
    dp = [[NEG] * (n + 1) for _ in range(m + 1)]
    bt: list[list[tuple[int, int] | None]] = [[None] * (n + 1) for _ in range(m + 1)]
    dp[0][0] = 0.0
    for i in range(m + 1):
        for j in range(n + 1):
            if dp[i][j] == NEG:
                continue
            for a in range(1, m - i + 1):
                for b in range(1, n - j + 1):
                    # cặp con lớn chỉ cho phép khi nó phủ hết phần còn lại (gộp đuôi)
                    if (a > _MAX or b > _MAX) and not (i + a == m and j + b == n):
                        continue
                    s = dp[i][j] + sc.bead(i, i + a, j, j + b)
                    if s > dp[i + a][j + b]:
                        dp[i + a][j + b], bt[i + a][j + b] = s, (a, b)
    cuts = []  # các điểm (i, j) cuối mỗi cặp con
    i, j = m, n
    while i or j:
        a, b = bt[i][j]
        cuts.append((i, j))
        i, j = i - a, j - b
    cuts = [(0, 0)] + cuts[::-1]

    # Gộp ranh giới mơ hồ: thử dời ranh giới (i, j) sang (i±1, j) hoặc (i, j±1) giữa hai cặp kề.
    changed = True
    while changed and len(cuts) > 2:
        changed = False
        for k in range(1, len(cuts) - 1):
            (i0, j0), (i, j), (i2, j2) = cuts[k - 1], cuts[k], cuts[k + 1]
            cur = sc.bead(i0, i, j0, j) + sc.bead(i, i2, j, j2)
            alt = max((sc.bead(i0, x, j0, y) + sc.bead(x, i2, y, j2)
                       for x, y in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1))
                       if i0 < x < i2 and j0 < y < j2), default=NEG)
            merged = sc.bead(i0, i2, j0, j2)
            if alt > cur - _MARGIN or sc.bead(i0, i, j0, j) < 0.3 or sc.bead(i, i2, j, j2) < 0.3 \
                    or merged > cur:
                del cuts[k]
                changed = True
                break
    out = []
    for (i0, j0), (i1, j1) in zip(cuts, cuts[1:]):
        out.append((" ".join(P[i0:i1]), " ".join(D[j0:j1])))
    return out

"""Dóng hàng Hán ↔ dịch nghĩa cho text sạch đã chia đoạn, không phiên âm (vd Tư trị thông giám).

Hai tầng quy hoạch động (Gale–Church + mốc từ vựng):
  1. Đoạn ↔ đoạn (1:1, 1:2, 2:1, 1:3, 3:1, 2:2).
  2. Trong mỗi nhóm đoạn: câu ↔ câu (a:b, a·b ≤ 6).
Chi phí một bead = w_len·|log(âm tiết Việt / (tỷ lệ·chữ Hán))| + phạt gộp − w_lex·log(1 + số mốc),
trong đó mốc là bigram âm Hán-Việt của chữ Hán trùng bigram âm tiết bản dịch (tên người, địa danh,
chức quan, can chi: 臧質 ↔ Tang Chất, 己亥 ↔ Kỷ Hợi).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from ..common.dictionary import Readings
from ..common.text import syl_key, syllables

HAN_CH = re.compile(r"[㐀-鿿豈-﫿\U00020000-\U0002ffff]")
# Dòng tiêu đề dính Hán + Việt trong bản dịch: "二年Năm Hiếu Kiến thứ 2"
_HEADER = re.compile(r"^([㐀-鿿豈-﫿]+)\s*([^㐀-鿿豈-﫿].*)$")

PARA_BEADS = [(1, 1), (1, 2), (2, 1), (1, 3), (3, 1), (2, 2)]
SENT_BEADS = [(a, b) for a in range(1, 5) for b in range(1, 5) if a * b <= 6]


@dataclass
class Bead:
    h0: int
    h1: int
    v0: int
    v1: int
    lex: int  # số mốc âm chung

    @property
    def kind(self) -> str:
        return f"{self.h1 - self.h0}:{self.v1 - self.v0}"


# ---------- đọc / tách ----------

def paragraphs(text: str) -> list[str]:
    """Mỗi dòng không rỗng là một đoạn."""
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def split_header(line: str) -> tuple[str, str] | None:
    """Tách dòng tiêu đề dính chữ Hán + bản dịch ('二年Năm Hiếu Kiến thứ 2') -> ('二年', 'Năm Hiếu Kiến thứ 2')."""
    m = _HEADER.match(line)
    if m and len(line) < 60 and re.search(r"[A-Za-zÀ-ỹ]", m.group(2)):
        return m.group(1), m.group(2).strip()
    return None


def split_han(p: str) -> list[str]:
    """Cắt câu Hán sau 。！？ (kèm 」』” đứng sau); không cắt bên trong lời dẫn 「…」 chưa đóng."""
    out, buf, depth, i = [], "", 0, 0
    while i < len(p):
        c = p[i]
        buf += c
        if c in "「『":
            depth += 1
        elif c in "」』":
            depth = max(0, depth - 1)
        if c in "。！？":
            while i + 1 < len(p) and p[i + 1] in "」』”":
                i += 1
                buf += p[i]
                if p[i] in "」』":
                    depth = max(0, depth - 1)
            if depth == 0:
                out.append(buf)
                buf = ""
        i += 1
    if buf.strip():
        out.append(buf)
    return out


_VI_CUT = re.compile(r"(?<=[.!?…])([”\"’)]*)\s+(?=[“\"(‘A-ZÀ-Ỹ0-9])")


def split_viet(p: str) -> list[str]:
    """Cắt câu Việt sau . ! ? khi theo sau là khoảng trắng + chữ hoa/số/ngoặc mở ('1.000' không bị cắt);
    ghép lại phần lời dẫn “…” bị cắt giữa chừng."""
    parts = _VI_CUT.split(p)
    raw = [(parts[i] + ((parts[i + 1] or "") if i + 1 < len(parts) else "")).strip()
           for i in range(0, len(parts), 2)]
    out: list[str] = []
    for s in raw:
        if out and out[-1].count("“") > out[-1].count("”"):
            out[-1] += " " + s
        elif s:
            out.append(s)
    return out


# ---------- đặc trưng ----------

def n_han(s: str) -> int:
    return len(HAN_CH.findall(s))


def n_syl(s: str) -> int:
    return len(syllables(s))


def han_bigrams(s: str, readings: Readings) -> set[str]:
    keys = [sorted(readings.han2keys.get(c, ()))[:6] for c in HAN_CH.findall(s)]
    out: set[str] = set()
    for k1, k2 in zip(keys, keys[1:]):
        for x in k1:
            for y in k2:
                out.add(f"{x} {y}")
                out.add(f"{y} {x}")  # tiếng Việt hay đảo trật tự: 兵部 -> Bộ Binh
    return out


def viet_bigrams(s: str) -> set[str]:
    ks = [syl_key(x) for x in syllables(s.replace("-", " "))]
    return {f"{x} {y}" for x, y in zip(ks, ks[1:])}


def _prior(a: int, b: int) -> float:
    return 0.6 * (a - 1) + 0.6 * (b - 1) + (1.0 if a > 1 and b > 1 else 0.0)


# ---------- quy hoạch động ----------

def align(H: list[str], V: list[str], readings: Readings, ratio: float, beads=PARA_BEADS,
          w_len: float = 4.0, w_lex: float = 1.0) -> list[Bead]:
    """Chia H (Hán) và V (Việt) thành các cặp liên tiếp. Không có lời giải -> một bead gộp tất cả."""
    n, m = len(H), len(V)
    if n == 0 or m == 0:
        return [Bead(0, n, 0, m, 0)] if n or m else []
    hb = [han_bigrams(x, readings) for x in H]
    vb = [viet_bigrams(x) for x in V]
    hl = [n_han(x) for x in H]
    vl = [n_syl(x) for x in V]
    INF = float("inf")
    D = [[INF] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int, int] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    D[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if D[i][j] == INF:
                continue
            for a, b in beads:
                if i + a > n or j + b > m:
                    continue
                lh, lv = sum(hl[i:i + a]), sum(vl[j:j + b])
                lex = len(set().union(*hb[i:i + a]) & set().union(*vb[j:j + b]))
                c = (D[i][j] + w_len * abs(math.log((lv + 2) / (ratio * lh + 2)))
                     + _prior(a, b) - w_lex * math.log1p(lex))
                if c < D[i + a][j + b]:
                    D[i + a][j + b] = c
                    back[i + a][j + b] = (a, b, lex)
    if D[n][m] == INF:
        return [Bead(0, n, 0, m, 0)]
    out, i, j = [], n, m
    while i or j:
        a, b, lex = back[i][j]  # type: ignore[misc]
        out.append(Bead(i - a, i, j - b, j, lex))
        i, j = i - a, j - b
    return out[::-1]


@dataclass
class Pair:
    group: int          # chỉ số nhóm đoạn (dùng làm doc_id)
    han: str
    viet: str
    kind: str           # "1:1", "1:2", ... hoặc "tieu_de"
    lex: int
    note: str = ""


def align_text(han_text: str, viet_text: str, readings: Readings) -> tuple[list[Pair], dict]:
    """Dóng hàng toàn văn. Trả (các cặp, thống kê)."""
    Hp, Vraw = paragraphs(han_text), paragraphs(viet_text)
    headers: dict[int, tuple[str, str]] = {}  # vị trí đoạn Việt kế tiếp -> (han, viet)
    Vp: list[str] = []
    for x in Vraw:
        h = split_header(x)
        if h:
            headers[len(Vp)] = h
        else:
            Vp.append(x)
    ratio = sum(map(n_syl, Vp)) / max(1, sum(map(n_han, Hp)))
    groups = align(Hp, Vp, readings, ratio, PARA_BEADS, w_len=4.0, w_lex=1.0)

    pairs: list[Pair] = []
    g = 0
    for bd in groups:
        for pos in sorted(k for k in headers if bd.v0 <= k < bd.v1 or (k == len(Vp) and bd.v1 == k)):
            hh, vv = headers.pop(pos)
            g += 1
            pairs.append(Pair(g, hh, vv, "tieu_de", 0,
                              "Tiêu đề: chữ Hán lấy từ dòng bản dịch, văn bản Hán không có dòng này."))
        g += 1
        hs = [s for p in Hp[bd.h0:bd.h1] for s in split_han(p)]
        vs = [s for p in Vp[bd.v0:bd.v1] for s in split_viet(p)]
        for sb in align(hs, vs, readings, ratio, SENT_BEADS, w_len=3.0, w_lex=1.2):
            pairs.append(Pair(g, "".join(hs[sb.h0:sb.h1]), " ".join(vs[sb.v0:sb.v1]), sb.kind, sb.lex))
    stats = {"han_paras": len(Hp), "viet_paras": len(Vp), "headers": len(Vraw) - len(Vp), "ratio": ratio,
             "para_not_1_1": [(b.h0 + 1, b.h1, b.v0 + 1, b.v1) for b in groups if b.kind != "1:1"]}
    return pairs, stats


def warnings(p: Pair, ratio: float) -> list[str]:
    """Cảnh báo để người rà: lệch độ dài, không có mốc âm chung, gộp nhiều-nhiều."""
    if p.kind == "tieu_de":
        return []
    nh, nv = n_han(p.han), n_syl(p.viet)
    out = []
    r = nv / max(1, nh)
    if nh > 6 and not (0.5 * ratio <= r <= 1.8 * ratio):
        out.append(f"LECH_DO_DAI({r:.2f})")
    if p.lex == 0 and nh > 15:
        out.append("KHONG_MOC")
    a, b = map(int, p.kind.split(":"))
    if a > 1 and b > 1:
        out.append(f"GOP_{p.kind}")
    return out

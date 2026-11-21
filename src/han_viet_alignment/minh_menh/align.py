"""Dóng hàng đoạn chữ Hán ↔ câu dịch cho sách không có phiên âm (Minh Mệnh chính yếu).

Không có phiên âm nên không cắt chữ Hán theo âm được. Thay vào đó, trong từng quyển, quy hoạch động
chọn cách chia chuỗi đoạn Hán và chuỗi câu dịch thành các cặp (a đoạn : b câu) với chi phí:

* độ dài: số âm tiết dịch so với số chữ Hán × tỷ lệ chung của sách (kiểu Gale–Church);
* mốc tờ: đoạn Hán và câu dịch phải nằm cùng (hoặc kề) mặt tờ — đây là neo chính;
* từ Hán-Việt chung: cặp chữ Hán liền nhau mà âm Hán-Việt xuất hiện thành cặp âm tiết trong câu dịch
  (tên người, địa danh, chức quan: 乾元 ↔ Càn-nguyên, 兵部 ↔ Bộ Binh) được thưởng;
* hình dạng cặp: 1:1 rẻ nhất, gộp nhiều đoạn/câu tốn dần; bỏ đoạn Hán hoặc câu dịch rất đắt.
"""
from __future__ import annotations

import math
import unicodedata
from collections import Counter
from dataclasses import dataclass

import numpy as np

from ..common.dictionary import Readings
from ..common.text import syl_key, syllables
from .han_ocr import SHEET, HanUnit
from .viet_text import VietSentence

MAX_A, MAX_B = 6, 6
LEX_WEIGHT = 1.0
FOLIO_BAND = 2


@dataclass
class Bead:
    han: list[int]
    viet: list[int]
    cost: float
    lex: int
    gap: int


def _prior(a: int, b: int) -> float:
    if a == 0 or b == 0:
        return 0.0
    p = 0.5 * (a - 1) + 1.2 * (b - 1)
    if a > 1 and b > 1:
        p += 1.0
    return p


def han_bigrams(text: str, readings: Readings) -> set[str]:
    out: set[str] = set()
    keys = [sorted(readings.han2keys.get(c, ()))[:8] for c in text]
    for k1, k2 in zip(keys, keys[1:]):
        for x in k1:
            for y in k2:
                out.add(f"{x} {y}")
                out.add(f"{y} {x}")  # tiếng Việt đảo trật tự: 兵部 -> Bộ Binh
    return out


def viet_bigrams(text: str) -> set[str]:
    ks = [syl_key(s) for s in syllables(text.replace("-", " ").replace(".", " "))]
    return {f"{x} {y}" for x, y in zip(ks, ks[1:])}


def _gap(h0: int, h1: int, v0: int, v1: int) -> int:
    return max(0, v0 - h1, h0 - v1)


def align_quyen(units: list[HanUnit], sents: list[VietSentence], readings: Readings,
                ratio: float, band: int = FOLIO_BAND) -> list[Bead]:
    """Nếu trong dải mặt tờ `band` không có lời giải (mất nhiều mốc liền nhau), nới dải dần."""
    for b in (band, band * 2, band * 4, 10 ** 6):
        try:
            return _align_quyen(units, sents, readings, ratio, b)
        except RuntimeError:
            continue
    raise RuntimeError("Không dóng hàng được quyển này.")


def _align_quyen(units: list[HanUnit], sents: list[VietSentence], readings: Readings,
                 ratio: float, band: int) -> list[Bead]:
    n, m = len(units), len(sents)
    if n == 0 or m == 0:
        return [Bead(list(range(n)), [], 0.0, 0, 0)] if n else [Bead([], list(range(m)), 0.0, 0, 0)] if m else []
    lh = [len(u.text) for u in units]
    lv = [len(syllables(s.text)) for s in sents]
    ph = np.concatenate([[0], np.cumsum(lh)])
    pv = np.concatenate([[0], np.cumsum(lv)])

    # Ma trận số cặp âm chung, chỉ tính trong dải mặt tờ gần nhau; bỏ cặp âm quá phổ biến.
    hb = [han_bigrams(u.text, readings) for u in units]
    vb = [viet_bigrams(s.text) for s in sents]
    df = Counter(b for s in vb for b in s)
    common = {b for b, c in df.items() if c > max(20, 0.05 * m)}
    vb = [s - common for s in vb]
    lex = np.zeros((n + 1, m + 1), dtype=np.int32)
    for i, u in enumerate(units):
        for j, s in enumerate(sents):
            if _gap(u.folio_start, u.folio_end, s.folio_start, s.folio_end) <= band and hb[i] and vb[j]:
                lex[i + 1, j + 1] = min(len(hb[i] & vb[j]), 10)
    lex = lex.cumsum(0).cumsum(1)

    # Dòng niên hiệu (明命三年 ↔ "NĂM MINH-MỆNH THỨ BA (1822)") là neo mạnh: nên đứng riêng, 1:1, cùng năm.
    hy = [u.year for u in units]
    vy = [s.year for s in sents]
    chy = np.concatenate([[0], np.cumsum([y is not None for y in hy])])
    cvy = np.concatenate([[0], np.cumsum([y is not None for y in vy])])

    # Dải j hợp lệ cho mỗi ranh giới i: câu dịch cách mặt tờ của đoạn Hán i không quá FOLIO_BAND.
    hf = [u.folio_start for u in units] + [units[-1].folio_end]
    vf = [s.folio_start for s in sents] + [sents[-1].folio_end]

    def allowed(i: int, j: int) -> bool:
        return abs(hf[i] - vf[j]) <= band

    var = 1.5 * ratio
    INF = float("inf")
    best: list[dict[int, tuple[float, int, int]]] = [dict() for _ in range(n + 1)]
    best[0][0] = (0.0, 0, 0)
    for i in range(n + 1):
        row = best[i]
        for j in sorted(row):
            base = row[j][0]
            for a in range(0, MAX_A + 1):
                i2 = i + a
                if i2 > n:
                    break
                for b in range(0, MAX_B + 1):
                    j2 = j + b
                    if j2 > m or (a == 0 and b == 0) or (a > 2 and b > 2):
                        continue
                    if not allowed(i2, j2) and not (i2 == n and j2 == m):
                        continue
                    if a == 0:
                        c = 4.0 + 0.15 * (pv[j2] - pv[j]) + 3.0 * (b - 1)
                        g = 0
                        L = 0
                    elif b == 0:
                        c = 4.0 + 0.25 * (ph[i2] - ph[i]) + 3.0 * (a - 1)
                        g = 0
                        L = 0
                    else:
                        H = ph[i2] - ph[i]
                        V = pv[j2] - pv[j]
                        d = (V - ratio * H) / math.sqrt(var * max(ratio * H, 1.0))
                        g = _gap(units[i].folio_start, units[i2 - 1].folio_end,
                                 sents[j].folio_start, sents[j2 - 1].folio_end)
                        L = int(lex[i2, j2] - lex[i, j2] - lex[i2, j] + lex[i, j])
                        c = d * d / 2 + _prior(a, b) + (0 if g == 0 else 2.0 if g == 1 else 10.0 * g)
                        c -= LEX_WEIGHT * L
                        nhy, nvy = chy[i2] - chy[i], cvy[j2] - cvy[j]
                        if nhy or nvy:
                            if a == 1 and b == 1 and nhy and nvy:
                                c += -6.0 if hy[i] == vy[j] else 10.0
                            else:
                                c += 6.0 * (nhy + nvy)
                        if sents[j].doc_id != sents[j2 - 1].doc_id:
                            c += 1.5  # gộp câu của hai văn bản
                    tot = base + c
                    if tot < best[i2].get(j2, (INF,))[0]:
                        best[i2][j2] = (tot, a, b)
    if m not in best[n]:
        raise RuntimeError("Không tìm được cách dóng hàng trong dải mặt tờ; kiểm tra mốc tờ.")
    beads: list[Bead] = []
    i, j = n, m
    while i or j:
        tot, a, b = best[i][j]
        prev = best[i - a][j - b][0]
        g = _gap(units[i - a].folio_start, units[i - 1].folio_end,
                 sents[j - b].folio_start, sents[j - 1].folio_end) if a and b else 0
        L = int(lex[i, j] - lex[i - a, j] - lex[i, j - b] + lex[i - a, j - b]) if a and b else 0
        beads.append(Bead(list(range(i - a, i)), list(range(j - b, j)), tot - prev, L, g))
        i, j = i - a, j - b
    beads.reverse()
    return beads


def split_by_quyen(units: list[HanUnit], sents: list[VietSentence]):
    qs = sorted({u.folio_start // SHEET for u in units} | {s.folio_start // SHEET for s in sents})
    for q in qs:
        yield (q, [u for u in units if u.folio_start // SHEET == q],
               [s for s in sents if s.folio_start // SHEET == q])


def low_confidence(n_han: int, n_syl: int, quyen_ratio: float, n_units: int, n_sents: int,
                   lex: int, gap: int, is_year: bool, warns: list[str], cut_score: float = 9.0) -> list[str]:
    """Lý do coi một cặp là kém tin cậy (rỗng = giữ). Ngưỡng chọn từ mẫu đọc tay R1204 (docs/…):
    các cặp lệch ranh giới/sai hầu hết có tỷ lệ âm tiết/chữ lệch xa tỷ lệ của quyển, bị ép gộp đủ
    MAX_B câu, vừa lệch tờ vừa gộp nhiều, hoặc là mảnh Hán rất ngắn không có cặp âm chung."""
    if is_year:
        return []
    out = []
    rel = (n_syl / max(n_han, 1)) / max(quyen_ratio, 1e-6)
    if rel > 1.45 or rel < 0.65:
        out.append("TIN_CAY_THAP:TY_LE")
    if n_sents >= MAX_B and lex == 0:
        out.append("TIN_CAY_THAP:GOP_TOI_DA")  # cặp gốc bị ép gộp đủ MAX_B câu và phần này không có âm chung
    if gap:
        out.append("TIN_CAY_THAP:LECH_TO")
    if n_han < 12 and lex == 0:
        out.append("TIN_CAY_THAP:QUA_NGAN")
    if "NOI_CAU_KHONG_CO_HAN" in warns:
        out.append("TIN_CAY_THAP:NOI_CAU")
    if cut_score <= 0 and lex == 0:
        out.append("TIN_CAY_THAP:CAT_TUY_Y")  # cắt giữa chuỗi chữ, không có ranh giới tự nhiên hay âm chung
    return out


# ---------------------------------------------------------------- tách tới đơn vị nhỏ nhất: 1 câu dịch

_FINAL = set("也矣乎焉哉耳")
_STARTS = ("帝曰", "帝諭", "諭曰", "帝從", "帝命", "帝謂", "帝以", "帝聞", "帝準", "帝可", "帝批", "帝善",
           "帝乃", "帝召", "帝覽", "帝御", "帝嘉", "帝念", "帝因", "帝又", "尋", "先是", "至是", "辰")
_AFTER = ("從之", "可之", "行之", "以聞", "其奏", "如議", "允之")


def _cut_bonus(text: str, p: int, col: set[int], para: set[int]) -> float:
    b = 0.0
    if p in para:
        b += 2.0
    elif p in col:
        b += 0.3
    if text[p - 1] in _FINAL:
        b += 1.2
    if any(text.startswith(s, p) for s in _STARTS):
        b += 1.0
    if any(text.endswith(s, 0, p) for s in _AFTER):
        b += 1.0
    if text.endswith("曰", 0, p):  # không cắt ngay sau 曰 (lời nói thuộc cùng câu)
        b -= 2.0
    return b


@dataclass
class Piece:
    han: str
    sents: list[VietSentence]
    cut_score: float  # điểm ranh giới thấp nhất của hai đầu đoạn (thấp = cắt tùy ý, kém tin cậy)
    lex: int


def split_to_sentences(units: list[HanUnit], sents: list[VietSentence], readings: Readings,
                       ratio: float) -> list[Piece]:
    """Chia chữ Hán của một cặp (a đoạn : b câu) thành b phần, mỗi phần ứng với đúng một câu dịch.

    Quy hoạch động trên vị trí cắt: chi phí độ dài (Gale–Church) − thưởng cặp âm chung giữa phần Hán và câu
    dịch − thưởng ranh giới tự nhiên (_cut_bonus). Ranh giới giữa hai văn bản chỉ cắt ở đầu cột nếu được.
    """
    lines = [ln for u in units for ln in (u.lines or [u.text])]
    text = "".join(lines)
    k = len(sents)
    if k <= 1 or len(text) < 2 * k:
        return [Piece(text, list(sents), 9.0, 0)]
    col, para, pos = set(), set(), 0
    for u in units:
        for ln in (u.lines or [u.text]):
            pos += len(ln)
            col.add(pos)
        para.add(pos)
    n = len(text)
    bonus = [0.0] + [_cut_bonus(text, p, col, para) for p in range(1, n)] + [9.0]
    has_cols = bool(col - {n})
    # vị trí p khớp câu j nếu cặp chữ text[p:p+2] có âm trùng một cặp âm tiết của câu j
    keys = [sorted(readings.han2keys.get(c, ()))[:8] for c in text]
    vbs = [viet_bigrams(s.text) for s in sents]
    pref = []
    for vb in vbs:
        acc = [0]
        for p in range(n):
            hit = 0
            if p + 1 < n and vb:
                for x in keys[p]:
                    for y in keys[p + 1]:
                        if f"{x} {y}" in vb or f"{y} {x}" in vb:
                            hit = 1
                            break
                    if hit:
                        break
            acc.append(acc[-1] + hit)
        pref.append(acc)
    lv = [max(1, len(syllables(s.text))) for s in sents]
    tot_v = sum(lv)
    var = 1.5 * ratio
    INF = float("inf")
    # best[j][p]: chi phí tốt nhất khi j câu đầu đã nhận text[:p]
    best = [dict() for _ in range(k + 1)]
    best[0][0] = (0.0, -1)
    cum_v = 0
    for j in range(k):
        cum_v_next = cum_v + lv[j]
        doc_change = j + 1 < k and sents[j].doc_id != sents[j + 1].doc_id
        exp_end = n * cum_v_next / tot_v
        lo_end = max(1, int(exp_end - 0.45 * n * lv[j] / tot_v) - 6)
        hi_end = min(n, int(exp_end + 0.45 * n * lv[j] / tot_v) + 6)
        if j == k - 1:
            lo_end = hi_end = n
        for p0, (c0, _) in best[j].items():
            for p in range(max(p0 + 1, lo_end), max(p0 + 1, hi_end) + 1):
                if p > n or (p < n and n - p < k - j - 1):
                    continue
                H = p - p0
                d = (lv[j] - ratio * H) / math.sqrt(var * max(ratio * H, 1.0))
                lex_hits = pref[j][p] - pref[j][p0]
                cut = bonus[p] if p < n else 0.0
                if doc_change and p < n and p not in col and has_cols:
                    cut -= 4.0  # ranh giới văn bản nên rơi vào đầu cột
                c = c0 + d * d / 2 - 0.7 * lex_hits - cut
                if c < best[j + 1].get(p, (INF,))[0]:
                    best[j + 1][p] = (c, p0)
        cum_v = cum_v_next
    if n not in best[k]:
        return [Piece(text, list(sents), 9.0, 0)]
    cuts = [n]
    p = n
    for j in range(k, 0, -1):
        p = best[j][p][1]
        cuts.append(p)
    cuts.reverse()  # [0, c1, ..., n]
    out = []
    for j in range(k):
        a, b = cuts[j], cuts[j + 1]
        edge = min(bonus[a] if a > 0 else 9.0, bonus[b] if b < n else 9.0)
        out.append(Piece(text[a:b], [sents[j]], edge, pref[j][b] - pref[j][a]))
    return out


# ------------------------------------------------- dóng toàn cục cấp chữ + gộp ranh giới không chắc chắn
# Đoạn OCR Hán (HanUnit) hay bị ngắt giữa câu (sang trang/cột, chú thích song hành), nên dóng theo đoạn rồi
# mới cắt (split_to_sentences) để lại lỗi ở ranh giới đoạn (đo trên mẫu gán nhãn tay R1204: ~45% cặp lệch).
# Ở đây coi cả quyển là một chuỗi chữ liên tục và chia thành đúng một đoạn cho mỗi câu dịch, trong dải ±W chữ
# quanh vị trí thô lấy từ align_quyen. Điểm của đoạn (chữ a..b ↔ câu j):
#   + âm Hán-Việt từng chữ có trong câu j (trọng số idf: âm xuất hiện ở ít câu thì đáng tin hơn)
#   + cặp chữ liền nhau khớp cặp âm tiết của câu j (tên riêng, chức quan: 兵部 ↔ Bộ Binh)
#   + dòng niên hiệu chỉ ghép với câu niên hiệu cùng năm
#   − lệch độ dài (Gale–Church) ; + ranh giới tự nhiên (đầu đoạn/cột, 也 矣, 帝曰…: _cut_bonus)
#   + khớp mép: 3 chữ sau điểm cắt ↔ âm tiết đầu câu sau, 3 chữ trước ↔ âm tiết cuối câu trước (âm Hán-Việt
#     hoặc từ dịch quen thuộc EDGE_EQ: "Vua dụ rằng" ↔ 帝諭…曰, "… tâu lên" ↔ …以聞)
# Mỗi điểm cắt có "biên độ" = chi phí tăng thêm khi dời nó > 2 chữ (giữ hai cắt bên cạnh). Biên độ thấp = mơ hồ:
# gộp hai câu kề vào một cặp (gộp vẫn đúng nghĩa, cắt sai thì cả hai cặp sai).

# w_cut, w_edge chọn trên nhãn ranh giới docs/danh_gia_minh_menh (354 điểm cắt): cắt đúng ±2 chữ 82.5% -> 88.7%.
GLOBAL = dict(w_uni=0.6, w_bi=1.2, w_len=0.7, w_cut=1.2, W=150, empty=5.0, year=3.0, fold=0.7,
              w_edge=1.0)

# Từ dịch quen thuộc ở đầu/cuối câu không trùng âm Hán-Việt với chữ Hán tương ứng (khóa đã bỏ dấu, _fold):
# "Vua dụ rằng" ↔ 帝諭…曰, "Trẫm" ↔ 朕, "… tâu lên" ↔ …以聞, "Vua ưng cho" ↔ 許之/從之.
EDGE_EQ = {
    "vua": "帝上", "tram": "朕", "tau": "奏言聞", "du": "諭", "bao": "謂諭", "phan": "曰諭", "rang": "曰",
    "khien": "命令", "sai": "命令遣", "xin": "請乞", "cho": "許準允從可", "ung": "許準允", "chuan": "準許",
    "theo": "從", "khen": "嘉奬賞", "thuong": "賞", "moi": "初", "truoc": "先初", "lai": "又復", "quan": "臣",
    "ban": "賜諭頒", "nay": "今玆", "neu": "如若儻", "phai": "是宜", "vay": "也矣", "duoc": "得",
}
EDGE_N = 5          # số âm tiết đầu/cuối câu dịch đem so
EDGE_POS = (1.0, 0.6, 0.3)  # trọng số chữ Hán thứ 1, 2, 3 tính từ điểm cắt


def _fold(key: str) -> str:
    """Khóa âm tiết bỏ hết dấu: bản dịch OCR hay sai dấu ('Tĩnh-thần' cho 省臣 tỉnh thần, 'Chàn-lạp')."""
    k = unicodedata.normalize("NFD", key[:-1]).replace("đ", "d")
    return "".join(c for c in k if not unicodedata.combining(c))


def _vkeys(text: str) -> list[str]:
    return [syl_key(s) for s in syllables(text.replace("-", " ").replace(".", " "))]


@dataclass
class Stream:
    text: str
    col: set[int]
    para: set[int]
    unit_start: list[int]
    years: list[tuple[int, int, int]]


def build_stream(units: list[HanUnit]) -> Stream:
    parts, col, para, ustart, years = [], set(), set(), [], []
    pos = 0
    for u in units:
        ustart.append(pos)
        for ln in (u.lines or [u.text]):
            parts.append(ln)
            pos += len(ln)
            col.add(pos)
        para.add(pos)
        if u.year is not None:
            years.append((ustart[-1], pos, u.year))
    return Stream("".join(parts), col, para, ustart, years)


def rough_cuts(units: list[HanUnit], sents: list[VietSentence], beads: list[Bead], st: Stream) -> list[int]:
    """Vị trí cắt thô cho m câu (m+1 số) từ các bead của align_quyen: chia đoạn Hán của bead theo độ dài câu."""
    rough = [0]
    for bd in beads:
        if not bd.viet:
            continue
        if bd.han:
            h0 = st.unit_start[bd.han[0]]
            last = units[bd.han[-1]]
            h1 = st.unit_start[bd.han[-1]] + sum(len(x) for x in (last.lines or [last.text]))
        else:
            h0 = h1 = rough[-1]
        lv = [max(1, len(syllables(sents[j].text))) for j in bd.viet]
        tot, acc = sum(lv), 0
        for v in lv:
            acc += v
            rough.append(max(rough[-1], h0 + round((h1 - h0) * acc / tot)))
    rough[-1] = len(st.text)
    return rough


def align_stream(st: Stream, sents: list[VietSentence], rough: list[int], readings: Readings,
                 ratio: float, P: dict | None = None) -> tuple[list[int], list[float]]:
    """Trả (cuts, margins): câu j nhận st.text[cuts[j]:cuts[j+1]]; margins[j] là biên độ của cuts[j]."""
    P = {**GLOBAL, **(P or {})}
    text = st.text
    n, m = len(text), len(sents)
    bonus = np.zeros(n + 1)
    for p in range(1, n):
        bonus[p] = _cut_bonus(text, p, st.col, st.para)
    K = [set(readings.han2keys.get(c, ())) for c in text]
    SK = [set(_vkeys(s.text)) for s in sents]
    df = Counter(x for sk in SK for x in sk)
    idf = {x: math.log(1 + m / d) / math.log(1 + m) for x, d in df.items()}
    BG = []
    for s in sents:
        ks = _vkeys(s.text)
        BG.append(set(zip(ks, ks[1:])))
    KF = [{_fold(x) for x in k} for k in K]
    SKF = [{_fold(x) for x in sk} for sk in SK]
    dff = Counter(x for sk in SKF for x in sk)
    idff = {x: math.log(1 + m / d) / math.log(1 + m) for x, d in dff.items()}
    BGF = [{(_fold(x), _fold(y)) for x, y in bg} for bg in BG]
    lv = np.array([max(1, len(syllables(s.text))) for s in sents], float)
    yr = [s.year for s in sents]
    W = P["W"]
    lo = [max(0, rough[j] - W) for j in range(m + 1)]
    hi = [min(n, rough[j] + W) for j in range(m + 1)]
    lo[0] = hi[0] = 0
    lo[m] = hi[m] = n
    for j in range(1, m + 1):
        lo[j] = max(lo[j], lo[j - 1])
    for j in range(m - 1, -1, -1):
        hi[j] = min(hi[j], hi[j + 1])
    var = 1.5 * ratio
    INF = 1e18

    # Khớp mép: chữ Hán ngay sau điểm cắt ↔ âm tiết đầu câu sau, chữ ngay trước ↔ âm tiết cuối câu trước.
    def edge_sets(keys: list[str]) -> tuple[set, set, set]:
        f = {_fold(x) for x in keys}
        return set(keys), f, {c for x in f for c in EDGE_EQ.get(x, "")}

    heads, tails = [], []
    for s in sents:
        ks = [k for k in _vkeys(s.text) if k[:-1].isalpha()]
        heads.append(edge_sets(ks[:EDGE_N]))
        tails.append(edge_sets(ks[-EDGE_N:]))

    def hit(p: int, sets: tuple[set, set, set]) -> bool:
        return bool(K[p] & sets[0] or KF[p] & sets[1] or text[p] in sets[2])

    def edge(j: int, ps: np.ndarray) -> np.ndarray:
        """Điểm khớp mép cho điểm cắt j (giữa câu j-1 và câu j) tại các vị trí ps."""
        out = np.zeros(len(ps))
        if not P["w_edge"] or j <= 0 or j >= m:
            return out
        for t, p in enumerate(ps):
            sc = 0.0
            for d, w in enumerate(EDGE_POS):
                if p + d < n and hit(p + d, heads[j]):
                    sc += w
                if p - 1 - d >= 0 and hit(p - 1 - d, tails[j - 1]):
                    sc += w
            out[t] = sc
        return out

    def emis(j: int, a: int, b: int) -> np.ndarray:
        e = np.zeros(b - a)
        for p in range(a, b):
            ks = K[p] & SK[j]
            if ks:
                e[p - a] += P["w_uni"] * max(idf[x] for x in ks)
            elif P["fold"] and (kf := KF[p] & SKF[j]):
                e[p - a] += P["fold"] * P["w_uni"] * max(idff[x] for x in kf)
        for p in range(a, b - 1):
            if any((x, y) in BG[j] or (y, x) in BG[j] for x in K[p] for y in K[p + 1]):
                e[p - a] += P["w_bi"]
                e[p + 1 - a] += P["w_bi"]
            elif P["fold"] and any((x, y) in BGF[j] or (y, x) in BGF[j] for x in KF[p] for y in KF[p + 1]):
                e[p - a] += P["fold"] * P["w_bi"]
                e[p + 1 - a] += P["fold"] * P["w_bi"]
        for ya, yb, y in st.years:
            s0, s1 = max(ya, a), min(yb, b)
            if s0 < s1:
                e[s0 - a:s1 - a] += P["year"] if yr[j] == y else -P["year"]
        if yr[j] is not None:
            e -= 1.0
        return np.concatenate([[0.0], np.cumsum(e)])

    best: list = [None] * (m + 1)
    arg: list = [None] * (m + 1)
    Es: list = [None] * (m + 1)
    edges: list = [None] * (m + 1)
    best[0] = np.array([0.0])
    for j in range(1, m + 1):
        a = lo[j - 1]
        E = emis(j - 1, a, hi[j])
        Es[j] = (a, E)
        p0s = np.arange(lo[j - 1], hi[j - 1] + 1)
        ps = np.arange(lo[j], hi[j] + 1)
        H = ps[:, None] - p0s[None, :]
        Hc = np.maximum(H, 0).astype(float)
        d = (lv[j - 1] - ratio * Hc) / np.sqrt(var * np.maximum(ratio * Hc, 1.0))
        cost = P["w_len"] * d * d / 2 - (E[ps - a][:, None] - E[p0s - a][None, :])
        cost = np.where(H == 0, P["empty"], cost)
        cost = np.where(H < 0, INF, cost)
        tot = best[j - 1][None, :] + cost
        k = np.argmin(tot, axis=1)
        bj = tot[np.arange(len(ps)), k]
        if j < m:
            edges[j] = edge(j, ps)
            bj = bj - P["w_cut"] * bonus[ps] - P["w_edge"] * edges[j]
        best[j], arg[j] = bj, p0s[k]
    cuts, p = [n], n
    for j in range(m, 0, -1):
        p = int(arg[j][p - lo[j]])
        cuts.append(p)
    cuts.reverse()

    def seg(j: int, x: int, y: int) -> float:
        a, E = Es[j + 1]
        H = y - x
        if H < 0:
            return INF
        if H == 0:
            return P["empty"]
        d = (lv[j] - ratio * H) / math.sqrt(var * max(ratio * H, 1.0))
        return P["w_len"] * d * d / 2 - (E[y - a] - E[x - a])

    margins = [9.0]
    for j in range(1, m):
        a_, c, b_ = cuts[j - 1], cuts[j], cuts[j + 1]

        def f(x: int) -> float:
            return (seg(j - 1, a_, x) + seg(j, x, b_) - P["w_cut"] * bonus[x]
                    - P["w_edge"] * edges[j][x - lo[j]])
        fc = f(c)
        alt = [f(x) for x in range(max(a_, lo[j]), min(b_, hi[j]) + 1) if abs(x - c) > 2]
        margins.append(min(alt) - fc if alt else 9.0)
    margins.append(9.0)
    return cuts, margins


def group_sentences(cuts: list[int], margins: list[float], tau: float) -> list[tuple[int, int]]:
    """Gộp câu qua các điểm cắt có biên độ < tau và qua đoạn Hán rỗng; trả [(câu đầu, câu cuối+1)]."""
    m = len(cuts) - 1
    groups, start = [], 0
    for j in range(1, m + 1):
        if j == m or (margins[j] >= tau and cuts[j] > cuts[start]):
            if j < m or cuts[j] > cuts[start] or not groups:
                groups.append((start, j))
            else:  # đoạn cuối rỗng: nối vào nhóm trước
                groups[-1] = (groups[-1][0], j)
            start = j
    return groups

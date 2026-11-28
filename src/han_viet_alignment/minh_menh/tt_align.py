"""P11-1: align clean (non-OCR) Han / Vietnamese texts (docs-local/122-124 .han.txt/.viet.txt; temporary labels T122-T124).

1. paragraphs = non-blank lines; the first two (header 'Bat dau tu nam...' and the title) stay as their own pairs;
2. paragraph DP (monotone; steps 1-1, 1-2, 2-1, skip Han, skip Viet) with the dictionary bridge + length prior;
3. inside a matched paragraph block: Han sentences split at 。！？； (inside 「」『』 never), Vietnamese at . ! ? (inside “ ” never);
   equal counts -> 1-1; otherwise a DP over sentences (steps up to 3-1 / 1-3 = n-1 merges) on length + bridge.
Texts are never edited: every pair is a verbatim slice (Han) / verbatim slices joined by one space (Viet).
Stdlib only; no LLM, no API, no network."""
import math
import re
import unicodedata

HAN_END = "。！？；"
OPEN_H, CLOSE_H = "「『", "」』"
OPEN_V, CLOSE_V = "“‘", "”’"


def norm(t: str) -> str:
    return unicodedata.normalize("NFC", t)


def read_paras(text: str) -> list:
    """[(line_no, text)] of the non-blank lines (line_no 1-based)."""
    return [(k + 1, l.rstrip("\r")) for k, l in enumerate(norm(text).split("\n")) if l.strip()]


def split_han(t: str) -> list:
    """[(a, b)] slices of t; a sentence ends after one of 。！？； (and a closing quote right after it) at quote depth 0."""
    out, a, depth = [], 0, 0
    i = 0
    while i < len(t):
        c = t[i]
        if c in OPEN_H:
            depth += 1
        elif c in CLOSE_H:
            depth = max(0, depth - 1)
            if depth == 0 and i > 0 and t[i - 1] in HAN_END:
                out.append((a, i + 1))
                a = i + 1
        elif c in HAN_END and depth == 0:
            j = i + 1
            while j < len(t) and t[j] in HAN_END:
                j += 1
            if j < len(t) and t[j] in CLOSE_H:  # terminator then a closing quote of an outer quote: leave to depth logic
                i = j
                continue
            out.append((a, j))
            a = j
            i = j
            continue
        i += 1
    if a < len(t):
        out.append((a, len(t)))
    return [(x, y) for x, y in out if t[x:y].strip()]


def split_viet(t: str) -> list:
    """[(a, b)] slices (whitespace between sentences excluded): split after . ! ? (and ... / ?! runs) followed by space +
    anything or end, at quote depth 0; a closing quote right after a terminator closes the sentence."""
    out, a, depth, i, n = [], 0, 0, 0, len(t)
    while i < n:
        c = t[i]
        if c in OPEN_V:
            depth += 1
        elif c in CLOSE_V:
            depth = max(0, depth - 1)
            if depth == 0 and i > 0 and t[i - 1] in ".!?" and (i + 1 >= n or t[i + 1].isspace()):
                out.append((a, i + 1))
                j = i + 1
                while j < n and t[j].isspace():
                    j += 1
                a, i = j, j
                continue
        elif c in ".!?" and depth == 0:
            j = i + 1
            while j < n and t[j] in ".!?":
                j += 1
            if j < n and t[j] in CLOSE_V and depth == 0:
                i = j
                continue
            if j >= n or t[j].isspace():
                out.append((a, j))
                while j < n and t[j].isspace():
                    j += 1
                a, i = j, j
                continue
            i = j
            continue
        i += 1
    if a < n and t[a:].strip():
        out.append((a, n))
    return [(x, y) for x, y in out if t[x:y].strip()]


def viet_text(t: str, sl: list) -> str:
    return " ".join(t[a:b] for a, b in sl)


# ------------------------------------------------------------------ scoring
def llr(scorer, han: str, viet_syl: list) -> float:
    M = scorer.matched(viet_syl)
    return scorer.unit_scores(han, M, scorer.p0(M)) if han else 0.0


def pair_score(scorer, han: str, vsyl: list, ratio: float, kappa: float) -> float:
    if not han or not vsyl:
        return -1e9
    exp = max(1.0, ratio * len(vsyl))
    return llr(scorer, han, vsyl) - kappa * math.log((len(han) + 3) / (exp + 3)) ** 2


def align_paras(H: list, V: list, scorer, ratio: float, kappa: float = 30.0, skip_h: float = 12.0, skip_v: float = 12.0,
                band: int = 20) -> list:
    """H: list of Han strings, V: list of syllable lists. Returns [(hi0, hi1, vj0, vj1)] with hi/vj ranges (a skip has an
    empty side)."""
    n, m = len(H), len(V)
    NEG = float("-inf")
    f = [[NEG] * (m + 1) for _ in range(n + 1)]
    bk = [[None] * (m + 1) for _ in range(n + 1)]
    f[0][0] = 0.0
    hlen = [len(h) for h in H]
    vlen = [len(v) for v in V]
    for i in range(n + 1):
        for j in range(m + 1):
            cur = f[i][j]
            if cur == NEG or abs(i - j) > band:
                continue
            opts = []
            if i < n:
                opts.append((i + 1, j, -skip_h - 0.05 * hlen[i], (i, i + 1, j, j)))
            if j < m:
                opts.append((i, j + 1, -skip_v - 0.01 * vlen[j], (i, i, j, j + 1)))
            for di, dj in ((1, 1), (1, 2), (2, 1)):
                if i + di <= n and j + dj <= m:
                    hs = "".join(H[i:i + di])
                    vs = [s for v in V[j:j + dj] for s in v]
                    s = pair_score(scorer, hs, vs, ratio, kappa)
                    if di != dj:
                        s -= 3.0
                    opts.append((i + di, j + dj, s, (i, i + di, j, j + dj)))
            for ni, nj, s, mv in opts:
                if cur + s > f[ni][nj]:
                    f[ni][nj] = cur + s
                    bk[ni][nj] = mv
    out, i, j = [], n, m
    while i or j:
        mv = bk[i][j]
        out.append(mv)
        i, j = mv[0], mv[2]
    return out[::-1]


def align_sentences(hs: list, vs: list, scorer, ratio: float, kappa: float = 8.0) -> list:
    """hs: [str] Han sentences, vs: [syllable list]. Returns [(h0, h1, v0, v1)], a partition of both sequences into
    consecutive blocks (1-1 when counts are equal; otherwise DP with up to 3-to-1 / 1-to-3 blocks)."""
    n, m = len(hs), len(vs)
    if n == m:
        return [(k, k + 1, k, k + 1) for k in range(n)]
    NEG = float("-inf")
    f = [[NEG] * (m + 1) for _ in range(n + 1)]
    bk = [[None] * (m + 1) for _ in range(n + 1)]
    f[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if f[i][j] == NEG:
                continue
            for di in range(0, 4):
                for dj in range(0, 4):
                    if (di == 0) == (dj == 0) and not (di and dj) or i + di > n or j + dj > m:
                        continue
                    if di > 1 and dj > 1:
                        continue
                    if di == 0 or dj == 0:
                        s = -40.0  # a sentence without partner: strongly discouraged (kept as its own flagged block)
                    else:
                        s = pair_score(scorer, "".join(hs[i:i + di]), [x for v in vs[j:j + dj] for x in v], ratio, kappa)
                        s -= 2.0 * (max(di, dj) - 1)
                    if f[i][j] + s > f[i + di][j + dj]:
                        f[i + di][j + dj] = f[i][j] + s
                        bk[i + di][j + dj] = (i, i + di, j, j + dj)
    out, i, j = [], n, m
    while i or j:
        mv = bk[i][j]
        out.append(mv)
        i, j = mv[0], mv[2]
    return out[::-1]

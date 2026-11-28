"""P8-4: document-level alignment for R1204: which Han lines belong to each of Quang's 309 documents.

Method (no LLM, no API, no network; the Sino-Vietnamese dictionary is used only INSIDE the scoring):
  1. leaf markers of the Vietnamese text are repaired with a Viterbi pass per quyen (leaf index 2*(to-1)+side,
     expected to advance by 1 per marker);
  2. Han page = first Han page of the quyen + leaf index (this is exactly how Quang's table is built);
  3. every Han page is split between the documents that touch it by dynamic programming over its body lines:
     a log-likelihood score of "the character's Sino-Vietnamese readings occur among the syllables of the
     document's Vietnamese text on that leaf side", a soft length prior and a small bonus for cutting at an
     indented / after a short column.
Nothing writes a Sino-Vietnamese reading into any delivered data; OCR text is never edited.
"""
import math
import re
import unicodedata
from collections import Counter, defaultdict
from statistics import median

YEAR_RE = re.compile(r"明命(?:元|[一二三四五六七八九十]{1,3})年")  # a Han year heading; documents often start here
VIET_YEAR_RE = re.compile(r"^\W*(?:(?:nam|niem)\W+)?[am]inh\W{0,3}[mn]enh\b", re.I)  # "NĂM MINH-MỆNH THỨ …", "MINH MỆNH NĂM THỨ …" (diacritics stripped first)


def viet_year_head(text: str) -> bool:
    t = unicodedata.normalize("NFD", text[:30]).replace("đ", "d").replace("Đ", "D")
    return bool(VIET_YEAR_RE.match("".join(c for c in t if unicodedata.category(c) != "Mn")))
TITLE_RE = re.compile(r"[\u4e00-\u9fff]{1,4}第[一二三四五六七八九十]{1,3}[上中下]?")  # '制兵第十三', '慎刑第十四下'
QUYEN_END_RE = re.compile(r"(?:明命)?政要卷之[一二三四五六七八九十]{1,3}止?")  # '明命政要卷之十五止'
SENT_END = "之也焉矣耳哉乎"  # characters after which a Han sentence (here: an edict) can end
OPENERS_CHAR = "帝諭詔辰尋又初命"  # characters that often open an edict (帝…, 諭…, 辰 = at that time, 尋 = then, 又 = also)
END_FORMULAS = ("帝然之", "帝從之", "從之", "然之", "許之", "可之", "允之", "報可", "從其請", "俱從之", "悉從之", "如所請", "如議行")  # closing formulas
QUYEN_PAGES = {"14": (218, 297), "15": (298, 361), "16": (362, 439), "17": (440, 511)}


# ------------------------------------------------------------------ dictionary / syllables
def norm_syl(s: str) -> str:
    s = unicodedata.normalize("NFD", s).replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in s.lower() if "a" <= c <= "z")


def viet_syllables(text: str) -> list:
    t = unicodedata.normalize("NFD", text).replace("đ", "d").replace("Đ", "D")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z]+", t.lower())


def build_dictionary(pairs) -> tuple:
    """pairs: iterable of (quoc_ngu, sino_nom). Returns (syllable -> set(chars), char -> set(syllables))."""
    syl2c, c2syl = defaultdict(set), defaultdict(set)
    for q, c in pairs:
        if not q or not c:
            continue
        s = norm_syl(str(q))
        for ch in str(c).strip():
            if s:
                syl2c[s].add(ch)
                c2syl[ch].add(s)
    return syl2c, c2syl


def load_dictionary(xlsx_path) -> tuple:
    import openpyxl  # only the dictionary loader needs it
    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    next(rows)  # header
    return build_dictionary((r[0], r[1]) for r in rows if r and r[0] and r[1])


# ------------------------------------------------------------------ leaves
def parse_leaf(dung: str):
    m = re.fullmatch(r"\s*(\d{1,3})\s*-\s*([ab])\s*", dung or "")
    return None if not m else 2 * (int(m.group(1)) - 1) + (0 if m.group(2) == "a" else 1)


def repair_leaves(readings: list, smax: int = 400) -> list:
    """readings: leaf index or None per marker (document order, one quyen). Viterbi: the true sequence advances
    by 1 per marker (cost 0), repeats/skips cost more; a reading that disagrees costs 3; start prefers leaf 0."""
    n = len(readings)
    if n == 0:
        return []
    inf = float("inf")
    tcost = {1: 0.0, 0: 2.0, 2: 2.0, 3: 4.0}
    prev = []
    back = []
    for k, r in enumerate(readings):
        cur, bk = [inf] * (smax + 1), [0] * (smax + 1)
        for s in range(smax + 1):
            em = 0.0 if r is None or r == s else 3.0
            if k == 0:
                cur[s] = em + 0.5 * s
                continue
            best, arg = inf, 0
            for d, c in tcost.items():
                p = s - d
                if p >= 0 and prev[p] + c < best:
                    best, arg = prev[p] + c, p
            cur[s], bk[s] = best + em, arg
        back.append(bk)
        prev = cur
    s = min(range(smax + 1), key=lambda i: prev[i])
    out = [s]
    for k in range(n - 1, 0, -1):
        s = back[k][s]
        out.append(s)
    return out[::-1]


# ------------------------------------------------------------------ scoring
class Scorer:
    """Log-likelihood of a Han character given the Vietnamese syllables of the document leaf-side."""

    def __init__(self, syl2c: dict, c2syl: dict, char_freq: Counter, p1: float = 0.5):
        self.syl2c, self.c2syl, self.p1 = syl2c, c2syl, p1
        tot = sum(char_freq.values()) or 1
        self.freq = {c: n / tot for c, n in char_freq.items()}

    def matched(self, syllables) -> set:
        m = set()
        for s in set(syllables):
            m |= self.syl2c.get(s, set())
        return m

    def p0(self, matched: set) -> float:
        return min(0.95, max(0.001, sum(self.freq.get(c, 0.0) for c in matched)))

    def unit_scores(self, text: str, matched: set, p0: float) -> float:
        a, b = math.log(self.p1 / p0), math.log((1 - self.p1) / (1 - p0))
        return sum(a if c in matched else b for c in text)


OPENERS = ("帝", "諭", "詔", "命")  # edict openers; deliberately NOT '明命' (kept for an independent check)


def partition_page(units: list, docs: list, scorer: Scorer, kappa: float = 2.0, bonus: float = 1.0,
                   ratio: float = 0.7, open_bonus: float = 0.0,
                   year_bonus: float = 3.0, year_pen: float = 2.0) -> list:
    """units: [{'text', 'cut_ok'}] body lines of one Han page in reading order; docs: [{'syll': [...], 'text'}] in
    order (the documents that touch this page; 'syll' = syllables of the doc's text on this leaf side).
    Returns the number of units given to each doc (sums to len(units)). Every doc gets >= 1 unit when possible."""
    n, k = len(units), len(docs)
    if k == 0:
        return []
    if k == 1:
        return [n]
    M = [scorer.matched(d["syll"]) for d in docs]
    P0 = [scorer.p0(m) for m in M]
    S = [[scorer.unit_scores(u["text"], M[j], P0[j]) for u in units] for j in range(k)]
    pre = [[0.0] * (n + 1) for _ in range(k)]
    chars = [0]
    for u in units:
        chars.append(chars[-1] + len(u["text"]))
    for j in range(k):
        for i in range(n):
            pre[j][i + 1] = pre[j][i] + S[j][i]
    exp = [ratio * len(d["syll"]) for d in docs]
    mn = 1 if n >= k else 0
    NEG = float("-inf")
    dp = [[NEG] * (n + 1) for _ in range(k + 1)]
    bk = [[0] * (n + 1) for _ in range(k + 1)]
    dp[0][0] = 0.0
    for j in range(1, k + 1):
        for i in range(n + 1):
            for p in range(0, i - mn + 1):
                if dp[j - 1][p] == NEG:
                    continue
                h = chars[i] - chars[p]
                sc = dp[j - 1][p] + pre[j - 1][i] - pre[j - 1][p] - kappa * abs(h - exp[j - 1]) / (exp[j - 1] + 10)
                if j < k and 0 < i < n and units[i].get("nocut"):
                    continue  # never start a document at a unit that is followed by a year heading
                if j < k and 0 < i < n:
                    if units[i]["cut_ok"]:
                        sc += bonus
                    if units[i]["text"].startswith(OPENERS):
                        sc += open_bonus
                    if units[i].get("year_start"):  # the next doc starts here: it should open with a year heading
                        sc += year_bonus if docs[j].get("year") else -year_pen
                if sc > dp[j][i]:
                    dp[j][i], bk[j][i] = sc, p
    i, out = n, []
    for j in range(k, 0, -1):
        p = bk[j][i]
        out.append(i - p)
        i = p
    return out[::-1]


# ------------------------------------------------------------------ character-level cuts (P8-4b)
QUOTE_CLAUSE_RE = re.compile(r"((?:[\u4e00-\u9fff]{0,4}?臣|臣))(?:又|復)?(?:奏)?[言曰云]")  # '廷臣又言', '刑部臣奏言', '帝諭羣臣曰' ends here
NO_END = "曰云言其以而又及與則若"  # a document cannot end right after these (the sentence is not finished)
NO_START = "之也焉矣耳哉乎者曰云言"  # a document cannot start with these
COMPOUNDS = ("通諭", "曉諭", "傳諭", "申諭", "宣諭", "頒諭", "諭令", "大辟", "命通", "奏言", "奏請", "奏曰")  # never cut inside


def cut_candidates(units: list) -> tuple:
    """units of one page (titles already removed). Returns (chars, cand) where chars = [(ch, unit_idx, off)] and
    cand = {cut_position: (bonus, kind, year_here, closes)}; a cut position i means 'between chars i-1 and i'.
    A document starts at the START OF A SENTENCE: after a sentence-final particle (之也焉矣耳哉乎) or a closing
    formula, before an opener (帝諭詔辰尋又初命), before the subject of a quotation clause (…臣又言/奏言/曰, found by
    looking back from the quotation verb), or at a year heading. NEVER right after 曰/云/言: the clause that
    introduces a speech belongs to the document that contains the speech. A bare line start (kind 'dong') stays a
    weak candidate with a penalty. Not candidates: inside a year heading; <= 24 chars before a year heading (that
    text belongs to the previous document); right after a character in NO_END; before a character in NO_START;
    inside a compound verb of COMPOUNDS."""
    chars = [(ch, ui, k) for ui, u in enumerate(units) for k, ch in enumerate(u["text"])]
    text = "".join(c for c, _, _ in chars)
    heads = []  # char index where a year heading starts
    for ui, u in enumerate(units):
        if u.get("year_start"):
            heads.append(next(i for i, (_, uj, k) in enumerate(chars) if uj == ui and k == 0))
    forb = set()
    for h in heads:
        ui = chars[h][1]
        m = YEAR_RE.match(units[ui]["text"])
        forb.update(range(h + 1, h + (m.end() if m else 1)))
        forb.update(range(max(1, h - 24), h))
    for comp in COMPOUNDS:  # one pass per compound: overlapping ones (命通 / 通諭) must all be protected
        for m in re.finditer(comp, text):
            forb.update(range(m.start() + 1, m.end()))
    quote_start = {}  # position -> bonus: the subject (title + 臣) of a quotation clause starts 1-4 chars before 臣
    for m in QUOTE_CLAUSE_RE.finditer(text):
        t = m.end(1) - 1  # index of 臣 in the subject
        for sp in range(max(m.start(), t - 4), t):
            quote_start[sp] = max(quote_start.get(sp, 0.0), 2.0 - 0.1 * (t - sp - 1))
    cand = {}
    for i in range(1, len(chars)):
        if i in forb:
            continue
        prev, cur = chars[i - 1], chars[i]
        if prev[0] in NO_END or cur[0] in NO_START:
            continue
        boundary = cur[1] != prev[1]
        after_end = prev[0] in SENT_END
        before_open = cur[0] in OPENERS_CHAR
        before_quote = i in quote_start
        qb = quote_start.get(i, 0.0)
        closes = any(text.endswith(f, 0, i) for f in END_FORMULAS)
        year_here = boundary and bool(units[cur[1]].get("year_start"))
        strong = after_end or before_open or before_quote or year_here or closes
        if not (boundary or strong):
            continue
        b = 0.0
        if after_end:
            b += 2.0
        if before_open:
            b += 1.0 + (1.0 if (boundary or after_end) else 0.0)
        if before_quote:
            b += qb + (1.0 if after_end else 0.0)
        if closes:
            b += 6.0
        if boundary:
            b += (0.5 + (1.0 if units[cur[1]]["cut_ok"] else 0.0)) if strong else -2.5
        cand[i] = (b, "cau" if strong else "dong", year_here, closes, before_quote)
    return chars, cand


OPT_MAX = 40  # most characters a neighbouring (optional) document may take at the edge of a page


def partition_page_chars(units: list, docs: list, scorer: Scorer, kappa: float = 2.0, ratio: float = 0.7,
                         year_bonus: float = 3.0, year_pen: float = 2.0, min_chars: int = 2) -> list:
    """Character-level version of partition_page. Returns [(a, b, start_kind, end_kind)] char ranges per doc
    plus the char list; kinds are 'trang' (page edge), 'cau', 'dong' (weak: only a line start) or 'giua'."""
    chars, cand = cut_candidates(units)
    n, k = len(chars), len(docs)
    text = "".join(c for c, _, _ in chars)
    if k == 1 or n == 0:
        return ([(0, n, "trang", "trang")] if k == 1 else [(0, 0, "trang", "trang")] * k), chars
    M = [scorer.matched(d["syll"]) for d in docs]
    P0 = [scorer.p0(m) for m in M]
    pre = []
    for j in range(k):
        a, b = math.log(scorer.p1 / P0[j]), math.log((1 - scorer.p1) / (1 - P0[j]))
        acc = [0.0]
        for ch in text:
            acc.append(acc[-1] + (a if ch in M[j] else b))
        pre.append(acc)
    exp = [ratio * len(d["syll"]) for d in docs]
    pos = sorted(set([0, n] + list(cand)))
    year_cuts = any(c[2] for c in cand.values())
    NEG = float("-inf")
    dp = [[NEG] * len(pos) for _ in range(k + 1)]
    bk = [[0] * len(pos) for _ in range(k + 1)]
    dp[0][0] = 0.0
    for j in range(1, k + 1):
        d = docs[j - 1]
        opt = d.get("opt")  # a neighbouring document that may own up to OPT_MAX leading/trailing chars of this page
        for ii in range(len(pos)):
            i = pos[ii]
            if opt and dp[j - 1][ii] != NEG and dp[j - 1][ii] > dp[j][ii]:  # empty share
                dp[j][ii], bk[j][ii] = dp[j - 1][ii], -1
            for pp in range(ii):
                if dp[j - 1][pp] == NEG:
                    continue
                size = i - pos[pp]
                if size < (1 if opt else min_chars) or (opt and size > OPT_MAX):
                    continue
                p = pos[pp]
                sc = dp[j - 1][pp] + pre[j - 1][i] - pre[j - 1][p] - (0.0 if opt else kappa * abs(size - exp[j - 1]) / (exp[j - 1] + 10))
                if opt:
                    # a neighbour owns edge chars only at a closing formula (previous doc) or a year heading (next doc)
                    if j == 1 and not (i in cand and (cand[i][3] or (cand[i][2] and docs[1].get("year")))):
                        continue
                    if j == k and not (p in cand and (cand[p][4] or cand[p][2])):
                        continue
                    sc -= 1.0
                end_ok = i == n and all(x.get("opt") for x in docs[j:])  # only optional neighbours remain: page end is fine
                if j < k and i not in cand and not end_ok:
                    continue  # a document boundary needs a candidate cut
                if j < k and i in cand:
                    b, _, yh, cl, qt = cand[i]
                    if docs[j].get("year") and year_cuts and not yh:
                        continue  # a document whose Viet text opens with a year heading starts AT a Han year heading
                    sc += b
                    if yh:
                        sc += year_bonus if docs[j].get("year") else -year_pen
                if sc > dp[j][ii]:
                    dp[j][ii], bk[j][ii] = sc, pp
    ii, cuts = len(pos) - 1, []
    if dp[k][ii] == NEG:  # too few characters for k documents: fall back to even split by lines
        step = max(1, n // k)
        bounds = [0] + [min(n, step * (j + 1)) for j in range(k - 1)] + [n]
        return [(bounds[j], bounds[j + 1], "giua", "giua") for j in range(k)], chars
    for j in range(k, 0, -1):
        pp = bk[j][ii]
        if pp == -1:
            cuts.append((pos[ii], pos[ii]))
            continue
        cuts.append((pos[pp], pos[ii]))
        ii = pp
    cuts = cuts[::-1]
    out = []
    for j, (a, b) in enumerate(cuts):
        sk = "trang" if j == 0 or a == 0 else cand.get(a, (0, "giua", False, False, False))[1]
        ek = "trang" if j == k - 1 or b == n else cand.get(b, (0, "giua", False, False, False))[1]
        out.append((a, b, sk, ek))
    return out, chars


def align_book_chars(docs: list, leaves: list, C: str, han_pages: dict, scorer: Scorer, kappa=2.0, ratio=0.7,
                     year_bonus=3.0, year_pen=2.0) -> dict:
    """Like align_book but cuts at character level. assign[i] = [(page, piece dict(text, dong, off))]; also
    cut_kinds[i] = [start_kind_on_its_first_page, end_kind_on_its_last_page] for the weak-boundary flags."""
    assign, kinds = defaultdict(list), defaultdict(dict)
    unassigned, shared, few = [], 0, []
    for page, units in sorted(han_pages.items()):
        unassigned += [(page, u, "tieu_de_thien_quyen") for u in units if u.get("title")]
        units = [u for u in units if not u.get("title")]
        touching = [i for i, lv in enumerate(leaves) if lv["pstart"] <= page <= lv["pend"]]
        if not touching:
            unassigned += [(page, u, "trang_khong_thuoc_van_ban_nao") for u in units]
            continue
        # neighbours that may own a few edge characters of this page (a marker is not always at the exact edge)
        prev_i = next((i for i in range(len(leaves) - 1, -1, -1) if leaves[i]["pend"] == page - 1), None)
        next_i = next((i for i in range(len(leaves)) if leaves[i]["pstart"] == page + 1), None)
        order = ([prev_i] if prev_i is not None and prev_i not in touching and docs[prev_i]["quyen"] == docs[touching[0]]["quyen"] else []) \
            + touching + ([next_i] if next_i is not None and next_i not in touching and docs[next_i]["quyen"] == docs[touching[-1]]["quyen"] else [])
        dl = []
        for i in order:
            q = docs[i]["quyen"]
            leaf = min(max(page - QUYEN_PAGES[q][0], leaves[i]["leaf_s"]), leaves[i]["leaf_e"])
            a, b = leaves[i]["segs"].get(leaf, (docs[i]["start"], docs[i]["end"]))
            dl.append({"syll": viet_syllables(C[a:b]), "opt": i not in touching,
                       "year": (leaves[i]["pstart"] == page or i not in touching) and viet_year_head(C[docs[i]["start"]:docs[i]["start"] + 30])})
        if len(touching) > 1:
            shared += 1
        if len(order) == 1:
            ranges, chars = [(0, sum(len(u["text"]) for u in units), "trang", "trang")], None
        else:
            ranges, chars = partition_page_chars(units, dl, scorer, kappa, ratio, year_bonus, year_pen)
        pos_units = [(ui, k) for ui, u in enumerate(units) for k in range(len(u["text"]))]
        for i, (a, b, sk, ek) in zip(order, ranges):
            if i in touching:
                kinds[i].setdefault("start", sk if leaves[i]["pstart"] == page else "trang")
                kinds[i]["end"] = ek if leaves[i]["pend"] == page else "trang"
            cur = None
            for q in range(a, b):
                ui, k = pos_units[q]
                if cur is None or cur[0] != ui:
                    if cur:
                        assign[i].append((page, {"text": units[cur[0]]["text"][cur[1]:cur[2] + 1], "dong": units[cur[0]]["dong"],
                                                 "off": units[cur[0]]["off"] + cur[1]}))
                    cur = [ui, k, k]
                else:
                    cur[2] = k
            if cur:
                assign[i].append((page, {"text": units[cur[0]]["text"][cur[1]:cur[2] + 1], "dong": units[cur[0]]["dong"],
                                         "off": units[cur[0]]["off"] + cur[1]}))
    return {"assign": assign, "unassigned": unassigned, "shared": shared, "few": few, "kinds": kinds}


# ------------------------------------------------------------------ assembling
def doc_leaves(docs: list, markers: list, quyen_pages: dict = QUYEN_PAGES) -> list:
    """docs: located docs in order [{'doc_id','quyen','start','end'}]; markers: [{'offset','dung'}] sorted by offset.
    Returns per doc: dict(pstart, pend, leaf_s, leaf_e, segs={leaf: (a, b)}, flags=[...]) and annotates markers
    with 'leaf' (repaired)."""
    def quyen_of(off):  # a marker inside a gap (cover page, quyen title) belongs to the NEXT document's quyen
        for d in docs:
            if off < d["end"]:
                return d["quyen"]
        return docs[-1]["quyen"]

    byq = defaultdict(list)
    for m in markers:
        m["quyen"] = quyen_of(m["offset"])
        byq[m["quyen"]].append(m)
    for q, ms in byq.items():
        rep = repair_leaves([parse_leaf(m.get("dung")) for m in ms])
        for m, L in zip(ms, rep):
            m["leaf"] = L
            r = parse_leaf(m.get("dung"))
            m["repaired"] = r is not None and r != L
    res = []
    for d in docs:
        q = d["quyen"]
        base, last = quyen_pages[q]
        ms = [m for m in byq[q]]
        before = [m for m in ms if m["offset"] <= d["start"]]
        ls = before[-1]["leaf"] if before else 0
        inside = [m for m in ms if d["start"] < m["offset"] < d["end"]]
        le = inside[-1]["leaf"] if inside else ls
        flags = []
        if any(m.get("repaired") or not m.get("dung") for m in ([before[-1]] if before else []) + inside):
            flags.append("moc_sua")
        if le < ls:
            le = ls
            flags.append("moc_nguoc")
        segs, cur, pos = {}, ls, d["start"]
        for m in inside:
            if m["leaf"] != cur:
                segs[cur] = (segs[cur][0], m["offset"]) if cur in segs else (pos, m["offset"])
                cur, pos = m["leaf"], m["offset"]
        segs[cur] = (segs[cur][0], d["end"]) if cur in segs else (pos, d["end"])
        ps, pe = base + ls, base + le
        if pe > last:
            flags.append("ngoai_quyen")
            pe = min(pe, last)
            ps = min(ps, last)
        res.append({"pstart": ps, "pend": pe, "leaf_s": ls, "leaf_e": le, "segs": segs, "flags": flags})
    return res


def align_book(docs: list, leaves: list, C: str, han_pages: dict, scorer: Scorer, kappa=2.0, bonus=1.0, ratio=0.7,
               open_bonus=0.0, year_bonus=3.0, year_pen=2.0) -> dict:
    """han_pages: {page: [unit dict(text, dong, cut_ok)]}. Returns {'assign': {doc_idx: [(page, unit)]},
    'unassigned': [(page, unit, why)], 'shared': n_pages_shared, 'few': [pages with fewer units than docs]}."""
    assign = defaultdict(list)
    unassigned, shared, few = [], 0, []
    for page, units in sorted(han_pages.items()):
        unassigned += [(page, u, "tieu_de_thien_quyen") for u in units if u.get("title")]
        units = [u for u in units if not u.get("title")]
        touching = [i for i, lv in enumerate(leaves) if lv["pstart"] <= page <= lv["pend"]]
        if not touching:
            unassigned += [(page, u, "trang_khong_thuoc_van_ban_nao") for u in units]
            continue
        dl = []
        for i in touching:
            q = docs[i]["quyen"]
            leaf = page - QUYEN_PAGES[q][0]
            a, b = leaves[i]["segs"].get(leaf, (docs[i]["start"], docs[i]["end"]))
            dl.append({"syll": viet_syllables(C[a:b]),
                       "year": leaves[i]["pstart"] == page and viet_year_head(C[docs[i]["start"]:docs[i]["start"] + 30])})
        counts = partition_page(units, dl, scorer, kappa, bonus, ratio, open_bonus, year_bonus, year_pen)
        if len(touching) > 1:
            shared += 1
            if len(units) < len(touching):
                few.append(page)
        pos = 0
        for i, c in zip(touching, counts):
            for u in units[pos:pos + c]:
                assign[i].append((page, u))
            pos += c
    return {"assign": assign, "unassigned": unassigned, "shared": shared, "few": few}


def split_line(t: str) -> list:
    """Cut one OCR line into pieces [(start, end, kind)], kind in 'text' | 'title' | 'year'.
    title: a thien title '…第N[上中下]' at the line start followed by nothing or by a year heading, or an end-of-quyen
    mark '…政要卷之N止' anywhere. year: a piece that starts with a Han year heading (明命…年)."""
    marks = []
    m = TITLE_RE.match(t)
    if m and (m.end() == len(t) or t[m.end():].startswith("明命")):
        marks.append((0, m.end()))
    for m in QUYEN_END_RE.finditer(t):
        marks.append((m.start(), m.end()))
    marks.sort()
    segs, pos = [], 0
    for a, b in marks:
        if a > pos:
            segs.append((pos, a, "text"))
        segs.append((a, b, "title"))
        pos = b
    if pos < len(t):
        segs.append((pos, len(t), "text"))
    out = []
    for a, b, kind in segs:
        if kind == "title":
            out.append((a, b, "title"))
            continue
        cuts = [a] + [a + m.start() for m in YEAR_RE.finditer(t[a:b]) if m.start() > 0] + [b]
        for k in range(len(cuts) - 1):
            out.append((cuts[k], cuts[k + 1], "year" if YEAR_RE.match(t[cuts[k]:cuts[k + 1]]) else "text"))
    return out


def han_units(rows: list) -> dict:
    """han_lines.tsv rows (dicts of strings) -> {page: [units in reading order]} for body lines only.
    A unit is a line, or a piece of a line (see split_line). Texts are exact slices of the OCR line (concatenating
    the pieces gives the line back). cut_ok marks a unit that starts an indented column or follows a short column;
    year_start marks a year heading; title marks a thien/quyen title (never part of a document)."""
    pages = defaultdict(list)
    for r in rows:
        if r["loai"] == "than" and r["thu_tu"] != "":
            pages[int(r["trang"])].append(r)
    out = {}
    for p, rs in pages.items():
        rs.sort(key=lambda r: int(r["thu_tu"]))
        units, prev_col, prev_short = [], None, False
        for r in rs:
            first_in_col = r["cot"] != prev_col
            cut_ok = bool(first_in_col and (r["thut"] == "1" or prev_short))
            t = r["van_ban"]
            for k, (a, b, kind) in enumerate(split_line(t)):
                units.append({"text": t[a:b], "dong": int(r["dong"]), "off": a, "cut_ok": cut_ok if k == 0 else True,
                              "year_start": kind == "year", "title": kind == "title", "diem": float(r["diem"])})
            prev_col, prev_short = r["cot"], r["cot_ngan"] == "1"
        for i in range(len(units) - 1):  # the text before a year heading belongs to the previous document
            if units[i + 1]["year_start"] and not units[i]["year_start"] and not units[i]["title"]:
                units[i]["nocut"] = True
        out[p] = units
    return out


def estimate_p1(docs, leaves, C, han_pages, scorer, quyens) -> float:
    """Mean match rate of single-document pages of the given quyen (the 'true doc' match probability)."""
    rates = []
    for page, units in han_pages.items():
        touching = [i for i, lv in enumerate(leaves) if lv["pstart"] <= page <= lv["pend"] and docs[i]["quyen"] in quyens]
        if len(touching) != 1 or not units:
            continue
        i = touching[0]
        leaf = page - QUYEN_PAGES[docs[i]["quyen"]][0]
        a, b = leaves[i]["segs"].get(leaf, (docs[i]["start"], docs[i]["end"]))
        m = scorer.matched(viet_syllables(C[a:b]))
        text = "".join(u["text"] for u in units)
        if text:
            rates.append(sum(c in m for c in text) / len(text))
    return min(0.9, max(0.2, median(rates))) if rates else 0.5


def estimate_ratio(docs, C, han_pages, quyens) -> float:
    """Han characters per Vietnamese syllable over the given quyen (pages of the quyen / syllables of its docs)."""
    chars = sum(len(u["text"]) for q in quyens for p in range(QUYEN_PAGES[q][0], QUYEN_PAGES[q][1] + 1)
                for u in han_pages.get(p, []))
    syl = sum(len(viet_syllables(C[d["start"]:d["end"]])) for d in docs if d["quyen"] in quyens)
    return chars / syl if syl else 0.7

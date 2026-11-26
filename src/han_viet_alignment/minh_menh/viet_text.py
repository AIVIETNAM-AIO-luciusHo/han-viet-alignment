"""Bản dịch Minh Mệnh chính yếu: tách câu và gắn mã mặt tờ cho từng câu.

Lớp chữ PDF của bản dịch (`02_ocr_tho/viet/<MA_SACH>_dich_nghia_sach.md`) giữ mốc "[tờ 12-a]" đúng
chỗ bắt đầu mặt tờ tương ứng của bản Hán. Văn bản đã chia sẵn (`03_text_sach/dich_nghia.txt`) đã bỏ
mốc, nên vị trí từng mốc được tìm lại bằng cách so chuỗi 4 từ ngay sau mốc.

Mốc do OCR nên hay sai ("6.8", "1ì-a", "2-3b", "SLa"): chỉ nhận mốc tăng dần hợp lý trong quyển,
mốc không đọc được thì bỏ (câu quanh đó lấy theo mốc gần nhất trước nó).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..alignment.cleaning import _FOOTNOTE_INDEX
from ..common.text import nfc, syllables
from .han_ocr import SHEET

MARKER = re.compile(r"[\[(]\s*t[ờơóòởỏ]\s*:?\s*([^\])}]{0,12})[\])}]"
                    r"|[\[({]\s*(\d{1,3}\s*[-.]?\s*[abAB])\s*[\])}]", re.I)
QUYEN_HEAD = re.compile(r"QUY[ỀỂÉÊÈE]N\s+TH[ỨỪU]", re.I)
YEAR_HEADER = re.compile(
    r"((?:NI[ÊE]N\s+HI[ỆE]U\s+)?(?:N[ĂA]M\s+)?MINH[\s.\-]*M[ỆE]NH\s*,?\s+(?:N[ĂA]M\s+)?"
    r"(?:TH[ỨU]\s+(?:\d{1,2}|[A-ZÀ-ỸĐ]{2,})(?:\s+[A-ZÀ-ỸĐ]{2,})*|Đ[ẦA]U)(?:\s*,?\s*\(\s*1[89]\d\d\s*\))?"
    r"|N[ĂA]M\s+Đ[ẦA]U\s+NI[ÊE]N\s+HI[ỆE]U\s+MINH[\s.\-]*M[ỆE]NH"
    r"|(?:NI[ÊE]N\s+HI[ỆE]U\s+)?(?:N[ĂA]M\s+)?MINH[\s.\-]*M[ỆE]NH[^()\n]{0,40}?\(\s*1[89]\d\d\s*\))")
SENT_END = re.compile(r"(?<=[.!?])\s+(?=[\"“(\[]?[A-ZÀ-ỸĐ0-9])")
_NUM_FIX = str.maketrans({"ì": "1", "í": "1", "i": "1", "l": "1", "I": "1", "}": "1", "|": "1", "!": "1",
                          "L": "1", "S": "3", "O": "0", "o": "0"})


@dataclass
class VietSentence:
    text: str
    doc_id: str
    folio_start: int = 0
    folio_end: int = 0
    note: str = ""

    @property
    def year(self) -> int | None:
        """Năm dương lịch của dòng niên hiệu. Ưu tiên số năm bằng chữ ('THỨ MƯỜI MỘT' -> 1830) vì năm trong
        ngoặc hay bị OCR/bản in sai ('(1928)', '(1829)')."""
        m = YEAR_HEADER.fullmatch(self.text)
        if not m:
            return None
        n = vn_year_number(m.group(1))
        if n:
            return 1819 + n
        y = re.search(r"1[89]\d\d", m.group(1))
        if not y:
            return None
        return int(y.group(0)) - 100 if int(y.group(0)) >= 1900 else int(y.group(0))


_VN_DIGIT = {"một": 1, "mốt": 1, "hai": 2, "ba": 3, "tư": 4, "bốn": 4, "năm": 5, "lăm": 5, "sáu": 6,
             "bảy": 7, "bẩy": 7, "tám": 8, "chín": 9}


def vn_year_number(header: str) -> int | None:
    """'NĂM MINH-MỆNH THỨ HAI MƯƠI MỐT (1840)' -> 21; 'NIÊN HIỆU … NĂM ĐẦU' -> 1."""
    h = nfc(header).lower()
    if "đầu" in h:
        return 1
    m = re.search(r"thứ\s+([^()]+)", h)
    if not m:
        return None
    d = re.match(r"\s*(\d{1,2})\b", m.group(1))
    if d:
        return int(d.group(1))
    total, cur = 0, 0
    for w in re.findall(r"\w+", m.group(1)):
        if w == "mười":
            total += 10
        elif w == "mươi":
            total += (cur or 1) * 10
            cur = 0
        elif w in _VN_DIGIT:
            cur = _VN_DIGIT[w]
        else:
            break
    total += cur
    return total or None


def words(s: str) -> list[str]:
    return re.findall(r"\w+", nfc(s).lower())



_DIGIT_CONFUSION = {"9": "2", "5": "3", "3": "5", "8": "3"}


def _digit_variants(num: str) -> set[int]:
    out = {""}
    for ch in num:
        out = {v + ch for v in out} | ({v + _DIGIT_CONFUSION[ch] for v in out} if ch in _DIGIT_CONFUSION else set())
    return {int(v) for v in out if v and v[0] != "0"}


def _marker_candidates(body: str) -> tuple[list[int], int | None]:
    """'12-a' -> ([12], 0); '2-3b' -> ([2, 23], 1); '6.8' -> ([6], 0); '27' -> ([27], None)."""
    m = re.match(r"\s*([0-9ìíilI}|!SLOo]{1,3})\s*[-.,\s]*(.*)$", body)
    if not m:
        return [], None
    num_part, rest = m.group(1).translate(_NUM_FIX), m.group(2).strip().lower()
    side: int | None = None
    if "b" in rest or "h" in rest:
        side = 1
    elif "a" in rest:
        side = 0
    elif rest[:1] in ("8", "4", "s"):
        side = 0
    elif rest[:1] in ("5", "6"):
        side = 1
    nums = []
    if num_part.isdigit():
        nums.append(int(num_part))
        tail = re.match(r"(\d+)", rest)
        if tail and side is not None and "b" in rest:
            nums.append(int(num_part + tail.group(1)))
    return nums, side


def parse_markers(md: str) -> list[tuple[int, int]]:
    """Trả về [(vị trí ký tự trong md, mã mặt tờ toàn cục)], tăng dần."""
    events = sorted([(m.start(), "m", m.group(1) or m.group(2) or "") for m in MARKER.finditer(md)] +
                    [(m.start(), "h", "") for m in QUYEN_HEAD.finditer(md)])
    out: list[tuple[int, int]] = []
    q, prev = -1, -1
    last_head = None
    bodies = [b for _, k, b in events if k == "m"]
    mi = -1

    def continues_old(after: int, prev: int) -> bool:
        """Một trong hai mốc kế tiếp vẫn nối dãy cũ -> mốc '1a/1b' hiện tại là đọc sai, chưa sang quyển mới."""
        for b in bodies[after + 1:after + 3]:
            ns, sd = _marker_candidates(b)
            for n in ns:
                for x in ([sd] if sd is not None else [0, 1]):
                    if prev < 2 * (n - 1) + x <= prev + 8:
                        return True
        return False

    for pos, kind, body in events:
        if kind == "h":
            last_head = pos
            continue
        mi += 1
        nums, side = _marker_candidates(body)
        sides = [side] if side is not None else [0, 1]
        cands = [2 * (n - 1) + s for n in nums for s in sides if n >= 1]
        new_q = [c for c in cands if c <= 1] if (prev >= 10 or q < 0) else []
        if new_q and q >= 0 and continues_old(mi, prev):
            new_q = []
        if new_q:
            q += 1
            k = min(new_q)
            if last_head is not None and (not out or last_head > out[-1][0]):
                out.append((last_head, q * SHEET))
            prev = k
            out.append((pos, q * SHEET + k))
            continue
        ok = [2 * (n - 1) + s for v in nums for n in _digit_variants(str(v)) for s in sides
              if n >= 1 and prev < 2 * (n - 1) + s <= prev + 6]
        if q < 0 or not ok:
            continue
        prev = min(ok)
        out.append((pos, q * SHEET + prev))
    return out


def anchor_positions(md: str, markers: list[tuple[int, int]], tokens: list[str]) -> list[tuple[int, int]]:
    """Đổi vị trí mốc trong md sang chỉ số từ trong `tokens` (văn bản đã chia) bằng 4-gram.

    Cụm 4 từ có thể lặp lại (lời dụ, công thức tâu), nên không lấy chỗ khớp đầu tiên mà lấy chỗ gần vị trí
    mong đợi nhất: vị trí mốc trước + số từ giữa hai mốc trong md (md còn đầu trang, số trang nên cho sai số).
    """
    index: dict[tuple[str, ...], list[int]] = {}
    for i in range(len(tokens) - 3):
        index.setdefault(tuple(tokens[i:i + 4]), []).append(i)
    md_words_before, acc, prev_pos = [], 0, 0
    for pos, _ in markers:
        acc += len(words(MARKER.sub(" ", md[prev_pos:pos])))
        md_words_before.append(acc)
        prev_pos = pos
    out: list[tuple[int, int]] = []
    last_tok, last_md = -1, 0
    for k, (pos, g) in enumerate(markers):
        after = words(MARKER.sub(" ", md[pos:pos + 600]))
        delta = md_words_before[k] - last_md
        expected = last_tok + max(delta, 0) * 0.97 if last_tok >= 0 else md_words_before[k] * 0.9
        tol = 300 + 0.35 * max(delta, 0) if last_tok >= 0 else 3000
        best = None
        for o in range(0, min(40, max(0, len(after) - 3))):
            shift = o if o <= 3 else 0
            for p_ in index.get(tuple(after[o:o + 4]), ()):
                cand = p_ - shift
                if cand <= last_tok or abs(cand - expected) > tol:
                    continue
                score = abs(cand - expected) + 25 * o
                if best is None or score < best[0]:
                    best = (score, cand)
        if best is not None:
            out.append((best[1], g))
            last_tok, last_md = best[1], md_words_before[k]
    return out



def clean_viet(text: str) -> str:
    """Làm sạch nhẹ, chỉ sửa lỗi OCR hiển nhiên; KHÔNG dùng clean_dich_nghia của sắc phong vì hàm đó bỏ
    số đứng lẻ ('2 vệ', '6 tỉnh' là nội dung ở đây) và bỏ chuỗi in hoa (dòng niên hiệu là nội dung)."""
    s = nfc(text)
    s = _FOOTNOTE_INDEX.sub(" ", s)
    s = re.sub(r"\(\s*\)\)?", " ", s)
    s = re.sub(r"(?<=\w)[*+%](?=\W|$)", "", s)
    s = re.sub(r"[*+%#£$]", " ", s)
    s = re.sub(r"\((\d)\s(\d{3})\)", r"(\1\2)", s)
    s = re.sub(r"\s+([,.;:!?)])", r"\1", s)
    s = re.sub(r"([(])\s+", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def split_sentences(text: str) -> list[str]:
    out: list[str] = []
    for i, piece in enumerate(YEAR_HEADER.split(text)):
        piece = piece.strip()
        if not piece:
            continue
        if i % 2:
            out.append(piece)
            continue
        carry = ""
        for s in SENT_END.split(piece):
            s = (carry + " " + s).strip() if carry else s.strip()
            carry = ""
            if not s:
                continue
            if len(words(s)) < 3:
                carry = s
            else:
                out.append(s)
        if carry:
            if out and not YEAR_HEADER.fullmatch(out[-1]):
                out[-1] += " " + carry
            else:
                out.append(carry)
    return out


def build_sentences(docs: dict[str, str]) -> list[VietSentence]:
    sents: list[VietSentence] = []
    for doc_id, raw in docs.items():
        parts = split_sentences(clean_viet(raw))
        if parts and sents and parts[0][:1].islower():
            sents[-1].text += " " + parts.pop(0)
            sents[-1].note = f"Nối phần đầu {doc_id} (đuôi câu bị chia sang văn bản sau) vào câu này."
        sents.extend(VietSentence(s, doc_id) for s in parts)
    return sents


def assign_folios(sents: list[VietSentence], anchors: list[tuple[int, int]]) -> None:
    """Gắn mã mặt tờ đầu/cuối cho từng câu theo vị trí từ của mốc trong chuỗi từ nối các câu."""
    a = 0
    g = anchors[0][1] if anchors else 0
    pos = 0
    for s in sents:
        n = len(words(s.text))
        while a < len(anchors) and anchors[a][0] <= pos:
            g = anchors[a][1]
            a += 1
        s.folio_start = g
        while a < len(anchors) and anchors[a][0] < pos + n:
            g = anchors[a][1]
            a += 1
        s.folio_end = g
        pos += n


def sentence_tokens(sents: list[VietSentence]) -> list[str]:
    return [w for s in sents for w in words(s.text)]


def syllable_count(s: str) -> int:
    return len(syllables(s))


__all__ = ["VietSentence", "parse_markers", "anchor_positions", "build_sentences", "assign_folios",
           "sentence_tokens", "syllable_count", "words", "SHEET"]



_RUNNING = re.compile(r"CH[ÍI]NH\W*Y[ẾE]U|^\W*\d{1,3}\W*$|^QUY[ỀỂÉÊE]N\b.{0,20}$|^Thi[êe]n\s+(?:th[ứu]|\d)", re.I)
_QUYEN_LINE = re.compile(r"QUY[ỀỂÉÊÈE]N\s+(?:TH[ỨỪU]\s*)?\S{1,3}\s*$", re.I)
_FOOTNOTE_LINE = re.compile(r"^\(\s*\d?\s*\)\)?")
_UPPER_START = re.compile(r"^[\[(\"“«]?\s*[A-ZÀ-ỸĐ]")
_BULLET = re.compile(r"^[$§_]\s*")
_SENT_DONE = re.compile(r"[.!?»”)]\s*$")
_SPEECH = re.compile(r"rằng\s*[.:]?\s*$|:\s*$")
_CONTINUATION = re.compile(
    r"^(?:Vua\s+(?:trả lời|bèn|phán|phún|phê|khen|y\b|cũng|giao|không|ra lời|nói|cho là|ưng|chuẩn|chuần|theo|"
    r"lại|nghe theo)|Dụ\b|Lại\b|Nay\b|Mỗi\b|Đình.thần|Các đình|Bàn\b|\d{1,2}\s*[.,)])", re.I)


def segment_translation(md: str) -> list[str]:
    """Chia lớp chữ PDF bản dịch thành văn bản (mỗi điều chép/sự việc) khi nhóm chưa chia tay.

    Bỏ đầu trang (số trang, "MINH-MỆNH CHÍNH-YẾU", "QUYỂN THỨ…", "Thiên thứ…"), dòng tiêu đề in hoa và
    chú thích cuối trang. Văn bản mới bắt đầu ở dòng niên hiệu, hoặc ở đầu đoạn (dòng trước hết câu và ngắn
    hơn dòng đầy, dòng sau viết hoa) trừ đoạn là lời đáp/phê tiếp theo. Bỏ phần trước mốc tờ/niên hiệu đầu
    tiên (bìa, lời tựa) và sau chữ "ngừng bút" cuối cùng (mục lục, trang xuất bản).
    """
    pages = re.split(r"^## Trang \d+\s*$", md, flags=re.M)[1:]
    lines: list[str] = []
    page_of: list[int] = []
    heads: list[int] = []
    for pi, page in enumerate(pages):
        pl = [ln.strip() for ln in page.splitlines() if ln.strip()]
        for i, ln in enumerate(pl):
            core = MARKER.sub("", ln).strip()
            if (QUYEN_HEAD.search(core) or _QUYEN_LINE.search(core)) and len(core) < 45:
                heads.append(len(lines))
            if not core:
                if MARKER.search(ln):
                    lines.append(ln)
                    page_of.append(pi)
                continue
            if _FOOTNOTE_LINE.match(core) and i >= 0.5 * len(pl):
                break
            if _RUNNING.search(core) and len(core) < 45 and not YEAR_HEADER.search(core):
                continue
            letters = [c for c in core if c.isalpha()]
            if (len(core) < 60 and letters and sum(c.isupper() for c in letters) > 0.8 * len(letters)
                    and not YEAR_HEADER.search(core)):
                continue
            lines.append(ln)
            page_of.append(pi)
    marked = [i for i, ln in enumerate(lines) if MARKER.search(ln)]
    if not marked:
        return []
    fm = marked[0]
    near = [h for h in heads if h <= fm and page_of[min(h, len(lines) - 1)] >= page_of[fm] - 3]
    first = max(near) if near else fm
    lm = marked[-1]
    stop = [i for i in range(lm, len(lines)) if page_of[i] <= page_of[lm] + 3 and "ngừng bút" in lines[i].lower()]
    last = stop[0] if stop else max(i for i in range(lm, len(lines)) if page_of[i] == page_of[lm])
    lines = lines[first:last + 1]
    full = sorted(len(x) for x in lines)[len(lines) // 2] if lines else 60
    docs: list[list[str]] = [[]]
    for i, ln in enumerate(lines):
        core = MARKER.sub("", ln).strip()
        bullet = bool(_BULLET.match(core))
        core = _BULLET.sub("", core)
        prev = MARKER.sub("", lines[i - 1]).strip() if i else ""
        prev_is_year = bool(YEAR_HEADER.fullmatch(prev)) if prev else False
        new = False
        if i and YEAR_HEADER.match(core) and len(core) < 60:
            new = True
        elif i and bullet and not prev_is_year:
            new = True
        elif i and not prev_is_year and _UPPER_START.match(core) and _SENT_DONE.search(prev) \
                and len(prev) < 0.8 * full and not _SPEECH.search(prev) and not _CONTINUATION.match(core):
            new = True
        if new and docs[-1]:
            docs.append([])
        docs[-1].append(core)
    out: list[str] = []
    for d in docs:
        text = re.sub(r"\s+", " ", " ".join(d)).strip()
        text = re.sub(r"(\w)- (\w)", r"\1-\2", text)
        if not text:
            continue
        if out and len(words(text)) < 15 and not YEAR_HEADER.match(text):
            out[-1] += " " + text
        else:
            out.append(text)
    while out and len(words(out[0])) < 8:
        out.pop(0)
    return out

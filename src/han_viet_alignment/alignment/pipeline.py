"""Ghép các bước: làm sạch → tách câu → dóng phiên âm↔dịch → chiếu sang Hán → dòng TSV + dòng review."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..common.dictionary import Readings
from ..common.text import DN_MISSING, MISSING, clean_cell, han_units, syllables
from .cleaning import clean_dich_nghia, clean_han, clean_phien_am
from .correction import PhraseMemory, load_sample_memory, simplified_only


def simplified_in(han: str) -> list[str]:
    """Chữ giản thể (do OCR sinh ra) trong ô han, kèm gợi ý phồn thể: ['钱→錢', '发→發/髮']."""
    return [f"{c}→{'/'.join(t)}" for c in dict.fromkeys(han) if (t := simplified_only(c))]
from .han_pa import learn_memory, match_score, reading_stats, split_han
from .pa_dn import pair_risks
from .pa_dn import align_sentences
from .segment import split_dich_nghia, split_phien_am

COLUMNS = ["sent_id", "doc_id", "doc_type", "han", "phien_am", "dich_nghia", "ghi_chu"]
REVIEW_COLUMNS = ["sent_id", "co", "so_chu_han", "so_am_tiet", "khop_am", "chu_lech", "canh_bao"]
# Mở đầu văn bản ('Sắc.', 'Chiếu.') hoặc công thức '… Hoàng đế chế/chiếu/sắc viết' (vd MAU.003)
_DOC_TYPES = [(r"^s[ắa]c\b|\bs[ắa]c\s+vi[ếe]t\b", "sac_phong"),
              (r"^chi[ếe]u\b|\bchi[ếe]u\s+vi[ếe]t\b", "chieu_phong"),
              (r"^ch[ếe]\b|\bch[ếe]\s+vi[ếe]t\b", "che_phong")]


@dataclass
class DocInput:
    doc_id: str
    han: str
    phien_am: str
    dich_nghia: str


def detect_doc_type(pa: str, dn: str, default: str) -> str:
    for text in (pa, dn):
        head = " ".join(text.strip().lower().split()[:12])
        for pat, t in _DOC_TYPES:
            if re.search(pat, head):
                return t
    return default


def _merge_rows(a: dict, b: dict) -> dict:
    dn = a["dn"] if b["dn"] in ("", DN_MISSING) else (
        b["dn"] if a["dn"] in ("", DN_MISSING) else f"{a['dn']} {b['dn']}")
    return {"han": a["han"] + b["han"], "pa": f"{a['pa']} {b['pa']}".strip(), "dn": dn,
            "n_sent": a["n_sent"] + b["n_sent"], "inserted": a["inserted"] + b["inserted"],
            "masked": a["masked"] + b["masked"], "notes": a["notes"] + b["notes"],
            "flags": a["flags"] + b["flags"]}


def _merge_empty_rows(rows: list[dict]) -> list[dict]:
    """Phòng hờ: dòng không có chữ Hán nào (kể cả □) gộp vào dòng kề (n–1) để không có ô han trống.

    Với phiên âm có âm tiết thì han_pa đã chèn □ cho chữ thiếu, nên trường hợp này hiếm.
    """
    out: list[dict] = []
    for r in rows:
        if out and not r["han"]:
            out[-1] = _merge_rows(out[-1], r)
        else:
            out.append(dict(r))
    if len(out) > 1 and not out[0]["han"]:
        first = out.pop(0)
        out[0] = _merge_rows(first, out[0])
    return out


def _clean(doc: DocInput, readings: Readings, clean: bool) -> tuple[str, str, str]:
    if not clean:
        return doc.han, doc.phien_am, doc.dich_nghia or DN_MISSING
    han = clean_han(doc.han)
    pa = clean_phien_am(doc.phien_am, readings)
    pa_upper = clean_phien_am(doc.phien_am, readings, keep_upper=True)
    # Chuỗi VIẾT HOA có thể là tiêu đề trang hoặc nội dung OCR in hoa ('HỘ QUỐC TÝ DÂN'): giữ khi
    # nó khớp được thêm chữ Hán (bỏ nhầm nội dung làm lệch cả cặp phiên âm ↔ dịch nghĩa).
    if pa_upper != pa and han and readings is not None and \
            match_score(han, pa_upper, readings) > match_score(han, pa, readings):
        pa = pa_upper
    return han, pa, clean_dich_nghia(doc.dich_nghia, readings)


def build_memory(docs: list[DocInput], readings: Readings, clean: bool = True) -> PhraseMemory:
    """Bộ nhớ cụm chữ–âm đã khớp trên toàn sách + dữ liệu mẫu, dùng để sửa chữ Hán OCR sai."""
    memory = load_sample_memory(readings)
    for d in docs:
        han, pa, _ = _clean(d, readings, clean)
        if han and pa:
            learn_memory(han, pa, readings, memory)
    return memory


def align_document(doc: DocInput, readings: Readings, default_doc_type: str = "sac_phong",
                   clean: bool = True, memory: PhraseMemory | None = None,
                   correct: bool = True, mask: bool = True) -> tuple[list[dict], list[dict]]:
    """correct: sửa lỗi OCR có bằng chứng; mask: chữ Hán OCR lệch âm không sửa được -> □ (xem correction.py)."""
    han, pa, dn = _clean(doc, readings, clean)
    if correct and memory is None:
        memory = build_memory([doc], readings, clean)
    doc_type = detect_doc_type(pa, dn, default_doc_type)

    pa_sents = split_phien_am(pa)
    has_dn = dn != DN_MISSING
    dn_ratio = (len(syllables(dn)) / max(len(syllables(pa)), 1)) if has_dn else 1.0
    dn_sents = split_dich_nghia(dn) if has_dn else []
    if has_dn and pa_sents:
        beads = align_sentences(pa_sents, dn_sents)
    else:
        beads = [([i], []) for i in range(len(pa_sents))]

    row_pa = [" ".join(pa_sents[i] for i in b[0]) for b in beads]
    row_dn = [" ".join(dn_sents[j] for j in b[1]) if b[1] else DN_MISSING for b in beads]
    split = split_han(han, row_pa, readings, memory, correct, mask) if row_pa else None
    if split:
        row_pa = split.pa_rows

    raw_rows = [{"han": h, "pa": p, "dn": d, "n_sent": len(b[0]) + len(b[1]), "inserted": n,
                 "masked": mk, "notes": nt, "flags": fl}
                for h, p, d, b, n, mk, nt, fl in zip(split.segments, row_pa, row_dn, beads, split.inserted,
                                                     split.masked, split.notes, split.flags)] if split else []
    if not raw_rows and han:  # không có phiên âm: một dòng cho cả văn bản để không mất dữ liệu
        raw_rows = [{"han": han, "pa": "", "dn": dn, "n_sent": 1, "inserted": 0,
                     "masked": 0, "notes": [], "flags": []}]
    rows_in = _merge_empty_rows(raw_rows)

    rows, review = [], []
    for k, r in enumerate(rows_in, 1):
        sid = f"{doc.doc_id}.{k}"
        # ghi_chu theo mục 3: giải thích chỗ có □ và [...]
        notes = []
        n_box = r["han"].count(MISSING)
        if r["inserted"]:
            notes.append(f"{r['inserted']} chữ Hán OCR chưa nhận được, ghi □; cần đối chiếu ảnh gốc để nhập lại.")
        pre_box = n_box - r["inserted"] - r["masked"]
        if pre_box > 0:
            # □ có sẵn trong đầu vào: không biết do OCR bỏ sót hay nguồn khuyết -> người xác định theo ảnh
            notes.append(f"{pre_box} chữ Hán không đọc được (OCR hoặc nguồn khuyết), ghi □; "
                         "cần đối chiếu ảnh gốc.")
        notes.extend(r["notes"])
        if DN_MISSING in r["dn"]:
            notes.append("Bản dịch khuyết đoạn tương ứng, ghi [...].")
        no_han = n_box > 0 and n_box == len(han_units(r["han"]))
        row = {"sent_id": sid, "doc_id": doc.doc_id, "doc_type": doc_type,
               "han": r["han"], "phien_am": r["pa"], "dich_nghia": r["dn"], "ghi_chu": " ".join(notes)}
        rows.append({c: clean_cell(row[c]) for c in COLUMNS})

        n_han, n_syl, ok, counted, bad = reading_stats(r["han"], r["pa"], readings)
        warns = list(r["flags"])
        if n_han != n_syl:
            warns.append(f"LECH_SO_CHU({n_han}/{n_syl})")
        elif counted and ok / counted < 0.95:
            warns.append("KHOP_AM_DUOI_95")
        if r["n_sent"] > 2:
            warns.append("GOP_NHIEU_CAU")
        if DN_MISSING not in r["dn"] and r["pa"]:
            warns.extend(pair_risks(r["pa"], r["dn"], dn_ratio))
        if not r["pa"] and readings is not None:
            warns.append("THIEU_PHIEN_AM")
        if DN_MISSING in r["dn"]:
            warns.append("THIEU_DICH")
        simp = simplified_in(r["han"])
        if simp:
            # Mục 3: chữ giản thể do OCR sinh ra phải sửa về đúng chữ gốc. Script chấm vẫn tính khớp (từ điển
            # có giản thể) nên phải gắn cờ riêng; không tự đổi vì một chữ giản có thể ứng với nhiều chữ phồn.
            warns.append(f"GIAN_THE({','.join(simp)})")
        if no_han:
            warns.append("THIEU_HAN")
        elif r["inserted"]:
            warns.append(f"OCR_THIEU_CHU({r['inserted']})")
        elif MISSING in r["han"]:
            warns.append("CO_O_VUONG")
        if k == 1 and split and split.leading_extra:
            warns.append(f"BO_CHU_HAN_THUA_DAU({split.leading_extra})")
        if k == len(rows_in) and split and split.trailing_extra:
            warns.append(f"BO_CHU_HAN_THUA_CUOI({split.trailing_extra})")
        review.append({"sent_id": sid, "co": "x" if warns else "",
                       "so_chu_han": str(n_han), "so_am_tiet": str(n_syl),
                       "khop_am": f"{ok}/{counted}" if n_han == n_syl else "",
                       "chu_lech": "; ".join(bad), "canh_bao": " ".join(warns)})
    return rows, review


def summarize(rows: list[dict], readings: Readings) -> dict:
    n_pa = n_pa_ok = n_char = n_ok = incomplete = 0
    for r in rows:
        if MISSING in r["han"] or MISSING in r["phien_am"] or DN_MISSING in r["dich_nghia"]:
            incomplete += 1
        if r["phien_am"]:
            n_pa += 1
            n_han, n_syl, ok, counted, _ = reading_stats(r["han"], r["phien_am"], readings)
            n_char += counted
            if n_han == n_syl:
                n_pa_ok += 1
                n_ok += ok
    return {"docs": len({r["doc_id"] for r in rows}), "pairs": len(rows), "valid_pairs": len(rows) - incomplete,
            "incomplete_pairs": incomplete, "rows_count_match": n_pa_ok, "rows_with_pa": n_pa,
            "chars_ok": n_ok, "chars_total": n_char,
            "reading_match": (n_ok / n_char * 100) if n_char else 0.0,
            "syllables": sum(len(syllables(r["phien_am"])) for r in rows),
            "simplified": sum(1 for r in rows for c in r["han"] if simplified_only(c)),
            "simplified_rows": [r["sent_id"] for r in rows if simplified_in(r["han"])]}

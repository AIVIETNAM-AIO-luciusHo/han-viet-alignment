"""Tách các dòng TSV đã có (kể cả đã hiệu đính tay) thành cặp mệnh đề nhỏ nhất (clause.refine_pair).

Dùng khi không muốn chạy lại dóng hàng từ đầu (mất bản sửa tay): mỗi dòng (han, phien_am, dich_nghia) được
chia theo cặp mệnh đề; chữ Hán chia theo số âm tiết (1 chữ = 1 âm tiết, giữ dấu câu Hán); ghi_chu do máy sinh
được chia lại cho đúng dòng con chứa chữ/âm được nhắc tới.
"""
from __future__ import annotations

import re

from ..common.dictionary import Readings
from ..common.text import DN_MISSING, MISSING, clean_cell, is_han, syl_key, syllables
from .clause import refine_pair
from .han_pa import _align

_SENT = re.compile(r"(?<=\.)\s+(?=[A-ZÀ-ỸĐ0-9])")
_OLD = r"(?:; cần đối chiếu ảnh(?: gốc)?(?: để nhập lại)?)?"
_N_INS = re.compile(r"^(\d+) chữ Hán OCR chưa nhận được, ghi □" + _OLD + r"\.$")
_N_PRE = re.compile(r"^(\d+) chữ Hán không đọc được \(OCR hoặc nguồn khuyết\), ghi □" + _OLD + r"\.$")
_SUA_PA = re.compile(r"^Sửa phiên âm lỗi OCR theo chữ Hán: (.*)\.$")
_SUA_HAN = re.compile(r"^Sửa chữ Hán OCR theo phiên âm \(chữ gần giống/cụm từ lặp\): (.*?)" + _OLD + r"\.$")
_CHE = re.compile(r"^\d+ chữ Hán OCR sai \(không khớp âm: (.*)\), ghi □" + _OLD + r"\.$")
_PA_THIEU = re.compile(r"^Phiên âm thiếu (\d+) âm tiết so với bản Hán \(OCR đọc: (.*)\), ghi □ ở cả chữ Hán và "
                       r"phiên âm" + _OLD + r"\.$")
_DN_MISS = "Bản dịch khuyết đoạn tương ứng, ghi [...]."


def split_han_by_pa(han: str, pa_parts: list[str], readings: Readings | None) -> list[str]:
    """Chia chuỗi Hán theo các phần phiên âm; dấu câu Hán đi theo chữ đứng trước."""
    pos = [k for k, c in enumerate(han) if is_han(c) or c == MISSING]
    counts = [len(syllables(p)) for p in pa_parts]
    if len(pos) == sum(counts):
        owner = [r for r, c in enumerate(counts) for _ in range(c)]
    else:
        syl_row = [r for r, c in enumerate(counts) for _ in range(c)]
        syls = [s for p in pa_parts for s in syllables(p)]
        chars = [han[k] for k in pos]
        owner, cur = [0] * len(pos), 0
        if readings is not None:
            for ci, sj in _align(chars, syls, readings):
                if sj is not None:
                    cur = syl_row[sj]
                if ci is not None:
                    owner[ci] = cur
        else:
            tot = max(sum(counts), 1)
            bounds, acc = [], 0
            for c in counts:
                acc += c
                bounds.append(acc * len(pos) / tot)
            owner = [next(r for r, b in enumerate(bounds) if k < b or r == len(bounds) - 1) for k in range(len(pos))]
    out = [""] * len(pa_parts)
    for idx, k in enumerate(pos):
        end = pos[idx + 1] if idx + 1 < len(pos) else len(han)
        out[owner[idx]] += han[k:end]
    if pos and pos[0] > 0:
        out[0] = han[:pos[0]] + out[0]
    return out


def _items(s: str) -> list[str]:
    return [x.strip() for x in re.split(r",\s+(?=['\"]|\S+(?:→|≠))", s) if x.strip()]


def _pa_keys(pa: str) -> set[str]:
    return {syl_key(s) for s in syllables(pa)}


def distribute_notes(note: str, subs: list[dict]) -> list[list[str]]:
    """Chia ghi_chu của dòng cha cho các dòng con (subs có 'han', 'phien_am', 'dich_nghia')."""
    n = len(subs)
    out: list[list[str]] = [[] for _ in range(n)]
    sua_pa: list[list[str]] = [[] for _ in range(n)]
    sua_han: list[list[str]] = [[] for _ in range(n)]
    che: list[list[str]] = [[] for _ in range(n)]
    explained = [0] * n
    ins_total = pre_total = 0
    keys = [_pa_keys(s["phien_am"]) for s in subs]

    def locate(start: int, pred) -> int:
        for r in range(start, n):
            if pred(r):
                return r
        for r in range(0, start):
            if pred(r):
                return r
        return min(start, n - 1)

    pieces = [p for p in _SENT.split(note.strip()) if p]
    for p in pieces:
        if m := _N_INS.match(p):
            ins_total += int(m.group(1))
        elif m := _N_PRE.match(p):
            pre_total += int(m.group(1))
        elif m := _SUA_PA.match(p):
            cur = 0
            for it in _items(m.group(1)):
                mm = re.match(r"'(.*?)'→'(.*?)' \((.)\)", it)
                if mm:
                    cur = locate(cur, lambda r: syl_key(mm.group(2)) in keys[r] and mm.group(3) in subs[r]["han"])
                sua_pa[cur].append(it)
        elif m := _SUA_HAN.match(p):
            cur = 0
            for it in _items(m.group(1)):
                mm = re.match(r"(.)→(.) \((.*?)\)", it)
                if mm:
                    cur = locate(cur, lambda r: mm.group(2) in subs[r]["han"] and syl_key(mm.group(3)) in keys[r])
                sua_han[cur].append(it)
        elif m := _CHE.match(p):
            cur = 0
            for it in _items(m.group(1)):
                mm = re.match(r"(.)≠(.*)", it)
                if mm:
                    cur = locate(cur, lambda r: MISSING in subs[r]["han"] and syl_key(mm.group(2)) in keys[r])
                che[cur].append(it)
                explained[cur] += 1
        elif m := _PA_THIEU.match(p):
            r = locate(0, lambda r: MISSING in subs[r]["phien_am"])
            out[r].append(p)
            explained[r] += int(m.group(1))
        elif p == _DN_MISS:
            for r in range(n):
                if DN_MISSING in subs[r]["dich_nghia"]:
                    out[r].append(p)
        else:
            hans = [c for c in p if is_han(c)]
            r = locate(0, lambda r: bool(hans) and all(c in subs[r]["han"] for c in hans)) if hans else 0
            out[r].append(p)

    final: list[list[str]] = []
    for r in range(n):
        notes: list[str] = []
        boxes = max(0, subs[r]["han"].count(MISSING) - explained[r])
        k_ins = min(boxes, ins_total)
        ins_total -= k_ins
        k_pre = min(boxes - k_ins, pre_total) if pre_total else 0
        pre_total -= k_pre
        if boxes - k_ins - k_pre > 0:
            k_pre += boxes - k_ins - k_pre
        if k_ins:
            notes.append(f"{k_ins} chữ Hán OCR chưa nhận được, ghi □.")
        if k_pre:
            notes.append(f"{k_pre} chữ Hán không đọc được (OCR hoặc nguồn khuyết), ghi □.")
        if sua_pa[r]:
            notes.append("Sửa phiên âm lỗi OCR theo chữ Hán: " + ", ".join(sua_pa[r]) + ".")
        if sua_han[r]:
            notes.append("Sửa chữ Hán OCR theo phiên âm (chữ gần giống/cụm từ lặp): " + ", ".join(sua_han[r])
                         + ".")
        if che[r]:
            notes.append(f"{len(che[r])} chữ Hán OCR sai (không khớp âm: " + ", ".join(che[r])
                         + "), ghi □.")
        final.append(notes + out[r])
    return final


def split_row(row: dict, readings: Readings | None) -> list[dict]:
    """Một dòng TSV -> các dòng con (sent_id chưa đánh lại). Trả [row] nếu không tách."""
    pa, dn = row["phien_am"], row["dich_nghia"]
    if not pa or not dn or DN_MISSING in dn:
        return [row]
    pairs = refine_pair(pa, dn)
    if len(pairs) < 2:
        return [row]
    pa_parts = [p for p, _ in pairs]
    hans = split_han_by_pa(row["han"], pa_parts, readings)
    if any(not h for h in hans):
        return [row]
    subs = [{**row, "han": h, "phien_am": clean_cell(p), "dich_nghia": clean_cell(d)}
            for h, (p, d) in zip(hans, pairs)]
    for s, nt in zip(subs, distribute_notes(row["ghi_chu"], subs)):
        s["ghi_chu"] = clean_cell(" ".join(nt))
    return subs


def renumber(rows: list[dict]) -> tuple[list[dict], dict[str, list[str]]]:
    """Đánh lại sent_id liên tục trong từng văn bản; trả kèm ánh xạ sent_id cũ -> danh sách id mới."""
    counter: dict[str, int] = {}
    mapping: dict[str, list[str]] = {}
    out = []
    for r in rows:
        counter[r["doc_id"]] = counter.get(r["doc_id"], 0) + 1
        new = f"{r['doc_id']}.{counter[r['doc_id']]}"
        mapping.setdefault(r["sent_id"], []).append(new)
        out.append({**r, "sent_id": new})
    return out, mapping

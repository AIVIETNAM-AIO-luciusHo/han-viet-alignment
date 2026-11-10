"""Dóng Hán ↔ phiên âm cấp chữ–âm tiết (Bước 7) và chiếu ranh giới câu phiên âm sang bản Hán.

Edit distance có từ điển: chữ Hán khớp âm theo từ điển (hoặc □) tốn 0, thay thế/thừa/thiếu tốn 1.
Mỗi chữ Hán được gán vào câu phiên âm của âm tiết mà nó dóng với. Kết quả luôn có số chữ Hán (kể cả □)
= số âm tiết trong mỗi câu, vì dòng lệch số chữ bị tính sai toàn bộ khi chấm độ khớp âm (mục 8):
- chữ thừa ở đầu/cuối văn bản (ấn triện, viền...) được tách riêng để người hiệu đính xem;
- chữ thừa giữa văn bản bị bỏ khỏi cột han và ghi vào ghi_chu (02_ocr_tho vẫn giữ OCR thô);
- âm tiết không có chữ Hán ghi □;
- cặp lệch âm được sửa/che theo correction.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..common.dictionary import Readings
from ..common.text import HAN_PUNCT, MISSING, is_han, syl_key, syllables
from .correction import MAX_N, PhraseMemory, fix_syllable, fix_tone, shape_candidates, tone_only

_SYL = re.compile(r"[\w□]+")  # cùng cách tách âm tiết với syllables()/script kiểm tra


@dataclass
class HanSplit:
    segments: list[str]            # chuỗi Hán cho từng câu phiên âm (giữ dấu câu Hán nếu có)
    trailing_extra: str = ""       # chữ Hán thừa ở cuối văn bản, không dóng được với âm tiết nào
    leading_extra: str = ""        # chữ Hán thừa ở đầu văn bản
    ops: list[tuple[str, str, str]] = field(default_factory=list)  # (op, chữ, âm) để báo cáo
    inserted: list[int] = field(default_factory=list)  # số □ đã chèn (OCR thiếu chữ) cho từng câu
    pa_rows: list[str] = field(default_factory=list)   # phiên âm từng câu sau khi sửa lỗi OCR
    notes: list[list[str]] = field(default_factory=list)  # ghi_chu từng câu (chỗ đã sửa/che/bỏ)
    flags: list[list[str]] = field(default_factory=list)  # cảnh báo review từng câu
    masked: list[int] = field(default_factory=list)       # số chữ OCR sai đã thay bằng □


def _align(chars: list[str], syls: list[str], readings: Readings) -> list[tuple[int | None, int | None]]:
    """Trả về danh sách cặp (chỉ số chữ, chỉ số âm tiết); None ở một vế là thừa/thiếu."""
    n, m = len(chars), len(syls)
    INF = 10 ** 9
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    bt = [[0] * (m + 1) for _ in range(n + 1)]  # 0 diag, 1 bỏ chữ, 2 bỏ âm
    # Bỏ một □ có sẵn rẻ hơn bỏ chữ thật: □ khớp mọi âm nên nếu cùng giá, DP dễ đẩy chữ thật lệch một ô
    del_cost = [0.5 if c == MISSING else 1.0 for c in chars]
    dp[0][0] = 0
    for i in range(1, n + 1):
        dp[i][0], bt[i][0] = dp[i - 1][0] + del_cost[i - 1], 1
    for j in range(1, m + 1):
        dp[0][j], bt[0][j] = j, 2
    for i in range(1, n + 1):
        ci = chars[i - 1]
        dc = del_cost[i - 1]
        row, prev = dp[i], dp[i - 1]
        for j in range(1, m + 1):
            best = prev[j - 1] + (0 if readings.match(ci, syls[j - 1]) else 1)
            arg = 0
            if prev[j] + dc < best:
                best, arg = prev[j] + dc, 1
            if row[j - 1] + 1 < best:
                best, arg = row[j - 1] + 1, 2
            row[j], bt[i][j] = best, arg
    pairs: list[tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        a = bt[i][j]
        if i > 0 and j > 0 and a == 0:
            pairs.append((i - 1, j - 1)); i -= 1; j -= 1
        elif i > 0 and (a == 1 or j == 0):
            pairs.append((i - 1, None)); i -= 1
        else:
            pairs.append((None, j - 1)); j -= 1
    pairs.reverse()
    return pairs


def _rebuild(sent: str, edits: dict[int, str], suffix: dict[int, str] | None = None) -> str:
    """Thay âm tiết thứ k của câu bằng edits[k] (và nối suffix[k] sau nó), giữ nguyên dấu câu/khoảng trắng."""
    suffix = suffix or {}
    if not edits and not suffix:
        return sent
    out, last = [], 0
    for k, m in enumerate(_SYL.finditer(sent)):
        if k in edits or k in suffix:
            out.append(sent[last:m.start()])
            out.append(edits.get(k, m.group(0)) + suffix.get(k, ""))
            last = m.end()
    out.append(sent[last:])
    return "".join(out)


def split_han(han_text: str, pa_sentences: list[str], readings: Readings,
              memory: PhraseMemory | None = None, correct: bool = True, mask: bool = True) -> HanSplit:
    """Chia bản Hán theo câu phiên âm; mỗi câu số chữ Hán (kể cả □) = số âm tiết.

    correct: sửa lỗi OCR có bằng chứng (correction.py). mask: chữ OCR lệch âm không sửa được -> □.
    """
    # Vị trí chữ (Hán/□) trong chuỗi gốc để giữ nguyên dấu câu Hán khi cắt
    positions = [k for k, c in enumerate(han_text) if is_han(c) or c == MISSING]
    chars = [han_text[k] for k in positions]
    syls: list[str] = []
    syl_sent: list[int] = []
    syl_local: list[int] = []
    for s_idx, sent in enumerate(pa_sentences):
        for k, sy in enumerate(syllables(sent)):
            syls.append(sy)
            syl_sent.append(s_idx)
            syl_local.append(k)

    pairs = _align(chars, syls, readings)
    ci_of_sj = {sj: ci for ci, sj in pairs if ci is not None and sj is not None}
    keys = [syl_key(sy) for sy in syls]

    def punct_after(ci: int) -> str:
        """Dấu câu Hán của nguồn đứng ngay sau chữ thứ ci."""
        k = positions[ci] + 1
        end = k
        while end < len(han_text) and han_text[end] in HAN_PUNCT:
            end += 1
        return han_text[k:end]

    def by_phrase(sj: int) -> str | None:
        """Chữ cho âm tiết sj theo cụm 2–4 âm tiết đã gặp; ưu tiên cụm dài và cụm có chữ neo đã khớp."""
        if memory is None:
            return None
        for n in range(MAX_N, 1, -1):
            loose = None
            for st in range(max(0, sj - n + 1), min(sj, len(syls) - n) + 1):
                rend = memory.lookup(tuple(keys[st:st + n]))
                if not rend:
                    continue
                if any(k != sj and k in ci_of_sj and chars[ci_of_sj[k]] == rend[k - st]
                       for k in range(st, st + n)):
                    return rend[sj - st]
                loose = loose or rend[sj - st]
            if loose:
                return loose
        return None

    n_sent = len(pa_sentences)
    buckets: list[list[str]] = [[] for _ in range(n_sent)]
    pa_edits: list[dict[int, str]] = [{} for _ in range(n_sent)]
    fixed_han: list[list[str]] = [[] for _ in range(n_sent)]
    fixed_pa: list[list[str]] = [[] for _ in range(n_sent)]
    masked_ch: list[list[str]] = [[] for _ in range(n_sent)]
    dropped: list[list[str]] = [[] for _ in range(n_sent)]
    variants: list[list[str]] = [[] for _ in range(n_sent)]
    inserted = [0] * n_sent
    ops: list[tuple[str, str, str]] = []

    # Chữ thừa trước âm tiết đầu / sau âm tiết cuối (OCR ấn triện, viền, chữ vùng khác): tách riêng
    aligned_ci = [ci for ci, sj in pairs if ci is not None and sj is not None]
    first_ci = min(aligned_ci, default=len(chars))
    last_ci = max(aligned_ci, default=-1)
    leading, trailing = [], []
    # Độ dài đoạn chữ thừa liên tiếp giữa văn bản mà mỗi chữ thuộc về
    inner = [ci is not None and sj is None and first_ci < ci < last_ci for ci, sj in pairs]
    run_len = [0] * len(pairs)
    p = 0
    while p < len(pairs):
        q = p
        while q < len(pairs) and inner[q]:
            q += 1
        for t in range(p, q):
            run_len[t] = q - p
        p = q + 1 if q == p else q
    pa_suffix: list[dict[int, str]] = [{} for _ in range(n_sent)]
    boxed: list[list[str]] = [[] for _ in range(n_sent)]
    last_sent = 0
    last_sj = -1
    for pi, (ci, sj) in enumerate(pairs):
        if sj is not None:
            last_sj = sj
        if ci is not None and sj is not None:
            last_sent = r = syl_sent[sj]
            ch, sy = chars[ci], syls[sj]
            if not readings.match(ch, sy):
                ops.append(("sub", ch, sy))
                new_sy = (fix_syllable(sy, ch, readings) or fix_tone(ch, sy, readings, memory)) if correct else None
                if new_sy:
                    # Lỗi OCR/in phiên âm (âm tiết hỏng, hoặc sai dấu mà sách đọc chữ này khác): sửa theo chữ Hán
                    pa_edits[r][syl_local[sj]] = new_sy
                    fixed_pa[r].append(f"'{sy}'→'{new_sy}' ({ch})")
                elif tone_only(ch, sy, readings):
                    variants[r].append(f"{ch}/{sy}")  # cách đọc theo sách (vd 記 Kỷ): giữ, để người quyết định
                else:
                    new_ch = None
                    if correct and readings.is_reading(sy):
                        new_ch = shape_candidates(ch, sy, readings, memory) or by_phrase(sj)
                    if new_ch:
                        fixed_han[r].append(f"{ch}→{new_ch} ({sy})")
                        ch = new_ch
                    elif mask:
                        masked_ch[r].append(f"{ch}≠{sy}")
                        ch = MISSING
            buckets[r].append(ch + punct_after(ci))
        elif ci is not None:
            ops.append(("extra_han", chars[ci], ""))
            if ci < first_ci:
                leading.append(chars[ci])
            elif ci > last_ci:
                trailing.append(chars[ci])
            elif run_len[pi] >= 2 and last_sj >= 0:
                # Đoạn ≥ 2 chữ thừa giữa văn bản: thường là câu/cụm có thật mà OCR phiên âm làm mất
                # (vd 'Hộ quốc tý dân'). Bỏ đi thì vế Hán thiếu ý so với dịch nghĩa (lỗi OMISSION trên cặp
                # "hợp lệ") -> ghi □ ở cả han và phien_am (mục 3), chữ OCR ghi ở ghi_chu.
                r = syl_sent[last_sj]
                buckets[r].append(MISSING)
                k = syl_local[last_sj]
                pa_suffix[r][k] = pa_suffix[r].get(k, "") + " " + MISSING
                boxed[r].append(chars[ci])
            else:
                # Một chữ thừa lẻ giữa văn bản (OCR lặp/ấn triện): giữ lại sẽ làm lệch số chữ/âm tiết
                # cả câu -> bỏ khỏi cột han, ghi vào ghi_chu để đối chiếu ảnh.
                dropped[last_sent].append(chars[ci])
                if buckets[last_sent]:
                    buckets[last_sent][-1] += punct_after(ci)
        else:
            # Âm tiết không có chữ Hán tương ứng (OCR bỏ sót): mỗi chữ thiếu ghi một □ (mục 3 hướng dẫn)
            last_sent = syl_sent[sj]
            buckets[last_sent].append(MISSING)
            inserted[last_sent] += 1
            ops.append(("missing_han", "", syls[sj]))

    notes: list[list[str]] = []
    flags: list[list[str]] = []
    for r in range(n_sent):
        nt, fl = [], []
        if fixed_pa[r]:
            nt.append("Sửa phiên âm lỗi OCR theo chữ Hán: " + ", ".join(fixed_pa[r]) + ".")
            fl.append(f"SUA_PA({len(fixed_pa[r])})")
        if fixed_han[r]:
            nt.append("Sửa chữ Hán OCR theo phiên âm (chữ gần giống/cụm từ lặp): "
                      + ", ".join(fixed_han[r]) + "; cần đối chiếu ảnh.")
            fl.append(f"SUA_HAN({len(fixed_han[r])})")
        if masked_ch[r]:
            nt.append(f"{len(masked_ch[r])} chữ Hán OCR sai (không khớp âm: " + ", ".join(masked_ch[r])
                      + "), ghi □; cần đối chiếu ảnh gốc.")
            fl.append(f"CHE_CHU_SAI({len(masked_ch[r])})")
        if boxed[r]:
            nt.append(f"Phiên âm thiếu {len(boxed[r])} âm tiết so với bản Hán (OCR đọc: {''.join(boxed[r])}), "
                      "ghi □ ở cả chữ Hán và phiên âm; cần đối chiếu ảnh.")
            fl.append(f"PA_THIEU_AM({len(boxed[r])})")
        if dropped[r]:
            nt.append(f"Bỏ chữ Hán OCR thừa không có âm tiết tương ứng: {''.join(dropped[r])}; cần đối chiếu ảnh.")
            fl.append(f"BO_CHU_THUA({''.join(dropped[r])})")
        if variants[r]:
            fl.append("KHAC_DAU(" + ",".join(variants[r]) + ")")
        notes.append(nt)
        flags.append(fl)

    return HanSplit(["".join(b) for b in buckets], "".join(trailing), "".join(leading), ops, inserted,
                    [_rebuild(p, e, x) for p, e, x in zip(pa_sentences, pa_edits, pa_suffix)], notes, flags,
                    [len(m) + len(b) for m, b in zip(masked_ch, boxed)])


def match_score(han_text: str, pa_text: str, readings: Readings) -> int:
    """Số chữ Hán dóng khớp âm với phiên âm — để chọn nguồn chữ Hán tốt hơn cho một văn bản."""
    chars = [c for c in han_text if is_han(c)]
    syls = syllables(pa_text)
    return sum(1 for ci, sj in _align(chars, syls, readings)
               if ci is not None and sj is not None and readings.match(chars[ci], syls[sj]))


def learn_memory(han_text: str, pa_text: str, readings: Readings, memory: PhraseMemory) -> None:
    """Thêm các đoạn chữ–âm khớp liên tiếp (≥ 2 chữ) của một văn bản vào bộ nhớ cụm từ."""
    chars = [c for c in han_text if is_han(c) or c == MISSING]
    syls = syllables(pa_text)
    run_c: list[str] = []
    run_s: list[str] = []
    for ci, sj in _align(chars, syls, readings) + [(None, None)]:
        if ci is not None and sj is not None and chars[ci] != MISSING and readings.match(chars[ci], syls[sj]):
            run_c.append(chars[ci])
            run_s.append(syls[sj])
            continue
        if len(run_c) >= 2:
            memory.add_run(run_c, run_s)
        run_c, run_s = [], []


def reading_stats(han: str, pa: str, readings: Readings) -> tuple[int, int, int, int, list[str]]:
    """(số chữ, số âm tiết, số chữ khớp, số chữ tính, danh sách chữ lệch) — giống kiem_tra_du_lieu.py."""
    chars = [c for c in han if is_han(c) or c == MISSING]
    syls = syllables(pa)
    counted = sum(1 for c in chars if c != MISSING)
    if len(chars) != len(syls):
        return len(chars), len(syls), 0, counted, []
    ok, bad = 0, []
    for c, sy in zip(chars, syls):
        if c == MISSING:
            continue
        if readings.match(c, sy):
            ok += 1
        else:
            bad.append(f"{c}≠{sy}" + ("" if c in readings else "(không có trong từ điển)"))
    return len(chars), len(syls), ok, counted, bad

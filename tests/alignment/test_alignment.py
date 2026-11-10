"""Kiểm tra quy tắc dóng hàng theo HUONG_DAN_DO_AN_HAN_VIET_HANH_CHINH (mục 3, 3.1, bước 5–7).

Không cần PDF/GPU/từ điển thật: dùng từ điển nhỏ dựng sẵn. Nếu có guideline/mau_du_lieu/MAU_parallel.tsv
và từ điển thật thì chạy thêm phép thử tái tạo đúng 22 cặp mẫu của giáo viên.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from han_viet_alignment.alignment.cleaning import clean_dich_nghia, clean_han, clean_phien_am  # noqa: E402
from han_viet_alignment.alignment.han_pa import split_han  # noqa: E402
from han_viet_alignment.alignment.pipeline import COLUMNS, DocInput, align_document  # noqa: E402
from han_viet_alignment.alignment.segment import split_dich_nghia, split_phien_am  # noqa: E402
from han_viet_alignment.common.dictionary import Readings  # noqa: E402
from han_viet_alignment.common.text import syl_key  # noqa: E402
from han_viet_alignment.export.writer import write_tsv, write_xlsx  # noqa: E402

TINY = {"敕": "sắc", "欽": "khâm", "哉": "tai", "保": "bảo", "我": "ngã", "黎": "lê", "民": "dân",
        "嗣": "tự", "德": "đức", "柒": "thất", "年": "niên", "拾": "thập", "月": "nguyệt", "壹": "nhất",
        "日": "nhật", "神": "thần", "其": "kỳ", "相": "tướng", "佑": "hựu", "雄": "hùng"}
READ = Readings({ch: {syl_key(s)} for ch, s in TINY.items()})

DOC = DocInput(
    "R9999.001",
    han="敕神其相佑保我黎民欽哉嗣德柒年拾月拾壹日",
    phien_am="Sắc. Thần kỳ tướng hựu, bảo ngã lê dân. Khâm tai! Tự Đức thất niên thập nguyệt thập nhất nhật",
    dich_nghia="Sắc ban cho thần. Mong thần hãy phù hộ che chở cho dân của ta. Kính cẩn thay! "
               "Ngày 11 tháng 10 năm Tự Đức thứ 7 (1854)",
)


class CleaningTests(unittest.TestCase):
    def test_han_only_han_and_box(self):
        self.assertEqual(clean_han("敕 神a1■其"), "敕神□其")

    def test_phien_am_drops_digits_and_lone_consonants(self):
        self.assertEqual(clean_phien_am("An V vũ xã 1 dụng"), "An vũ xã dụng")

    def test_phien_am_joins_split_syllable(self):
        self.assertEqual(clean_phien_am("Hù ng tuấn", READ), "Hùng tuấn")

    def test_dich_nghia_keeps_dates_drops_footnotes(self):
        s = clean_dich_nghia("huyện Kim Động%, chính trị 1 thần[2]. Kính cần thayl Ngày 11 tháng 10 năm thứ 7 (1854)")
        self.assertEqual(s, "huyện Kim Động, chính trị thần. Kính cẩn thay! Ngày 11 tháng 10 năm thứ 7 (1854)")

    def test_missing_translation(self):
        self.assertEqual(clean_dich_nghia(""), "[...]")


class SegmentTests(unittest.TestCase):
    def test_short_header_merges_forward(self):
        self.assertEqual(split_phien_am("Sắc. Thần kỳ tướng hựu. Khâm tai! Tự Đức"),
                         ["Sắc. Thần kỳ tướng hựu.", "Khâm tai!", "Tự Đức"])

    def test_lowercase_continuation(self):
        self.assertEqual(split_dich_nghia("Thần nguyên. được tặng là X; Y."), ["Thần nguyên. được tặng là X;", "Y."])


class HanSplitTests(unittest.TestCase):
    def test_missing_chars_become_boxes(self):
        # OCR bỏ sót 黎: chèn đúng một □ tại vị trí đó (mục 3: mỗi chữ thiếu một □)
        sp = split_han("保我民", ["bảo ngã lê dân."], READ)
        self.assertEqual(sp.segments, ["保我□民"])
        self.assertEqual(sp.inserted, [1])

    def test_trailing_noise_removed(self):
        sp = split_han("欽哉除安", ["Khâm tai!"], READ)
        self.assertEqual(sp.segments, ["欽哉"])
        self.assertEqual(sp.trailing_extra, "除安")


READ_S = Readings({ch: {syl_key(s)} for ch, s in TINY.items()} | {"應": {syl_key("ứng")}, "記": {syl_key("ký")},
                                                            "己": {syl_key("kỷ")}},
                  {syl_key(s): s for s in [*TINY.values(), "ứng", "ký", "kỷ"]})


class CorrectionTests(unittest.TestCase):
    """Sửa lỗi OCR để độ khớp âm của file cuối cao nhất mà không bịa chữ (correction.py)."""

    def _mem(self, *pairs):
        from han_viet_alignment.alignment.correction import PhraseMemory
        mem = PhraseMemory()
        for han, pa in pairs:
            mem.add_run(list(han), pa.split())
        return mem

    def test_inner_extra_han_dropped_so_counts_match(self):
        # Chữ thừa giữa câu làm lệch số chữ -> cả dòng bị tính sai; phải bỏ và ghi chú
        sp = split_han("保我除黎民", ["bảo ngã lê dân."], READ_S, correct=False)
        self.assertEqual(sp.segments, ["保我黎民"])
        self.assertTrue(any("除" in n for n in sp.notes[0]))

    def test_phrase_memory_fixes_formula(self):
        sp = split_han("雅奇", ["Khâm tai!"], READ_S, memory=self._mem(("欽哉", "khâm tai")))
        self.assertEqual(sp.segments, ["欽哉"])
        self.assertIn("SUA_HAN(2)", sp.flags[0])

    def test_broken_syllable_fixed_from_han(self):
        sp = split_han("應", ["Tứng."], READ_S)
        self.assertEqual(sp.pa_rows, ["Ứng."])
        self.assertTrue(sp.notes[0])

    def test_unverifiable_char_masked_and_noted(self):
        sp = split_han("保我雅民", ["bảo ngã lê dân."], READ_S, memory=self._mem())
        self.assertEqual(sp.segments, ["保我□民"])
        self.assertIn("雅≠lê", " ".join(sp.notes[0]))
        sp = split_han("保我雅民", ["bảo ngã lê dân."], READ_S, memory=self._mem(), mask=False)
        self.assertEqual(sp.segments, ["保我雅民"])

    def test_tone_variant_kept_without_evidence(self):
        # 記 'Kỷ' (tên chức theo sách, như MAU): không che, không sửa nếu sách không đọc 記 là 'ký' ở chỗ khác
        sp = split_han("記", ["Kỷ."], READ_S, memory=self._mem())
        self.assertEqual((sp.segments, sp.pa_rows), (["記"], ["Kỷ."]))
        sp = split_han("記", ["Kỷ."], READ_S, memory=self._mem(("記神", "ký thần")))
        self.assertEqual(sp.pa_rows, ["Ký."])


class PairErrorTests(unittest.TestCase):
    """Giảm cặp lỗi (mục 6–8: tỷ lệ lỗi tính trên cặp hợp lệ)."""

    def test_lowercase_after_long_sentence_is_new_sentence(self):
        # OCR mất chữ hoa đầu câu: không gộp, để dóng hàng chọn đơn vị nhỏ nhất (HD 3.1)
        self.assertEqual(split_phien_am("Sắc Cao Sơn chi thần. nguyên tặng Minh đạt chi thần."),
                         ["Sắc Cao Sơn chi thần.", "nguyên tặng Minh đạt chi thần."])

    def test_formula_splits_when_punctuation_lost(self):
        self.assertEqual(split_phien_am("Sắc Linh phù chi thần Hướng lai hộ quốc tý dân. Tứ kim"),
                         ["Sắc Linh phù chi thần", "Hướng lai hộ quốc tý dân.", "Tứ kim"])
        self.assertEqual(split_dich_nghia("che chở cho dân của ta. Kính cẩn thay! Ngày 9 tháng 10"),
                         ["che chở cho dân của ta.", "Kính cẩn thay!", "Ngày 9 tháng 10"])

    def test_dich_nghia_ocr_junk(self):
        s = clean_dich_nghia('ban tặng sắc "2,2 phong. Năm Tự Đức thứ 31,(1,000)" 1878), cho phép 1981 thờ (1 887)')
        self.assertEqual(s, "ban tặng sắc phong. Năm Tự Đức thứ 31, (1878), cho phép thờ (1887)")
        self.assertEqual(clean_dich_nghia("Kinh cần thay]"), "Kính cẩn thay!")

    def test_uppercase_content_kept_when_it_matches_han(self):
        d = DocInput("R9999.004", "保我黎民欽哉", "BẢO NGÃ LÊ DÂN, Khâm tai!", "")
        rows, _ = align_document(d, READ)
        self.assertTrue(rows[0]["phien_am"].startswith("BẢO NGÃ LÊ DÂN"))

    def test_inner_extra_run_boxed_on_both_sides(self):
        # Đoạn ≥ 2 chữ thừa = phiên âm bị mất âm tiết: □ ở cả hai vế để không thành cặp "hợp lệ" thiếu ý
        sp = split_han("神其除安保我", ["thần kỳ bảo ngã."], READ_S, correct=False)
        self.assertEqual(sp.segments, ["神其□□保我"])
        self.assertEqual(sp.pa_rows, ["thần kỳ □ □ bảo ngã."])

    def test_pair_risks(self):
        from han_viet_alignment.alignment.pa_dn import pair_risks
        self.assertEqual(pair_risks("Khâm tai!", "Kính cẩn thay!", 1.5), [])
        self.assertIn("LECH_MOC_KET", pair_risks("Khâm tai!", "Ngày 9 tháng 10 năm Thiệu Trị thứ 6 (1846).", 1.5))


def _has_opencc() -> bool:
    import importlib.util
    return importlib.util.find_spec("opencc") is not None


@unittest.skipUnless(_has_opencc(), "cần opencc-python-reimplemented (requirements.txt)")
class SimplifiedTests(unittest.TestCase):
    """Chữ giản thể do OCR sinh ra: chỉ nhận diện + gắn cờ, không tự chuyển (HD mục 3)."""

    def test_detects_simplified_only(self):
        from han_viet_alignment.alignment.correction import simplified_only
        self.assertEqual(simplified_only("钱"), ("錢",))
        self.assertEqual(simplified_only("发"), ("發", "髮"))  # nhiều chữ phồn: lý do không tự đổi
        for ch in "准台后云干里余敕欽錢":  # vừa giản vừa phồn hợp lệ, hoặc vốn là phồn thể
            self.assertIsNone(simplified_only(ch), ch)

    def test_memory_never_learns_simplified(self):
        from han_viet_alignment.alignment.correction import PhraseMemory
        mem = PhraseMemory()
        mem.add_run(list("动静保我"), "động tĩnh bảo ngã".split())
        self.assertIsNone(mem.lookup((syl_key("động"), syl_key("tĩnh"))))
        self.assertEqual(mem.lookup((syl_key("bảo"), syl_key("ngã"))), "保我")

    def test_flag_without_converting(self):
        read = Readings({"钱": {syl_key("tiền")}, "保": {syl_key("bảo")}})
        rows, review = align_document(DocInput("R9999.005", "保钱", "bảo tiền.", ""), read)
        self.assertEqual(rows[0]["han"], "保钱")
        self.assertIn("GIAN_THE(钱→錢)", review[0]["canh_bao"])


class HanFilterTests(unittest.TestCase):
    def test_drop_only_low_score_and_mismatch(self):
        from han_viet_alignment.alignment.han_filter import filter_han_lines
        lines = ["保我黎民", "氏松著宝", "欽哉"]
        pa = "bảo ngã lê dân. Khâm tai!"
        infos = filter_han_lines(lines, [0.9, 0.3, 0.2], pa, READ)
        # dòng 2: điểm thấp + không khớp -> loại; dòng 3: điểm thấp nhưng khớp âm -> giữ
        self.assertEqual([i.kept for i in infos], [True, False, True])

    def test_no_scores_means_no_filtering(self):
        from han_viet_alignment.alignment.han_filter import filter_han_lines
        infos = filter_han_lines(["氏松"], [None], "bảo ngã", READ)
        self.assertTrue(infos[0].kept)


class PipelineTests(unittest.TestCase):
    def test_rows_follow_contract(self):
        rows, review = align_document(DOC, READ)
        self.assertEqual([r["han"] for r in rows], ["敕神其相佑保我黎民", "欽哉", "嗣德柒年拾月拾壹日"])
        self.assertEqual(rows[1]["dich_nghia"], "Kính cẩn thay!")
        self.assertTrue(rows[2]["dich_nghia"].endswith("(1854)"))
        self.assertEqual([r["sent_id"] for r in rows], ["R9999.001.1", "R9999.001.2", "R9999.001.3"])
        self.assertTrue(all(r["doc_type"] == "sac_phong" for r in rows))
        self.assertEqual(review[1]["khop_am"], "2/2")

    def test_no_han_never_collapses_document(self):
        # OCR không ra chữ Hán nào: vẫn tách câu, mỗi chữ ghi □, có ghi_chu (mục 3.1: không gộp cả văn bản)
        rows, _ = align_document(DocInput("R9999.002", "", DOC.phien_am, DOC.dich_nghia), READ)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["han"], "□□")
        self.assertIn("□", rows[1]["ghi_chu"])

    def test_missing_translation_marked(self):
        rows, _ = align_document(DocInput("R9999.003", DOC.han, DOC.phien_am, ""), READ)
        self.assertTrue(all(r["dich_nghia"] == "[...]" and "[...]" in r["ghi_chu"] for r in rows))


class ExportTests(unittest.TestCase):
    def test_tsv_and_xlsx_identical(self):
        import pandas as pd
        rows, _ = align_document(DOC, READ)
        with tempfile.TemporaryDirectory() as d:
            tsv, xlsx = Path(d) / "x.tsv", Path(d) / "x.xlsx"
            write_tsv(tsv, rows, COLUMNS)
            write_xlsx(xlsx, rows, COLUMNS)
            raw = tsv.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\r", raw)
            df = pd.read_csv(tsv, sep="\t", dtype=str, keep_default_na=False, quoting=3, encoding="utf-8")
            dx = pd.read_excel(xlsx, sheet_name="DONG_HANG", dtype=str).fillna("")
            self.assertEqual(list(df.columns), COLUMNS)
            self.assertTrue(dx.equals(df))


MAU = ROOT / "guideline" / "mau_du_lieu" / "MAU_parallel.tsv"
DICT = ROOT / "guideline" / "dict" / "QuocNgu_SinoNom_TongHop3.xlsx"


@unittest.skipUnless(MAU.exists() and DICT.exists(), "cần guideline/ (dữ liệu mẫu + từ điển của giáo viên)")
class TeacherSampleTests(unittest.TestCase):
    def test_reconstructs_all_sample_pairs(self):
        import pandas as pd
        from han_viet_alignment.common.dictionary import load_readings
        readings = load_readings(DICT)
        gold = pd.read_csv(MAU, sep="\t", dtype=str, keep_default_na=False, quoting=3)
        for doc, g in gold.groupby("doc_id", sort=False):
            d = DocInput(doc, "".join(g.han), " ".join(g.phien_am), " ".join(g.dich_nghia))
            rows, _ = align_document(d, readings)
            self.assertEqual(len(rows), len(g), doc)
            for gr, pr in zip(g.to_dict("records"), rows):
                for c in ("sent_id", "han", "phien_am", "dich_nghia", "doc_type"):
                    self.assertEqual(pr[c], gr[c], f"{gr['sent_id']} {c}")


if __name__ == "__main__":
    unittest.main()

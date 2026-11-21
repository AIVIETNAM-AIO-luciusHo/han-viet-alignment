"""Kiểm tra dóng hàng Minh Mệnh (không phiên âm): mốc tờ, lọc chữ lề, niên hiệu, dóng hàng theo mặt tờ.

Dữ liệu dựng tay, không cần PDF/từ điển thật.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from han_viet_alignment.common.dictionary import Readings  # noqa: E402
from han_viet_alignment.common.text import syl_key  # noqa: E402
from han_viet_alignment.minh_menh.align import (  # noqa: E402
    align_quyen, align_stream, build_stream, group_sentences, low_confidence, rough_cuts, split_to_sentences)
from han_viet_alignment.minh_menh.han_ocr import SHEET, HanUnit, cn2int, load_han_book  # noqa: E402
from han_viet_alignment.minh_menh.viet_text import (  # noqa: E402
    VietSentence, anchor_positions, assign_folios, build_sentences, parse_markers, sentence_tokens,
    segment_translation, split_sentences, vn_year_number)

READ = Readings({ch: {syl_key(s)} for ch, s in
                 {"乾": "càn", "元": "nguyên", "殿": "điện", "兵": "binh", "部": "bộ"}.items()})

HAN_MD = """# R9999
## Trang 1

明命政要卷之十四

制兵第十三

明命元年

命諸軍操演戎陣

帝謂侍臣曰朝廷養兵無所靳費每有興造輒加賞

月命文要

## Trang 2

曰名正耳

光YTE

刻減及藉事游移者各從重論

1b

明命二年
"""


class TestHanOcr(unittest.TestCase):
    def test_cn2int(self):
        self.assertEqual([cn2int(s) for s in ("十", "十四", "二十", "二十二", "三")], [10, 14, 20, 22, 3])

    def test_folios_margins_and_units(self):
        book = load_han_book(HAN_MD)
        self.assertEqual(book.quyen_numbers, {0: 14})
        self.assertEqual(book.page_folio, {1: 0, 2: 1})  # trang đầu quyển là 1a, trang sau là 1b
        texts = [u.text for u in book.units]
        # Bỏ tiêu đề quyển, tên thiên, chữ lề (月命文要, 曰名正耳), rác OCR (光YTE, 1b)
        self.assertEqual(texts, ["明命元年", "命諸軍操演戎陣",
                                 "帝謂侍臣曰朝廷養兵無所靳費每有興造輒加賞刻減及藉事游移者各從重論", "明命二年"])
        self.assertEqual(book.units[0].year, 1820)
        self.assertEqual((book.units[2].folio_start, book.units[2].folio_end), (0, 1))  # đoạn vắt qua hai mặt
        reasons = {r for _, _, r in book.dropped}
        self.assertTrue({"tieu_de_quyen", "ten_thien", "le_trang"} <= reasons)


class TestVietText(unittest.TestCase):
    def test_markers_repair_ocr_noise(self):
        md = "[tờ 1-A] a [tờ 1-b] b [tờ 2-a] c [tờ 2-5b] d [tờ 3-4] e [tờ 6.8] f [tờ 1ì-a] g [tờ 2-3b]"
        got = [g for _, g in parse_markers(md)]
        # 2-5b -> 2b, 3-4 -> 3a, '6.8' -> 6a (nhảy mặt hợp lệ), '1ì-a' và '2-3b' sai thứ tự -> bỏ
        self.assertEqual(got, [0, 1, 2, 3, 4, 10])

    def test_new_quyen_uses_header_when_1a_missing(self):
        md = "[tờ 1-a] x " + " ".join(f"[tờ {n}-a] y [tờ {n}-b] y" for n in range(2, 8)) + \
             " QUYỀN THỨ 15 NĂM MINH-MỆNH [tờ 1-b] z"
        got = parse_markers(md)
        self.assertEqual([g for _, g in got][-2:], [SHEET, SHEET + 1])

    def test_year_numbers(self):
        self.assertEqual(vn_year_number("NĂM MINH-MỆNH THỨ HAI MƯƠI MỐT (1840)"), 21)
        self.assertEqual(vn_year_number("NIÊN HIỆU MINH-MỆNH NĂM ĐẦU (1820)"), 1)
        self.assertEqual(VietSentence("NĂM MINH-MỆNH THỨ CHÍN (1928)", "d").year, 1828)

    def test_split_sentences_keeps_year_header_and_numbers(self):
        s = split_sentences("NĂM MINH.MỆNH THỨ HAI (1821) Đầu mùa xuân duyệt binh. 1. Vua lấy 2 vệ đi.")
        self.assertEqual(s, ["NĂM MINH.MỆNH THỨ HAI (1821)", "Đầu mùa xuân duyệt binh.", "1. Vua lấy 2 vệ đi."])

    def test_leading_fragment_joins_previous_doc(self):
        sents = build_sentences({"D.001": "Quan tâu xin cấp áo cho lính.", "D.002": "ấy là phải. Vua dụ rằng."})
        self.assertEqual([s.doc_id for s in sents], ["D.001", "D.002"])
        self.assertTrue(sents[0].text.endswith("ấy là phải."))

    def test_anchor_positions_and_folios(self):
        docs = {"D.001": "Vua ngự điện Càn nguyên xem tập trận. Vua bảo rằng quân phải chăm luyện tập.",
                "D.002": "Bộ Binh tâu xin đặt thêm quân."}
        md = "## Trang 10\nVua ngự điện Càn nguyên xem tập trận. Vua bảo rằng [tờ 1-b] quân phải chăm luyện " \
             "tập.\n[tờ 2-a] Bộ Binh tâu xin đặt thêm quân."
        md = "[tờ 1-A] " + md
        sents = build_sentences(docs)
        anchors = anchor_positions(md, parse_markers(md), sentence_tokens(sents))
        assign_folios(sents, anchors)
        self.assertEqual([(s.folio_start, s.folio_end) for s in sents], [(0, 0), (0, 1), (2, 2)])

    def test_bare_markers_and_digit_confusion(self):
        # R1205: mốc không có chữ 'tờ', OCR đọc '2' thành '9', '3' thành '5'
        got = [g for _, g in parse_markers("[1b] x [9a] y (9b] z [5a} w [3b] [4b]")]
        self.assertEqual(got, [1, 2, 3, 4, 5, 7])

    def test_lost_digit_is_not_new_quyen(self):
        md = " ".join(f"[tờ {n}a] y [tờ {n}b] y" for n in range(1, 11)) + " [tờ 1b] z [tờ 12a] z"
        got = [g for _, g in parse_markers(md)]
        self.assertTrue(all(g < SHEET for g in got))  # '[tờ 1b]' là '11b' mất chữ số, không sang quyển mới

    def test_year_header_without_parentheses(self):
        self.assertEqual(VietSentence("MINH-MỆNH NĂM THỨ MƯỜI", "d").year, 1829)
        self.assertEqual(VietSentence("NĂM MINH.MỆNH THỨ 2", "d").year, 1821)
        self.assertEqual(VietSentence("NĂM ĐẦU NIÊN HIỆU MINH.MỆNH", "d").year, 1820)
        self.assertIsNone(VietSentence("MINH-MỆNH CHÍNH-YẾU", "d").year)

    def test_segment_translation(self):
        md = """## Trang 1
Bìa sách
## Trang 2
QUYỀN THỨ 18
NĂM MINH-MỆNH THỨ HAI (1821)
[tờ 1a] Quan Bộ Binh tâu xin đặt thêm quân ở các trấn biên giới phía bắc.
Vua phán rằng:
Cho làm như lời tâu, các trấn phải lo liệu cho đủ số quân cần
dùng.
Bộ Hộ tâu xin định lại lệ thuế ruộng công của các tỉnh từ Quảng-bình trở vào Nam.
(1) chú thích cuối trang
## Trang 3
12
MINH-MỆNH CHÍNH-YẾU
[tờ 1b] Vua y cho thi hành ngay từ năm ấy, các quan đều phải tuân theo lệ mới.
## Trang 4
Mục lục
"""
        docs = segment_translation(md)
        self.assertEqual(len(docs), 2)
        self.assertTrue(docs[0].startswith("NĂM MINH-MỆNH THỨ HAI (1821) Quan Bộ Binh"))
        self.assertIn("Vua phán rằng: Cho làm", docs[0])  # lời đáp thuộc cùng sự việc
        self.assertTrue(docs[1].startswith("Bộ Hộ tâu xin"))
        self.assertNotIn("chú thích", " ".join(docs))
        self.assertNotIn("Mục lục", " ".join(docs))


class TestAlign(unittest.TestCase):
    def test_align_by_folio_length_and_years(self):
        units = [HanUnit("明命元年", 0, 0, (1, 1), ["明命元年"]),
                 HanUnit("帝御乾元殿觀之", 0, 0, (1, 1), ["帝御乾元殿觀之"]),
                 HanUnit("命兵部改正兵籍", 1, 1, (2, 2), ["命兵部改正兵籍"])]
        sents = [VietSentence("NIÊN HIỆU MINH-MỆNH NĂM ĐẦU (1820)", "D.001", 0, 0),
                 VietSentence("Vua ngự ra điện Càn-nguyên xem tập.", "D.001", 0, 0),
                 VietSentence("Khiến quan Bộ Binh cải chính số binh tịch.", "D.002", 1, 1)]
        beads = align_quyen(units, sents, READ, ratio=1.5)
        self.assertEqual([(b.han, b.viet) for b in beads], [([0], [0]), ([1], [1]), ([2], [2])])

    def test_split_to_sentences_one_sentence_per_pair(self):
        unit = HanUnit("帝御乾元殿觀之命兵部改正兵籍", 0, 0, (1, 1), ["帝御乾元殿觀之", "命兵部改正兵籍"])
        sents = [VietSentence("Vua ngự ra điện Càn-nguyên xem tập.", "D.001"),
                 VietSentence("Khiến quan Bộ Binh cải chính số binh tịch.", "D.002")]
        pieces = split_to_sentences([unit], sents, READ, ratio=1.5)
        self.assertEqual([(p.han, [s.doc_id for s in p.sents]) for p in pieces],
                         [("帝御乾元殿觀之", ["D.001"]), ("命兵部改正兵籍", ["D.002"])])

    def test_split_prefers_sentence_final_particle(self):
        text = "朕甚厭之其令兵部傳諭凡月餉恩賜也帝從之"
        unit = HanUnit(text, 0, 0, (1, 1), [text])
        sents = [VietSentence("Ta rất chán ghét, bảo Bộ Binh truyền dụ, phàm lương tháng ban thưởng.", "D.001"),
                 VietSentence("Vua theo lời ấy.", "D.001")]
        pieces = split_to_sentences([unit], sents, READ, ratio=1.5)
        self.assertEqual([p.han for p in pieces], ["朕甚厭之其令兵部傳諭凡月餉恩賜也", "帝從之"])

    def test_low_confidence_rules(self):
        self.assertEqual(low_confidence(40, 55, 1.4, 1, 1, 3, 0, False, []), [])
        self.assertIn("TIN_CAY_THAP:TY_LE", low_confidence(10, 60, 1.4, 1, 1, 3, 0, False, []))
        self.assertIn("TIN_CAY_THAP:LECH_TO", low_confidence(40, 55, 1.4, 1, 1, 3, 1, False, []))
        self.assertIn("TIN_CAY_THAP:CAT_TUY_Y", low_confidence(40, 55, 1.4, 1, 1, 0, 0, False, [], cut_score=0))
        self.assertEqual(low_confidence(4, 9, 1.4, 1, 1, 0, 2, True, []), [])  # dòng niên hiệu luôn giữ

    def test_global_cut_crosses_ocr_paragraphs(self):
        # Đoạn OCR ngắt giữa câu (…命兵 | 部改正兵籍): dóng cấp chữ vẫn cắt đúng chỗ đổi câu, không theo đoạn
        units = [HanUnit("明命元年", 0, 0, (1, 1), ["明命元年"]),
                 HanUnit("帝御乾元殿觀之命兵", 0, 0, (1, 1), ["帝御乾元殿觀之命兵"]),
                 HanUnit("部改正兵籍", 0, 0, (1, 1), ["部改正兵籍"])]
        sents = [VietSentence("NIÊN HIỆU MINH-MỆNH NĂM ĐẦU (1820)", "D.001", 0, 0),
                 VietSentence("Vua ngự ra điện Càn-nguyên xem tập.", "D.001", 0, 0),
                 VietSentence("Khiến quan Bộ Binh cải chính số binh tịch.", "D.002", 0, 0)]
        st = build_stream(units)
        beads = align_quyen(units, sents, READ, ratio=1.5)
        cuts, margins = align_stream(st, sents, rough_cuts(units, sents, beads, st), READ, ratio=1.5)
        self.assertEqual([st.text[a:b] for a, b in zip(cuts, cuts[1:])], ["明命元年", "帝御乾元殿觀之", "命兵部改正兵籍"])
        self.assertEqual(len(margins), len(cuts))

    def test_global_cut_matches_sentence_edges(self):
        # Theo độ dài thì cắt sớm (câu 1 ngắn); khớp mép "… tâu lên" ↔ 以聞, "Vua ưng cho" ↔ 上許 kéo về đúng chỗ
        text = "臣奏請增設防兵以聞上許之命廷議"
        st = build_stream([HanUnit(text, 0, 0, (1, 1), [text])])
        sents = [VietSentence("Quan xin thêm lính, tâu lên.", "D.001", 0, 0),
                 VietSentence("Vua ưng cho, lại sai đình thần họp bàn định số lính phòng giữ mỗi đồn.", "D.001", 0, 0)]
        rough = [0, 6, len(text)]
        cuts, _ = align_stream(st, sents, rough, READ, ratio=1.5, P={"w_edge": 0.0})
        self.assertEqual(text[:cuts[1]], "臣奏請增")
        cuts, _ = align_stream(st, sents, rough, READ, ratio=1.5)
        self.assertEqual(text[:cuts[1]], "臣奏請增設防兵以聞")

    def test_group_merges_uncertain_and_empty(self):
        cuts = [0, 5, 9, 9, 20]
        # biên độ thấp ở cắt 2 -> gộp câu 1–2; câu 2 có đoạn Hán rỗng (cuts[2] == cuts[3]) -> gộp với câu sau
        self.assertEqual(group_sentences(cuts, [9, 3.0, 0.2, 3.0, 9], 1.0), [(0, 1), (1, 3), (3, 4)])
        self.assertEqual(group_sentences(cuts, [9, 3.0, 3.0, 3.0, 9], 1.0), [(0, 1), (1, 2), (2, 4)])

if __name__ == "__main__":
    unittest.main()

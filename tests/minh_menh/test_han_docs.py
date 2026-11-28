import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from han_viet_alignment.minh_menh import han_docs as D  # noqa: E402

PAIRS = [("vua", "帝"), ("bảo", "謂"), ("binh", "兵"), ("bộ", "部"), ("hình", "刑"), ("quan", "官"), ("thần", "臣"),
         ("dân", "民"), ("tâu", "奏"), ("năm", "年"), ("minh", "明"), ("mệnh", "命"), ("tù", "囚"), ("tội", "罪")]


def scorer(p1=0.7, text="帝謂兵部刑官臣民奏年明命囚罪"):
    s2c, c2s = D.build_dictionary(PAIRS)
    return D.Scorer(s2c, c2s, Counter(text), p1)


def unit(t, dong=0, cut_ok=False, year=False, nocut=False):
    return {"text": t, "dong": dong, "off": 0, "cut_ok": cut_ok, "year_start": year, "nocut": nocut}


class HanDocsTests(unittest.TestCase):
    def test_syllables_strip_diacritics_and_split_hyphens(self):
        self.assertEqual(D.viet_syllables("Vua bảo Đô-đốc Nguyễn-Công"), ["vua", "bao", "do", "doc", "nguyen", "cong"])
        self.assertEqual(D.norm_syl("Đức"), "duc")

    def test_dictionary_maps_both_ways(self):
        s2c, c2s = D.build_dictionary([("Binh", "兵"), ("bình", "平"), ("binh", "冰")])
        self.assertEqual(s2c["binh"], {"兵", "平", "冰"})
        self.assertEqual(c2s["平"], {"binh"})

    def test_parse_leaf(self):
        self.assertEqual([D.parse_leaf(x) for x in ("1-a", "1-b", "12-b", "", "x")], [0, 1, 23, None, None])

    def test_repair_leaves_fixes_wrong_and_missing_readings(self):
        # true 0..7; reading errors: an unreadable one, a wrong one (99), a repeat
        self.assertEqual(D.repair_leaves([0, 1, None, 3, 99, 5, 6, 7]), [0, 1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(D.repair_leaves([5, 6, 7]), [5, 6, 7])  # a quyen whose first markers were missed
        self.assertEqual(D.repair_leaves([]), [])

    def test_doc_leaves_page_mapping_and_segments(self):
        C = "A" * 300
        docs = [{"doc_id": "d1", "quyen": "14", "start": 10, "end": 120}, {"doc_id": "d2", "quyen": "14", "start": 120, "end": 300}]
        markers = [{"offset": 0, "dung": "1-a"}, {"offset": 60, "dung": "1-b"}, {"offset": 150, "dung": "2-a"}]
        lv = D.doc_leaves(docs, markers)
        self.assertEqual((lv[0]["pstart"], lv[0]["pend"]), (218, 219))   # base 218 + leaf 0 .. 1
        self.assertEqual((lv[1]["pstart"], lv[1]["pend"]), (219, 220))   # starts on side 1-b, ends on 2-a
        self.assertEqual(lv[0]["segs"], {0: (10, 60), 1: (60, 120)})

    def test_partition_follows_the_lexical_bridge(self):
        sc = scorer()
        docs = [{"syll": D.viet_syllables("Vua bảo bộ Hình tâu quan thần")}, {"syll": D.viet_syllables("dân tù tội năm")}]
        units = [unit("帝謂部刑奏官臣"), unit("帝謂刑部臣奏"), unit("民囚罪年民囚"), unit("罪囚民年罪")]
        self.assertEqual(D.partition_page(units, docs, sc, kappa=0.0, bonus=0.0), [2, 2])

    def test_every_doc_gets_a_unit_when_possible_and_counts_sum_to_units(self):
        sc = scorer()
        docs = [{"syll": ["vua"]}, {"syll": ["dan"]}, {"syll": ["toi"]}]
        for n in (3, 5, 2):
            units = [unit("帝" * 3) for _ in range(n)]
            c = D.partition_page(units, docs, sc)
            self.assertEqual(sum(c), n)
            if n >= 3:
                self.assertTrue(all(x >= 1 for x in c))

    def test_year_heading_cue_and_nocut(self):
        sc = scorer()
        docs = [{"syll": ["vua"], "year": False}, {"syll": ["vua"], "year": True}]
        units = [unit("帝" * 5), unit("帝" * 5), unit("明命二年帝帝", year=True), unit("帝" * 5)]
        c = D.partition_page(units, docs, sc, kappa=0.0, bonus=0.0)
        self.assertEqual(c, [2, 2])  # the second doc (Viet year heading) opens at the Han year heading
        units[1]["nocut"] = True  # cutting before unit 1 is forbidden anyway; the optimum is unchanged
        self.assertEqual(D.partition_page(units, docs, sc, kappa=0.0, bonus=0.0), [2, 2])

    def test_han_units_split_before_year_headings_and_keep_text_exact(self):
        rows = [{"loai": "than", "thu_tu": "1", "trang": "300", "dong": "0", "cot": "1", "thut": "0", "cot_ngan": "0",
                 "van_ban": "以開正初七日爲始明命八年", "diem": "0.9"},
                {"loai": "than", "thu_tu": "2", "trang": "300", "dong": "1", "cot": "2", "thut": "1", "cot_ngan": "0",
                 "van_ban": "之明命四年兵部臣奏言", "diem": "0.9"},
                {"loai": "tieu_de_le", "thu_tu": "", "trang": "300", "dong": "2", "cot": "", "thut": "", "cot_ngan": "",
                 "van_ban": "明命政要卷之十四", "diem": "0.5"}]
        us = D.han_units(rows)[300]
        self.assertEqual("".join(u["text"] for u in us), "以開正初七日爲始明命八年之明命四年兵部臣奏言")
        self.assertEqual([u["text"] for u in us], ["以開正初七日爲始", "明命八年", "之", "明命四年兵部臣奏言"])
        self.assertEqual([u["year_start"] for u in us], [False, True, False, True])
        self.assertTrue(us[0]["nocut"] and us[2]["nocut"] and not us[1].get("nocut"))
        self.assertEqual([u["off"] for u in us], [0, 8, 0, 1])

    def test_align_book_covers_every_unit_and_lists_pages_without_doc(self):
        sc = scorer()
        C = "Vua bảo bộ Hình. dân tù tội."
        docs = [{"quyen": "14", "start": 0, "end": 16}, {"quyen": "14", "start": 16, "end": len(C)}]
        leaves = [{"pstart": 218, "pend": 218, "segs": {0: (0, 16)}, "flags": []},
                  {"pstart": 218, "pend": 219, "segs": {0: (16, 22), 1: (22, len(C))}, "flags": []}]
        pages = {218: [unit("帝謂部刑", 0), unit("民囚罪", 1)], 219: [unit("囚罪", 0)], 230: [unit("帝", 0)]}
        out = D.align_book(docs, leaves, C, pages, sc, kappa=0.0, bonus=0.0)
        got = sum(len(u["text"]) for v in out["assign"].values() for _, u in v) + sum(len(u["text"]) for _, u, _ in out["unassigned"])
        self.assertEqual(got, sum(len(u["text"]) for us in pages.values() for u in us))
        self.assertEqual([(p, w) for p, _, w in out["unassigned"]], [(230, "trang_khong_thuoc_van_ban_nao")])
        self.assertEqual(out["shared"], 1)

    def test_estimators(self):
        sc = scorer()
        C = "vua bao binh " * 10
        docs = [{"quyen": "14", "start": 0, "end": len(C)}]
        pages = {p: [unit("帝謂兵")] for p in range(218, 298)}
        self.assertAlmostEqual(D.estimate_ratio(docs, C, pages, ("14",)), 80 * 3 / 30)
        leaves = [{"pstart": 218, "pend": 218, "segs": {0: (0, len(C))}, "flags": []}]
        self.assertAlmostEqual(D.estimate_p1(docs, leaves, C, {218: [unit("帝謂兵")]}, sc, ("14",)), 0.9)


def U(t, dong=0, cut_ok=False, year=False):
    return {"text": t, "dong": dong, "off": 0, "cut_ok": cut_ok, "year_start": year, "title": False}


class CharLevelTests(unittest.TestCase):
    def test_title_pieces_are_split_off_and_listed(self):
        self.assertEqual(D.split_line("制兵第十三"), [(0, 5, "title")])
        pieces = D.split_line("慎刑第十四下明命十一年辰天福")
        self.assertEqual([k for _, _, k in pieces], ["title", "year"])
        self.assertEqual(D.split_line("得延宕明命政要卷之十五止")[-1][2], "title")
        # a sentence that merely starts with '…第N…' is not a title (the remainder is not empty / a year heading)
        self.assertEqual([k for _, _, k in D.split_line("王第二子為親王")], ["text"])

    def test_cut_candidates_respect_year_headings_and_openers(self):
        units = [U("初定京外兵為三等"), U("明命三年", year=True), U("帝以內務武庫匠役多因事侵虧也諭陳登儀")]
        chars, cand = D.cut_candidates(units)
        pos = {i for i in cand}
        self.assertIn(8, pos)                    # the year heading starts here
        self.assertTrue(cand[8][2])
        self.assertNotIn(9, pos)                 # never inside a year heading
        self.assertFalse(any(i in pos for i in range(1, 8)))  # <= 24 chars before a heading: belongs to the previous doc
        self.assertIn(next(i for i, c in enumerate(chars) if c[0] == "諭"), pos)  # before an opener after a sentence-final particle

    def test_char_level_cut_lands_on_the_sentence_boundary_inside_a_line(self):
        sc = scorer()
        docs = [{"syll": D.viet_syllables("Vua bảo bộ Hình tâu quan thần")}, {"syll": D.viet_syllables("dân tù tội năm"), "year": False}]
        units = [U("帝謂部刑奏官臣之民囚罪年民囚罪", cut_ok=False)]  # one OCR line holding the end of doc 1 and doc 2
        ranges, chars = D.partition_page_chars(units, docs, sc, kappa=0.0, min_chars=2)
        self.assertEqual(ranges[0][1], 8)         # cut right after the particle 之
        self.assertEqual(ranges[1][0], 8)
        self.assertEqual(ranges[0][3], "cau")

    def test_closing_formula_goes_to_the_previous_document(self):
        sc = scorer()
        units = [U("帝然之刑部臣奏言民囚罪")]
        docs = [{"syll": ["vua"], "opt": True}, {"syll": D.viet_syllables("Bộ Hình tâu dân tù tội")}]
        ranges, _ = D.partition_page_chars(units, docs, sc, kappa=0.0)
        self.assertEqual((ranges[0][0], ranges[0][1]), (0, 3))

    def test_year_heading_rule_forces_the_cut_at_the_heading(self):
        sc = scorer()
        docs = [{"syll": ["vua"], "year": False}, {"syll": ["vua"], "year": True}]
        units = [U("帝" * 30), U("明命二年", year=True), U("帝" * 20)]
        ranges, chars = D.partition_page_chars(units, docs, sc, kappa=0.0)
        self.assertEqual(ranges[1][0], 30)

    def test_viet_year_head_variants(self):
        for t in ("NĂM MINH-MỆNH THỨ HAI", "MINH MỆNH NĂM THỨ BA", "MINH-MỆNH NĂM THỨ BA Vua", "AINH-MỆNH NĂM ĐẦU"):
            self.assertTrue(D.viet_year_head(t), t)
        self.assertFalse(D.viet_year_head("Vua bảo rằng"))


class QuoteClauseTests(unittest.TestCase):
    def test_no_cut_right_after_a_quotation_verb_but_before_its_subject(self):
        units = [U("帝以事諭陳登儀曰汝等職在監臨宜慎乃攸司也廷臣又言向例重案人罪")]
        chars, cand = D.cut_candidates(units)
        text = "".join(c for c, _, _ in chars)
        after_yue = text.index("曰") + 1
        self.assertNotIn(after_yue, cand)                      # 帝…曰: the speech belongs to the same document
        subj = text.index("廷臣")
        self.assertIn(subj, cand)                              # …before the subject of the next quotation clause
        self.assertGreater(cand[subj][0], 2.0)

    def test_no_document_ends_mid_sentence_or_starts_with_a_particle(self):
        units = [U("帝以事諭曰汝等而又曰也之矣以其宜慎")]
        chars, cand = D.cut_candidates(units)
        text = "".join(c for c, _, _ in chars)
        for i in cand:
            self.assertNotIn(text[i - 1], "曰云言其以而又及與則若")
            self.assertNotIn(text[i], "之也焉矣耳哉乎者曰云言")

    def test_compound_verbs_are_not_split(self):
        units = [U("命通"), U("諭廣平以南諸轄當班兵月一操演")]
        chars, cand = D.cut_candidates(units)
        self.assertNotIn(2, cand)                              # between 通 and 諭 (通諭)

    def test_bare_line_start_is_only_a_penalised_fallback(self):
        units = [U("民暗裏虧心豈待預知"), U("面小省設巡撫考五面", cut_ok=True)]
        chars, cand = D.cut_candidates(units)
        self.assertEqual(cand[9][1], "dong")
        self.assertLess(cand[9][0], 0)

    def test_next_document_takes_a_quotation_clause_from_the_end_of_the_page(self):
        sc = scorer()
        docs = [{"syll": D.viet_syllables("Vua bảo bộ Hình tâu quan thần")},
                {"syll": D.viet_syllables("dân tù tội năm quan thần"), "opt": True, "year": False}]
        units = [U("帝謂部刑奏官臣之廷臣又言民囚罪")]
        ranges, _ = D.partition_page_chars(units, docs, sc, kappa=2.0)
        self.assertEqual(ranges[0][1], 8)                      # 廷臣又言… goes to the next document
        self.assertEqual(ranges[1], (8, 15, "cau", "trang"))

    def test_year_heading_at_the_top_of_a_page_leaves_the_text_before_it_to_the_previous_document(self):
        sc = scorer()
        docs = [{"syll": ["vua"], "opt": True}, {"syll": D.viet_syllables("năm minh mệnh vua"), "year": True}]
        units = [U("辟速奏裁處母得淹緩"), U("明命二年", year=True), U("帝" * 12)]
        ranges, _ = D.partition_page_chars(units, docs, sc, kappa=0.0)
        self.assertEqual(ranges[0][1], 9)


if __name__ == "__main__":
    unittest.main()

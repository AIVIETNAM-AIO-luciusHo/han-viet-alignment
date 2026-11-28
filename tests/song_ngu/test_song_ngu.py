"""Kiểm tra dóng hàng song ngữ (text sạch, đã chia đoạn). Dữ liệu dựng tay, không cần từ điển thật."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from han_viet_alignment.common.dictionary import Readings  # noqa: E402
from han_viet_alignment.common.text import syl_key  # noqa: E402
from han_viet_alignment.song_ngu.align import align_text, split_han, split_header, split_viet  # noqa: E402

READ = Readings({ch: {syl_key(s)} for ch, s in {
    "臧": "tang", "質": "chất", "義": "nghĩa", "宣": "tuyên", "己": "kỷ", "亥": "hợi", "魏": "ngụy"}.items()})


class TestSplit(unittest.TestCase):
    def test_han_quote_not_cut(self):
        s = "質曰：「事中宜然。天下危。」時義宣已奉帝。"
        self.assertEqual(split_han(s), ["質曰：「事中宜然。天下危。」", "時義宣已奉帝。"])

    def test_viet_number_and_quote(self):
        s = "Có hơn 1.000 chiếc thuyền. Ông nói: “Việc này. Thế này.” Rồi đi."
        self.assertEqual(split_viet(s), ["Có hơn 1.000 chiếc thuyền.", "Ông nói: “Việc này. Thế này.”", "Rồi đi."])

    def test_header(self):
        self.assertEqual(split_header("二年Năm Hiếu Kiến thứ 2"), ("二年", "Năm Hiếu Kiến thứ 2"))
        self.assertIsNone(split_header("Mùa xuân, tháng giêng."))


class TestAlign(unittest.TestCase):
    def test_header_and_sentences(self):
        han = "春，正月，己亥朔，大赦。\n\n臧質謀反。義宣從之。\n\n魏主還。"
        viet = ("Mùa xuân, tháng giêng, ngày Kỷ Hợi mồng 1, đại xá.\n二年Năm Hiếu Kiến thứ 2\n"
                "Tang Chất mưu phản. Nghĩa Tuyên theo ông ta.\nVua Ngụy trở về.")
        pairs, st = align_text(han, viet, READ)
        self.assertEqual(st["headers"], 1)
        got = [(p.han, p.viet, p.kind) for p in pairs]
        self.assertEqual(got, [
            ("春，正月，己亥朔，大赦。", "Mùa xuân, tháng giêng, ngày Kỷ Hợi mồng 1, đại xá.", "1:1"),
            ("二年", "Năm Hiếu Kiến thứ 2", "tieu_de"),
            ("臧質謀反。", "Tang Chất mưu phản.", "1:1"),
            ("義宣從之。", "Nghĩa Tuyên theo ông ta.", "1:1"),
            ("魏主還。", "Vua Ngụy trở về.", "1:1"),
        ])
        self.assertEqual([p.group for p in pairs], [1, 2, 3, 3, 4])


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from han_viet_alignment.minh_menh import tt_align as T  # noqa: E402


class TT(unittest.TestCase):
    def test_han_quote_whole(self):
        t = "帝曰：「卿來。朕喜。」魏主還。丙申，進；退！"
        self.assertEqual([t[a:b] for a, b in T.split_han(t)], ["帝曰：「卿來。朕喜。」", "魏主還。", "丙申，進；", "退！"])
        self.assertEqual("".join(t[a:b] for a, b in T.split_han(t)), t)

    def test_viet_quote_whole(self):
        t = "Vua nói: “Khanh đến. Trẫm vui.” Ngụy chủ về. Tháng 2, tiến quân!"
        self.assertEqual([t[a:b] for a, b in T.split_viet(t)],
                         ["Vua nói: “Khanh đến. Trẫm vui.”", "Ngụy chủ về.", "Tháng 2, tiến quân!"])

    def test_equal_counts_one_to_one(self):
        class S:  # scorer never called when counts are equal
            pass
        self.assertEqual(T.align_sentences(["a", "b"], [["x"], ["y"]], S(), 1.0), [(0, 1, 0, 1), (1, 2, 1, 2)])


if __name__ == "__main__":
    unittest.main()

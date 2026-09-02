"""哈夫曼编码的正确性测试。

运行方式：python -m pytest tem/test_huffman.py -v
或：       python tem/test_huffman.py
"""

import random
import string
import unittest

from huffman import HuffmanCoding


class TestHuffmanCoding(unittest.TestCase):
    """针对不同输入的往返（round-trip）正确性测试。"""

    def _roundtrip(self, text: str) -> None:
        """压缩 -> 解压 必须还原原文，且编码为前缀码。"""
        data = HuffmanCoding().compress(text)
        restored = HuffmanCoding.decompress(data)
        self.assertEqual(restored, text)

    def test_single_char(self):
        # 只有一种字符的特殊情况
        self._roundtrip("a")
        self._roundtrip("aaaaaa")

    def test_two_chars(self):
        self._roundtrip("ab")
        self._roundtrip("ababababab")

    def test_empty_should_raise(self):
        with self.assertRaises(ValueError):
            HuffmanCoding().build("")

    def test_basic_text(self):
        self._roundtrip("hello world")
        self._roundtrip("The quick brown fox jumps over the lazy dog")

    def test_chinese(self):
        self._roundtrip("你好，世界！这是一个哈夫曼编码测试。")

    def test_special_characters(self):
        self._roundtrip("!@#$%^&*()_+=-`~[]{};':\",./<>?\\|")

    def test_random_text(self):
        # 多轮随机文本往返测试
        rng = random.Random(42)
        alphabet = string.ascii_letters + string.digits + string.punctuation + " 你好"
        for _ in range(20):
            length = rng.randint(1, 500)
            text = "".join(rng.choice(alphabet) for _ in range(length))
            self._roundtrip(text)

    def test_newline_and_tabs(self):
        self._roundtrip("line1\nline2\tline3\r\nend")

    def test_compress_smaller_than_original(self):
        # 重复内容应能显著压缩
        text = "ab" * 1000
        data = HuffmanCoding().compress(text)
        self.assertLess(len(data), len(text.encode("utf-8")))

    def test_codes_are_prefix_free(self):
        """所有编码应满足前缀码性质（哈夫曼编码的充分条件）。"""
        h = HuffmanCoding().build("aababcabcd")
        codes = h.codes()
        keys = sorted(codes.values(), key=len)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                self.assertFalse(keys[j].startswith(keys[i]))

    def test_frequency_weighted_length(self):
        """更频繁的字符编码长度不应超过低频字符。"""
        # 'a' 出现 100 次，'b' 1 次
        h = HuffmanCoding().build("a" * 100 + "b")
        codes = h.codes()
        self.assertLessEqual(len(codes["a"]), len(codes["b"]))

    def test_decode_invalid_bitstring(self):
        h = HuffmanCoding().build("hello")
        # 不完整、停留在内部节点的编码串应报错
        # 注意：'0' 恰好是 'l' 的完整编码，因此 "000..." 是合法输入，不应报错。
        with self.assertRaises(ValueError):
            h.decode("1")   # 停留在内部节点
        with self.assertRaises(ValueError):
            h.decode("11")  # 停留在内部节点
        with self.assertRaises(ValueError):
            h.decode("1101")  # "110"=h 后 "1" 停留在内部节点


if __name__ == "__main__":
    unittest.main(verbosity=2)

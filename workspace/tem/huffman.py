"""哈夫曼编码（Huffman Coding）实现。

包含：
- 哈夫曼树的构建
- 根据哈夫曼树生成字符编码表
- 文本的编码（压缩）与解码（解压）
- 基于 pickle 序列化的编解码（便于持久化保存压缩结果）
"""

from __future__ import annotations

import pickle
from collections import Counter, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class Node:
    """哈夫曼树节点。"""

    char: Optional[str] = None   # 叶子节点保存字符，内部节点为 None
    freq: int = 0                # 出现频率
    left: Optional["Node"] = None
    right: Optional["Node"] = None

    def __lt__(self, other: "Node") -> bool:
        # 用于堆排序：频率低者优先；频率相同时保证排序稳定
        return self.freq < other.freq


class HuffmanCoding:
    """哈夫曼编解码器。"""

    def __init__(self) -> None:
        self._root: Optional[Node] = None
        self._codes: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # 构建哈夫曼树
    # ------------------------------------------------------------------
    def build(self, text: str) -> "HuffmanCoding":
        """根据输入文本统计频率并构建哈夫曼树、生成编码表。"""
        if not text:
            raise ValueError("输入文本为空，无法构建哈夫曼树。")

        freq = Counter(text)

        # 使用优先队列（最小堆）构建哈夫曼树
        heap = _MinHeap()
        for ch, f in freq.items():
            heap.push(Node(char=ch, freq=f))

        while heap.size() > 1:
            left = heap.pop()
            right = heap.pop()
            parent = Node(freq=left.freq + right.freq, left=left, right=right)
            heap.push(parent)

        self._root = heap.pop()
        self._codes = {}
        self._build_codes(self._root, "")
        return self

    def _build_codes(self, node: Optional[Node], prefix: str) -> None:
        """递归生成编码表：左子树补 '0'，右子树补 '1'。"""
        if node is None:
            return
        if node.char is not None:
            # 单字符文本时编码为空串，此处做特殊处理
            self._codes[node.char] = prefix if prefix else "0"
            return
        self._build_codes(node.left, prefix + "0")
        self._build_codes(node.right, prefix + "1")

    # ------------------------------------------------------------------
    # 编码 / 解码
    # ------------------------------------------------------------------
    def encode(self, text: str) -> str:
        """将文本编码为 0/1 字符串。"""
        if not self._codes:
            raise RuntimeError("请先调用 build() 构建哈夫曼树。")
        return "".join(self._codes[ch] for ch in text)

    def decode(self, bit_string: str) -> str:
        """将 0/1 字符串解码为原始文本。"""
        if self._root is None:
            raise RuntimeError("请先调用 build() 构建哈夫曼树。")

        if self._root.char is not None:
            # 只有一种字符的特殊情况
            return self._root.char * len(bit_string)

        result: List[str] = []
        node = self._root
        for bit in bit_string:
            node = node.left if bit == "0" else node.right
            if node is None:
                raise ValueError("编码串包含非法路径，解码失败。")
            if node.char is not None:
                result.append(node.char)
                node = self._root
        if node is not self._root:
            raise ValueError("编码串不完整，解码失败。")
        return "".join(result)

    # ------------------------------------------------------------------
    # 压缩 / 解压（字节流，便于写文件）
    # ------------------------------------------------------------------
    def compress(self, text: str) -> bytes:
        """把文本压缩为字节流。返回的字节流可通过 decompress 还原。"""
        self.build(text)
        bit_string = self.encode(text)
        # 末尾补齐位，记录原始 bit 长度，便于还原
        padding = (8 - len(bit_string) % 8) % 8
        padded = bit_string + "0" * padding

        payload = bytearray()
        for i in range(0, len(padded), 8):
            payload.append(int(padded[i : i + 8], 2))

        return pickle.dumps(
            {
                "codes": self._codes,
                "padding": padding,
                "payload": bytes(payload),
            }
        )

    @staticmethod
    def decompress(data: bytes) -> str:
        """从 compress 产生的字节流还原原始文本。"""
        obj = pickle.loads(data)
        codes: Dict[str, str] = obj["codes"]
        padding: int = obj["padding"]
        payload: bytes = obj["payload"]

        # 重建哈夫曼树
        coding = HuffmanCoding()
        coding._root = _rebuild_tree(codes)
        coding._codes = codes

        bit_string = "".join(f"{b:08b}" for b in payload)
        if padding:
            bit_string = bit_string[:-padding]
        return coding.decode(bit_string)

    # ------------------------------------------------------------------
    # 统计信息（辅助/测试用）
    # ------------------------------------------------------------------
    def codes(self) -> Dict[str, str]:
        """返回字符到编码的映射表副本。"""
        return dict(self._codes)


class _MinHeap:
    """基于列表的最小堆，避免外部依赖 heapq 的用法混淆。"""

    def __init__(self) -> None:
        self._data: List[Node] = []

    def push(self, node: Node) -> None:
        self._data.append(node)
        self._sift_up(len(self._data) - 1)

    def pop(self) -> Node:
        if not self._data:
            raise IndexError("pop from empty heap")
        top = self._data[0]
        last = self._data.pop()
        if self._data:
            self._data[0] = last
            self._sift_down(0)
        return top

    def size(self) -> int:
        return len(self._data)

    def _sift_up(self, idx: int) -> None:
        data = self._data
        while idx > 0:
            parent = (idx - 1) // 2
            if data[idx].freq < data[parent].freq:
                data[idx], data[parent] = data[parent], data[idx]
                idx = parent
            else:
                break

    def _sift_down(self, idx: int) -> None:
        data = self._data
        n = len(data)
        while True:
            left, right = 2 * idx + 1, 2 * idx + 2
            smallest = idx
            if left < n and data[left].freq < data[smallest].freq:
                smallest = left
            if right < n and data[right].freq < data[smallest].freq:
                smallest = right
            if smallest != idx:
                data[idx], data[smallest] = data[smallest], data[idx]
                idx = smallest
            else:
                break


def _rebuild_tree(codes: Dict[str, str]) -> Node:
    """根据编码表重建哈夫曼树（供 decompress 使用）。"""
    root = Node(freq=0)
    for ch, code in codes.items():
        node = root
        for bit in code:
            if bit == "0":
                if node.left is None:
                    node.left = Node(freq=0)
                node = node.left
            else:
                if node.right is None:
                    node.right = Node(freq=0)
                node = node.right
        node.char = ch
    return root


# ----------------------------------------------------------------------
# 命令行入口：python huffman.py <input_file> <output_file>  压缩
#            python huffman.py -d <input_file> <output_file> 解压
# ----------------------------------------------------------------------
def _main(argv: List[str]) -> int:
    if len(argv) < 3:
        print("用法:")
        print("  压缩: python huffman.py <输入文件> <输出文件>")
        print("  解压: python huffman.py -d <输入文件> <输出文件>")
        return 1

    if argv[0] == "-d":
        with open(argv[1], "rb") as f:
            text = HuffmanCoding.decompress(f.read())
        with open(argv[2], "w", encoding="utf-8") as f:
            f.write(text)
        print(f"解压完成: {argv[1]} -> {argv[2]}")
    else:
        with open(argv[0], "r", encoding="utf-8") as f:
            text = f.read()
        data = HuffmanCoding().compress(text)
        with open(argv[1], "wb") as f:
            f.write(data)
        orig = len(text.encode("utf-8"))
        print(f"压缩完成: {argv[0]} -> {argv[1]} ({orig} bytes -> {len(data)} bytes)")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv[1:]))

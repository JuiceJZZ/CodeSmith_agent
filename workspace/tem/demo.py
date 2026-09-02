"""端到端演示：压缩 -> 解压 -> 校验原文一致，并展示编码表。"""

from huffman import HuffmanCoding

text = "hello world" * 100

# 1. 构建 + 编码
h = HuffmanCoding().build("aababcabcd")
print("编码表:", dict(sorted(h.codes().items())))

# 2. 压缩 / 解压往返
data = HuffmanCoding().compress(text)
restored = HuffmanCoding.decompress(data)

assert restored == text, "往返还原失败！"
print("往返一致 OK")
print(f"原文本: {len(text.encode('utf-8'))} bytes -> 压缩后: {len(data)} bytes")

"""只读本地工具的单元测试。"""

import tempfile
import unittest
from pathlib import Path

from codesmith.tools import MAX_FILE_SIZE, ToolError, list_files, read_file


class ReadOnlyToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        (self.workspace / "src").mkdir()
        (self.workspace / "src" / "app.py").write_text(
            "print('hello')\n", encoding="utf-8"
        )
        (self.workspace / "说明.txt").write_text("你好，CodeSmith！", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_list_files_returns_sorted_workspace_relative_paths(self) -> None:
        self.assertEqual(list_files(self.workspace), ["src/", "说明.txt"])
        self.assertEqual(list_files(self.workspace, "src"), ["src/app.py"])

    def test_read_file_returns_utf8_text(self) -> None:
        self.assertEqual(read_file(self.workspace, "说明.txt"), "你好，CodeSmith！")

    def test_parent_path_escape_is_rejected(self) -> None:
        with self.assertRaisesRegex(ToolError, "超出 workspace"):
            read_file(self.workspace, "../outside.txt")

    def test_absolute_path_is_rejected(self) -> None:
        with self.assertRaisesRegex(ToolError, "相对于 workspace"):
            read_file(self.workspace, str((self.workspace / "说明.txt").resolve()))

    def test_missing_file_has_clear_error(self) -> None:
        with self.assertRaisesRegex(ToolError, "文件不存在"):
            read_file(self.workspace, "missing.txt")

    def test_reading_directory_as_file_is_rejected(self) -> None:
        with self.assertRaisesRegex(ToolError, "目标不是文件"):
            read_file(self.workspace, "src")

    def test_non_utf8_file_is_rejected(self) -> None:
        (self.workspace / "binary.bin").write_bytes(b"\xff\xfe\x00")
        with self.assertRaisesRegex(ToolError, "UTF-8"):
            read_file(self.workspace, "binary.bin")

    def test_large_file_is_rejected(self) -> None:
        (self.workspace / "large.txt").write_bytes(b"a" * (MAX_FILE_SIZE + 1))
        with self.assertRaisesRegex(ToolError, "超过"):
            read_file(self.workspace, "large.txt")


if __name__ == "__main__":
    unittest.main()

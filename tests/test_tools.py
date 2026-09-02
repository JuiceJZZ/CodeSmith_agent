"""本地文件工具的单元测试。"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codesmith.tools import (
    MAX_FILE_SIZE,
    MAX_COMMAND_OUTPUT,
    ToolError,
    edit_file,
    execute_tool,
    list_files,
    read_file,
    run_command,
    write_file,
)


class FileToolsTest(unittest.TestCase):
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

    def test_execute_list_files_returns_json_text(self) -> None:
        result = execute_tool("list_files", {}, self.workspace)
        self.assertEqual(json.loads(result), ["src/", "说明.txt"])

    def test_execute_tool_rejects_unknown_tool(self) -> None:
        with self.assertRaisesRegex(ToolError, "未知工具"):
            execute_tool("delete_file", {"path": "说明.txt"}, self.workspace)

    def test_execute_tool_rejects_unknown_argument(self) -> None:
        with self.assertRaisesRegex(ToolError, "未知工具参数"):
            execute_tool("read_file", {"path": "说明.txt", "extra": True}, self.workspace)

    def test_write_file_creates_parent_directories(self) -> None:
        result = write_file(self.workspace, "new/package/app.py", "print('ok')\n")
        self.assertIn("已写入", result)
        self.assertEqual(
            (self.workspace / "new" / "package" / "app.py").read_text(
                encoding="utf-8"
            ),
            "print('ok')\n",
        )

    def test_write_file_can_overwrite_existing_file(self) -> None:
        write_file(self.workspace, "说明.txt", "新内容")
        self.assertEqual(read_file(self.workspace, "说明.txt"), "新内容")

    def test_write_file_rejects_workspace_escape(self) -> None:
        with self.assertRaisesRegex(ToolError, "超出 workspace"):
            write_file(self.workspace, "../outside.txt", "blocked")

    def test_write_file_rejects_large_content(self) -> None:
        with self.assertRaisesRegex(ToolError, "超过"):
            write_file(self.workspace, "large.txt", "a" * (MAX_FILE_SIZE + 1))

    def test_edit_file_replaces_one_exact_match(self) -> None:
        result = edit_file(self.workspace, "说明.txt", "CodeSmith", "Agent")
        self.assertIn("替换 1 处", result)
        self.assertEqual(read_file(self.workspace, "说明.txt"), "你好，Agent！")

    def test_edit_file_rejects_ambiguous_match(self) -> None:
        write_file(self.workspace, "repeat.txt", "same same")
        with self.assertRaisesRegex(ToolError, "出现 2 次"):
            edit_file(self.workspace, "repeat.txt", "same", "new")
        self.assertEqual(read_file(self.workspace, "repeat.txt"), "same same")

    def test_edit_file_can_replace_all_matches(self) -> None:
        write_file(self.workspace, "repeat.txt", "same same")
        edit_file(self.workspace, "repeat.txt", "same", "new", replace_all=True)
        self.assertEqual(read_file(self.workspace, "repeat.txt"), "new new")

    def test_edit_file_rejects_missing_text(self) -> None:
        with self.assertRaisesRegex(ToolError, "没有找到"):
            edit_file(self.workspace, "说明.txt", "missing", "new")

    def test_execute_write_file_validates_content_type(self) -> None:
        with self.assertRaisesRegex(ToolError, "content 参数必须是字符串"):
            execute_tool(
                "write_file", {"path": "new.txt", "content": 123}, self.workspace
            )

    def test_run_python_script_returns_structured_result(self) -> None:
        write_file(self.workspace, "hello.py", "print('hello from command')\n")
        result = json.loads(run_command(self.workspace, ["python", "hello.py"]))
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"], "hello from command\n")
        self.assertFalse(result["timed_out"])

    def test_run_command_returns_nonzero_exit_code(self) -> None:
        write_file(self.workspace, "fail.py", "raise SystemExit(3)\n")
        result = json.loads(run_command(self.workspace, ["python", "fail.py"]))
        self.assertEqual(result["exit_code"], 3)

    def test_run_command_rejects_unknown_executable(self) -> None:
        with self.assertRaisesRegex(ToolError, "只允许执行"):
            run_command(self.workspace, ["powershell", "Get-ChildItem"])

    def test_run_command_rejects_python_code_flag(self) -> None:
        with self.assertRaisesRegex(ToolError, "python -c"):
            run_command(self.workspace, ["python", "-c", "print('unsafe')"])

    def test_run_command_rejects_parent_path(self) -> None:
        with self.assertRaisesRegex(ToolError, "超出 workspace"):
            run_command(self.workspace, ["python", "../outside.py"])

    def test_run_command_times_out(self) -> None:
        write_file(self.workspace, "slow.py", "import time\ntime.sleep(2)\n")
        result = json.loads(
            run_command(self.workspace, ["python", "slow.py"], timeout=1)
        )
        self.assertTrue(result["timed_out"])
        self.assertIsNone(result["exit_code"])

    def test_run_command_truncates_long_output(self) -> None:
        write_file(
            self.workspace,
            "verbose.py",
            f"print('x' * {MAX_COMMAND_OUTPUT + 100})\n",
        )
        result = json.loads(run_command(self.workspace, ["python", "verbose.py"]))
        self.assertIn("已截断", result["stdout"])

    def test_run_command_hides_api_key_from_child(self) -> None:
        write_file(
            self.workspace,
            "environment.py",
            "import os\nprint(os.getenv('DEEPSEEK_API_KEY', 'missing'))\n",
        )
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "should-not-leak"}):
            result = json.loads(
                run_command(self.workspace, ["python", "environment.py"])
            )
        self.assertEqual(result["stdout"], "missing\n")

    def test_run_command_preserves_chinese_output(self) -> None:
        write_file(self.workspace, "chinese.py", "print('中文输出正常')\n")
        result = json.loads(run_command(self.workspace, ["python", "chinese.py"]))
        self.assertEqual(result["stdout"], "中文输出正常\n")


if __name__ == "__main__":
    unittest.main()

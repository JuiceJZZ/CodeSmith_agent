"""命令行入口测试，不发送真实 API 请求。"""

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import main as cli
from codesmith.agent import ToolExecution


class CommandLineTest(unittest.TestCase):
    def test_output_streams_are_configured_as_utf8(self) -> None:
        stdout = MagicMock()
        stderr = MagicMock()
        with (
            patch.object(cli.sys, "stdout", stdout),
            patch.object(cli.sys, "stderr", stderr),
        ):
            cli.configure_output_encoding()
        stdout.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")
        stderr.reconfigure.assert_called_once_with(encoding="utf-8", errors="replace")

    def test_positional_task_runs_agent(self) -> None:
        with patch.object(cli, "run_agent_mode", return_value=0) as run_agent_mode:
            with patch("sys.argv", ["main.py", "检查测试"]):
                exit_code = cli.main()
        self.assertEqual(exit_code, 0)
        run_agent_mode.assert_called_once_with("检查测试")

    def test_no_arguments_prompts_for_task(self) -> None:
        with (
            patch.object(cli, "run_agent_mode", return_value=0) as run_agent_mode,
            patch("builtins.input", return_value="修复失败测试"),
            patch("sys.argv", ["main.py"]),
        ):
            exit_code = cli.main()
        self.assertEqual(exit_code, 0)
        run_agent_mode.assert_called_once_with("修复失败测试")

    def test_check_mode_only_calls_text_api(self) -> None:
        with (
            patch.object(cli, "load_settings", return_value=object()),
            patch.object(cli, "chat", return_value="connected") as chat,
            patch("sys.argv", ["main.py", "--check"]),
        ):
            exit_code = cli.main()
        self.assertEqual(exit_code, 0)
        chat.assert_called_once()

    def test_conflicting_task_and_mode_is_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            cli.parse_args(["任务", "--check"])

    def test_write_arguments_are_summarized(self) -> None:
        execution = ToolExecution(
            1,
            "write_file",
            {"path": "large.py", "content": "x" * 500},
            "已写入 large.py。",
        )
        displayed = cli.format_arguments_for_display(execution)
        self.assertIn("共 500 字符", displayed["content"])
        self.assertLess(len(displayed["content"]), 300)

    def test_read_observation_is_shortened_for_terminal(self) -> None:
        execution = ToolExecution(1, "read_file", {"path": "large.py"}, "x" * 5_000)
        displayed = cli.format_observation_for_display(execution)
        self.assertIn("终端预览已省略", displayed)
        self.assertLess(len(displayed), 1_100)

    def test_command_display_keeps_exit_code_and_output_tail(self) -> None:
        observation = json.dumps(
            {"exit_code": 1, "timed_out": False, "stdout": "", "stderr": "x" * 3_000}
        )
        execution = ToolExecution(1, "run_command", {"command": ["python", "x.py"]}, observation)
        displayed = cli.format_observation_for_display(execution)
        self.assertIn("exit_code=1", displayed)
        self.assertIn("stderr（末尾）", displayed)
        self.assertLess(len(displayed), 1_700)

    def test_model_progress_is_visible(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            cli.print_model_step(3, 15)
        self.assertIn("模型轮次 3/15", output.getvalue())


if __name__ == "__main__":
    unittest.main()

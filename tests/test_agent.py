"""最小 Agent Loop 测试，使用模拟模型回复。"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codesmith.agent import (
    MAX_OBSERVATION_CHARS,
    MAX_REPEATED_TOOL_FAILURES,
    AgentError,
    run_agent,
)
from codesmith.config import Settings
from codesmith.llm import ModelReply, ToolCall


class AgentLoopTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)
        (self.workspace / "hello.txt").write_text("hello", encoding="utf-8")
        self.settings = Settings(
            deepseek_api_key="test-key",
            deepseek_base_url="https://example.com",
            deepseek_model="test-model",
            workspace_path=self.workspace,
            max_steps=3,
            command_timeout=60,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_tool_observation_is_returned_to_model(self) -> None:
        replies = [
            ModelReply(None, (ToolCall("call_1", "read_file", {"path": "hello.txt"}),)),
            ModelReply("文件内容是 hello。", ()),
        ]
        message_snapshots: list[list[dict[str, object]]] = []

        def fake_complete(messages, settings):
            message_snapshots.append([dict(message) for message in messages])
            return replies.pop(0)

        with patch("codesmith.agent.complete_with_tools", side_effect=fake_complete):
            result = run_agent("读取 hello.txt", self.settings)

        self.assertEqual(result.final_answer, "文件内容是 hello。")
        self.assertEqual(result.model_calls, 2)
        self.assertEqual(len(result.tool_executions), 1)
        second_call_messages = message_snapshots[1]
        self.assertEqual([message["role"] for message in second_call_messages], [
            "system", "user", "assistant", "tool"
        ])
        self.assertEqual(second_call_messages[-1]["content"], "hello")
        self.assertEqual(second_call_messages[-1]["tool_call_id"], "call_1")

    def test_tool_error_becomes_observation(self) -> None:
        replies = [
            ModelReply(None, (ToolCall("call_1", "unknown_tool", {}),)),
            ModelReply("工具不可用，任务结束。", ()),
        ]
        observations: list[str] = []

        def fake_complete(messages, settings):
            if messages[-1]["role"] == "tool":
                observations.append(str(messages[-1]["content"]))
            return replies.pop(0)

        with patch("codesmith.agent.complete_with_tools", side_effect=fake_complete):
            result = run_agent("调用未知工具", self.settings)

        self.assertIn("工具执行失败", observations[0])
        self.assertEqual(result.model_calls, 2)

    def test_max_steps_stops_infinite_tool_calls(self) -> None:
        limited_settings = Settings(
            **{**self.settings.__dict__, "max_steps": 2}
        )
        reply = ModelReply(None, (ToolCall("call_1", "list_files", {}),))
        with patch("codesmith.agent.complete_with_tools", return_value=reply):
            with self.assertRaisesRegex(AgentError, "MAX_STEPS=2"):
                run_agent("不断列出文件", limited_settings)

    def test_empty_task_is_rejected(self) -> None:
        with self.assertRaisesRegex(AgentError, "不能为空"):
            run_agent("   ", self.settings)

    def test_multiple_tool_calls_are_executed_in_order(self) -> None:
        replies = [
            ModelReply(
                None,
                (
                    ToolCall("call_1", "write_file", {"path": "a.txt", "content": "A"}),
                    ToolCall("call_2", "write_file", {"path": "b.txt", "content": "B"}),
                ),
            ),
            ModelReply("两个文件已创建。", ()),
        ]
        with patch("codesmith.agent.complete_with_tools", side_effect=replies):
            result = run_agent("创建两个文件", self.settings)

        self.assertEqual([item.name for item in result.tool_executions], [
            "write_file", "write_file"
        ])
        self.assertEqual((self.workspace / "a.txt").read_text(encoding="utf-8"), "A")
        self.assertEqual((self.workspace / "b.txt").read_text(encoding="utf-8"), "B")

    def test_long_observation_is_truncated_before_model_call(self) -> None:
        replies = [
            ModelReply(None, (ToolCall("call_1", "read_file", {"path": "big.txt"}),)),
            ModelReply("已收到截断结果。", ()),
        ]
        snapshots: list[list[dict[str, object]]] = []

        def fake_complete(messages, settings):
            snapshots.append([dict(message) for message in messages])
            return replies.pop(0)

        with (
            patch("codesmith.agent.complete_with_tools", side_effect=fake_complete),
            patch("codesmith.agent.execute_tool", return_value="x" * 50_000),
        ):
            run_agent("读取大文件", self.settings)

        observation = str(snapshots[1][-1]["content"])
        self.assertLessEqual(len(observation), MAX_OBSERVATION_CHARS)
        self.assertIn("observation 已截断", observation)

    def test_tool_execution_callback_receives_trace(self) -> None:
        replies = [
            ModelReply(None, (ToolCall("call_1", "list_files", {}),)),
            ModelReply("完成。", ()),
        ]
        received = []
        with patch("codesmith.agent.complete_with_tools", side_effect=replies):
            run_agent("列出文件", self.settings, on_tool_execution=received.append)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].name, "list_files")

    def test_model_step_callback_receives_progress(self) -> None:
        replies = [ModelReply("完成。", ())]
        progress = []
        with patch("codesmith.agent.complete_with_tools", side_effect=replies):
            run_agent("回答任务", self.settings, on_model_step=lambda step, limit: progress.append((step, limit)))
        self.assertEqual(progress, [(1, self.settings.max_steps)])

    def test_repeated_identical_tool_failure_stops_early(self) -> None:
        failing_reply = ModelReply(
            None, (ToolCall("call_1", "run_command", {"command": "bad"}),)
        )
        with patch(
            "codesmith.agent.complete_with_tools", return_value=failing_reply
        ) as complete:
            with self.assertRaisesRegex(AgentError, "连续 3 次"):
                run_agent("运行命令", self.settings)
        self.assertEqual(complete.call_count, MAX_REPEATED_TOOL_FAILURES)


if __name__ == "__main__":
    unittest.main()

"""模型 Tool Calling 响应解析测试，不发送真实 API 请求。"""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from codesmith.config import Settings
from codesmith.llm import chat_with_tools
from codesmith.tools import TOOL_DEFINITIONS


def _response(content: str | None = None, tool_calls: list[object] | None = None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _tool_call(arguments: str, name: str = "read_file", call_id: str = "call_1"):
    function = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(id=call_id, function=function)


class ToolCallingParsingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            deepseek_api_key="test-key",
            deepseek_base_url="https://example.com",
            deepseek_model="test-model",
            workspace_path=Path("workspace"),
            max_steps=10,
            command_timeout=60,
        )

    def _mock_client(self, response: object) -> MagicMock:
        client = MagicMock()
        client.chat.completions.create.return_value = response
        return client

    def test_parses_single_tool_call(self) -> None:
        client = self._mock_client(_response(tool_calls=[_tool_call('{"path":"a.py"}')]))
        with patch("codesmith.llm.create_client", return_value=client):
            reply = chat_with_tools("读取 a.py", self.settings)

        self.assertIsNone(reply.content)
        self.assertEqual(reply.tool_call.name, "read_file")
        self.assertEqual(reply.tool_call.arguments, {"path": "a.py"})
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["tools"], TOOL_DEFINITIONS)
        self.assertEqual(request["tool_choice"], "auto")

    def test_accepts_plain_text_reply(self) -> None:
        client = self._mock_client(_response(content="不需要查看文件。", tool_calls=[]))
        with patch("codesmith.llm.create_client", return_value=client):
            reply = chat_with_tools("你好", self.settings)

        self.assertEqual(reply.content, "不需要查看文件。")
        self.assertIsNone(reply.tool_call)

    def test_rejects_invalid_tool_arguments_json(self) -> None:
        client = self._mock_client(_response(tool_calls=[_tool_call("not-json")]))
        with patch("codesmith.llm.create_client", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "有效 JSON"):
                chat_with_tools("读取文件", self.settings)

    def test_rejects_non_object_arguments(self) -> None:
        client = self._mock_client(_response(tool_calls=[_tool_call("[]")]))
        with patch("codesmith.llm.create_client", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "JSON 对象"):
                chat_with_tools("读取文件", self.settings)

    def test_rejects_multiple_tool_calls(self) -> None:
        calls = [_tool_call("{}", "list_files", "call_1"), _tool_call("{}")]
        client = self._mock_client(_response(tool_calls=calls))
        with patch("codesmith.llm.create_client", return_value=client):
            with self.assertRaisesRegex(RuntimeError, "只支持一个"):
                chat_with_tools("查看项目", self.settings)


if __name__ == "__main__":
    unittest.main()

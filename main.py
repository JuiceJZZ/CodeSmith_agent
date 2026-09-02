"""CodeSmith 当前阶段的命令行入口。"""

import argparse
import json
import sys

from codesmith.agent import AgentError, ToolExecution, run_agent
from codesmith.config import ConfigError, load_settings
from codesmith.llm import chat, chat_with_tools
from codesmith.tools import ToolError, execute_tool


MAX_ARGUMENT_PREVIEW = 200
MAX_FILE_PREVIEW = 500
MAX_COMMAND_STREAM_PREVIEW = 1_000


def configure_output_encoding() -> None:
    """统一 Python 与现代终端的输出编码，避免 Windows GBK/UTF-8 混用。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CodeSmith 本地 Coding Agent")
    parser.add_argument("task", nargs="?", help="要交给 Agent 的自然语言编程任务。")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--tool-demo",
        metavar="TASK",
        help="执行一轮模型决策及其返回的工具调用，然后结束。",
    )
    mode.add_argument(
        "--agent",
        metavar="TASK",
        help="兼容旧用法：运行指定任务的 Agent Loop。",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="只测试 DeepSeek API 连接。",
    )
    args = parser.parse_args(argv)
    if args.task and (args.tool_demo or args.agent or args.check):
        parser.error("位置参数 task 不能和 --tool-demo、--agent 或 --check 同时使用。")
    return args


def run_tool_demo(task: str) -> int:
    """完成一次模型 Tool Calling 演示，不进入自动循环。"""
    settings = load_settings()
    reply = chat_with_tools(task, settings)

    if not reply.tool_calls:
        print("模型没有调用工具，直接回复：")
        print(reply.content)
        return 0

    for tool_call in reply.tool_calls:
        print(f"模型选择工具：{tool_call.name}")
        print(f"工具参数：{tool_call.arguments}")
        result = execute_tool(
            tool_call.name,
            tool_call.arguments,
            settings.workspace_path,
            settings.command_timeout,
        )
        print("工具结果：")
        print(result)
    print("\n单轮演示结束：工具结果尚未回传给模型。")
    return 0


def run_agent_mode(task: str) -> int:
    """运行 Agent Loop 并展示工具轨迹与最终答案。"""
    settings = load_settings()
    result = run_agent(
        task,
        settings,
        on_tool_execution=print_tool_execution,
        on_model_step=print_model_step,
    )

    print(f"\nAgent 完成，共调用模型 {result.model_calls} 次。")
    print("最终回答：")
    print(result.final_answer)
    return 0


def print_tool_execution(execution: ToolExecution) -> None:
    """在工具完成后立即显示轨迹，便于用户观察 Agent 运行过程。"""
    print(f"\n[步骤 {execution.step}] 工具：{execution.name}")
    print(f"参数：{format_arguments_for_display(execution)}")
    print(f"Observation：{format_observation_for_display(execution)}")


def print_model_step(step: int, max_steps: int) -> None:
    """显示当前模型轮次，让用户知道 Agent 是否接近上限。"""
    print(f"\n[模型轮次 {step}/{max_steps}] 正在决策...")


def format_arguments_for_display(execution: ToolExecution) -> dict[str, object]:
    """隐藏大段写入文本，只展示足以理解操作的参数摘要。"""
    arguments = dict(execution.arguments)
    for name in ("content", "old_text", "new_text"):
        value = arguments.get(name)
        if isinstance(value, str) and len(value) > MAX_ARGUMENT_PREVIEW:
            arguments[name] = f"<共 {len(value)} 字符：{value[:MAX_ARGUMENT_PREVIEW]}...>"
    return arguments


def format_observation_for_display(execution: ToolExecution) -> str:
    """根据工具类型生成简短终端预览，不改变回传模型的内容。"""
    observation = execution.observation
    if execution.name == "read_file":
        return _head_preview(observation, MAX_FILE_PREVIEW)

    if execution.name == "run_command":
        try:
            result = json.loads(observation)
        except json.JSONDecodeError:
            return _head_preview(observation, MAX_FILE_PREVIEW)
        if not isinstance(result, dict):
            return _head_preview(observation, MAX_FILE_PREVIEW)

        parts = [
            f"exit_code={result.get('exit_code')}, timed_out={result.get('timed_out')}"
        ]
        stdout = result.get("stdout")
        stderr = result.get("stderr")
        if isinstance(stdout, str) and stdout:
            parts.append("stdout（末尾）：\n" + _tail_preview(stdout))
        if isinstance(stderr, str) and stderr:
            parts.append("stderr（末尾）：\n" + _tail_preview(stderr))
        message = result.get("message")
        if isinstance(message, str) and message:
            parts.append(message)
        return "\n".join(parts)

    return _head_preview(observation, MAX_FILE_PREVIEW)


def _head_preview(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n... 终端预览已省略 {len(text) - limit} 个字符 ..."


def _tail_preview(text: str) -> str:
    if len(text) <= MAX_COMMAND_STREAM_PREVIEW:
        return text
    omitted = len(text) - MAX_COMMAND_STREAM_PREVIEW
    return f"... 已省略前面 {omitted} 个字符 ...\n{text[-MAX_COMMAND_STREAM_PREVIEW:]}"


def run_connection_test() -> int:
    """执行一次最小 DeepSeek 文本连接测试。"""
    print("DeepSeek connection test...")
    settings = load_settings()
    reply = chat("请只回复：CodeSmith API connected.", settings)
    print("\n模型返回：")
    print(reply)
    return 0


def main() -> int:
    """运行自然语言任务、连接测试或单轮工具演示。"""
    configure_output_encoding()
    args = parse_args()
    print("CodeSmith")

    try:
        if args.check:
            return run_connection_test()

        if args.agent:
            print("Agent loop...")
            return run_agent_mode(args.agent)

        if args.tool_demo:
            print("Single tool-calling demo...")
            return run_tool_demo(args.tool_demo)

        task = args.task
        if task is None:
            task = input("请输入编程任务：").strip()
        print("Agent loop...")
        return run_agent_mode(task)
    except ConfigError as error:
        print(f"配置错误：{error}")
        return 1
    except ToolError as error:
        print(f"工具执行失败：{error}")
        return 1
    except AgentError as error:
        print(f"Agent 运行失败：{error}")
        return 1
    except Exception as error:
        # API、网络或其他意外错误统一转换为简洁的 CLI 提示。
        print(f"运行失败：{error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

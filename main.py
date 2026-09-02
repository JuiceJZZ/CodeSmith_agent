"""CodeSmith 当前阶段的命令行入口。"""

import argparse
import sys

from codesmith.config import ConfigError, load_settings
from codesmith.llm import chat, chat_with_tools
from codesmith.tools import ToolError, execute_tool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CodeSmith 本地 Coding Agent")
    parser.add_argument(
        "--tool-demo",
        metavar="TASK",
        help="让模型针对任务选择并执行一次只读工具，然后结束。",
    )
    return parser.parse_args()


def run_tool_demo(task: str) -> int:
    """完成一次模型 Tool Calling 演示，不进入自动循环。"""
    settings = load_settings()
    reply = chat_with_tools(task, settings)

    if reply.tool_call is None:
        print("模型没有调用工具，直接回复：")
        print(reply.content)
        return 0

    tool_call = reply.tool_call
    print(f"模型选择工具：{tool_call.name}")
    print(f"工具参数：{tool_call.arguments}")
    result = execute_tool(tool_call.name, tool_call.arguments, settings.workspace_path)
    print("工具结果：")
    print(result)
    print("\n单轮演示结束：工具结果尚未回传给模型。")
    return 0


def main() -> int:
    """运行连接测试，或执行一次 Tool Calling 演示。"""
    args = parse_args()
    print("CodeSmith")

    try:
        if args.tool_demo:
            print("Single tool-calling demo...")
            return run_tool_demo(args.tool_demo)

        print("DeepSeek connection test...")
        settings = load_settings()
        reply = chat("请只回复：CodeSmith API connected.", settings)
    except ConfigError as error:
        print(f"配置错误：{error}")
        return 1
    except ToolError as error:
        print(f"工具执行失败：{error}")
        return 1
    except Exception as error:
        # 当前阶段还没有完整错误分类，先保留明确的单次运行错误。
        print(f"运行失败：{error}")
        return 1

    print("\n模型返回：")
    print(reply)
    return 0


if __name__ == "__main__":
    sys.exit(main())

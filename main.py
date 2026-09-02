"""CodeSmith 当前阶段的命令行入口。"""

import sys

from codesmith.config import ConfigError, load_settings
from codesmith.llm import chat


def main() -> int:
    """读取配置并完成一次最小的 DeepSeek 文本调用。"""
    print("CodeSmith")
    print("DeepSeek connection test...")

    try:
        settings = load_settings()
        reply = chat("请只回复：CodeSmith API connected.", settings)
    except ConfigError as error:
        print(f"配置错误：{error}")
        return 1
    except Exception as error:
        # 当前阶段还没有完整错误系统，先给出易理解的连接失败信息。
        print(f"DeepSeek API 调用失败：{error}")
        return 1

    print("\n模型返回：")
    print(reply)
    return 0


if __name__ == "__main__":
    sys.exit(main())

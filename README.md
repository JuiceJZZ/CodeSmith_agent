# CodeSmith

CodeSmith 是一个从零实现的轻量级本地 Coding Agent。它计划通过大语言模型理解编程任务，并在本地工作区内读取文件、修改代码和运行命令。

项目不会使用 LangChain、LlamaIndex、OpenAI Agents SDK 等 Agent 框架。对话历史、工具执行、模型输出解析、Agent Loop 和终止条件等核心能力均由项目自行实现。

## 当前开发状态

目前已完成最小项目骨架、DeepSeek 文本调用、本地文件工具、Tool Calling 解析，以及受步骤限制的最小 Agent Loop。

```text
Python -> OpenAI Python SDK -> DeepSeek API -> 文本回复
```

Agent 已能维护消息历史、回传 observation，在 workspace 内读写文件，并运行受限的 Python 测试命令。


## 安装依赖

```bash
python -m pip install -r requirements.txt
```

## 配置环境变量

复制 `.env.example` 为 `.env`：

```bash
copy .env.example .env
```

然后打开 `.env`，将 `DEEPSEEK_API_KEY` 改为自己的 API Key。`.env` 已加入 `.gitignore`，不要将真实密钥提交到 Git、README 或演示视频中。

其余配置已有适合本阶段的默认值：

- `DEEPSEEK_BASE_URL`：DeepSeek OpenAI 兼容接口地址
- `DEEPSEEK_MODEL`：调用的模型名称
- `WORKSPACE_PATH`：未来 Agent 可以操作的本地目录
- `MAX_STEPS`：未来 Agent Loop 的最大步数
- `COMMAND_TIMEOUT`：本地命令的超时时间（秒）

## 运行

```bash
python main.py
```

程序会向 DeepSeek 发送一次固定的测试消息，并输出模型返回的文本。此调用会产生少量 API 费用。

也可以让模型选择并执行一次工具：

```bash
python main.py --tool-demo "请列出当前工作区的文件"
```

该模式只完成一轮模型调用并执行该轮返回的工具调用，不会把工具结果再次发送给模型。

运行 Agent Loop：

```bash
python main.py --agent "请检查 workspace 中的文件并总结内容"
```

Agent 会持续进行“模型决策、工具执行、结果回传”，直到模型给出最终回答或达到 `MAX_STEPS`。

## 当前目录职责

- `main.py`：最小 CLI 入口
- `codesmith/config.py`：读取和校验环境配置
- `codesmith/llm.py`：封装普通文本调用及单次 Tool Calling 响应解析
- `codesmith/prompts.py`：保存简单系统提示词
- `codesmith/agent.py`：维护消息历史、observation 回传和循环终止条件
- `codesmith/tools.py`：实现受 workspace 边界保护的文件工具和受限命令执行
- `workspace/`：未来 Agent 唯一允许操作目标代码的目录

## 运行测试

```bash
python -m unittest discover -s tests -v
```

测试覆盖 Agent Loop、文件读写、精确替换、命令退出码、超时、输出截断、敏感环境清理和 workspace 越界保护；测试不会调用真实 API。

`run_command` 当前只接受参数数组形式的 Python/pytest 命令，使用 `shell=False`，并拒绝绝对路径、父目录越界和 `python -c`。它是面向本地考核项目的安全护栏，不是操作系统级沙箱，不应运行来源不可信的项目。

## 后续计划

建议下一步完成一个端到端编程任务，补充必要的上下文与错误处理测试，并进行提交前安全检查。

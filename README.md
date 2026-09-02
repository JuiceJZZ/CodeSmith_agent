# CodeSmith

CodeSmith 是一个从零实现的轻量级本地 Coding Agent。它计划通过大语言模型理解编程任务，并在本地工作区内读取文件、修改代码和运行命令。

项目不会使用 LangChain、LlamaIndex、OpenAI Agents SDK 等 Agent 框架。对话历史、上下文管理、工具执行、模型输出解析和 Agent Loop 等核心能力将在后续阶段自行实现。

## 当前开发状态

目前已完成最小项目骨架、DeepSeek 文本调用、两个本地只读工具，以及一次模型 Tool Calling 的解析与执行。

```text
Python -> OpenAI Python SDK -> DeepSeek API -> 文本回复
```

单轮工具演示执行工具后立即停止，尚未实现 observation 回传、Agent Loop、文件修改或命令执行。


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
- `COMMAND_TIMEOUT`：未来本地命令的超时时间（秒）

## 运行

```bash
python main.py
```

程序会向 DeepSeek 发送一次固定的测试消息，并输出模型返回的文本。此调用会产生少量 API 费用。

也可以让模型选择并执行一次只读工具：

```bash
python main.py --tool-demo "请列出当前工作区的文件"
```

该模式只完成一次模型调用和一次工具执行，不会把工具结果再次发送给模型。

## 当前目录职责

- `main.py`：最小 CLI 入口
- `codesmith/config.py`：读取和校验环境配置
- `codesmith/llm.py`：封装普通文本调用及单次 Tool Calling 响应解析
- `codesmith/prompts.py`：保存简单系统提示词
- `codesmith/agent.py`：预留 Agent Loop 模块
- `codesmith/tools.py`：实现受 workspace 边界保护的 `list_files` 和 `read_file`
- `workspace/`：未来 Agent 唯一允许操作目标代码的目录

## 运行测试

```bash
python -m unittest discover -s tests -v
```

测试覆盖工具响应解析、参数 JSON 校验、目录列举、UTF-8 文件读取、绝对路径拒绝、父目录越界、缺失文件和非文本文件等情况；测试不会调用真实 API。

## 后续计划

建议下一步实现最小对话历史和 observation 回传，再加入受 `MAX_STEPS` 限制的 Agent Loop。

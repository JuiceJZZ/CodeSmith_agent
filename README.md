# CodeSmith

CodeSmith 是一个从零实现的轻量级本地 Coding Agent。它通过 DeepSeek 理解编程任务，并在本地工作区内读取文件、修改代码和运行测试。

项目不会使用 LangChain、LlamaIndex、OpenAI Agents SDK 等 Agent 框架。对话历史、工具执行、模型输出解析、Agent Loop 和终止条件等核心能力均由项目自行实现。

## 当前开发状态

目前已完成 DeepSeek Tool Calling、本地文件工具、受限命令执行、消息历史、上下文限制和受步骤限制的 Agent Loop。

```text
用户任务 → 模型决策 → 工具调用 → 本地执行 → observation 回传 → 模型再决策 → ... → 最终答案
```

Agent 已能维护消息历史、回传 observation，在 workspace 内读写文件，并运行受限的 Python 测试命令。

## 运行环境

- Python 3.11
- DeepSeek API（默认模型 `deepseek-v4-flash`）

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
- `WORKSPACE_PATH`：Agent 可以操作的本地目录
- `MAX_STEPS`：Agent Loop 的最大模型调用轮数，默认 25
- `COMMAND_TIMEOUT`：本地命令的超时时间（秒）



## 运行

```bash
python main.py
```

程序会提示输入自然语言编程任务。也可以直接把任务写在命令中：

```bash
python main.py "请检查失败的测试并修复"
```

单独测试 DeepSeek 连接：

```bash
python main.py --check
```

也可以让模型选择并执行一次工具：

```bash
python main.py --tool-demo "请列出当前工作区的文件"
```

该模式只完成一轮模型调用并执行该轮返回的工具调用，不会把工具结果再次发送给模型。

旧版 `--agent` 参数仍然可用：

```bash
python main.py --agent "请检查 workspace 中的文件并总结内容"
```

Agent 会持续进行“模型决策、工具执行、结果回传”，直到模型给出最终回答或达到 `MAX_STEPS`。终端会显示当前模型轮次，并对大段文件内容和命令输出进行预览截断；截断只影响展示，不影响模型收到的受控 observation。

## 当前目录职责

- `main.py`：自然语言 CLI 入口和实时工具轨迹展示
- `codesmith/config.py`：读取和校验环境配置
- `codesmith/llm.py`：封装模型调用及 Tool Calling 响应解析
- `codesmith/prompts.py`：保存系统提示词
- `codesmith/agent.py`：维护消息历史、observation 限制、结果回传和循环终止
- `codesmith/tools.py`：实现受 workspace 边界保护的文件工具、文件删除和受限命令执行
- `workspace/`：Agent 唯一允许操作目标代码的目录
- `tests/`：不访问真实模型的单元测试



## 运行测试

```bash
python -m unittest discover -s tests -v
```

测试覆盖 Agent Loop、CLI、上下文截断、文件读写、命令退出码、超时、输出截断、敏感环境清理和 workspace 越界保护；单元测试不会调用真实 API。

`run_command` 当前只接受参数数组形式的 Python/pytest 命令，使用 `shell=False`，并拒绝绝对路径、父目录越界和 `python -c`。它是面向本地考核项目的安全护栏，不是操作系统级沙箱，不应运行来源不可信的项目。

模型偶尔会把命令数组二次编码成 JSON 字符串，执行器会在校验后兼容解析。若同一工具连续三次产生完全相同的错误，Agent 会提前停止，避免持续消耗 API。删除文件应使用 `delete_file`，而不是生成临时清理脚本。

### Windows 终端乱码

CodeSmith 启动时会把 stdout 和 stderr 显式设置为 UTF-8，并要求 Python 测试子进程同样使用 UTF-8，解决 Windows 代码页 936 与现代终端 UTF-8 输出不一致造成的乱码。项目文件也始终使用 UTF-8 读写。如果仍有第三方程序输出乱码，可先在当前终端执行 `chcp 65001` 后重试。

## 当前限制

- 只支持 Python/pytest 命令，不支持任意 shell 命令。
- 单个文件最大 1 MB，单条 observation 最多 30,000 字符。
- 这是本地开发工具，不是操作系统级安全沙箱，不应处理来源不可信的项目。

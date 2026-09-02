CodeSmith——本地编程智能体

一、Git 仓库
https://github.com/JuiceJZZ/CodeSmith_agent.git

二、运行方法
环境：Python 3.11。

1. 创建环境、安装依赖：
conda create -n codesmith python=3.11
conda activate codesmith
python -m pip install -r requirements.txt

2. 复制 .env.example 为 .env，填写 DEEPSEEK_API_KEY。我使用的是 deepseek-v4-flash。

3. 将目标项目（你想要和智能体交互的项目）放入 workspace，运行：
python main.py
输入自然语言任务，或直接执行：
python main.py "请检查失败的测试并修复"（或者可以直接在终端与智能体交互）

连接测试：python main.py --check
单元测试：python -m unittest discover -s tests -v

三、特色功能
1. 不使用 Agent 框架或 SDK。对话历史、上下文控制、Tool Calling 解析、工具调度、observation 回传、Agent Loop、终止条件和错误处理均已自行实现。
2. 支持 list_files、read_file、write_file、edit_file、delete_file、run_command，可自主查看项目、修改代码、运行测试并根据输出继续修复。
3. 文件操作限制在 workspace 内，使用 pathlib 校验真实路径。命令采用 shell=False，仅开放受限的 Python/pytest，具有超时、输出截断和敏感环境清理。
4. 支持单轮多个工具调用及二次编码命令参数兼容。相同工具错误连续三次时熔断，MAX_STEPS 提供最终上限。
5. 主进程和 Python 子进程统一使用 UTF-8；终端显示模型轮次并压缩长输出。

四、说明
本项目结构力求简单，未使用多 Agent、RAG、MCP、数据库或 Web 前端。run_command 只是本地安全护栏，并非操作系统级沙箱，不应运行不可信项目。

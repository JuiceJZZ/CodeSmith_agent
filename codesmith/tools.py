"""CodeSmith 的本地工具。

所有路径都必须相对于 workspace，避免模型读写项目工作区之外的文件。
"""

import json
import os
import subprocess
import sys
from pathlib import Path


MAX_FILE_SIZE = 1_000_000
MAX_COMMAND_OUTPUT = 10_000


# 这里使用模型原生 Function Calling 所需的 JSON Schema，不依赖 Agent SDK。
TOOL_DEFINITIONS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "列出 workspace 内指定目录的直接子项。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对于 workspace 的目录路径，默认为当前目录。",
                    }
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取 workspace 内一个 UTF-8 文本文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对于 workspace 的文件路径。",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "创建或完整覆盖 workspace 内一个 UTF-8 文本文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对于 workspace 的文件路径。",
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入文件的完整文本内容。",
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "精确替换 workspace 内文本文件中的一段内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对于 workspace 的文件路径。",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "文件中需要被替换的精确原文。",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "替换后的新文本。",
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "是否替换全部匹配，默认为 false。",
                    },
                },
                "required": ["path", "old_text", "new_text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "在 workspace 中运行受限的 Python 或 pytest 命令，并返回退出码、"
                "标准输出和错误输出。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": (
                            "命令参数数组，例如 ['python', '-m', 'unittest', "
                            "'discover', '-s', 'tests', '-v']。"
                        ),
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
]


class ToolError(ValueError):
    """工具参数无效或本地操作失败时抛出的可读异常。"""


def _resolve_workspace_path(workspace: Path, relative_path: str) -> Path:
    """将模型给出的相对路径安全地解析到 workspace 内。"""
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise ToolError(f"工作区不存在或不是目录：{workspace}")

    requested_path = Path(relative_path)
    if requested_path.is_absolute():
        raise ToolError("只允许使用相对于 workspace 的路径。")

    resolved_path = (workspace / requested_path).resolve()
    if not resolved_path.is_relative_to(workspace):
        raise ToolError("路径超出 workspace，操作已拒绝。")
    return resolved_path


def list_files(workspace: Path, relative_path: str = ".") -> list[str]:
    """列出指定目录的直接子项，并返回相对于 workspace 的路径。"""
    directory = _resolve_workspace_path(workspace, relative_path)
    if not directory.exists():
        raise ToolError(f"目录不存在：{relative_path}")
    if not directory.is_dir():
        raise ToolError(f"目标不是目录：{relative_path}")

    entries: list[str] = []
    for entry in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
        display_path = entry.relative_to(workspace.resolve()).as_posix()
        if entry.is_dir():
            display_path += "/"
        entries.append(display_path)
    return entries


def read_file(workspace: Path, relative_path: str) -> str:
    """读取 workspace 内不超过 1 MB 的 UTF-8 文本文件。"""
    file_path = _resolve_workspace_path(workspace, relative_path)
    if not file_path.exists():
        raise ToolError(f"文件不存在：{relative_path}")
    if not file_path.is_file():
        raise ToolError(f"目标不是文件：{relative_path}")
    if file_path.stat().st_size > MAX_FILE_SIZE:
        raise ToolError(
            f"文件超过 {MAX_FILE_SIZE} 字节，当前阶段拒绝读取：{relative_path}"
        )

    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ToolError(f"文件不是有效的 UTF-8 文本：{relative_path}") from error


def write_file(workspace: Path, relative_path: str, content: str) -> str:
    """创建或覆盖 UTF-8 文件；缺失的父目录会一并创建。"""
    file_path = _resolve_workspace_path(workspace, relative_path)
    if file_path.exists() and not file_path.is_file():
        raise ToolError(f"目标不是文件：{relative_path}")

    content_size = len(content.encode("utf-8"))
    if content_size > MAX_FILE_SIZE:
        raise ToolError(
            f"写入内容超过 {MAX_FILE_SIZE} 字节，操作已拒绝：{relative_path}"
        )

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
    except OSError as error:
        raise ToolError(f"写入文件失败：{relative_path}；{error}") from error
    return f"已写入 {relative_path}（{content_size} 字节）。"


def edit_file(
    workspace: Path,
    relative_path: str,
    old_text: str,
    new_text: str,
    replace_all: bool = False,
) -> str:
    """用精确文本替换修改文件，默认要求原文只出现一次。"""
    if not old_text:
        raise ToolError("edit_file 的 old_text 不能为空。")

    original = read_file(workspace, relative_path)
    match_count = original.count(old_text)
    if match_count == 0:
        raise ToolError(f"文件中没有找到 old_text：{relative_path}")
    if match_count > 1 and not replace_all:
        raise ToolError(
            f"old_text 在文件中出现 {match_count} 次；请提供更精确的文本，"
            "或明确设置 replace_all=true。"
        )

    count = -1 if replace_all else 1
    updated = original.replace(old_text, new_text, count)
    write_file(workspace, relative_path, updated)
    replaced_count = match_count if replace_all else 1
    return f"已编辑 {relative_path}，替换 {replaced_count} 处。"


def run_command(
    workspace: Path, command: list[str], timeout: int = 60
) -> str:
    """在 workspace 中以非 shell 方式运行受限命令。"""
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise ToolError(f"工作区不存在或不是目录：{workspace}")
    if not command or not all(isinstance(argument, str) for argument in command):
        raise ToolError("run_command 需要非空字符串数组 command。")
    if timeout <= 0:
        raise ToolError("命令超时时间必须大于 0。")

    safe_command = _build_safe_command(workspace, command)
    environment = _sanitized_environment()

    try:
        completed = subprocess.run(
            safe_command,
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            shell=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as error:
        result = {
            "exit_code": None,
            "stdout": _truncate_output(error.stdout or ""),
            "stderr": _truncate_output(error.stderr or ""),
            "timed_out": True,
            "message": f"命令执行超过 {timeout} 秒，已终止。",
        }
        return json.dumps(result, ensure_ascii=False)
    except OSError as error:
        raise ToolError(f"启动命令失败：{error}") from error

    result = {
        "exit_code": completed.returncode,
        "stdout": _truncate_output(completed.stdout),
        "stderr": _truncate_output(completed.stderr),
        "timed_out": False,
    }
    return json.dumps(result, ensure_ascii=False)


def _build_safe_command(workspace: Path, command: list[str]) -> list[str]:
    """将允许的用户命令转换为不经过 shell 的实际参数。"""
    executable = command[0].lower()
    arguments = command[1:]
    _reject_unsafe_command_arguments(arguments)

    if executable in {"pytest", "pytest.exe"}:
        return [sys.executable, "-m", "pytest", *arguments]

    if executable not in {"python", "python.exe"}:
        raise ToolError("当前只允许执行 python 或 pytest 命令。")
    if not arguments:
        raise ToolError("python 命令缺少脚本或模块参数。")

    first_argument = arguments[0]
    if first_argument == "--version" and len(arguments) == 1:
        return [sys.executable, "--version"]
    if first_argument == "-c":
        raise ToolError("出于安全考虑，不允许使用 python -c。")
    if first_argument == "-m":
        if len(arguments) < 2 or arguments[1] not in {"unittest", "pytest"}:
            raise ToolError("python -m 当前只允许 unittest 或 pytest。")
        return [sys.executable, *arguments]

    script_path = _resolve_workspace_path(workspace, first_argument)
    if script_path.suffix.lower() != ".py" or not script_path.is_file():
        raise ToolError("python 只能运行 workspace 内已存在的 .py 文件。")
    return [sys.executable, str(script_path), *arguments[1:]]


def _reject_unsafe_command_arguments(arguments: list[str]) -> None:
    """拒绝可能把命令指向 workspace 外部的明显路径参数。"""
    for argument in arguments:
        if "\x00" in argument or "\n" in argument or "\r" in argument:
            raise ToolError("命令参数包含非法控制字符。")
        if argument in {"|", "&", ";", ">", ">>", "<"}:
            raise ToolError("命令不支持 shell 运算符。")

        path_candidate = argument.split("=", 1)[-1]
        candidate_path = Path(path_candidate)
        if candidate_path.is_absolute() or ".." in candidate_path.parts:
            raise ToolError("命令参数不得使用绝对路径或超出 workspace。")


def _sanitized_environment() -> dict[str, str]:
    """复制进程环境，但不把 API Key 等敏感变量交给待运行代码。"""
    environment = os.environ.copy()
    sensitive_markers = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
    for name in list(environment):
        if any(marker in name.upper() for marker in sensitive_markers):
            environment.pop(name)
    # 父进程固定按 UTF-8 解码，因此也要求 Python 子进程使用 UTF-8 输出。
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    return environment


def _truncate_output(output: str | bytes) -> str:
    # TimeoutExpired 在部分 Python 版本中即使 text=True 也可能携带 bytes。
    if isinstance(output, bytes):
        output = output.decode("utf-8", errors="replace")
    if len(output) <= MAX_COMMAND_OUTPUT:
        return output
    omitted = len(output) - MAX_COMMAND_OUTPUT
    return f"{output[:MAX_COMMAND_OUTPUT]}\n... 已截断 {omitted} 个字符 ..."


def execute_tool(
    name: str,
    arguments: dict[str, object],
    workspace: Path,
    command_timeout: int = 60,
) -> str:
    """校验模型生成的参数，执行一个已注册工具并返回文本结果。"""
    if name == "list_files":
        _reject_unknown_arguments(arguments, {"path"})
        relative_path = arguments.get("path", ".")
        if not isinstance(relative_path, str):
            raise ToolError("list_files 的 path 参数必须是字符串。")
        return json.dumps(list_files(workspace, relative_path), ensure_ascii=False)

    if name == "read_file":
        _reject_unknown_arguments(arguments, {"path"})
        relative_path = arguments.get("path")
        if not isinstance(relative_path, str) or not relative_path:
            raise ToolError("read_file 需要非空字符串 path 参数。")
        return read_file(workspace, relative_path)

    if name == "write_file":
        _reject_unknown_arguments(arguments, {"path", "content"})
        relative_path = arguments.get("path")
        content = arguments.get("content")
        if not isinstance(relative_path, str) or not relative_path:
            raise ToolError("write_file 需要非空字符串 path 参数。")
        if not isinstance(content, str):
            raise ToolError("write_file 的 content 参数必须是字符串。")
        return write_file(workspace, relative_path, content)

    if name == "edit_file":
        _reject_unknown_arguments(
            arguments, {"path", "old_text", "new_text", "replace_all"}
        )
        relative_path = arguments.get("path")
        old_text = arguments.get("old_text")
        new_text = arguments.get("new_text")
        replace_all = arguments.get("replace_all", False)
        if not isinstance(relative_path, str) or not relative_path:
            raise ToolError("edit_file 需要非空字符串 path 参数。")
        if not isinstance(old_text, str):
            raise ToolError("edit_file 的 old_text 参数必须是字符串。")
        if not isinstance(new_text, str):
            raise ToolError("edit_file 的 new_text 参数必须是字符串。")
        if not isinstance(replace_all, bool):
            raise ToolError("edit_file 的 replace_all 参数必须是布尔值。")
        return edit_file(
            workspace, relative_path, old_text, new_text, replace_all
        )

    if name == "run_command":
        _reject_unknown_arguments(arguments, {"command"})
        command = arguments.get("command")
        if not isinstance(command, list) or not all(
            isinstance(argument, str) for argument in command
        ):
            raise ToolError("run_command 的 command 参数必须是字符串数组。")
        return run_command(workspace, command, command_timeout)

    raise ToolError(f"未知工具：{name}")


def _reject_unknown_arguments(
    arguments: dict[str, object], allowed_names: set[str]
) -> None:
    unknown_names = set(arguments) - allowed_names
    if unknown_names:
        names = ", ".join(sorted(unknown_names))
        raise ToolError(f"包含未知工具参数：{names}")

"""CodeSmith 的本地工具。

当前阶段只提供只读工具。所有路径都必须相对于 workspace，避免模型读取
项目工作区之外的文件。
"""

import json
from pathlib import Path


MAX_FILE_SIZE = 1_000_000


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


def execute_tool(name: str, arguments: dict[str, object], workspace: Path) -> str:
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

    raise ToolError(f"未知工具：{name}")


def _reject_unknown_arguments(
    arguments: dict[str, object], allowed_names: set[str]
) -> None:
    unknown_names = set(arguments) - allowed_names
    if unknown_names:
        names = ", ".join(sorted(unknown_names))
        raise ToolError(f"包含未知工具参数：{names}")


# TODO: 后续逐步实现 write_file、edit_file、run_command。

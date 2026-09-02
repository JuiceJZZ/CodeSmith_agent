"""集中读取和校验 CodeSmith 的环境配置。"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(ValueError):
    """环境变量缺失或格式错误时抛出的友好配置异常。"""


@dataclass(frozen=True)
class Settings:
    """当前阶段需要的配置，以及为后续 Agent 预留的基础限制。"""

    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    workspace_path: Path
    max_steps: int
    command_timeout: int


def _read_positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ConfigError(f"{name} 必须是整数，当前值为 {raw_value!r}。") from error

    if value <= 0:
        raise ConfigError(f"{name} 必须大于 0，当前值为 {value}。")
    return value


def _resolve_workspace(raw_path: str) -> Path:
    if not raw_path:
        raise ConfigError("WORKSPACE_PATH 不能为空。")

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved_path = path.resolve()

    # 后续工具只允许接触项目内的工作区，因此现在就固定安全边界。
    if not resolved_path.is_relative_to(PROJECT_ROOT):
        raise ConfigError("WORKSPACE_PATH 必须位于 CodeSmith 项目目录内。")
    return resolved_path


def load_settings() -> Settings:
    """加载 `.env` 和系统环境变量，并返回经过校验的配置。"""
    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        raise ConfigError(
            "未找到有效的 DEEPSEEK_API_KEY。请复制 .env.example 为 .env，"
            "并在 .env 中填写新生成的 DeepSeek API Key。"
        )

    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash").strip()
    if not base_url:
        raise ConfigError("DEEPSEEK_BASE_URL 不能为空。")
    if not model:
        raise ConfigError("DEEPSEEK_MODEL 不能为空。")

    return Settings(
        deepseek_api_key=api_key,
        deepseek_base_url=base_url,
        deepseek_model=model,
        workspace_path=_resolve_workspace(
            os.getenv("WORKSPACE_PATH", "workspace").strip()
        ),
        max_steps=_read_positive_int("MAX_STEPS", 25),
        command_timeout=_read_positive_int("COMMAND_TIMEOUT", 60),
    )

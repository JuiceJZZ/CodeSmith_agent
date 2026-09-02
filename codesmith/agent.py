"""CodeSmith 的最小 Agent Loop。

该模块自行维护消息历史、执行工具、回传 observation，并根据模型最终回复
或 MAX_STEPS 结束循环，不依赖任何 Agent 框架。
"""

import json
from dataclasses import dataclass
from typing import Callable

from codesmith.config import Settings
from codesmith.llm import ToolCall, complete_with_tools
from codesmith.prompts import AGENT_SYSTEM_PROMPT
from codesmith.tools import ToolError, execute_tool


MAX_OBSERVATION_CHARS = 30_000


class AgentError(RuntimeError):
    """Agent 无法正常完成任务时抛出的异常。"""


@dataclass(frozen=True)
class ToolExecution:
    """一次本地工具执行记录，供 CLI 展示和测试检查。"""

    step: int
    name: str
    arguments: dict[str, object]
    observation: str


@dataclass(frozen=True)
class AgentResult:
    """Agent 正常结束时返回的最终文本与执行摘要。"""

    final_answer: str
    model_calls: int
    tool_executions: tuple[ToolExecution, ...]


def _assistant_tool_message(
    tool_calls: tuple[ToolCall, ...], content: str | None
) -> dict[str, object]:
    """构造需要写入历史的 assistant tool-call 消息。"""
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {
                "id": tool_call.call_id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                },
            }
            for tool_call in tool_calls
        ],
    }


def _limit_observation(observation: str) -> str:
    """限制单次工具结果长度，避免消息历史被大文件快速撑满。"""
    if len(observation) <= MAX_OBSERVATION_CHARS:
        return observation

    suffix = f"\n... observation 已截断，原始长度 {len(observation)} 字符 ..."
    kept_length = MAX_OBSERVATION_CHARS - len(suffix)
    return observation[:kept_length] + suffix


def run_agent(
    task: str,
    settings: Settings,
    on_tool_execution: Callable[[ToolExecution], None] | None = None,
    on_model_step: Callable[[int, int], None] | None = None,
) -> AgentResult:
    """运行受 MAX_STEPS 限制的 Agent Loop。"""
    if not task.strip():
        raise AgentError("编程任务不能为空。")

    messages: list[dict[str, object]] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    executions: list[ToolExecution] = []

    for step in range(1, settings.max_steps + 1):
        if on_model_step is not None:
            on_model_step(step, settings.max_steps)
        reply = complete_with_tools(messages, settings)
        if not reply.tool_calls:
            final_answer = reply.content
            if not final_answer:
                raise AgentError("模型返回了空的最终答案。")
            messages.append({"role": "assistant", "content": final_answer})
            return AgentResult(final_answer, step, tuple(executions))

        messages.append(_assistant_tool_message(reply.tool_calls, reply.content))

        # 模型可能在一轮中返回多个调用；本地按顺序执行，便于观察和复现。
        for tool_call in reply.tool_calls:
            try:
                observation = execute_tool(
                    tool_call.name,
                    tool_call.arguments,
                    settings.workspace_path,
                    settings.command_timeout,
                )
            except ToolError as error:
                # 工具参数错误也属于模型可观察的信息，让下一轮有机会修正。
                observation = f"工具执行失败：{error}"

            observation = _limit_observation(observation)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.call_id,
                    "content": observation,
                }
            )
            execution = ToolExecution(
                step, tool_call.name, tool_call.arguments, observation
            )
            executions.append(execution)
            if on_tool_execution is not None:
                on_tool_execution(execution)

    raise AgentError(
        f"已达到最大步骤数 MAX_STEPS={settings.max_steps}，任务仍未结束；"
        f"本次已执行 {len(executions)} 个工具调用。"
    )

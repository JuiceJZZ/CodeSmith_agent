"""DeepSeek OpenAI-compatible API 的最小文本调用封装。"""

import json
from dataclasses import dataclass

from openai import OpenAI

from codesmith.config import Settings
from codesmith.prompts import SYSTEM_PROMPT, TOOL_SYSTEM_PROMPT
from codesmith.tools import TOOL_DEFINITIONS


@dataclass(frozen=True)
class ToolCall:
    """从模型响应中解析出的单个工具调用。"""

    call_id: str
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class ModelReply:
    """模型的一次回复：普通文本或一个工具调用。"""

    content: str | None
    tool_call: ToolCall | None


def create_client(settings: Settings) -> OpenAI:
    """根据项目配置创建普通 OpenAI 客户端，不引入任何 Agent SDK。"""
    return OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


def chat(user_message: str, settings: Settings) -> str:
    """向 DeepSeek 发送一次普通文本对话并返回文本内容。"""
    client = create_client(settings)
    response = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("DeepSeek API 返回成功，但回复内容为空。")
    return content


def chat_with_tools(user_message: str, settings: Settings) -> ModelReply:
    """让模型进行一次决策，并解析普通文本或单个工具调用。"""
    messages: list[dict[str, object]] = [
        {"role": "system", "content": TOOL_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    return complete_with_tools(messages, settings)


def complete_with_tools(
    messages: list[dict[str, object]], settings: Settings
) -> ModelReply:
    """根据完整消息历史调用一次模型，并解析本轮回复。"""
    client = create_client(settings)
    response = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
        tools=TOOL_DEFINITIONS,
        tool_choice="auto",
    )

    message = response.choices[0].message
    raw_tool_calls = message.tool_calls or []
    if len(raw_tool_calls) > 1:
        raise RuntimeError("当前阶段每次只支持一个工具调用，但模型返回了多个。")

    if not raw_tool_calls:
        if not message.content:
            raise RuntimeError("模型既没有返回文本，也没有返回工具调用。")
        return ModelReply(content=message.content, tool_call=None)

    raw_tool_call = raw_tool_calls[0]
    try:
        arguments = json.loads(raw_tool_call.function.arguments)
    except json.JSONDecodeError as error:
        raise RuntimeError("模型返回的工具参数不是有效 JSON。") from error
    if not isinstance(arguments, dict):
        raise RuntimeError("模型返回的工具参数必须是 JSON 对象。")

    tool_call = ToolCall(
        call_id=raw_tool_call.id,
        name=raw_tool_call.function.name,
        arguments=arguments,
    )
    return ModelReply(content=message.content, tool_call=tool_call)

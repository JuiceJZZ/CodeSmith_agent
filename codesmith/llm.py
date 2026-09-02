"""DeepSeek OpenAI-compatible API 的最小文本调用封装。"""

from openai import OpenAI

from codesmith.config import Settings
from codesmith.prompts import SYSTEM_PROMPT


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


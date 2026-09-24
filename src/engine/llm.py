"""LLM 客户端：统一封装各家厂商（都是 OpenAI 兼容格式）。

对应 TS 版的 engine/llmService.ts。
关键点：tool_calls 归一化成 ToolCall（参数从 JSON 字符串解析成 dict），
解析失败不抛异常 —— 交给工具执行层把错误回填给模型重试。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from ..config import LLMConfig


@dataclass
class ToolCall:
    """归一化后的工具调用（参数已解析成 dict）。"""

    id: str
    name: str
    args: dict[str, Any]


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


def _to_tool_call(raw: Any) -> ToolCall:
    fn = getattr(raw, "function", None)
    name = getattr(fn, "name", "") or ""
    raw_args = getattr(fn, "arguments", "") or ""
    try:
        args = json.loads(raw_args) if raw_args else {}
    except json.JSONDecodeError:
        # 模型偶尔吐非法 JSON —— 降级成空参数，让工具侧报错回填
        args = {}
    return ToolCall(id=getattr(raw, "id", ""), name=name, args=args)


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        self._client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """发一次请求。传入 tools 即启用 Function Calling。"""
        kwargs: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # 工具定义必须每轮都传 —— 模型无状态，不会记住上一次有哪些工具
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        return LLMResponse(
            content=msg.content or "",
            tool_calls=[_to_tool_call(tc) for tc in (msg.tool_calls or [])],
        )

    def simple(self, prompt: str, system: str = "", temperature: float = 0.2) -> str:
        """单轮问答（不带工具），用于测试连通性。"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=temperature).content

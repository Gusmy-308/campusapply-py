"""Agent 的工具集：定义（给模型看的说明书）+ 执行器（真正干活）。

对应 TS 版的 engine/agentFill.ts 里的 FILL_TOOLS 与 executeTool。

⭐ 核心分工：**模型决定调哪个工具，这里负责真正执行。**
模型输出 tool_calls（工具名 + 参数），我们按名字找到函数执行，把结果回填。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from playwright.sync_api import Page

from ..browser.filler import fill_one
from ..browser.scanner import FormField, read_field_value, scan_fields
from ..engine.matcher import MatchResult, UserData, match_field, pick_option

# ---------------- 工具定义（JSON Schema，写给模型看）------------------
# ⚠️ 描述就是 Prompt —— 写清楚「什么时候用我」，模型才选得对。

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "scan_form",
            "description": (
                "扫描当前页面上所有可填写的表单字段，返回字段列表"
                "（每个字段含 id、标签、类型、是否必填、下拉选项、当前值）。"
                "开始填表前必须先调用一次；页面翻页或动态加载出新字段后也应重新调用。"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_data",
            "description": (
                "根据字段的语义从用户信息库查询应填的值。"
                "会先走本地规则/语义匹配，匹配不到再调大模型兜底。"
                "返回 found=false 表示信息库里确实没有这项信息，"
                "此时应跳过该字段，**不要编造**。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "field_label": {"type": "string", "description": "表单字段的标签文本，如「姓名」「毕业院校」"},
                    "field_context": {"type": "string", "description": "字段的上下文提示，如所属分组、placeholder"},
                },
                "required": ["field_label"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fill_field",
            "description": (
                "把一个值填进页面上指定的字段。field_id 必须是 scan_form 返回过的 id。"
                "填写下拉框时请传选项的完整文本。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "field_id": {"type": "string", "description": "scan_form 返回的字段 id"},
                    "value": {"type": "string", "description": "要填入的值"},
                },
                "required": ["field_id", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_field",
            "description": (
                "重新读取页面上某个字段当前实际填入的值，"
                "用于校验上一步填写是否真正写进了页面（前端框架可能拦截赋值）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "field_id": {"type": "string", "description": "scan_form 返回的字段 id"},
                },
                "required": ["field_id"],
            },
        },
    },
]

TOOL_NAMES = {t["function"]["name"] for t in TOOL_DEFINITIONS}


# ---------------- 工具上下文 ----------------

@dataclass
class ToolContext:
    """工具执行需要的一切外部依赖。"""

    page: Page
    user: UserData
    llm_matcher: Callable[[str, str], MatchResult] | None = None  # LLM 兜底（可选）
    # 会话内缓存：同一个字段标签不重复查
    value_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    # 扫描到的字段，供 fill_field / check_field 按 id 反查
    fields: dict[str, FormField] = field(default_factory=dict)
    # 执行轨迹
    log: list[dict[str, Any]] = field(default_factory=list)


# ---------------- 工具实现 ----------------

def tool_scan_form(ctx: ToolContext) -> dict[str, Any]:
    fields = scan_fields(ctx.page)
    ctx.fields = {f.id: f for f in fields}
    return {
        "count": len(fields),
        "fields": [
            {
                "id": f.id,
                "label": f.label,
                "type": f.type,
                "required": f.required,
                "options": (f.options or [])[:20] or None,
                "currentValue": f.current_value,
                "section": f.section or None,
            }
            for f in fields
        ],
    }


def tool_get_user_data(ctx: ToolContext, field_label: str, field_context: str = "") -> dict[str, Any]:
    if not field_label:
        return {"error": "缺少 field_label 参数"}

    if field_label in ctx.value_cache:
        return {**ctx.value_cache[field_label], "cached": True}

    # ① 本地两级匹配（规则 + 语义）—— 零成本
    m = match_field(field_label, ctx.user, placeholder=field_context)
    value, source, conf = m.value, m.matched_by, m.confidence

    # ② 本地拿不准（< 0.5）才调 LLM 兜底
    if (not value or conf < 0.5) and ctx.llm_matcher:
        try:
            llm_res = ctx.llm_matcher(field_label, field_context)
            if llm_res and llm_res.value and llm_res.confidence > conf:
                value, source, conf = llm_res.value, "llm", llm_res.confidence
        except Exception:
            # LLM 失败静默降级 —— 旁路原则，不阻塞 Agent 主流程
            pass

    out = {"found": bool(value), "value": value, "source": source, "confidence": round(conf, 2)}
    ctx.value_cache[field_label] = out
    return out


def tool_fill_field(ctx: ToolContext, field_id: str, value: str) -> dict[str, Any]:
    if not field_id:
        return {"error": "缺少 field_id 参数"}
    f = ctx.fields.get(field_id)
    res = fill_one(
        ctx.page, field_id, value,
        name=f.name if f else "", selector=f.selector if f else "", label=f.label if f else "",
    )
    return {
        "status": res.status,
        "filledValue": res.filled_value,
        "error": res.error or None,
    }


def tool_check_field(ctx: ToolContext, field_id: str) -> dict[str, Any]:
    if not field_id:
        return {"error": "缺少 field_id 参数"}
    f = ctx.fields.get(field_id)
    actual = read_field_value(ctx.page, field_id, f.name if f else "",
                              f.selector if f else "")
    if actual is None:
        return {"error": f"页面上找不到 id 为 {field_id} 的字段（可能页面已刷新）"}
    return {"field_id": field_id, "label": f.label if f else "", "actualValue": actual}


# ---------------- 调度 ----------------

def execute_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """按工具名分发。未知工具返回错误而不是抛异常 —— 让模型自己纠正。"""
    # ⭐ 白名单校验：模型可能幻觉出不存在的工具
    if name not in TOOL_NAMES:
        return {"error": f'不存在名为 "{name}" 的工具。可用工具：{", ".join(sorted(TOOL_NAMES))}'}

    if name == "scan_form":
        return tool_scan_form(ctx)
    if name == "get_user_data":
        return tool_get_user_data(ctx, str(args.get("field_label", "")), str(args.get("field_context", "")))
    if name == "fill_field":
        return tool_fill_field(ctx, str(args.get("field_id", "")), str(args.get("value", "")))
    if name == "check_field":
        return tool_check_field(ctx, str(args.get("field_id", "")))
    return {"error": f"工具 {name} 未实现"}


def suggest_option(value: str, options: list[str]) -> str | None:
    """给下拉框选项做同义对齐（供 matcher 使用，这里透出便于测试）。"""
    return pick_option(value, options)

"""Agent 主循环（Function Calling）。

对应 TS 版的 engine/agentFill.ts —— 两版结构完全一致。

与 Workflow 的区别：
    Workflow（workflow.py）= 步骤写死：加载→扫描→匹配→填充→统计，快、省、可控
    Agent（本文件）        = 只给目标，模型自主决定调哪个工具、调几次、何时停

四个工程要点（面试会问）：
    ① 终止条件 —— 模型不再调工具 / 触达最大轮次（防死循环）
    ② 工具描述 —— description 写清楚「什么时候用我」，直接决定选得准不准
    ③ 错误回填 —— 工具失败不中断循环，把错误当结果回填给模型自己决策
    ④ 白名单校验 —— 模型可能幻觉出不存在的工具名
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from playwright.sync_api import Page

from ..config import AgentConfig
from ..tools.fill_tools import TOOL_DEFINITIONS, ToolContext, execute_tool
from .llm import LLMClient
from .matcher import MatchResult, UserData, match_field

SYSTEM_PROMPT = """你是校招网申表单填充助手，通过调用工具帮用户把当前页面的表单填好。

工作原则：
1. 先调用 scan_form 看清页面上有哪些字段，再动手。
2. 对每个可填字段：先 get_user_data 查值，查到就 fill_field 填进去，填完用 check_field 校验。
3. get_user_data 返回 found=false 时，说明信息库里没有这项，**跳过该字段，绝不编造**。
4. 遇到不该填的字段（验证码、密码、附件上传、搜索框），直接跳过。
5. 工具报错时不要慌：换个参数重试，或跳过。不要因为一个字段失败就停下。
6. 所有能填的都填完后，停止调用工具，用一句话总结（填了几个、跳过了几个、哪些没填）。

不要输出多余解释，直接调工具或给总结。"""

FILL_GOAL = "请把当前页面的网申表单填好。填完后告诉我：成功填入几个字段、跳过了几个、分别是什么原因。"


@dataclass
class AgentResult:
    success: bool
    turns: int
    summary: str
    log: list[dict[str, Any]] = field(default_factory=list)


def run_agent(
    page: Page,
    llm: LLMClient,
    user: UserData,
    agent_cfg: AgentConfig,
    llm_matcher: Callable[[str, str], MatchResult] | None = None,
    on_step: Callable[[int, str, dict[str, Any]], None] | None = None,
) -> AgentResult:
    """跑一次 Agent 填充。"""
    ctx = ToolContext(page=page, user=user, llm_matcher=llm_matcher)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": FILL_GOAL},
    ]

    for turn in range(1, agent_cfg.max_turns + 1):
        # ① 调模型：把【工具定义】随请求发出去（模型无状态，每轮都要传）
        resp = llm.chat(
            messages=messages,
            tools=TOOL_DEFINITIONS,
            temperature=agent_cfg.temperature,
            max_tokens=agent_cfg.max_tokens,
        )

        # ② 模型没要求调工具 → 任务完成，退出循环（终止条件一）
        if not resp.wants_tools:
            return AgentResult(
                success=True, turns=turn,
                summary=resp.content or "已完成", log=ctx.log,
            )

        # ③ 把 assistant 的决策记进历史
        messages.append({
            "role": "assistant",
            "content": resp.content or None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.args, ensure_ascii=False)},
                }
                for tc in resp.tool_calls
            ],
        })

        # ④ 逐个执行工具，结果回填
        for tc in resp.tool_calls:
            if on_step:
                on_step(turn, tc.name, tc.args)
            try:
                result = execute_tool(ctx, tc.name, tc.args)
            except Exception as e:
                # ⚠️ 工具失败不中断循环 —— 错误当结果回填，让模型自己决定重试还是换方案
                result = {"error": f"{type(e).__name__}: {e}"}

            text = json.dumps(result, ensure_ascii=False)
            ctx.log.append({"turn": turn, "tool": tc.name, "args": tc.args, "result": text[:300]})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})

    # ⑤ 触达最大轮次（终止条件二，防死循环）
    return AgentResult(
        success=False, turns=agent_cfg.max_turns,
        summary=f"达到最大轮次（{agent_cfg.max_turns}），任务可能未完成。共 {len(ctx.log)} 次工具调用。",
        log=ctx.log,
    )


# =================== Workflow 模式（对照组）===================

def run_workflow(
    page: Page,
    user: UserData,
    llm_matcher: Callable[[str, str], MatchResult] | None = None,
    on_progress: Callable[[str, int], None] | None = None,
) -> dict[str, Any]:
    """固定五步流程 —— 与 TS 版的 fillOrchestrator 对应。

    大部分表单结构规整，这条路几步就完事，且只有拿不准的字段才调模型。
    和 Agent 模式并存，让用户按场景选。
    """
    from ..browser.filler import fill_fields
    from ..browser.scanner import scan_fields

    def progress(msg: str, pct: int) -> None:
        if on_progress:
            on_progress(msg, pct)

    # ① 扫描（用户数据已由调用方传入，等价于 TS 版的 loadUserData）
    progress("正在扫描页面表单…", 20)
    fields = scan_fields(page)

    # ② 三级匹配
    progress(f"发现 {len(fields)} 个字段，开始匹配…", 45)
    actions: list[dict[str, Any]] = []
    stat = {"rule": 0, "semantic": 0, "llm": 0, "skipped": 0}

    for f in fields:
        m = match_field(f.label, user, placeholder=f.placeholder, section=f.section, options=f.options)
        value, source, conf = m.value, m.matched_by, m.confidence

        if (not value or conf < 0.5) and llm_matcher:
            try:
                r = llm_matcher(f.label, f"{f.section} {f.placeholder}".strip())
                if r and r.value and r.confidence > conf:
                    value, source, conf = r.value, "llm", r.confidence
            except Exception:
                pass

        # 置信度阈值：宁可少填，不可错填
        if not value or conf <= 0.3:
            stat["skipped"] += 1
            continue

        # 下拉框对齐到真实选项
        if f.options:
            from .matcher import pick_option
            opt = pick_option(value, f.options)
            if opt:
                value = opt

        stat[source if source in stat else "rule"] += 1
        actions.append({
            "fieldId": f.id, "id": f.id, "name": f.name,
            "selector": f.selector, "label": f.label, "value": value,
        })

    # ③ 填充
    progress(f"填充 {len(actions)} 个字段…", 75)
    results = fill_fields(page, actions)
    ok = sum(1 for r in results if r.ok)

    progress("完成", 100)
    return {
        "total_fields": len(fields),
        "filled": ok,
        "failed": len(results) - ok,
        "skipped": stat["skipped"],
        "by_source": stat,
    }

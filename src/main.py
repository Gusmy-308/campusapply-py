"""CampusApply Python 版 · CLI 入口

用法：
    python -m src.main test                 # 测试 LLM 连通 + Function Calling 能力
    python -m src.main scan  <url>          # 打开页面并扫描表单字段
    python -m src.main fill  <url>          # Workflow 模式填充（快、省）
    python -m src.main agent <url>          # Agent 模式填充（模型自主决策）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .browser.driver import SiteBlockedError, open_browser
from .browser.scanner import scan_fields
from .config import DATA_DIR, Config, load_config
from .engine.agent import run_agent, run_workflow
from .engine.llm import LLMClient
from .engine.matcher import MatchResult, UserData

console = Console()


def load_user_data() -> UserData:
    path = DATA_DIR / "profile.json"
    if not path.exists():
        raise FileNotFoundError(f"找不到 {path}，请先创建用户信息文件")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return UserData(
        personal_info=raw.get("personalInfo", {}),
        educations=raw.get("educations", []),
        experiences=raw.get("experiences", []),
        skills=raw.get("skills", []),
        special=raw.get("special", {}),
    )


def make_llm_matcher(llm: LLMClient):
    """LLM 兜底匹配器：只在本地两级都拿不准时才被调用。"""

    def matcher(label: str, context: str) -> MatchResult:
        # 截断上限放到 6000：数据里有 3 段经历 + 教育 + 技能，1500 会截掉后面的项目
        summary = json.dumps(load_user_data().__dict__, ensure_ascii=False, default=str)[:6000]
        prompt = (
            f"用户信息：\n{summary}\n\n"
            f"表单字段：{label}\n字段上下文：{context}\n\n"
            "请给出这个字段最合适的填写内容。只返回值本身；"
            "如果信息里没有对应内容，返回空字符串。"
        )
        value = llm.simple(prompt, system="你是校招网申填充助手，只返回填写内容。", temperature=0.1).strip()
        # 置信度给 0.7 —— 模型兜底不如本地精确规则可靠
        return MatchResult(label=label, value=value, matched_by="llm", confidence=0.7 if value else 0.0)

    return matcher


# ---------------- 子命令 ----------------

def _resolve_page(browser, url: str | None, use_current: bool):
    """--current → 操作你当前打开的标签页（不导航、不开新标签）；否则新开并导航到 url。"""
    if use_current:
        page = browser.current_page()
    else:
        if not url:
            raise SystemExit("需要提供目标 URL，或加 --current 操作当前标签页")
        page = browser.goto(url)
    console.print(f"[bold]页面[/] {page.title() or page.url}")
    return page


def cmd_test(cfg: Config) -> int:
    client = LLMClient(cfg.llm)
    console.print(Panel.fit(
        f"[bold]provider[/] {cfg.llm.provider}\n[bold]model[/]    {cfg.llm.model}",
        title="LLM 配置",
    ))

    with console.status("测试连通性…"):
        reply = client.simple("只回复两个字：通了")
    console.print(f"① 连通性      [green]✅[/] {reply.strip()}")

    with console.status("测试 Function Calling…"):
        resp = client.chat(
            messages=[{"role": "user", "content": "我要填网申表单的「姓名」，帮我查一下该填什么"}],
            tools=[{
                "type": "function",
                "function": {
                    "name": "get_user_data",
                    "description": "根据字段语义查询用户信息库",
                    "parameters": {
                        "type": "object",
                        "properties": {"field_label": {"type": "string"}},
                        "required": ["field_label"],
                    },
                },
            }],
        )
    if resp.wants_tools:
        tc = resp.tool_calls[0]
        console.print(f"② Function Calling [green]✅[/] {tc.name}({tc.args})")
    else:
        console.print(f"② Function Calling [red]❌[/] {resp.content!r}")
        return 1

    # ③ 用户信息
    try:
        user = load_user_data()
        console.print(f"③ 用户信息    [green]✅[/] {user.personal_info.get('name')} / {len(user.educations)} 段教育经历")
    except FileNotFoundError as e:
        console.print(f"③ 用户信息    [red]❌[/] {e}")
        return 1

    console.print("\n[bold green]✅ 环境就绪[/]")
    return 0


def cmd_scan(cfg: Config, url: str | None, use_current: bool = False) -> int:
    with open_browser(cfg.browser) as browser:
        page = _resolve_page(browser, url, use_current)
        fields = scan_fields(page)
        if not fields:
            console.print("[yellow]⚠️ 没扫到字段（页面未渲染完 / 需登录 / 非表单页）[/]")
            return 1

        table = Table(title=f"发现 {len(fields)} 个表单字段")
        table.add_column("#", style="dim", width=3)
        table.add_column("标签", style="bold", max_width=28)
        table.add_column("类型", style="cyan", width=10)
        table.add_column("必填", width=4)
        table.add_column("选项", max_width=24)
        for i, f in enumerate(fields, 1):
            table.add_row(str(i), f.label or "(无标签)", f.type,
                          "✓" if f.required else "",
                          "/".join((f.options or [])[:6]))
        console.print(table)
    return 0


def _print_actions(log: list[dict]) -> None:
    table = Table(title="Agent 执行轨迹")
    table.add_column("轮次", width=5)
    table.add_column("工具", style="magenta", width=15)
    table.add_column("参数", max_width=32)
    table.add_column("结果", style="green", max_width=40)
    for item in log:
        table.add_row(
            str(item["turn"]), item["tool"],
            json.dumps(item["args"], ensure_ascii=False)[:32],
            item["result"][:40],
        )
    console.print(table)


def cmd_fill(cfg: Config, url: str | None, use_current: bool = False) -> int:
    user = load_user_data()
    llm = LLMClient(cfg.llm)
    with open_browser(cfg.browser) as browser:
        page = _resolve_page(browser, url, use_current)
        stats = run_workflow(
            page, user, llm_matcher=make_llm_matcher(llm),
            on_progress=lambda m, p: console.print(f"  [dim]{m}[/]"),
        )
    console.print(Panel.fit(
        f"字段总数 [bold]{stats['total_fields']}[/]\n"
        f"成功填入 [green]{stats['filled']}[/]\n"
        f"失败     [red]{stats['failed']}[/]\n"
        f"跳过     [yellow]{stats['skipped']}[/]\n"
        f"来源分布 {stats['by_source']}",
        title="Workflow 结果",
    ))
    return 0


def cmd_agent(cfg: Config, url: str | None, use_current: bool = False) -> int:
    user = load_user_data()
    llm = LLMClient(cfg.llm)
    with open_browser(cfg.browser) as browser:
        page = _resolve_page(browser, url, use_current)
        console.print("[dim]Agent 启动，模型将自主决定调用哪些工具…[/]\n")

        result = run_agent(
            page, llm, user, cfg.agent,
            llm_matcher=make_llm_matcher(llm),
            on_step=lambda turn, tool, args: console.print(
                f"  [magenta]第 {turn} 轮[/] → [bold]{tool}[/] "
                f"[dim]{json.dumps(args, ensure_ascii=False)[:60]}[/]"
            ),
        )

    _print_actions(result.log)
    console.print(Panel.fit(
        f"轮次 [bold]{result.turns}[/]　工具调用 [bold]{len(result.log)}[/] 次\n\n"
        f"{result.summary}",
        title=("✅ Agent 完成" if result.success else "⚠️ 未完成"),
    ))
    return 0 if result.success else 1


# ---------------- 入口 ----------------

def main() -> int:
    parser = argparse.ArgumentParser(prog="campusapply", description="校招网申自动化（Python 版）")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("test", help="测试环境与 LLM 连通性")

    for name, help_text in [("scan", "扫描页面表单字段"),
                            ("fill", "Workflow 模式填充"),
                            ("agent", "Agent 模式填充")]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("url", nargs="?", help="目标页面 URL（配合 --current 时可省略）")
        p.add_argument("--current", action="store_true",
                       help="不导航，直接操作你当前打开的标签页（附着模式专用）")

    args = parser.parse_args()

    try:
        cfg = load_config()
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[red]配置错误：{e}[/]")
        return 1

    try:
        if args.cmd == "test":
            return cmd_test(cfg)
        if args.cmd == "scan":
            return cmd_scan(cfg, args.url, args.current)
        if args.cmd == "fill":
            return cmd_fill(cfg, args.url, args.current)
        if args.cmd == "agent":
            return cmd_agent(cfg, args.url, args.current)
    except SiteBlockedError as e:
        console.print(f"\n[yellow]⚠️  {e}[/]")
        return 2

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

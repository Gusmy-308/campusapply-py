"""Playwright 浏览器封装。

两种模式，差别在【浏览器身份】而不在【登录态】：

  ① 附着模式（config 里 cdp_url 非空）—— connect_over_cdp 连到
     **你自己正在运行的那个 Chrome**。请求由你的真实浏览器发出，
     进程、TLS 指纹、登录态、Cookie 全是你的，动态防护无从识别自动化。
     → 这是过瑞数（Riversafe）这类 WAF 的唯一姿势。

  ② 独立模式（默认）—— launch_persistent_context 另起一个 Chromium。
     ⚠️ 复用的只是「登录态」（user-data-dir 里的 cookie/存储），
        **不是「浏览器身份」**。登录态能过表单校验，过不了 WAF —— 两回事。
        遇到瑞数会拿到 412 + 空 body。

对应 TS 版的「扩展天然跑在你自己的浏览器里」：扩展本来就是附着，
Python 版靠 connect_over_cdp 达到同样效果。
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from playwright.sync_api import BrowserContext, Page, sync_playwright

from ..config import BrowserConfig

# Chrome 被动态防护拦截时的典型响应：4xx + 极短 body
_BLOCKED_STATUS = {400, 403, 412}
_BLOCKED_BODY_MAX = 300


class SiteBlockedError(RuntimeError):
    """页面被动态防护（瑞数等）拦截 —— 应提示用户手动填写，而不是硬刚。"""


class Browser:
    """浏览器会话。用 with 语法保证退出时干净关闭。"""

    def __init__(self, cfg: BrowserConfig):
        self.cfg = cfg
        self._pw = None
        self._ctx: BrowserContext | None = None
        self._attached = False

    def __enter__(self) -> "Browser":
        self._pw = sync_playwright().start()

        if self.cfg.cdp_url:
            # —— 附着模式：连到你正在运行的 Chrome，不新起进程、不换身份 ——
            try:
                browser = self._pw.chromium.connect_over_cdp(self.cfg.cdp_url)
            except Exception as e:
                raise RuntimeError(
                    f"连不上 Chrome 调试端口 {self.cfg.cdp_url}\n"
                    f"请先【完全退出 Chrome（⌘Q）】，再用调试端口启动：\n"
                    f'  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome '
                    f"--remote-debugging-port=9222\n"
                    f"原始错误：{e}"
                ) from e
            self._attached = True
            self._ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        else:
            # —— 独立模式：另起一个 Chromium（登录态能留，身份留不下）——
            profile = Path(self.cfg.profile_dir)
            profile.mkdir(parents=True, exist_ok=True)
            self._ctx = self._pw.chromium.launch_persistent_context(
                user_data_dir=str(profile),
                headless=self.cfg.headless,
                slow_mo=self.cfg.slow_mo,
                viewport={"width": 1440, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
            )

        self._ctx.set_default_timeout(self.cfg.timeout)
        return self

    def __exit__(self, *exc) -> None:
        # ⚠️ 附着模式只断开 CDP 连接，绝不关闭用户自己的浏览器
        if self._ctx and not self._attached:
            self._ctx.close()
        if self._pw:
            self._pw.stop()

    @property
    def context(self) -> BrowserContext:
        assert self._ctx is not None, "请用 with Browser(cfg) as b: 语法"
        return self._ctx

    def new_page(self) -> Page:
        """新开标签页。"""
        page = self.context.new_page()
        page.set_default_timeout(self.cfg.timeout)
        return page

    def current_page(self) -> Page:
        """取当前活跃标签页 —— 「在哪个页面就填哪个」用这个，不导航、不新开。"""
        pages = [p for p in self.context.pages if not p.is_closed()]
        # 跳过 chrome:// 内部页（新标签页、设置页…），它们不是要填的目标
        real = [p for p in pages if not p.url.startswith("chrome://")]
        candidates = real or pages
        return candidates[-1] if candidates else self.new_page()

    def goto(self, url: str) -> Page:
        """打开页面并等待网络空闲（SPA 表单要等 JS 渲染完）。"""
        page = self.new_page()
        # 深链先走 domcontentloaded，SPA 的路由由下面的 networkidle 兜
        resp = page.goto(url, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            # 有些站点长连接不断，networkidle 永远等不到 —— 不算错误
            pass
        self._raise_if_blocked(page, resp)
        return page

    @staticmethod
    def _raise_if_blocked(page: Page, resp) -> None:
        """识别动态防护拦截：4xx + 空 body 是瑞数这类 WAF 的招牌响应。"""
        status = resp.status if resp else None
        if status in _BLOCKED_STATUS and len(page.content()) < _BLOCKED_BODY_MAX:
            raise SiteBlockedError(
                f"该站启用了动态防护（瑞数等）：返回 {status} 且页面内容为空，"
                f"自动化访问在入口就被拦截。\n"
                f"→ 这是预期内的（项目支持范围是北森/Moka/智联等标准校招系统）。\n"
                f"→ 请用你自己的 Chrome 手动填写该表单。\n"
                f"→ 若要用自动化：把 config.json 的 browser.cdp_url 设为 "
                f"http://localhost:9222 并附着到你的真实 Chrome。"
            )


@contextmanager
def open_browser(cfg: BrowserConfig) -> Iterator[Browser]:
    with Browser(cfg) as b:
        yield b

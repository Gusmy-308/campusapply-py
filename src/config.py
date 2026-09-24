"""配置加载：从 config.json 读取，缺项用默认值兜底。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"


@dataclass
class LLMConfig:
    """LLM 配置。

    ⚠️ 这里的默认值只在 config.json 缺对应字段时才生效。
    config.json 里写了什么，就用什么 —— 改模型请改 config.json。
    """

    provider: str = "deepseek"
    api_key: str = ""
    model: str = "deepseek-v4-flash"
    base_url: str = "https://api.deepseek.com/v1"


@dataclass
class BrowserConfig:
    headless: bool = False
    profile_dir: str = "./chrome-profile"
    slow_mo: int = 100
    timeout: int = 30000
    # 非空则进入【附着模式】：连到你正在运行的 Chrome（如 http://localhost:9222），
    # 用你自己的浏览器身份访问 —— 这是过瑞数这类动态防护的唯一姿势。
    cdp_url: str = ""


@dataclass
class AgentConfig:
    max_turns: int = 20
    temperature: float = 0.2
    max_tokens: int = 2000


@dataclass
class MatchingConfig:
    """三级匹配各级的置信度阈值。"""

    rule_confidence: float = 0.8
    semantic_confidence: float = 0.6
    llm_fallback_threshold: float = 0.5


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    matching: MatchingConfig = field(default_factory=MatchingConfig)


def load_config(path: Path | None = None) -> Config:
    path = path or CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"找不到配置文件 {path}\n"
            f"请复制 config.example.json 为 config.json 并填入 API Key"
        )

    raw = json.loads(path.read_text(encoding="utf-8"))
    cfg = Config(
        llm=LLMConfig(**raw.get("llm", {})),
        browser=BrowserConfig(**raw.get("browser", {})),
        agent=AgentConfig(**raw.get("agent", {})),
        matching=MatchingConfig(**raw.get("matching", {})),
    )

    if not cfg.llm.api_key or cfg.llm.api_key.startswith("在这里填"):
        raise ValueError("config.json 里还没填 API Key")

    # 相对路径统一转成项目根目录下的绝对路径，避免受 cwd 影响
    if not Path(cfg.browser.profile_dir).is_absolute():
        cfg.browser.profile_dir = str(ROOT / cfg.browser.profile_dir)

    return cfg

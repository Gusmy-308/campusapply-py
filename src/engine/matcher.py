"""三级匹配引擎：规则匹配 → 语义匹配 → LLM 兜底。

为什么要分级（而不是全走大模型）：
  · 规则匹配：本地查表，毫秒级、零成本，能覆盖约 80% 的字段
  · 语义匹配：字符重叠率兜住规则没覆盖的近义写法，仍然零成本
  · LLM 兜底：只有前两级都拿不准（confidence < 0.5）才调模型
这样既准又省 —— 全走 LLM 会把一次填表变成几十次 API 调用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .rules import ALL_FIELD_RULES, FieldRule

# 语义匹配的类别锚点：先判断字段属于哪个板块，再只在同板块内做重叠比对
_CATEGORY_ANCHORS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"教育|学校|院校|学历|专业"), "education"),
    (re.compile(r"实习|项目|工作|公司|科研|经历"), "experience"),
    (re.compile(r"技能|技术|证书|资质"), "skill"),
    (re.compile(r"意向|期望|求职"), "intention"),
]

# 标签清洗：去掉必填星号、提示语、括号，统一小写
_NOISE = re.compile(r"[*:\s：（）()【】\[\]]|请输入|请选择|请填写|可选|选填|必填")


@dataclass
class MatchResult:
    label: str
    value: str = ""
    matched_by: str = "none"  # rule | semantic | llm | none
    confidence: float = 0.0
    rule: FieldRule | None = None
    options: list[str] | None = None
    recommended: str | None = None

    @property
    def hit(self) -> bool:
        return bool(self.value)


@dataclass
class UserData:
    """用户信息。"""

    personal_info: dict[str, Any] = field(default_factory=dict)
    educations: list[dict[str, Any]] = field(default_factory=list)
    experiences: list[dict[str, Any]] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    # special.* 规则（自我评价/职业规划/爱好/推荐人）走这里
    special: dict[str, Any] = field(default_factory=dict)


def normalize_label(label: str) -> str:
    return _NOISE.sub("", label or "").strip().lower()


# ---------------- 值转换 ----------------

def _extract_family_name(name: str) -> str:
    if re.search(r"[一-龥]", name or ""):
        compound = ["欧阳", "司马", "上官", "皇甫", "令狐", "诸葛", "司徒", "公孙"]
        head2 = name[:2]
        return head2 if head2 in compound else name[:1]
    parts = (name or "").strip().split()
    return parts[-1] if parts else ""


def _extract_given_name(name: str) -> str:
    if re.search(r"[一-龥]", name or ""):
        compound = ["欧阳", "司马", "上官", "皇甫", "令狐", "诸葛", "司徒", "公孙"]
        head2 = name[:2]
        return name[2:] if head2 in compound else name[1:]
    parts = (name or "").strip().split()
    return " ".join(parts[:-1])


_TRANSFORMS = {
    "extractFamilyName": _extract_family_name,
    "extractGivenName": _extract_given_name,
    "joinArray": lambda v: "、".join(v) if isinstance(v, list) else str(v),
    "formatSkills": lambda v: "；".join(v) if isinstance(v, list) else str(v),
}


# ---------------- 取值 ----------------

def resolve_path(data_path: str, user: UserData) -> str:
    """把 "personalInfo.name" / "education.school" 解析成实际值。"""
    root, _, rest = data_path.partition(".")
    if root == "personalInfo":
        value = user.personal_info.get(rest, "")
    elif root == "education":
        edu = next((e for e in user.educations if e.get("isPrimary")), None) or (
            user.educations[0] if user.educations else {}
        )
        value = edu.get(rest, "")
    elif root == "experience":
        exp = user.experiences[0] if user.experiences else {}
        value = exp.get(rest, "")
    elif root == "skills":
        value = user.skills
    elif root == "special":
        value = user.special.get(rest, "")
    else:
        value = ""
    return "" if value is None else str(value)


def _apply_transform(value: str, transform: str | None) -> str:
    if not transform:
        return value
    fn = _TRANSFORMS.get(transform)
    return fn(value) if fn and value else value


# ---------------- 两级本地匹配 ----------------

def _try_rule_match(labels: list[str], user: UserData) -> MatchResult | None:
    best: tuple[float, FieldRule] | None = None

    for rule in ALL_FIELD_RULES:
        score = 0.0
        for kw in rule["keywords"]:
            k = kw.lower()
            for lbl in labels:
                if not lbl:
                    continue
                if lbl == k:
                    score = 1.0
                elif lbl in k or k in lbl:
                    # 长度越接近，越可能是同一个字段
                    ratio = min(len(lbl), len(k)) / max(len(lbl), len(k))
                    score = max(score, 0.6 + ratio * 0.4)
        if score <= 0:
            continue
        # 同分时用 priority 决胜（「姓名」优先于「名」这种宽泛词）
        if best is None or score * rule["priority"] > best[0] * best[1]["priority"]:
            best = (score, rule)

    if best is None:
        return None

    score, rule = best
    value = _apply_transform(resolve_path(rule["data_path"], user), rule.get("transform"))
    return MatchResult(label=labels[0] if labels else "", value=value,
                       matched_by="rule", confidence=score, rule=rule)


def _try_semantic_match(labels: list[str], user: UserData) -> MatchResult | None:
    joined = " ".join(labels)
    for pattern, category in _CATEGORY_ANCHORS:
        if not pattern.search(joined):
            continue
        for rule in (r for r in ALL_FIELD_RULES if r["category"] == category):
            for kw in rule["keywords"]:
                chars = list(kw.lower())
                for lbl in labels:
                    if not lbl:
                        continue
                    overlap = sum(1 for c in chars if c in lbl) / len(chars)
                    # 阈值 0.6 + 长度约束：防止「名」这种短词匹配到超长标签
                    if overlap >= 0.6 and len(lbl) <= len(kw) * 2:
                        value = _apply_transform(
                            resolve_path(rule["data_path"], user), rule.get("transform")
                        )
                        if value:
                            # 语义匹配置信度打折（0.7）—— 不如精确规则可靠
                            return MatchResult(label=labels[0], value=value,
                                               matched_by="semantic",
                                               confidence=overlap * 0.7, rule=rule)
    return None


# ---------------- 对外接口 ----------------

def match_field(
    label: str,
    user: UserData,
    placeholder: str = "",
    section: str = "",
    options: list[str] | None = None,
    rule_threshold: float = 0.8,
    semantic_threshold: float = 0.6,
) -> MatchResult:
    """单字段三级匹配（LLM 兜底由调用方决定是否触发）。"""
    labels = [x for x in (normalize_label(label), (placeholder or "").lower(), (section or "").lower()) if x]

    r = _try_rule_match(labels, user)
    if r and r.confidence >= rule_threshold:
        return _with_option(r, options)

    s = _try_semantic_match(labels, user)
    if s and s.confidence >= semantic_threshold:
        return _with_option(s, options)

    # 返回较好的那个（可能低于阈值），供上层决定要不要走 LLM
    return _with_option(r or s or MatchResult(label=label), options)


def _with_option(r: MatchResult, options: list[str] | None) -> MatchResult:
    if options and r.value:
        r.options = options
        r.recommended = pick_option(r.value, options)
    return r


def pick_option(value: str, options: list[str]) -> str | None:
    """把值对齐到下拉框的某个选项。"""
    v = (value or "").strip().lower()
    if not v:
        return None
    for o in options:
        if o.strip().lower() == v:
            return o
    for o in options:
        ol = o.strip().lower()
        if ol and (ol in v or v in ol):
            return o

    # 同义映射：性别/学历/政治面貌这类固定枚举
    synonyms = {
        "男": ["男", "男性", "male", "m", "1"],
        "女": ["女", "女性", "female", "f", "2"],
        "本科": ["本科", "大学本科", "bachelor", "undergraduate", "学士"],
        "硕士": ["硕士", "研究生", "master", "graduate", "硕士研究生"],
        "博士": ["博士", "phd", "doctor", "doctoral"],
        "共青团员": ["共青团员", "团员"],
        "中共党员": ["中共党员", "党员"],
        "全日制": ["全日制", "统招", "普通全日制"],
    }
    for canon, aliases in synonyms.items():
        if v in aliases:
            for o in options:
                if o.strip() in aliases or canon in o:
                    return o
    return None

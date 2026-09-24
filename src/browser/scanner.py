"""页面表单字段扫描。

做法：往页面里注入一段 JS，在浏览器上下文里直接读 DOM ——
这样拿到的是框架渲染之后的真实 DOM，而不是 HTML 源码里的空壳。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import Page

# 注入到页面里执行的扫描脚本。
# 同一批选择器、同一种 label 提取策略，过滤掉隐藏 / 禁用 / 按钮类元素。
_SCAN_JS = r"""
() => {
  const VISIBLE = (el) => {
    if (!el.offsetParent && el.tagName !== 'BODY') return false;
    const s = window.getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  const SELECTOR = [
    'input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=reset]):not([type=image])',
    'select',
    'textarea',
    '[contenteditable="true"]',
  ].join(',');

  const CF_ATTR = 'data-cf-id';   // 给无 id/name 的元素盖的戳（见下方 selector 生成）

  // label 提取：不同 UI 框架关联方式不同，逐级降级
  const labelOf = (el) => {
    // ① 显式 for
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l && l.innerText.trim()) return l.innerText.trim();
    }
    // ② aria-label / placeholder
    const aria = el.getAttribute('aria-label');
    if (aria && aria.trim()) return aria.trim();
    // ③ 包裹式 label
    const wrap = el.closest('label');
    if (wrap && wrap.innerText.trim()) return wrap.innerText.trim().slice(0, 60);
    // ④ Ant Design / Element UI：label 在兄弟节点
    const formItem = el.closest('.ant-form-item, .el-form-item, .moka-form-item');
    if (formItem) {
      const lab = formItem.querySelector('.ant-form-item-label, .el-form-item__label, label');
      if (lab && lab.innerText.trim()) return lab.innerText.trim();
    }
    // ⑤ 上一个兄弟元素兜底
    const prev = el.previousElementSibling;
    if (prev && prev.innerText && prev.innerText.trim().length < 40) return prev.innerText.trim();
    // ⑥ placeholder 兜底
    return (el.getAttribute('placeholder') || '').trim();
  };

  const out = [];
  document.querySelectorAll(SELECTOR).forEach((el, i) => {
    if (!VISIBLE(el)) return;
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    const label = labelOf(el) || '';

    // 无标签又无 placeholder 的，多半是搜索框/验证码之类的噪声，跳过
    if (!label && !el.getAttribute('name')) return;

    let options = null;
    if (tag === 'select') {
      options = Array.from(el.options).map((o) => o.text.trim()).filter(Boolean);
    }

    // ⚠️ 关键：没有 id/name 的元素（Ant Design 这类受控组件）必须盖一个稳定戳。
    // 扫描和填写是两次独立的 page.evaluate，中间拿不到元素引用 ——
    // 不盖戳就会出现「扫描时认得、填写时找不到」。
    const nameAttr = el.getAttribute('name') || '';
    let selector;
    if (el.id) {
      selector = `#${CSS.escape(el.id)}`;
    } else if (nameAttr) {
      selector = `[name="${CSS.escape(nameAttr)}"]`;
    } else {
      const stamp = `cf_${i}`;
      el.setAttribute(CF_ATTR, stamp);
      selector = `[${CF_ATTR}="${stamp}"]`;
    }

    out.push({
      id: el.id || nameAttr || `field_${i}`,
      label: label.slice(0, 80),
      name: nameAttr,
      tag: tag,
      type: type || tag,
      placeholder: el.getAttribute('placeholder') || '',
      required: el.hasAttribute('required') || el.getAttribute('aria-required') === 'true',
      options: options,
      currentValue: (el.value || el.innerText || '').trim().slice(0, 200),
      section: (el.closest('fieldset, .ant-card, .el-card, section')?.querySelector('h1,h2,h3,legend')?.innerText || '').trim().slice(0, 40),
      selector: selector,
    });
  });
  return out;
}
"""

# 读回某字段当前实际值（check_field 用）
_READ_JS = r"""
(args) => {
  const { id, name, selector } = args;
  let el = null;
  if (id) el = document.getElementById(id);
  if (!el && name) el = document.querySelector(`[name="${CSS.escape(name)}"]`);
  if (!el && selector) el = document.querySelector(selector);
  if (!el) return null;
  return (el.value !== undefined ? el.value : el.innerText || '').trim();
}
"""


@dataclass
class FormField:
    """页面上的一个表单字段。"""

    id: str
    label: str
    name: str = ""
    tag: str = "input"
    type: str = "text"
    placeholder: str = ""
    required: bool = False
    options: list[str] | None = None
    current_value: str = ""
    section: str = ""
    selector: str = ""
    # 运行时填充的结果（不来自页面扫描）
    filled_value: str = ""
    matched_by: str = ""
    confidence: float = 0.0
    status: str = "pending"
    error: str = ""

    @classmethod
    def from_raw(cls, raw: dict[str, Any]) -> "FormField":
        return cls(
            id=str(raw.get("id", "")),
            label=str(raw.get("label", "")),
            name=str(raw.get("name", "")),
            tag=str(raw.get("tag", "input")),
            type=str(raw.get("type", "text")),
            placeholder=str(raw.get("placeholder", "")),
            required=bool(raw.get("required")),
            options=raw.get("options"),
            current_value=str(raw.get("currentValue", "")),
            section=str(raw.get("section", "")),
            selector=str(raw.get("selector", "")),
        )

    @property
    def display(self) -> str:
        tag = f"[{self.type}]" if self.tag == "input" else f"[{self.tag}]"
        req = " *" if self.required else ""
        return f"{self.label or '(无标签)'}{req} {tag}"


def scan_fields(page: Page) -> list[FormField]:
    """扫描当前页面所有可填字段。"""
    raw = page.evaluate(_SCAN_JS)
    return [FormField.from_raw(r) for r in raw]


def read_field_value(page: Page, field_id: str, field_name: str = "",
                     selector: str = "") -> str | None:
    """读回字段当前值，用于填写后校验。"""
    return page.evaluate(_READ_JS, {"id": field_id, "name": field_name, "selector": selector})


def dump_fields(fields: list[FormField]) -> str:
    return json.dumps([f.__dict__ for f in fields], ensure_ascii=False, indent=2)

"""把值填进页面字段。

**核心难点：现代前端框架是「受控组件」** —— 直接改 el.value 不触发 React/Vue
的状态更新，表面上填进去了，一提交就没了。
解法：用原型上的原生 setter 赋值，再手动派发 input/change 事件。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from playwright.sync_api import Page

# 注入到页面里执行填充。
# 用 Object.getOwnPropertyDescriptor(...).set 拿原生 setter 绕过框架拦截，
# 然后 dispatchEvent 让框架感知到变化。
_FILL_JS = r"""
(actions) => {
  const results = [];

  const nativeSet = (el, value) => {
    const proto =
      el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype :
      el.tagName === 'SELECT'   ? HTMLSelectElement.prototype   :
                                  HTMLInputElement.prototype;
    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
    if (desc && desc.set) desc.set.call(el, value);
    else el.value = value;
  };

  const fire = (el) => {
    ['input', 'change', 'blur'].forEach((t) =>
      el.dispatchEvent(new Event(t, { bubbles: true }))
    );
  };

  for (const a of actions) {
    try {
      let el = null;
      if (a.id) el = document.getElementById(a.id);
      if (!el && a.name) el = document.querySelector(`[name="${CSS.escape(a.name)}"]`);
      if (!el && a.selector) el = document.querySelector(a.selector);

      if (!el) {
        results.push({ fieldId: a.fieldId, status: 'failed', errorMessage: '页面上找不到该字段' });
        continue;
      }
      if (el.disabled || el.readOnly) {
        results.push({ fieldId: a.fieldId, status: 'failed', errorMessage: '字段是只读/禁用状态' });
        continue;
      }

      if (el.tagName === 'SELECT') {
        // 下拉：按文本匹配选项
        const want = String(a.value).trim();
        const opt = Array.from(el.options).find(
          (o) => o.text.trim() === want || o.value.trim() === want
        );
        if (!opt) {
          results.push({ fieldId: a.fieldId, status: 'failed',
                         errorMessage: `下拉框没有「${want}」这个选项` });
          continue;
        }
        nativeSet(el, opt.value);
      } else if (el.getAttribute('contenteditable') === 'true') {
        el.focus();
        el.innerText = String(a.value);
      } else {
        el.focus();
        nativeSet(el, String(a.value));
      }

      fire(el);

      // 读回校验：确认真的写进去了
      const actual = (el.value !== undefined ? el.value : el.innerText || '').trim();
      const ok = actual === String(a.value).trim() || actual.length > 0;
      results.push({
        fieldId: a.fieldId,
        label: a.label || '',
        status: ok ? 'success' : 'failed',
        filledValue: actual,
        errorMessage: ok ? null : '赋值后读回为空，可能被框架拦截',
      });
    } catch (e) {
      results.push({ fieldId: a.fieldId, status: 'failed', errorMessage: String(e) });
    }
  }
  return results;
}
"""

# 清空已填内容
_CLEAR_JS = r"""
() => {
  const sel = 'input:not([type=hidden]):not([type=submit]):not([type=button]),select,textarea,[contenteditable="true"]';
  let n = 0;
  document.querySelectorAll(sel).forEach((el) => {
    try {
      if (el.tagName === 'SELECT') { el.selectedIndex = 0; }
      else if (el.getAttribute('contenteditable') === 'true') { el.innerText = ''; }
      else {
        const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const d = Object.getOwnPropertyDescriptor(proto, 'value');
        if (d && d.set) d.set.call(el, ''); else el.value = '';
      }
      ['input', 'change'].forEach((t) => el.dispatchEvent(new Event(t, { bubbles: true })));
      n++;
    } catch (e) {}
  });
  return n;
}
"""


@dataclass
class FillResult:
    field_id: str
    label: str = ""
    status: str = "unknown"
    filled_value: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "success"


def fill_fields(page: Page, actions: list[dict[str, Any]]) -> list[FillResult]:
    """批量填字段。actions 每项：{fieldId, id, name, selector, label, value}"""
    if not actions:
        return []
    raw = page.evaluate(_FILL_JS, actions)
    return [
        FillResult(
            field_id=str(r.get("fieldId", "")),
            label=str(r.get("label", "")),
            status=str(r.get("status", "unknown")),
            filled_value=str(r.get("filledValue", "")),
            error=str(r.get("errorMessage") or ""),
        )
        for r in raw
    ]


def fill_one(page: Page, field_id: str, value: str, name: str = "", selector: str = "",
             label: str = "") -> FillResult:
    """填单个字段。"""
    res = fill_fields(page, [{
        "fieldId": field_id, "id": field_id, "name": name,
        "selector": selector, "label": label, "value": value,
    }])
    return res[0] if res else FillResult(field_id=field_id, status="failed", error="无返回")


def clear_all(page: Page) -> int:
    """清空页面上所有已填内容。"""
    return int(page.evaluate(_CLEAR_JS))

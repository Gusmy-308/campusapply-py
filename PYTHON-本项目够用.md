# Python 速查（只看这份，够看懂本项目）

> **不用去学 Python 基础课。** 这个项目只用到下面 15 个语法点，
> 每条都配了**项目里的真实代码**，看完就能读代码。
> 排序：越靠前，出现频率越高。

---

## ① 类型标注（到处都是，但可以当注释看）

```python
def scan_fields(page: Page) -> list[FormField]:
#             ────┬───     ────────┬────────
#                 │                └─ 返回 list[FormField]
#                 └─ 参数 page 是 Page 类型

age: int = 22
name: str = "黄开拓"
```

**关键：Python 的类型标注【运行时不起作用】，纯给人看的。**

```python
x: int = "这是字符串"    # 不报错！Python 不管你
```

> Java 对照：**完全相反** —— Java 的类型是强制的，写错编译不过。
> Python 靠"自觉 + IDE 提示"，这也是为什么会有 `tsc`/`mypy` 这类工具。

**`list[dict[str, Any]]` 怎么读：**
```
list[ ... ]           列表
dict[str, Any]        字典，键是字符串，值是任意类型

合起来 = List<Map<String, Object>>   ← Java 写法
```

**`X | None`** = 可以是 X，也可以是 None
```python
model: str | None = None       # 字符串 或 空
```
> Java 的 `@Nullable String model`

---

## ② f-string（格式化字符串）

```python
return f"不存在名为 "{name}" 的工具"
```
`f"..."` 里的 `{变量}` 会被替换成变量的值。

```python
name = "黄开拓"
f"你好 {name}"              # → "你好 黄开拓"
f"{len('abc')}"             # → "3"（`{}` 里能放任何表达式）
```

> Java 对照：`String.format("你好 %s", name)`，但 f-string 更短，还能直接写表达式。

---

## ③ `.get(key, 默认值)`（字典安全取值）

```python
value = args.get("field_label", "")
#              ─┬─        ────┬─────  ─
#               │             │        └─ 键不存在时返回 ""
#               │             └─ 要取的键
#               └─ 从字典里取
```

**对比两种写法：**
```python
args["field_label"]           # 键不存在 → 抛 KeyError → 崩
args.get("field_label", "")   # 键不存在 → 返回 ""  → 安全
```

> Java 对照：`map.getOrDefault("field_label", "")`

**⭐ 这个项目中到处都在用，因为模型的参数可能缺失。**

---

## ④ `a if 条件 else b`（三元表达式）

```python
content=resp.content or "已完成"          # ① or 短路
label=labels[0] if labels else ""         # ② 三元
```

```python
# or 短路：左边是"假值"就用右边
"" or "默认"        # → "默认"
None or "默认"      # → "默认"
"有值" or "默认"    # → "有值"

# 三元：和 Java 写法【顺序相反】
x if 条件 else y     # Python（结果是 条件成立取x）
条件 ? x : y         # Java
```

**Python 里被认为是「假」的值：**
```
False、0、""、[]、{}、None      ← 这些都会触发 or 走右边
```

---

## ⑤ 列表推导式 / 字典推导式

```python
# 列表推导式
fields = [f.id for f in form_fields]
# 等价于
fields = []
for f in form_fields:
    fields.append(f.id)

# 带条件
actives = [f for f in fields if f.required]
# 等价于：只保留 required 为真的

# 字典推导式
ctx.fields = {f.id: f for f in fields}
# 等价于
ctx.fields = {}
for f in fields:
    ctx.fields[f.id] = f
```

> Java 对照：`list.stream().map(...).collect(...)`，但 Python 一行直接写。

---

## ⑥ `**` 拆包（字典 → 关键字参数）

```python
LLMConfig(**raw.get("llm", {}))
```

```python
data = {"provider": "deepseek", "model": "deepseek-v4-flash"}

LLMConfig(**data)
# 等价于
LLMConfig(provider="deepseek", model="deepseek-v4-flash")
```

> Java 对照：没有直接语法，得用反射。Python 一行搞定。

**另一种用法（字典合并）：**
```python
a = {"found": True, "value": "张三"}
b = {**a, "cached": True}
# b = {"found": True, "value": "张三", "cached": True}
```

---

## ⑦ `with` 上下文管理器（自动清理）

```python
with open_browser(cfg.browser) as browser:
    page = browser.goto(url)
    ...
# ← 离开这块，自动关闭浏览器
```

**等价于：**
```python
browser = open_browser(cfg.browser)
try:
    page = browser.goto(url)
    ...
finally:
    browser.close()          # ← 无论如何都执行
```

> Java 对照：`try (Resource r = ...) { }`（try-with-resources）

**⭐ 为什么要用：保证出异常也能清理干净。**

---

## ⑧ `@dataclass`（快速定义数据类）

```python
@dataclass
class MatchResult:
    label: str
    value: str = ""
    confidence: float = 0.0
```

**`@dataclass` 背地里生成 `__init__`：**
```python
# 等价于手写
class MatchResult:
    def __init__(self, label, value="", confidence=0.0):
        self.label = label
        self.value = value
        self.confidence = confidence
```

> Java 对照：Lombok 的 `@Data`

**⚠️ 坑：list/dict 做默认值必须写 `field(default_factory=...)`**
```python
log: list = []                        # ❌ 所有实例共享同一个列表
log: list = field(default_factory=list)  # ✅ 每个实例新建一个
```

---

## ⑨ `@property`（方法当属性用）

```python
@dataclass
class MatchResult:
    value: str = ""

    @property
    def hit(self) -> bool:
        return bool(self.value)
```

```python
r = MatchResult(value="张三")
r.hit          # → True    ← 不加括号！
r.hit()        # ❌ 报错：bool 不可调用
```

> Java 对照：`isHit()` 方法，但调用时 Java 要写 `r.isHit()`，Python 写 `r.hit`

---

## ⑩ `lambda`（匿名函数）

```python
_TRANSFORMS = {
    "joinArray": lambda v: "、".join(v) if isinstance(v, list) else str(v),
}
```

```python
lambda v: "、".join(v)      # Python
v -> String.join("、", v)   # Java
```

**⭐ 项目里用在"字典存函数"的场景。**

---

## ⑪ `"分隔符".join(列表)`（列表拼字符串）

```python
"、".join(["杭州", "绍兴"])      # → "杭州、绍兴"
"；".join(user.skills)          # → "Java；Spring Boot；MySQL"
```

> Java 对照：`String.join("、", list)`

---

## ⑫ 切片 `[起点:终点]`

```python
name[:2]      # 前 2 个字符
name[2:]      # 从第 3 个到结尾
name[-1]      # 最后一个字符
items[:20]    # 前 20 个
```

**规则：包前不包后**（`[0:2]` 取第 0、1 个，不含第 2 个）

---

## ⑬ 生成器 + `next()`（取第一个匹配项）

```python
edu = next((e for e in user.educations if e.get("isPrimary")), None)
#          ─┬─────────────────────────────────────  ─┬──
#           │                                        └─ 找不到就返回 None
#           └─ 生成器表达式：不立刻生成列表，用到才算
```

> Java 对照：
> ```java
> Education edu = educations.stream()
>     .filter(e -> Boolean.TRUE.equals(e.get("isPrimary")))
>     .findFirst().orElse(null);
> ```

---

## ⑭ `try / except`（异常处理）

```python
try:
    result = execute_tool(ctx, tc.name, tc.args)
except Exception as e:
    result = {"error": f"{type(e).__name__}: {e}"}
```

> Java 对照：`try { } catch (Exception e) { }`

**`type(e).__name__`** → 异常类名（如 `TimeoutError`）
> Java 的 `e.getClass().getSimpleName()`

**`pass`** = 什么都不做（Python 不允许空代码块）
```python
except Exception:
    pass          # 静默忽略
```

---

## ⑮ `range` / `enumerate`

```python
for turn in range(1, max_turns + 1):     # 1,2,3,...,max_turns
for i, f in enumerate(fields, 1):        # i 从 1 开始，f 是元素
```

```python
range(5)         # 0,1,2,3,4
range(1, 5)      # 1,2,3,4
```

> Java 对照：`for (int i=1; i<=n; i++)` / `for (int i=0; i<len; i++)`

---

# 🎯 自测：这 5 行你能读懂吗？

```python
① result = [f.id for f in fields if f.required]
② cfg = LLMConfig(**raw.get("llm", {}))
③ value = args.get("field_label", "") or "未知"
④ edu = next((e for e in edus if e.get("isPrimary")), None)
⑤ return f"{type(e).__name__}: {e}"
```

<details>
<summary>点开看答案</summary>

```
① 从 fields 里筛出 required 为真的，取出它们的 id，组成新列表
② 从 raw 里取 "llm" 那块（没有就用空字典），拆成参数传给 LLMConfig
③ 从 args 取 field_label（没有就返回空串）；空串是假值 → 走 or → 用 "未知"
④ 从 edus 里找第一个 isPrimary 为真的；找不到返回 None
⑤ 拼成 "异常类名: 异常内容"，比如 "TimeoutError: 等待超时"
```
</details>

---

**看完这 15 条，你就能读这个项目的所有代码了。**
**哪条还是绕，告诉我编号，我换种说法讲。**

# 代码学习路线（LEARNING.md）

> 目标：**看完能像自己写过一样**，清楚每行代码为什么存在。
> 原则：**按依赖顺序自底向上** —— 每个文件只用它下面已经学过的文件，绝不往上跳。

---

## 一、为什么之前会乱

我一开始按「文件名」讲，但文件之间有依赖：

```
讲 agent.py  →  引用了 fill_tools.py（没讲过）
讲 fill_tools.py  →  引用了 matcher.py（没讲过）
讲 matcher.py  →  引用了 rules.py（没讲过）
```

**跳来跳去，你当然跟不上。**

**正确顺序**：先讲「不依赖任何自己代码」的，再讲「只依赖已讲过的」。

---

## 二、全景依赖图

```
                    main.py (230)          ← 第 10 课：CLI 入口
                        │
        ┌───────────────┼───────────────┐
        ↓               ↓               ↓
   agent.py (191)  fill_tools.py (207)  config.py (78)
        │               │                   ↑
        │        ┌──────┼──────┬────────────┘
        │        ↓      ↓      ↓
        │   scanner  filler  matcher  llm        ← 第 3/4/6/7 课
        │   (165)    (160)   (239)   (88)
        │      │       │       │       │
        │      └───┬───┘       ↓       │
        │          ↓        rules (71) │
        │      driver (75)       ↑     │
        │          ↑             │     │
        └──────────┴─────────────┴─────┘
                   │
              config.py (78)              ← 第 1 课：所有东西的地基
```

---

## 三、10 个 Lesson

| # | 文件 | 行数 | 依赖谁 | 学完能干什么 |
|---|------|------|--------|------------|
| **1** | `src/config.py` | 78 | 无 | 理解配置怎么从 JSON 变成对象 |
| **2** | `src/browser/driver.py` | 75 | config | **能用代码打开一个网页** |
| **3** | `src/browser/scanner.py` | 165 | driver | **能扫出页面上的所有表单字段** |
| **4** | `src/browser/filler.py` | 160 | driver | **能把值填进页面**（含受控组件坑）|
| **5** | `src/engine/rules.py` | 71 | 无 | 理解 50 条规则表的结构 |
| **6** | `src/engine/matcher.py` | 239 | rules | **能把「姓名」匹配成「黄开拓」** |
| **7** | `src/engine/llm.py` | 88 | config | **能调通大模型**（含 Function Calling）|
| **8** | `src/tools/fill_tools.py` | 207 | 3,4,6,7 | 理解「工具」是什么（说明书 + 执行器）|
| **9** | `src/engine/agent.py` | 191 | 8 | **理解 Agent 主循环**（最有价值）|
| **10** | `src/main.py` | 230 | 全部 | 把上面全部串成 CLI 命令 |

**分两批走**（消化不了就停）：

```
第一批（能动手操作页面）：1 → 2 → 3 → 4
  学完你就能：写个脚本打开网页、扫字段、填表

第二批（能思考决策）：5 → 6 → 7 → 8 → 9 → 10
  学完你就能：理解 Agent 怎么自主填表
```

---

## 四、每个 Lesson 的学法（四步）

```
① 这一步要解决什么问题？      ← 我先讲背景
② 最小实现长什么样？          ← 我写 15-30 行的极简版
③ 项目里的完整版多了什么？     ← 对照真实代码
④ 跑一下验证                  ← 你亲手执行，看到结果
```

**每课结束都有一个可执行的命令** —— 看到效果才算学会。

---

## 五、Java → Python 速查（你会 Java，这些对照记住就够）

### 包与导入

| Java | Python |
|---|---|
| `package com.example;` | 目录 + `__init__.py` |
| `import com.example.Foo;` | `from .foo import Foo`（相对）<br>`from src.engine.foo import Foo`（绝对）|
| 无相对导入概念 | `.` = 当前包，`..` = 上一层 |
| `public class Foo` 一个文件一个类 | **一个文件可放多个类/函数**，文件名全小写 |

### 语法

| Java | Python |
|---|---|
| `List<Map<String,Object>>` | `list[dict[str, Any]]` |
| `map.getOrDefault(k, d)` | `d.get(k, d)` |
| `x != null ? a : b` | `a if x else b` |
| `for (int i=1; i<=n; i++)` | `for i in range(1, n+1)` |
| `list.stream().filter().findFirst()` | `next((x for x in lst if cond), None)` |
| `String.join("、", list)` | `"、".join(lst)` |
| `new HashMap<>(a); put(k,v)` | `{**a, k: v}` |
| `throw new X()` | `raise X()` |
| `@Data` (Lombok) | `@dataclass` |
| `obj.getter()` | `@property` 装饰 → `obj.attr` |
| `instanceof` | `isinstance(x, T)` |
| `e.getClass().getSimpleName()` | `type(e).__name__` |
| 三元 `a ? b : c` | `b if a else c` |
| 默认参数只求值一次 → 可变默认值要小心 | **同左，list/dict 必须 `field(default_factory=list)`** |

### 环境

| Java | Python |
|---|---|
| `pom.xml` | `requirements.txt` |
| `~/.m2/repository`（全局） | **`.venv/`（每项目一份）** |
| `mvn install` | `pip install -r requirements.txt` |
| `java -cp ...` | `python -m 包.模块` |

**⭐ 一条铁律：代码里有 `from .xxx import` 时，必须用 `python -m src.main` 跑，不能用 `python src/main.py`。**

---

## 六、学习时的检查点

每学完一课，问自己三个问题：

```
① 这个文件接收什么、返回什么？（输入输出）
② 它依赖谁？（只能是已学过的）
③ 如果抽掉它，项目会怎样？（理解它存在的必要性）
```

**第 ③ 个问题最重要 —— 它能让你记住"为什么需要这个文件"，而不是"这个文件里有什么"。**

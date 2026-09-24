# CampusApply-Py · 校招网申表单自动填充

把校招网申页面上几十个表单字段，用「本地规则 → 语义匹配 → 大模型兜底」三级降级自动填好。

起因很实际：2027 届秋招投递量上来之后，每家都要重填一遍几乎相同的个人信息，纯手工填表成了最大的时间消耗。

**Python + Playwright + 大模型 Function Calling**，约 1600 行。

> ⚠️ 本工具**只填不提交**。短信/图形验证码、实名认证、附件上传一律由本人手动完成。

---

## 两种填充模式

| 模式 | 命令 | 适用场景 |
|---|---|---|
| **Workflow** | `python -m src.main fill` | 表单结构规整。步骤写死（扫描→匹配→填充→统计），快、省 token |
| **Agent** | `python -m src.main agent` | 结构未知或字段刁钻。只给目标，模型自主决定调哪个工具、调几次、何时停 |

Agent 模式基于 Function Calling 实现，四个工具构成闭环：

```
scan_form  →  get_user_data  →  fill_field  →  check_field
 扫描字段       语义查值          写入页面        读回校验
```

几个工程细节：

- **工具描述就是 Prompt** —— `description` 里写清楚「什么时候用我」，直接决定模型选得准不准
- **白名单校验** —— 模型可能幻觉出不存在的工具名，命中不了白名单就返回可用列表让它自己纠正
- **错误回填** —— 工具报错不中断循环，把错误当结果回填，让模型自己决定重试还是换方案
- **两道终止条件** —— 模型不再调工具即完成；触达最大轮次强制退出，防死循环

---

## 三级降级匹配引擎

全走大模型会把一次填表变成几十次 API 调用，所以做了分层：

| 级别 | 手段 | 成本 | 置信度 |
|---|---|---|---|
| ① 规则 | 50+ 条字段规则查表，标签归一化后比对（去星号/提示语/括号） | 零 | 0.8+ |
| ② 语义 | 先按类别锚点（教育/经历/技能/意向）判定板块，再在同板块内做字符重叠比对 | 零 | 0.6+ |
| ③ LLM | 前两级都拿不准才调模型 | 有 | 0.7 |

约 **80% 的字段由前两级本地解决**。置信度低于阈值直接跳过 —— **宁可不填，不可错填**：填错一个手机号比空着更糟。

下拉框另做同义对齐（`男` / `男性` / `Male` / `1` → 页面上真实存在的那个选项）。

---

## ⭐ 两个踩坑记录

### 1. WAF 认的是「浏览器身份」，不是「登录态」

瑞数这类动态防护会拦截自动化访问：返回 `412` + 空 body。

一开始以为是登录态问题，用 `launch_persistent_context` 复用 `user-data-dir`（cookie、localStorage 全在）—— **照样 412**。

原因是：`user-data-dir` 复用的是**存储**，不是**进程指纹**。TLS 指纹、JS 引擎特征、进程环境全都变了，WAF 认的是后者。

**解法**：`connect_over_cdp` 附着到用户**正在运行的真实 Chrome**，请求由真实浏览器发出，身份无从识别。

```bash
# 用调试端口启动 Chrome（Chrome 136+ 禁止对默认 profile 开调试口，所以要指定 --user-data-dir）
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="$HOME/.chrome-cdp-profile" --remote-debugging-port=9222

# 然后走附着模式，--current 表示操作你当前打开的标签页
python -m src.main scan --current
python -m src.main fill --current
```

实测：独立进程打开某银行网申页 = `400/412` 空页；附着到真实 Chrome = 完整表单，正常填充。

> `config.json` 的 `browser.cdp_url` 留空则回退到独立进程模式。

### 2. 扫描和填写是两次独立的页面执行，中间拿不到元素引用

Ant Design 这类框架的 `input` 没有 `id`、没有 `name`，扫描时认得出，填写时 `document.querySelector` 却定位不到 —— 因为两次 `page.evaluate` 之间元素引用早失效了。

**解法**：扫描时给这类元素盖一个稳定戳：

```js
el.setAttribute('data-cf-id', `cf_${i}`);   // 扫描时盖戳
selector = `[data-cf-id="cf_${i}"]`;        // 填写时按戳定位
```

不加这步的现象就是「扫描时认得、填写时找不到」。

---

## 快速开始

```bash
git clone https://github.com/Gusmy-308/campusapply-py.git
cd campusapply-py

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp config.example.json config.json     # 填入你的 LLM API Key
# 准备 data/profile.json（见下）
```

### 准备个人信息

`data/profile.json` **不在版本库里**（含身份证号、住址、家人联系方式等，绝不入库）。

本工具的字段规则通过 `resolve_path()` 约定 `personalInfo.* / education.* / experience.* / skills / special.*` 这套结构，用 `sync_profile.py` 从你自己的资料源单向生成：

```bash
# 默认读 ~/秋招材料/profile.json，输出到 data/profile.json
python sync_profile.py

# 或指定路径
python sync_profile.py <源文件> <输出文件>
```

> ⚠️ `data/profile.json` 是**生成物**，不要手改 —— 下次同步会被覆盖。要改就改源文件。

### 运行

```bash
python -m src.main test                     # 自检：LLM 连通性 + Function Calling + 资料加载
python -m src.main scan  <url>              # 只扫描，看看页面上有哪些字段
python -m src.main fill  <url>              # Workflow 模式填充
python -m src.main agent <url>              # Agent 模式填充
# 以上三个都支持 --current，操作当前标签页（附着模式专用）
```

---

## 目录结构

```
src/
├── main.py                 CLI 入口（test / scan / fill / agent）
├── config.py               配置加载
├── engine/
│   ├── rules.py            字段规则表（关键词 → 数据路径 → 转换函数）
│   ├── matcher.py          三级降级匹配 + 下拉选项同义对齐
│   ├── llm.py              LLM 客户端（OpenAI 兼容接口），tool_calls 归一化
│   └── agent.py            Agent 主循环 + Workflow 固定流程
├── browser/
│   ├── driver.py           Playwright 封装：CDP 附着模式 / 独立进程模式
│   ├── scanner.py          注入 JS 扫描表单字段，给无 id/name 的元素盖戳
│   └── filler.py           注入 JS 填充，原生 setter 绕过框架拦截
└── tools/
    └── fill_tools.py       Agent 的四个工具：定义（给模型看）+ 执行器

sync_profile.py             从资料源单向生成 data/profile.json
peek.mjs                    给「真实 Chrome」装眼睛：Node 直连 CDP 看页面/点元素
LEARNING.md                 按依赖序写的学习路径（先读哪个文件、为什么）
```

---

## 已知限制

- **动态防护站点**：独立进程模式会被瑞数类 WAF 拦截（返回 412）。需改用 CDP 附着模式；附着也过不去的，请手动填写
- **只覆盖输入类控件**：文件上传、图形/短信验证码、实名认证不处理
- **受控组件**：用原型链原生 setter + 派发 `input`/`change` 事件绕过 React/Vue 拦截；若某站点仍填不进去，通常是它用了更特殊的受控逻辑
- **日期控件**：Ant Design 的 `DatePicker` 是 `readonly`，不能直接赋值，需用 CDP 真实鼠标事件（`Input.dispatchMouseEvent`）点击，尚未并入 `filler.py`

---

## 说明

本项目为个人秋招期间自用的工具，仅用于**填写自己的**网申信息，不做批量刷投。

`LICENSE`: 未指定。

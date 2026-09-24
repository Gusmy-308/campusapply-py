"""把「唯一事实源」转换成本工具的用户数据结构。

用法：
    python sync_profile.py                    # 用默认路径
    python sync_profile.py <源文件> <输出文件>

背景：
    网申资料只有一个事实源 —— `~/秋招材料/profile.json`（改一处，全局生效）。
    本工具需要的是另一种 schema（personalInfo / educations / experiences / skills / special），
    所以用本脚本【单向生成】，绝不要反过来手改 data/profile.json（会被覆盖）。

    ⚠️ 事实源变了 → 重跑一次本脚本即可。

数据结构来源：src/engine/rules.py 的 50 条规则（data_path）+ src/engine/matcher.py 的 resolve_path
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = Path.home() / "秋招材料" / "profile.json"
DEFAULT_OUTPUT = ROOT / "data" / "profile.json"

# 事实源里没有、但表单常问的补充项（改这里就行）
FALLBACK = {
    "nameEn": "Huang Kaituo",
    "github": "https://github.com/Gusmy-308",
    "targetCities": ["杭州", "宁波", "绍兴", "南昌", "上饶"],
    "gpaTotal": "100",
    "cet4": "434",
    # 紧急联系人默认填哪一位（网申表一般只要一个）
    "emergencyContactKey": "母亲",
    # 「现居城市」类字段要的是城市名，不是完整地址
    "currentCity": "绍兴市",
}


def _split_positions(raw: str) -> list[str]:
    """'软件开发 / IT技术支持 / AI应用开发' → ['软件开发', 'IT技术支持', 'AI应用开发']"""
    return [p.strip() for p in raw.replace("｜", "|").split("/") if p.strip()]


def build_personal(src: dict) -> dict:
    b = src["basic"]
    # 紧急联系人：拆成三格（姓名/关系/电话），规则一一对应
    contacts = b.get("紧急联系人", {})
    ec = contacts.get(FALLBACK["emergencyContactKey"]) or next(iter(contacts.values()), {})
    return {
        "name": b["姓名"],
        "nameEn": FALLBACK["nameEn"],
        "gender": b["性别"],
        "birthDate": b["出生日期"],
        "age": b["年龄"],
        "phone": b["手机"],
        "email": b["邮箱"],
        "idNumber": b["身份证号"],
        "ethnicity": b["民族"],
        "politicalStatus": b["政治面貌"],
        "nativePlace": b["籍贯"],
        # ⚠️ 三级别混用：「所在城市」要城市名，地址类字段要完整地址
        "currentCity": FALLBACK["currentCity"],
        "currentAddress": b["现居地"],
        "mailingAddress": b["通信地址"],
        "postalCode": b["邮政编码"],
        "github": FALLBACK["github"],
        # 微信号请在【事实源】basic.微信号 里补，这里只做透传
        "wechat": b.get("微信号", ""),
        "targetCities": FALLBACK["targetCities"],
        "targetPositions": _split_positions(b["求职意向"]),
        # 期望薪资填「兜底值」—— 面议在表单里填不进去
        "expectedSalary": b["期望薪资（必填兜底）"],
        "availableDate": b["可到岗时间"],
        "height": b["身高"],
        "weight": b["体重"],
        "maritalStatus": b["婚姻状况"],
        "health": b["健康状况"],
        "isFreshGraduate": b["是否应届毕业生"],
        "emergencyName": ec.get("姓名", ""),
        "emergencyRelation": ec.get("关系", ""),
        "emergencyPhone": ec.get("电话", ""),
        "emergencyContact": "；".join(
            f'{v["姓名"]}（{v["关系"]}）{v["电话"]}' for v in contacts.values()
        ),
    }


def build_educations(src: dict) -> list[dict]:
    """教育经历。只有第一条 isPrimary=True（resolve_path 优先取它）。"""
    educations = []
    for i, e in enumerate(src.get("education", [])):
        educations.append({
            "isPrimary": i == 0,
            "school": e.get("学校", ""),
            "college": e.get("学院", ""),
            "major": e.get("专业", ""),
            "type": e.get("学历", ""),
            "degree": e.get("学位", ""),
            "startDate": e.get("开始时间", ""),
            "endDate": e.get("结束时间", ""),
            "gpa": e.get("学分绩", ""),
            "gpaTotal": FALLBACK["gpaTotal"] if e.get("学分绩") else "",
            "ranking": e.get("专业排名", ""),
            "cet4": FALLBACK["cet4"] if i == 0 else "",
            "cet6": "",
            "trainingMode": "全日制" if e.get("是否全日制") == "是" else "",
            "mainCourses": e.get("主修课程", ""),
            "description": e.get("专业描述", ""),
            # 获奖挂在教育经历上（规则 education.awards）
            "awards": [a["奖励名称"] + f'（{a["获奖时间"]}）' for a in src.get("awards", [])] if i == 0 else [],
        })
    return educations


def build_experiences(src: dict) -> list[dict]:
    """实习 + 项目，合并成一个列表。

    ⚠️ 规则里 experience.* 只解析 experiences[0] —— 所以【实习必须排第一】。
       项目类字段靠语义匹配 + LLM 兜底（它们能看到完整数据）。
    """
    experiences = []

    # ① 实习（必须第一）
    for it in src.get("internship", []):
        experiences.append({
            "organization": it.get("公司", ""),
            "role": it.get("岗位", ""),
            "startDate": it.get("入职", "")[:7],      # 2026-05-19 → 2026-05
            "endDate": it.get("离职", "")[:7],
            "location": "深圳",
            "description": it.get("工作描述（长）", ""),
            "achievements": [
                "PVD 蒸镀机联机接口开发 + 文档交付",
                "线上 CPU 飙高治理：接口请求量降低 66%",
                "MySQL GET_LOCK 命名锁解决并发抢号",
                "金蝶 ERP 自动领料闭环 + WMS 物流状态机",
                "累计处理 16+ 线上问题",
            ],
            "techStack": ["Java", "MySQL", "Redis"],
        })

    # ② 项目（跳过与实习重复的 MES 那条）
    for p in src.get("projects", []):
        if "MES" in p.get("项目名称", ""):
            continue  # 与上方实习重复，内容已并入
        experiences.append({
            "organization": p.get("项目名称", ""),
            "role": p.get("角色", ""),
            "startDate": p.get("时间", "").split("-")[0],
            "endDate": p.get("时间", "").split("-")[-1],
            "location": "",
            "description": p.get("项目简述", ""),
            "achievements": [p["面试价值"]] if p.get("面试价值") else [],
            "techStack": [t.strip() for t in p.get("技术栈", "").split("、") if t.strip()],
        })

    return experiences


def build_skills(src: dict) -> list[str]:
    """技能列表。formatSkills 变换会用「；」拼接。"""
    s = src.get("skills", {})
    skills = []
    if s.get("技能特长"):
        # 长文本按「；」拆成条目，表单里更好用
        skills += [x.strip() for x in s["技能特长"].split("；") if x.strip()]
    if s.get("证书"):
        skills.append(s["证书"])
    if s.get("其他证书"):
        skills.append(s["其他证书"])
    return skills


def build_special(src: dict) -> dict:
    """自我评价 / 职业规划 / 爱好 —— ⚠️ 需要 matcher.resolve_path 支持 special 分支。"""
    q = src.get("open_questions", {})
    role = src.get("campus_role", {})
    return {
        "selfIntroduction": q.get("自我评价（通用版）", ""),
        "selfIntroductionAI": q.get("自我评价（AI岗版）", ""),   # 投 AI 岗时可手动换过来
        "careerPlan": q.get("职业规划（5年）", ""),
        "hobbies": q.get("爱好", ""),
        "campusRole": f'{role.get("职务", "")}（{role.get("时间", "")}），{role.get("责任成就", "")}',
        "strengths": q.get("优点", []),
        "weakness": q.get("缺点", ""),
        "setback": q.get("挫折经历", ""),
    }


def convert(src: dict) -> dict:
    return {
        "personalInfo": build_personal(src),
        "educations": build_educations(src),
        "experiences": build_experiences(src),
        "skills": build_skills(src),
        "special": build_special(src),
    }


def main() -> int:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT

    if not source.exists():
        print(f"❌ 找不到事实源：{source}")
        return 1

    src = json.loads(source.read_text(encoding="utf-8"))
    if "basic" not in src:
        print(f"❌ {source} 看起来不是事实源（缺少 basic 字段）")
        return 1

    out = convert(src)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ 已生成 {output}")
    print(f"   来源：{source}")
    print(f"   personalInfo  {len(out['personalInfo'])} 个字段")
    print(f"   educations    {len(out['educations'])} 段")
    print(f"   experiences   {len(out['experiences'])} 段（{out['experiences'][0]['organization']} 优先）")
    print(f"   skills        {len(out['skills'])} 条")
    print(f"   special       {len(out['special'])} 个字段")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""字段映射规则表 —— 从 TS 版 fieldMappingRules.ts 自动搬运，保证两版口径一致。

共 50 条规则、408 个关键词。
如需新增字段，直接往列表里加 dict 即可。
"""

from __future__ import annotations

from typing import Any, TypedDict


class FieldRule(TypedDict, total=False):
    keywords: list[str]
    data_path: str
    category: str
    priority: int
    transform: str


ALL_FIELD_RULES: list[FieldRule] = [
    {"keywords": ["姓名", "真实姓名", "名字", "中文名", "全名", "考生姓名", "申请人姓名", "您的姓名", "name", "full name", "your name"], "data_path": "personalInfo.name", "category": "basic", "priority": 100},
    {"keywords": ["英文名", "英文姓名", "拼音", "姓名拼音", "english name", "name in english"], "data_path": "personalInfo.nameEn", "category": "basic", "priority": 90},
    {"keywords": ["姓氏", "姓", "last name", "family name", "surname"], "data_path": "personalInfo.name", "category": "basic", "priority": 80, "transform": "extractFamilyName"},
    {"keywords": ["名", "first name", "given name"], "data_path": "personalInfo.name", "category": "basic", "priority": 80, "transform": "extractGivenName"},
    {"keywords": ["性别", "男/女", "男女", "gender", "sex"], "data_path": "personalInfo.gender", "category": "basic", "priority": 100},
    {"keywords": ["出生日期", "出生年月", "生日", "出生年月日", "出生时间", "birth date", "date of birth", "birthday", "dob"], "data_path": "personalInfo.birthDate", "category": "basic", "priority": 100},
    {"keywords": ["手机", "手机号", "手机号码", "联系电话", "电话号码", "移动电话", "联系方式", "联系手机", "phone", "mobile", "tel", "telephone", "phone number", "cell phone"], "data_path": "personalInfo.phone", "category": "basic", "priority": 100},
    {"keywords": ["邮箱", "电子邮箱", "邮件", "电子邮件", "email", "e-mail", "email address"], "data_path": "personalInfo.email", "category": "basic", "priority": 100},
    {"keywords": ["身份证", "身份证号", "身份证号码", "证件号", "证件号码", "id number", "id card", "identity"], "data_path": "personalInfo.idNumber", "category": "basic", "priority": 95},
    {"keywords": ["民族", "族别", "ethnicity", "ethnic group", "nationality"], "data_path": "personalInfo.ethnicity", "category": "basic", "priority": 90},
    {"keywords": ["政治面貌", "政治身份", "党派", "political status", "political affiliation"], "data_path": "personalInfo.politicalStatus", "category": "basic", "priority": 90},
    {"keywords": ["籍贯", "户籍", "户籍所在地", "户口所在地", "原籍", "native place", "hometown", "place of origin", "birthplace"], "data_path": "personalInfo.nativePlace", "category": "basic", "priority": 85},
    {"keywords": ["现居城市", "居住城市", "现居住地", "当前所在地", "目前所在城市", "所在城市", "所在地区", "常住地", "current city", "current location", "location", "city"], "data_path": "personalInfo.currentCity", "category": "basic", "priority": 80},
    {"keywords": ["微信", "微信号", "微信账号", "wechat", "weixin"], "data_path": "personalInfo.wechat", "category": "basic", "priority": 85},
    {"keywords": ["linkedin", "领英", "linkedin链接", "linkedin url", "linkedin profile"], "data_path": "personalInfo.linkedin", "category": "basic", "priority": 80},
    {"keywords": ["github", "github链接", "github url", "github profile", "代码仓库"], "data_path": "personalInfo.github", "category": "basic", "priority": 80},
    {"keywords": ["作品集", "个人作品", "作品链接", "个人网站", "个人主页", "博客", "portfolio", "personal website", "blog", "website"], "data_path": "personalInfo.portfolio", "category": "basic", "priority": 75},
    {"keywords": ["意向城市", "期望城市", "期望工作城市", "工作城市", "工作地点", "期望工作地", "意向工作地", "preferred city", "work location", "desired location"], "data_path": "personalInfo.targetCities", "category": "intention", "priority": 85, "transform": "joinArray"},
    {"keywords": ["意向岗位", "期望岗位", "应聘岗位", "申请岗位", "意向职位", "期望职位", "目标岗位", "preferred position", "desired position", "target position", "applied position"], "data_path": "personalInfo.targetPositions", "category": "intention", "priority": 85, "transform": "joinArray"},
    {"keywords": ["期望薪资", "期望薪酬", "薪资期望", "薪资要求", "期望月薪", "薪资范围", "expected salary", "salary expectation", "desired salary"], "data_path": "personalInfo.expectedSalary", "category": "intention", "priority": 80},
    {"keywords": ["到岗时间", "最早到岗", "可到岗", "入职时间", "可入职时间", "到岗日期", "available date", "start date", "availability"], "data_path": "personalInfo.availableDate", "category": "intention", "priority": 80},
    {"keywords": ["学校", "毕业院校", "院校", "所学学校", "就读学校", "本科学校", "硕士学校", "毕业学校", "大学", "所在学校", "school", "university", "college", "institution"], "data_path": "education.school", "category": "education", "priority": 100},
    {"keywords": ["学院", "院系", "所在学院", "所属学院", "faculty", "department", "school/college"], "data_path": "education.college", "category": "education", "priority": 90},
    {"keywords": ["专业", "所学专业", "主修专业", "就读专业", "专业名称", "专业方向", "major", "field of study", "discipline", "specialization"], "data_path": "education.major", "category": "education", "priority": 100},
    {"keywords": ["学历", "最高学历", "学历层次", "学位", "学历学位", "学位类别", "degree", "education level", "qualification"], "data_path": "education.type", "category": "education", "priority": 95},
    {"keywords": ["入学时间", "入学日期", "开始时间", "就读开始", "start date", "enrollment date", "from"], "data_path": "education.startDate", "category": "education", "priority": 85},
    {"keywords": ["毕业时间", "毕业日期", "预计毕业", "结束时间", "毕业年月", "graduation date", "end date", "expected graduation", "to"], "data_path": "education.endDate", "category": "education", "priority": 85},
    {"keywords": ["gpa", "绩点", "平均绩点", "平均成绩", "学分绩", "学业成绩", "成绩绩点", "grade point average"], "data_path": "education.gpa", "category": "education", "priority": 95},
    {"keywords": ["gpa满分", "绩点满分", "满分绩点", "gpa total", "gpa scale", "out of"], "data_path": "education.gpaTotal", "category": "education", "priority": 85},
    {"keywords": ["排名", "专业排名", "年级排名", "全班排名", "成绩排名", "名次", "ranking", "rank", "class rank"], "data_path": "education.ranking", "category": "education", "priority": 90},
    {"keywords": ["四级", "cet4", "cet-4", "英语四级", "大学英语四级", "四级成绩", "四级分数"], "data_path": "education.cet4", "category": "education", "priority": 90},
    {"keywords": ["六级", "cet6", "cet-6", "英语六级", "大学英语六级", "六级成绩", "六级分数"], "data_path": "education.cet6", "category": "education", "priority": 90},
    {"keywords": ["雅思", "ielts", "雅思成绩", "雅思分数"], "data_path": "education.ielts", "category": "education", "priority": 85},
    {"keywords": ["托福", "toefl", "托福成绩", "托福分数"], "data_path": "education.toefl", "category": "education", "priority": 85},
    {"keywords": ["培养方式", "学习方式", "学制", "全日制", "training mode", "study mode"], "data_path": "education.trainingMode", "category": "education", "priority": 80},
    {"keywords": ["主修课程", "核心课程", "主要课程", "专业课程", "相关课程", "courses", "major courses", "relevant courses"], "data_path": "education.mainCourses", "category": "education", "priority": 75, "transform": "joinArray"},
    {"keywords": ["在校获奖", "校内荣誉", "获奖情况", "荣誉称号", "奖项", "所获奖项", "获奖经历", "awards", "honors", "achievements"], "data_path": "education.awards", "category": "education", "priority": 80, "transform": "joinArray"},
    {"keywords": ["公司", "公司名称", "实习公司", "单位", "单位名称", "企业名称", "组织", "工作单位", "实习单位", "company", "company name", "organization", "employer"], "data_path": "experience.organization", "category": "experience", "priority": 100},
    {"keywords": ["岗位", "职位", "岗位名称", "实习岗位", "职位名称", "担任职务", "角色", "任职岗位", "position", "title", "role", "job title"], "data_path": "experience.role", "category": "experience", "priority": 100},
    {"keywords": ["实习开始", "工作开始", "开始时间", "起始时间", "入职时间", "start date", "from", "begin date"], "data_path": "experience.startDate", "category": "experience", "priority": 80},
    {"keywords": ["实习结束", "工作结束", "结束时间", "离职时间", "end date", "to", "finish date"], "data_path": "experience.endDate", "category": "experience", "priority": 80},
    {"keywords": ["工作地点", "实习地点", "办公地点", "工作城市", "work location", "office location"], "data_path": "experience.location", "category": "experience", "priority": 75},
    {"keywords": ["工作内容", "工作描述", "职责描述", "主要职责", "岗位职责", "工作职责", "实习内容", "核心职责", "job description", "responsibilities", "description", "duties"], "data_path": "experience.description", "category": "experience", "priority": 90},
    {"keywords": ["工作成果", "工作业绩", "主要成果", "项目成果", "取得成绩", "achievements", "accomplishments", "results"], "data_path": "experience.achievements", "category": "experience", "priority": 85, "transform": "joinArray"},
    {"keywords": ["技术栈", "使用技术", "技术工具", "技术关键词", "关键技能", "tech stack", "technologies", "skills used", "tools"], "data_path": "experience.techStack", "category": "experience", "priority": 75, "transform": "joinArray"},
    {"keywords": ["自我评价", "自我介绍", "个人简介", "个人介绍", "自述", "个人概述", "自我描述", "self introduction", "about me", "self assessment", "summary", "personal statement"], "data_path": "special.selfIntroduction", "category": "other", "priority": 70},
    {"keywords": ["职业规划", "职业发展", "个人规划", "发展计划", "未来规划", "career plan", "career goal"], "data_path": "special.careerPlan", "category": "other", "priority": 60},
    {"keywords": ["兴趣爱好", "爱好", "个人爱好", "特长", "兴趣特长", "hobbies", "interests", "hobby"], "data_path": "special.hobbies", "category": "other", "priority": 60},
    {"keywords": ["专业技能", "个人技能", "技能特长", "核心技能", "专业能力", "资质证书", "专业证书", "所获证书", "skills", "certifications", "certificates", "qualifications"], "data_path": "skills", "category": "skill", "priority": 75, "transform": "formatSkills"},
    {"keywords": ["推荐人", "推荐人姓名", "引荐人", "reference", "referral", "referee"], "data_path": "special.reference", "category": "other", "priority": 50},
    # 紧急联系人：网申表几乎都拆成三格，规则必须分开，否则 LLM 兜底会把姓名/关系/电话串格
    # ⚠️ 顺序不能动：先具体、后笼统（"紧急联系人与本人关系" 也含 "紧急联系人"）
    {"keywords": ["紧急联系人与本人关系", "与本人关系", "紧急联系人关系", "联系人关系"], "data_path": "personalInfo.emergencyRelation", "category": "basic", "priority": 92},
    {"keywords": ["紧急联系人手机号", "紧急联系人手机", "紧急联系人电话", "联系人手机号"], "data_path": "personalInfo.emergencyPhone", "category": "basic", "priority": 92},
    {"keywords": ["紧急联系人姓名", "紧急联系人", "联系人姓名"], "data_path": "personalInfo.emergencyName", "category": "basic", "priority": 91},
    # 体征
    {"keywords": ["身高", "height"], "data_path": "personalInfo.height", "category": "basic", "priority": 88},
    {"keywords": ["体重", "weight"], "data_path": "personalInfo.weight", "category": "basic", "priority": 88},
    # 地址：通讯/通信 在前（更具体），现居/详细 在后
    {"keywords": ["通讯地址", "通信地址", "联系地址", "邮寄地址", "mailing address"], "data_path": "personalInfo.mailingAddress", "category": "basic", "priority": 87},
    {"keywords": ["现居地址", "现居住地址", "居住地址", "详细地址", "家庭地址", "现住址", "home address"], "data_path": "personalInfo.currentAddress", "category": "basic", "priority": 87},
]

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
八字人物卡牌生成器（card.py）

把 paipan.py 的排盘结果，拼装成 3:4 竖版「人物卡牌」：
  - 形象出图 Prompt（外貌 × 神态 × 身强弱 × 五行配色）
  - 文字分析（核心优势 / 性格弱点 / 性格总评 / 当下心态）

依赖：与 paipan.py 相同（sxtwl），且需与 paipan.py 同目录。

用法：
    python3 card.py --date 1990-05-20 --time 14:30 --gender 男 --city 北京 --zwt 116.4
    python3 card.py --date 1990-05-20 --time 14:30 --gender 男 --json
"""

import argparse
import json
from datetime import datetime

import paipan  # 复用排盘引擎的常量与函数

# =====================================================================
# 一、数据表（依据 cardskill.md 设计框架，逐条硬编码）
# =====================================================================

# 3.1 日主外貌基础层
GAN_APPEARANCE = {
    "甲": {"face": "长鹅蛋脸 / 长方脸", "features": "眉骨高、眉浓修长、眼细长有神、鼻梁直",
           "body": "高挑修长、肩宽", "aura": "正气爽朗、有威严"},
    "乙": {"face": "瓜子脸 / 小圆脸", "features": "弯眉、桃花眼 / 杏眼、唇厚薄适中",
           "body": "纤细匀称、柔性体态", "aura": "温婉耐看、亲和力"},
    "丙": {"face": "圆脸 / 方圆脸", "features": "大眼亮眼、眉上扬、唇红润",
           "body": "饱满厚实、精气神外放", "aura": "阳光热情、有感染力"},
    "丁": {"face": "尖鹅蛋脸 / 窄长小脸", "features": "眼深邃狭长、眸含光、眉细",
           "body": "苗条清瘦、骨架小", "aura": "清冷内敛、越细看越好看"},
    "戊": {"face": "方脸 / 国字脸", "features": "鼻宽大厚实、眼偏小沉稳、唇厚",
           "body": "骨架粗大、身壮厚实", "aura": "敦厚老实、可靠稳重"},
    "己": {"face": "方圆圆脸 / 肉感圆脸", "features": "五官圆润柔和、鼻头圆、眉眼温顺",
           "body": "匀称丰满、中等个", "aura": "随和接地气、忍耐温柔"},
    "庚": {"face": "棱角长方脸", "features": "剑眉、眼锐利、鼻梁高挺锋利",
           "body": "骨架坚硬、肩宽骨感、挺拔", "aura": "干练凌厉、英气十足"},
    "辛": {"face": "精致瓜子脸 / 小巧鹅蛋脸", "features": "五官精巧、眼秀气、鼻梁精致、唇形好看",
           "body": "纤细精致、体态秀气", "aura": "贵气清冷、精致优雅"},
    "壬": {"face": "宽圆脸 / 阔面", "features": "大眼灵动、眼窝略深、耳偏大",
           "body": "匀称修长、体态灵活", "aura": "圆滑通透、机敏随性"},
    "癸": {"face": "窄小脸 / 柔和尖脸", "features": "眼含秋水、眼细长、眉眼有氛围感",
           "body": "柔弱纤细、娇小柔软", "aura": "敏感柔情、神秘内敛"},
}

# 日主意象（用于性格总评「{日主意象}般」）
GAN_IMAGERY = {
    "甲": "参天大树", "乙": "花草藤蔓", "丙": "太阳骄阳", "丁": "烛火星火",
    "戊": "高山厚土", "己": "田园湿土", "庚": "利剑矿石", "辛": "珠宝玉石",
    "壬": "大江大海", "癸": "雨露幽泉",
}

# 3.2 格局神态叠加层
PATTERN_DEMEANOR = {
    "正官格": "神情端正克制、眉眼肃穆、举止规整、眼神平稳",
    "七杀格": "眼神锐利聚光、自带压迫感、习惯皱眉、双目有神",
    "正印格": "面相和善松弛、眉眼慈祥沉静、书卷气、神色淡定",
    "偏印格": "眼神深邃冷淡、侧眼打量、疏离感、不易展露情绪",
    "正财格": "面部敦厚务实、笑容朴实、肉感充足",
    "偏财格": "气色鲜活、笑容外放、眼神活络、亲和力强",
    "食神格": "面部饱满松弛、神情安逸、笑起来舒展无害",
    "伤官格": "眼珠灵动、眼神带傲气、表情丰富、不服管束的灵气",
    "建禄格": "神情独立勤快、亲力亲为感、踏实打拼气",
    "羊刃格": "性情刚烈、自尊心强、爱恨分明、气场刚硬",
    "月劫格": "性情刚烈、自尊心强、气场刚硬",
    "专旺格": "执拗主见极强、气场压倒性、五行元素极度外放",
    "从格": "顺势而为的机敏感、环境适应力强、神情灵活多变",
}

# 上等复合格局额外加分（关键词命中即叠加）
COMPOSITE_DEMEANOR = {
    "官印": "端庄温润、正气耐看",
    "杀印": "双目有神、威严但不凶狠",
    "伤官配印": "五官聪慧秀气、眼神通透、知性",
    "食神制杀": "外表随和、眼底藏决断、外柔内刚",
    "财官": "气色丰润、富贵和气",
}

# 3.3 身强身弱修正层
STRENGTH_FIX = {
    "身强": {"体态": "挺拔、有力量感、骨架感更强", "眼神": "坚定有力、目光直视",
             "气场": "外放、自信、有压迫感", "肤色": "气色偏旺、光泽感强",
             "表情": "表情主动、笑容明朗", "prompt": "身姿挺拔、气场强大、目光坚定、气色红润有光泽"},
    "身弱": {"体态": "柔和、单薄、皮肉偏少", "眼神": "内敛躲闪、目光柔和",
             "气场": "内收、谨慎、温和", "肤色": "气色偏淡、可能偏苍白 / 憔悴",
             "表情": "表情被动、笑容含蓄", "prompt": "身姿柔和、气质内敛、目光温润、肤色细腻偏白"},
    "中和": {"体态": "匀称标准", "眼神": "平和自然", "气场": "平衡舒适",
             "肤色": "健康均匀", "表情": "自然流露", "prompt": "体态匀称、气质平和"},
}

# 五行过旺 / 过弱的外貌瑕疵（可选叠加）
FLAW_MAP = {
    "木过旺": "脸长生硬、青筋明显", "火过旺": "面色泛红出油、眼露亢奋",
    "土过旺": "脸盘宽大浮肿、笨重感", "金过旺": "棱角过重、冷漠感",
    "水过旺": "眼袋重、面部浮肿、眼神飘忽", "木弱": "眉稀疏、眼无神、肩单薄",
    "火弱": "唇色暗淡、没血色、精神萎靡", "土弱": "脸颊凹陷、皮肉松弛",
    "金弱": "五官粗糙、精致感缺失", "水弱": "眼干无神、缺少氛围感",
}

# 3.4 五行配色与背景意象
ELEMENT_PALETTE = {
    "木": {"main": "青绿、翠绿", "aux": "浅棕、米白", "imagery": "森林、竹林、藤蔓、枝叶、晨光"},
    "火": {"main": "赤红、橙红", "aux": "金黄、暖白", "imagery": "烈日、火焰、晚霞、灯光、星空"},
    "土": {"main": "土黄、赭石", "aux": "深棕、米白", "imagery": "高山、大地、田野、岩石、沙漠"},
    "金": {"main": "银白、冷金", "aux": "浅灰、深蓝", "imagery": "金属、珠宝、刀剑、矿石、霜雪"},
    "水": {"main": "深蓝、墨黑", "aux": "银白、浅青", "imagery": "江海、湖泊、雨露、溪流、雾气"},
}

# 4.1 格局优势库
PATTERN_STRENGTH = {
    "正官格": "守规矩、重名誉、责任心强、稳重靠谱、贵人多",
    "七杀格": "胆识过人、决断干脆、抗压强、敢闯敢拼、危机翻盘",
    "正印格": "心地宽厚、共情强、爱读书、悟性好、长辈贵人多",
    "偏印格": "洞察力顶尖、第六感敏锐、思维非常规、谋略强",
    "正财格": "脚踏实地、勤俭守信、擅长规划、重视家庭",
    "偏财格": "豪爽大方、社交厉害、眼光灵活、人脉广阔、机遇多",
    "食神格": "乐观随和、情商高、多才多艺、懂得享受生活",
    "伤官格": "智商出众、创新力强、口才出众、厌恶陈旧规则",
    "建禄格": "独立勤快、吃苦耐劳、亲力亲为、白手起家",
    "羊刃格": "刚烈果断、自尊心强、行动力猛、能扛事",
    "月劫格": "独立要强、行动力强、能扛事、自尊自爱",
}

# 4.2 格局缺点库
PATTERN_WEAKNESS = {
    "正官格": "保守、爱面子、思虑重、怕犯错、不懂变通",
    "七杀格": "急躁、情绪化、脾气刚烈、易冲动、招是非",
    "正印格": "依赖性强、犹豫多虑、进取心弱、想得多做得少",
    "偏印格": "多疑、防备心重、孤僻、敏感内耗、易悲观",
    "正财格": "过于现实、看重利益、舍不得冒险、格局保守",
    "偏财格": "花钱大手大脚、耐性不足、难深耕、异性缘旺",
    "食神格": "安逸懒惰、贪图舒服、抗压差、遇困境躺平",
    "伤官格": "恃才傲物、孤傲、爱顶撞、口舌是非",
    "建禄格": "凡事亲力亲为、不懂放权、劳碌命",
    "羊刃格": "刚愎自用、易走极端、脾气冲、争斗心强",
    "月劫格": "刚愎自用、易冲动、争夺心强、不服管",
}

# 身强弱特有优势 / 弱点（「中和」为补充，框架未单列）
STRENGTH_ADVANTAGE = {
    "身强": "能担财官、扛得住压力、主动性强、精力充沛、敢于争取",
    "身弱": "观察力细、共情力强、谨慎稳妥、善于借力、柔性取胜",
    "中和": "心态平和、可进可退、适应力强、不偏不倚",
}
STRENGTH_DISADVANTAGE = {
    "身强": "过于自信、固执己见、听不进劝、容易冲动、逞强",
    "身弱": "缺乏自信、容易退缩、扛不住压力、依赖性强、优柔寡断",
    "中和": "缺乏突出锋芒、易安于现状、决断力偏弱",
}

# 4.4 大运十神心态关键词
DECADE_MOOD = {
    "正官": "压力感、责任感增强、想稳定、求认可、可能焦虑",
    "七杀": "挑战感强、紧张亢奋、想突破、压力山大、易急躁",
    "正印": "心态平和、想学习充电、依赖感强、佛系、求安稳",
    "偏印": "想独处思考、敏感多疑、对玄学 / 冷门感兴趣、易焦虑",
    "正财": "务实、想赚钱、关注物质、有干劲、可能计较",
    "偏财": "想搞钱、投机心起、社交活跃、花钱冲动、心浮",
    "食神": "心态放松、想享受、创作欲强、佛系躺平、没压力",
    "伤官": "想表达、不服管、创新欲强、易叛逆、心高气傲",
    "比肩": "想竞争、独立意识强、朋友多、易破财、不服输",
    "劫财": "争夺心强、冲动、合伙易纠纷、花钱冲动",
}

# 十神归类（用于承受力判断）
OFFICER_WEALTH = {"正官", "七杀", "正财", "偏财"}
YIN_BI = {"正印", "偏印", "比肩", "劫财"}

ALL_ELEMENTS = ["木", "火", "土", "金", "水"]


# =====================================================================
# 二、工具函数
# =====================================================================

def _map_strength(status: str) -> str:
    """paipan 的「偏旺/偏弱/中和」→ 卡牌口径「身强/身弱/中和」。"""
    return {"偏旺": "身强", "偏弱": "身弱", "中和": "中和"}[status]


def _map_pattern_type(pattern_analysis: dict) -> str:
    """据已取格局判大类；建禄/月劫归禄刃，其余常规归正格。"""
    selected = pattern_analysis["selected"]["pattern"]
    if selected in ("建禄格", "月劫格"):
        return "禄刃格"
    if selected in ("专旺格", "从格", "化气格"):
        return selected
    return "正格"


def _composite_demeanor(pattern_analysis: dict) -> str:
    """命中上等复合格局时，返回额外神态加分。"""
    candidates = "、".join(p["pattern"] for p in pattern_analysis["candidates"])
    hits = [v for k, v in COMPOSITE_DEMEANOR.items() if k in candidates]
    return "、".join(hits)


# =====================================================================
# 三、排盘（复用 paipan 内部函数）
# =====================================================================

def cast_chart(date, time, gender, city, zwt, tz_offset):
    """排盘并返回结构化命盘，等价于 paipan.main 的中间产物。"""
    local_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    solar_dt, longitude_offset, equation_offset, ganzhi = paipan.calculate_ganzhi(
        local_dt, zwt, tz_offset
    )
    yGZ, mGZ, dGZ, hGZ = ganzhi
    day_gan = paipan.GAN[dGZ.tg]

    pillars = [
        ("年", paipan.GAN[yGZ.tg], paipan.ZHI[yGZ.dz]),
        ("月", paipan.GAN[mGZ.tg], paipan.ZHI[mGZ.dz]),
        ("日", paipan.GAN[dGZ.tg], paipan.ZHI[dGZ.dz]),
        ("时", paipan.GAN[hGZ.tg], paipan.ZHI[hGZ.dz]),
    ]
    day_analysis = paipan.analyze_day_master(pillars)
    pattern_analysis = paipan.analyze_pattern(pillars, day_analysis)
    use_gods = paipan.analyze_use_gods(pillars, day_analysis, pattern_analysis)
    wuxing = paipan.wuxing_distribution(pillars)

    # 起大运（复现 paipan.main 的逻辑）
    yang_year = paipan.GAN[yGZ.tg] in paipan.GAN_YANG
    forward = (yang_year and gender == "男") or (not yang_year and gender == "女")
    y, m, d, hh, mm = local_dt.year, local_dt.month, local_dt.day, local_dt.hour, local_dt.minute
    days_to = paipan._days_to_jie(y, m, d, hh, mm, forward)
    start_age = days_to / 3.0
    seq = []
    idx_g, idx_z = mGZ.tg, mGZ.dz
    step = 1 if forward else -1
    for _ in range(8):
        idx_g = (idx_g + step) % 10
        idx_z = (idx_z + step) % 12
        seq.append(paipan.GAN[idx_g] + paipan.ZHI[idx_z])

    return {
        "local_dt": local_dt, "solar_dt": solar_dt, "day_gan": day_gan,
        "pillars": pillars, "day_analysis": day_analysis,
        "pattern_analysis": pattern_analysis, "use_gods": use_gods,
        "wuxing": wuxing, "start_age": start_age, "decades": seq,
        "forward": forward, "birth_year": y,
    }


def current_decade_and_year(chart, now=None):
    """计算当前大运与当前流年（流年以立春分界）。"""
    now = now or datetime.now()
    # 当前流年
    today = paipan.sxtwl.fromSolar(now.year, now.month, now.day)
    liunian = paipan.GAN[today.getYearGZ().tg] + paipan.ZHI[today.getYearGZ().dz]

    # 当前大运：当前年龄落在哪一步（0-7），未起运归第一步
    age = now.year - chart["birth_year"]
    idx = int((age - chart["start_age"]) // 10)
    idx = max(0, min(idx, 7))
    decade = chart["decades"][idx]
    return decade, liunian


# =====================================================================
# 四、形象出图 Prompt 拼装
# =====================================================================

def build_image_prompt(card):
    """拼装出图 Prompt。"""
    ap = GAN_APPEARANCE[card["day_gan"]]
    strength = STRENGTH_FIX[card["body_strength"]]
    palette = ELEMENT_PALETTE[card["element"]]
    demeanor = PATTERN_DEMEANOR.get(card["pattern"], "")
    composite = card.get("composite_demeanor", "")

    lines = [
        "竖版人物卡牌插画，3:4比例。",
        f"主体：一位年轻人物，{ap['face']}，{ap['features']}，{ap['body']}，"
        f"{strength['prompt']}，气质{ap['aura']}。",
    ]
    if demeanor:
        lines.append(f"神态：{demeanor}。")
    if composite:
        lines.append(f"复合格局加成：{composite}。")
    lines.append(
        f"背景：{palette['imagery']}，主色调{palette['main']}，"
        f"辅助色{palette['aux']}；融入喜用神「{card['useful_god']}」的意象，"
        f"弱化忌神「{card['avoid_god']}」元素。"
    )
    lines.append("风格：精致唯美插画风格，光影柔和，细节丰富，塔罗牌质感。")
    return "\n".join(lines)


# =====================================================================
# 五、文字分析拼装
# =====================================================================

def build_text(card):
    """拼装核心优势 / 性格弱点 / 性格总评 / 当下心态。"""
    p = card["pattern"]
    strengths = []
    if p in PATTERN_STRENGTH:
        strengths.append(PATTERN_STRENGTH[p])
    strengths.append(STRENGTH_ADVANTAGE[card["body_strength"]])

    weaknesses = []
    if p in PATTERN_WEAKNESS:
        weaknesses.append(PATTERN_WEAKNESS[p])
    weaknesses.append(STRENGTH_DISADVANTAGE[card["body_strength"]])

    summary = (
        f"如{GAN_IMAGERY[card['day_gan']]}般{GAN_APPEARANCE[card['day_gan']]['aura']}，"
        f"{PATTERN_STRENGTH.get(p, '')}。{card['body_strength']}使得你"
        f"{STRENGTH_ADVANTAGE[card['body_strength']]}，"
        f"整体是一个{_summary_tag(card)}的人。"
    )

    mood = _build_mood(card)
    return {
        "strengths": "；".join(s for s in strengths if s),
        "weaknesses": "；".join(w for w in weaknesses if w),
        "summary": summary,
        "mood": mood,
    }


def _summary_tag(card):
    """一句话标签，按身强弱 + 格局给个稳定的概括。"""
    strong_tag = {"身强": "敢打敢拼、能扛事", "身弱": "靠巧劲与内力取胜", "中和": "进退有度、稳中求进"}
    return strong_tag[card["body_strength"]]


def _build_mood(card):
    """当下心态：大运十神 + 流年生克喜忌 + 身强弱承受力。"""
    decade = card["current_decade"]
    decade_gan = decade[0]
    decade_deity = paipan.shishen(card["day_gan"], decade_gan)
    mood_key = DECADE_MOOD.get(decade_deity, "平稳过渡")

    liunian = card["current_year"]
    liunian_gan = liunian[0]
    ln_wx = paipan.GAN_WX[liunian_gan]
    dy_wx = paipan.GAN_WX[decade_gan]

    # 流年与大运生克
    if paipan.SHENG[ln_wx] == dy_wx:
        relation = "流年生扶大运，该十神能量增强、心态被放大"
    elif paipan.KE[ln_wx] == dy_wx:
        relation = "流年克制大运，心态受阻、有波折、内心矛盾"
    else:
        relation = "流年与大运关系平顺"

    # 流年喜忌
    useful = {e.strip() for e in card["useful_god"].split("、")}
    avoid = {e.strip() for e in card["avoid_god"].split("、")}
    if ln_wx in useful:
        year_tone = "为喜用神，整体心态积极、顺势而为"
    elif ln_wx in avoid:
        year_tone = "为忌神，整体心态压抑、需要调整"
    else:
        year_tone = "喜忌不显，心态中性"

    # 身强弱对大运的承受力
    if decade_deity in OFFICER_WEALTH:
        capacity = ("能担起，心态是「想干事、能扛事」" if card["body_strength"] == "身强"
                    else "扛不住，心态是「压力大、想逃避、焦虑」")
    elif decade_deity in YIN_BI:
        capacity = ("太旺，心态是「固执、懒散、不想动」" if card["body_strength"] == "身强"
                    else "得助，心态是「有底气、有人帮、信心回升」")
    else:
        capacity = ("泄秀得宜，创作表达欲强" if card["body_strength"] == "身强"
                    else "泄身偏重，容易想多做少、精力分散")

    advice = _build_advice(card)

    return (
        f"当前处于{decade}（{decade_deity}），整体心态偏向{mood_key}。"
        f"{liunian}天干{liunian_gan}（{ln_wx}）{year_tone}；{relation}。"
        f"{card['body_strength']}的你{capacity}。建议：{advice}。"
    )


def _build_advice(card):
    """据扶抑喜神候选给 1 条行动建议。"""
    fuyi = card.get("fuyi", [])
    if not fuyi:
        return "结合格局成败与岁运，稳中求进"
    _, reason = fuyi[0]
    if "印" in reason:
        return "多借助学习、长辈、贵人的力量，减少内耗"
    if "比劫" in reason or "帮身" in reason:
        return "善用朋友与团队的力量，主动争取支持"
    if "食伤" in reason or "泄秀" in reason:
        return "专注创作与表达，把才华落地"
    if "财" in reason:
        return "务实经营、把握机会，专注积累"
    if "官杀" in reason or "制身" in reason:
        return "以目标为导向，用纪律和担当约束自己"
    return "顺着喜用神方向，顺势而为"


# =====================================================================
# 六、主流程
# =====================================================================

def build_card(chart, now=None):
    """把排盘结果映射为卡牌输入规范，并拼装出卡牌全部内容。"""
    day_analysis = chart["day_analysis"]
    pattern_analysis = chart["pattern_analysis"]
    use_gods = chart["use_gods"]
    selected = pattern_analysis["selected"]

    day_gan = chart["day_gan"]
    element = paipan.GAN_WX[day_gan]
    body_strength = _map_strength(day_analysis["status"])
    pattern = selected["pattern"]
    useful_elements = [e for e, _ in use_gods["fuyi"]]
    useful_god = "、".join(useful_elements)
    avoid_god = "、".join(e for e in ALL_ELEMENTS if e not in useful_elements)
    current_decade, current_year = current_decade_and_year(chart, now)

    card = {
        "day_master": f"{day_gan}{element}",
        "yin_yang": "阳" if day_gan in paipan.GAN_YANG else "阴",
        "element": element,
        "pattern": pattern,
        "pattern_type": _map_pattern_type(pattern_analysis),
        "body_strength": body_strength,
        "useful_god": useful_god,
        "avoid_god": avoid_god,
        "five_elements_count": {k: round(v, 1) for k, v in chart["wuxing"].items()},
        "current_decade": f"{current_decade}大运",
        "current_year": f"{current_year}年",
        "ten_god_dominant": selected["deity"],
        "composite_demeanor": _composite_demeanor(pattern_analysis),
        "fuyi": use_gods["fuyi"],
        "day_gan": day_gan,
    }
    card["image_prompt"] = build_image_prompt(card)
    text = build_text(card)
    card.update(text)
    return card


def render_text(card):
    """人类可读输出。"""
    line = "=" * 50
    top = f"{card['day_master']} · {card['pattern']}"
    return "\n".join([
        line,
        f"八字人物卡牌 · {top}",
        line,
        "",
        f"【身强弱与喜用神】",
        f"  {card['body_strength']} ｜ 喜用神: {card['useful_god']} ｜ 忌神: {card['avoid_god']}",
        f"  格局大类: {card['pattern_type']} ｜ 主导十神: {card['ten_god_dominant']}",
        "",
        f"【出图 Prompt】",
        card["image_prompt"],
        "",
        f"【核心优势】",
        f"  {card['strengths']}",
        "",
        f"【性格弱点】",
        f"  {card['weaknesses']}",
        "",
        f"【性格总评】",
        f"  {card['summary']}",
        "",
        f"【当下心态】",
        f"  {card['mood']}",
        "",
        line,
    ])


def main():
    ap = argparse.ArgumentParser(description="八字人物卡牌生成器")
    ap.add_argument("--date", required=True, help="公历生日 YYYY-MM-DD")
    ap.add_argument("--time", required=True, help="出生时刻 HH:MM (24h)")
    ap.add_argument("--gender", required=True, choices=["男", "女"])
    ap.add_argument("--city", default="")
    ap.add_argument("--zwt", type=float, default=None, help="出生地经度(东经为正)")
    ap.add_argument("--tz-offset", type=float, default=8.0)
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    a = ap.parse_args()

    chart = cast_chart(a.date, a.time, a.gender, a.city, a.zwt, a.tz_offset)
    card = build_card(chart)

    if a.json:
        print(json.dumps(card, ensure_ascii=False, indent=2))
    else:
        print(f"公历 {a.date} {a.time}  {a.gender}" + (f"  出生地 {a.city}" if a.city else ""))
        print(render_text(card))


if __name__ == "__main__":
    main()

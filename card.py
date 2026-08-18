#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
八字人物卡牌生成器（card.py）

把 paipan.py 的排盘结果，拼装成 3:4 竖版「人物卡牌」：
  - 命运剧本（角色定位 / 主线任务 / 当前章节 / 顺风低谷）
  - 天赋与技能点（本命技能 / 天赋方向 / 角色定位 / 加点建议）
  - 形象出图 Prompt（外貌 × 神态 × 身强弱 × 五行配色，武侠玄幻风）
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

# 3.1 日主外貌基础层（骨相 + 体态 + 气场锚点，保证十天干形态差异化）
GAN_APPEARANCE = {
    "甲": {"build": "高挑挺拔", "face": "长方方正脸型、眉骨偏高",
           "features": "眉浓修长、眼细长有神、鼻梁挺直",
           "aura": "正气威严", "anchor": "如松树般挺拔硬朗"},
    "乙": {"build": "纤细柔弱", "face": "瓜子脸、线条柔润",
           "features": "弯眉、桃花眼、唇厚薄适中",
           "aura": "温婉耐看", "anchor": "如花草般柔美亲和"},
    "丙": {"build": "体态匀称、线条柔和圆润", "face": "圆润柔和的圆脸",
           "features": "大而明亮的杏眼、眉上扬、唇色红润",
           "aura": "温暖外放", "anchor": "如太阳般温暖亲和"},
    "丁": {"build": "苗条清瘦", "face": "尖小精致脸型",
           "features": "眼深邃狭长、眸含光、眉细",
           "aura": "清冷内敛", "anchor": "如烛火般精巧耐看"},
    "戊": {"build": "结实敦厚", "face": "国字脸方脸、鼻宽大厚实",
           "features": "眼偏小沉稳、唇厚",
           "aura": "敦厚稳重", "anchor": "如高山般厚重可靠"},
    "己": {"build": "体态匀称、柔和圆润", "face": "圆润柔和的圆脸、五官柔和",
           "features": "鼻头圆、眉眼温顺",
           "aura": "随和温柔", "anchor": "如田园般温润亲和"},
    "庚": {"build": "骨感挺拔", "face": "棱角分明的方脸",
           "features": "剑眉、眼锐利、鼻梁高挺锋利",
           "aura": "凌厉英气", "anchor": "如刀剑般锋利干练"},
    "辛": {"build": "纤细精致", "face": "精致小巧的瓜子脸",
           "features": "五官精巧、眼秀气、鼻梁精致、唇形好看",
           "aura": "贵气清冷", "anchor": "如珠宝般精致优雅"},
    "壬": {"build": "高挑修长灵动", "face": "宽圆略带棱角的脸型",
           "features": "大眼灵动有神、眼窝微深、表情洒脱",
           "aura": "机敏通透", "anchor": "如江河般流动随性"},
    "癸": {"build": "娇小柔弱", "face": "窄小脸、柔和尖脸",
           "features": "眼含秋水、眼细长、眉眼有氛围感",
           "aura": "敏感柔情", "anchor": "如雨露般纤细神秘"},
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

# 天赋：主导十神 → 天赋方向
DEITY_TALENT = {
    "食神": "创意才华 · 艺术审美 · 生活美学 · 感染力",
    "伤官": "创新突破 · 技术天赋 · 口才表达 · 颠覆思维",
    "正官": "领导管理 · 组织执行 · 责任担当 · 规则意识",
    "七杀": "胆识魄力 · 危机突破 · 抗压竞争 · 开拓攻坚",
    "正财": "理财规划 · 务实经营 · 价值判断 · 稳健积累",
    "偏财": "社交人脉 · 机会嗅觉 · 资源整合 · 灵活应变",
    "正印": "学习能力 · 悟性研究 · 文化底蕴 · 深度思考",
    "偏印": "洞察谋略 · 非常规思维 · 心理洞察 · 专精深耕",
    "比肩": "独立自主 · 行动执行 · 竞争意识 · 坚韧抗压",
    "劫财": "胆识敢闯 · 掌控决断 · 人脉整合 · 进取突破",
}

# 天赋：日主五行 → 天赋气质呈现
ELEMENT_TALENT = {
    "木": "以生长与规划的方式呈现，擅长培育引导",
    "火": "以表现与感染的方式呈现，自带魅力气场",
    "土": "以承载与整合的方式呈现，稳健厚重",
    "金": "以决断与精进的方式呈现，执行力强",
    "水": "以洞察与变通的方式呈现，智谋机敏",
}

# 1.5 命运剧本：日主角色（游戏化职业定位）
GAN_ROLE = {
    "甲": ("森林守护者", "高大挺拔、正气凛然，天生的守护者，习惯站在别人前面挡风遮雨"),
    "乙": ("田园织梦者", "温柔坚韧、善于联结，天生的编织者，把散落的美好连成一片风景"),
    "丙": ("烈日骑士", "热烈坦荡、自带光芒，天生的引路人，走到哪里，哪里就亮起来"),
    "丁": ("暗夜引路人", "安静专注、内心滚烫，天生的守望者，越是暗处，越见你的光"),
    "戊": ("大地壁垒", "厚重可靠、稳如磐石，天生的承重墙，山雨欲来，你自岿然"),
    "己": ("沃土孕育者", "温润包容、滋养万物，天生的耕耘者，能把贫瘠之地养成良田"),
    "庚": ("破阵剑士", "锋锐果决、直来直往，天生的破局者，认准了便一剑开山"),
    "辛": ("秘宝鉴藏师", "精致敏锐、慧眼识珠，天生的鉴赏者，于细微处见大美"),
    "壬": ("沧海行者", "开阔灵动、随物赋形，天生的航海家，江河湖海都是你的路"),
    "癸": ("幽泉冥想师", "沉静敏锐、柔韧绵长，天生的聆听者，于无声处听惊雷"),
}

# 1.6 命运剧本：格局 → 主线任务
PATTERN_QUEST = {
    "正官格": ("「秩序与名望之路」", "在规则之内，靠沉稳与担当，一步步建立自己的权威"),
    "七杀格": ("「逆风翻盘之路」", "在压力与挑战中淬炼成钢，越是逆风，越能翻盘"),
    "正印格": ("「传承与守护之路」", "以学识与慈心为灯，照亮自己，也照亮后来的人"),
    "偏印格": ("「秘境探索之路」", "在冷门与玄思中寻找答案，你的地图上有别人看不见的路"),
    "正财格": ("「实业筑城之路」", "一砖一瓦，垒出踏实而丰盛的人生城池"),
    "偏财格": ("「逐浪机遇之路」", "在流动的人群与财富间起舞，机会是你的主场"),
    "食神格": ("「创造与品味之路」", "把平凡日子过成作品，让生活因你而变得更好"),
    "伤官格": ("「破旧立新之路」", "做规则的怀疑者与改写者，旧墙由你凿出新窗"),
    "建禄格": ("「白手起家之路」", "不靠祖荫、不靠运气，全靠自己这双手"),
    "羊刃格": ("「烈火淬锋之路」", "刚烈果决、敢爱敢恨，在一次次的对抗中把自己磨成利刃"),
    "月劫格": ("「自强不息之路」", "独立要强，争的是一口气，拼的是一条自己的路"),
    "专旺格": ("「一极独行之路」", "把一种力量走到极致，你就是自己的偏执与骄傲"),
    "从格": ("「顺势而为之路」", "识时务、借大势，你不是随波逐流，你是顺水行舟的高手"),
}

# 1.7 天赋技能点：十神 → 本命技能
TEN_GOD_TALENT = {
    "正官": {"name": "秩序光环", "desc": "被信任与被托付的能力，稳重靠谱是你与生俱来的被动技能"},
    "七杀": {"name": "破阵之势", "desc": "越是高压越清醒，危机关头能爆发出惊人的翻盘之力"},
    "正印": {"name": "传承之心", "desc": "学什么都快，天然懂得把知识化为滋养自己的养分"},
    "偏印": {"name": "慧眼识机", "desc": "直觉敏锐，能看见事物背面与角落里藏着的答案"},
    "正财": {"name": "实业之基", "desc": "务实稳健，能把一件事做深做久，像种树一样积累"},
    "偏财": {"name": "机遇之眼", "desc": "对机会天生敏感，人脉与眼光是你随身携带的通行证"},
    "食神": {"name": "创造之泉", "desc": "才华与品味俱佳，能把平常事做出滋味来"},
    "伤官": {"name": "破旧之刃", "desc": "思维锋利，天生不喜欢旧答案，革新是你的本能"},
    "比肩": {"name": "并肩之力", "desc": "独立又合群，站得稳，也愿意为同伴挺身而出"},
    "劫财": {"name": "逆境战意", "desc": "越挫越勇，绝境里反而能爆发出惊人的能量"},
}

# 1.8 身强弱 → 角色定位
STRENGTH_ROLE = {
    "身强": ("正面作战型", "血厚攻高、扛得住压力，适合冲锋在前、担起大梁；但要记得，不必所有事都自己扛"),
    "身弱": ("智谋协作型", "血薄但敏捷点满，适合借力打力、以柔克刚，你的战场在幕后与细节"),
    "中和": ("均衡发展型", "可攻可守、进退有度，没有明显短板，稳中求进是你最好的节奏"),
}

# 1.9 大运十神 → 剧情章节
DECADE_CHAPTER = {
    "正官": ("秩序考验", "责任加身的一章，站稳脚跟，名望会在规矩里慢慢长出来"),
    "七杀": ("逆风试炼", "压力即磨刀石的一章，扛过去，你会换一个人"),
    "正印": ("静水流深", "蓄力充电的一章，别急着赶路，沉淀是为了走得更远"),
    "偏印": ("迷雾探秘", "向内探索的一章，独处不是孤独，是你在自己的地图上开新路"),
    "正财": ("播种收获", "务实耕耘的一章，一分耕耘一分收获，稳住就能赢"),
    "偏财": ("风起云涌", "机遇涌动的一章，机会很多，更要慢一步看清再下注"),
    "食神": ("悠游乐章", "舒展身心的一章，享受生活不是懈怠，是回血"),
    "伤官": ("破茧之音", "表达自我的一章，别怕与众不同，你的声音就是你的路"),
    "比肩": ("并肩之战", "独立成长的一章，朋友与对手都会推着你往前走"),
    "劫财": ("争锋时刻", "竞争激烈的一章，守住本心，别被冲动带偏"),
}

# 1.10 稀有度（星辉流，全正向档位，按格局组合的独特程度判定，不代表命贵命贱）
RARITY_LEVELS = {
    5: ("天命", "多重罕见格局交辉，千中无一——你这套角色设定，独一无二"),
    4: ("极星", "不靠祖荫、自带锋芒的格局——你的路，是自己闯出来的"),
    3: ("耀星", "五行均衡、可进可退——这种配置可遇不可求，你自带平衡的光芒"),
    2: ("明星", "成格稳健、路线清晰——你的天赋组合很扎实，稳中求进即是上策"),
    1: ("晨星", "破晓之星——你的剧本还在展开，光芒会越走越亮"),
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
    """据已取格局判大类；建禄/月劫/羊刃归禄刃，其余常规归正格。"""
    selected = pattern_analysis["selected"]["pattern"]
    if selected in ("建禄格", "月劫格", "羊刃格"):
        return "禄刃格"
    if selected in ("专旺格", "从格", "化气格"):
        return selected
    return "正格"


def _composite_demeanor(pattern_analysis: dict) -> str:
    """命中上等复合格局时，返回额外神态加分。"""
    candidates = "、".join(p["pattern"] for p in pattern_analysis["candidates"])
    hits = [v for k, v in COMPOSITE_DEMEANOR.items() if k in candidates]
    return "、".join(hits)


def _age_group(age):
    """周岁年龄 → 年龄段描述。"""
    if age < 18:
        return "少年"
    if age < 30:
        return "青年"
    if age < 45:
        return "青壮年"
    if age < 60:
        return "中年"
    if age < 75:
        return "中老年"
    return "老年"


def _current_age(chart, now=None):
    """按出生时刻精确计算周岁年龄。"""
    now = now or datetime.now()
    born = chart["local_dt"]
    age = now.year - born.year
    if (now.month, now.day) < (born.month, born.day):
        age -= 1
    return max(age, 0)


def _rarity_rank(chart):
    """稀有度判定（1-5，全正向）：按格局组合的独特程度，不代表命贵命贱。"""
    pa = chart["pattern_analysis"]
    pattern_type = _map_pattern_type(pa)
    special = "、".join(pa.get("special_candidates", []))
    if any(k in special for k in ("专旺格候选", "从弱格候选", "从强格候选", "从格候选")):
        return 5
    if pattern_type == "禄刃格":
        return 4
    if pattern_type == "正格" and chart["day_analysis"]["status"] == "中和":
        return 3
    if len(pa["candidates"]) == 1:
        return 2
    return 1


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
        "forward": forward, "birth_year": y, "gender": gender,
    }


def current_decade_and_year(chart, now=None):
    """计算当前大运、当前流年（流年以立春分界）与大运序号（0-7，未起运归 0）。"""
    now = now or datetime.now()
    # 当前流年
    today = paipan.sxtwl.fromSolar(now.year, now.month, now.day)
    liunian = paipan.GAN[today.getYearGZ().tg] + paipan.ZHI[today.getYearGZ().dz]

    # 当前大运：当前年龄落在哪一步（0-7），未起运归第一步
    age = now.year - chart["birth_year"]
    idx = int((age - chart["start_age"]) // 10)
    idx = max(0, min(idx, 7))
    decade = chart["decades"][idx]
    return decade, liunian, idx


# =====================================================================
# 四、形象出图 Prompt 拼装
# =====================================================================

def build_image_prompt(card):
    """拼装出图 Prompt（武侠玄幻风，差异化外貌）。"""
    ap = GAN_APPEARANCE[card["day_gan"]]
    strength = STRENGTH_FIX[card["body_strength"]]
    palette = ELEMENT_PALETTE[card["element"]]
    demeanor = PATTERN_DEMEANOR.get(card["pattern"], "")
    composite = card.get("composite_demeanor", "")
    gender = "男性" if card["gender"] == "男" else "女性"
    age = card["age"]
    age_desc = f"一位{age}岁、正值{_age_group(age)}的{gender}中国武侠人物"

    lines = [
        "中国武侠玄幻风人物立绘，竖版构图，人物居中偏上，主体突出放大。",
        f"主体：{age_desc}，{ap['build']}，{ap['face']}，{ap['features']}，"
        f"{strength['prompt']}，气场{ap['aura']}，{ap['anchor']}。",
    ]
    if demeanor:
        lines.append(f"神态：{demeanor}。")
    if composite:
        lines.append(f"复合格局加成：{composite}。")
    lines.append(
        f"服饰：中国武侠风劲装长袍，{palette['main']}为主色调，{palette['aux']}纹饰，广袖飘逸，衣袂翻飞。"
    )
    avoid_phrase = (
        f"弱化忌神「{card['avoid_god']}」元素" if card["avoid_god"] != "无显著忌神"
        else "不刻意强化任何忌神意象"
    )
    lines.append(
        f"背景：玄幻氛围，深邃星空与流动云雾，{palette['imagery']}，"
        f"融入喜用神「{card['useful_god']}」的意象，{avoid_phrase}，梦幻强烈的光影特效。"
    )
    lines.append("风格：中国武侠玄幻游戏角色立绘，精致唯美，人物主体强化突出，高级质感。"
                 "不要任何文字，不要塔罗牌边框，不要占星符号，不要罗马数字。")
    return "\n".join(lines)


def build_card_layout_prompt(card):
    """生成「人物 + 文字排版」一体的完整卡牌出图提示词，可直接喂 AI 绘图工具出成品卡牌。"""
    s = card["script"]
    t = card["talents"]
    palette_main = ELEMENT_PALETTE[card["element"]]["main"]
    # 复用形象 Prompt 的主体部分（剔除"不要任何文字"等纯人物约束）
    body_lines = [
        ln for ln in card["image_prompt"].split("\n")
        if ln and not ln.startswith("风格：") and "竖版构图" not in ln
    ]
    return "\n".join([
        "设计一张中国武侠玄幻风人物卡牌，竖版 3:4 构图，精致唯美，高级质感。",
        "",
        "【整体布局】",
        "经典人物卡构图：中央为主视觉区，人物立绘居中、主体突出放大；文字环绕人物分布——"
        "顶部为标题区，左右两侧为信息文字区，底部为标签区，文字不遮挡人物主体。"
        f"整体以「{palette_main}」色调的边框与水墨渐变装饰，文字排版工整清晰、中文宋体/楷体风格，留白舒适。",
        "",
        "【图片主体】",
        " ".join(body_lines),
        "",
        "【顶部标题区】需包含以下文字：",
        f"标题：八字人物卡牌 · {card['day_master']} · {card['pattern']}",
        f"稀有度：{card['rarity']['name']}",
        f"副标题：角色：{s['role']} ｜ 主线任务：{s['quest']}",
        "",
        "【左侧文字区】需包含以下文字：",
        "《命运剧本》",
        f"角色定位：{s['role']}——{s['role_desc']}",
        f"主线任务：{s['quest']}——{s['quest_desc']}",
        f"当前章节：第{s['chapter_no']}章「{s['chapter']}」——{s['chapter_desc']}",
        s['year_tone'],
        "",
        "【右侧文字区】需包含以下文字：",
        "《天赋与技能点》",
        f"本命技能：「{t['skill_name']}」（{t['deity']}）——{t['skill_desc']}",
        f"天赋方向：{card['talent']}",
        f"角色定位：{t['role_type']}——{t['role_desc']}",
        f"加点建议：{t['skill_points']}",
        "",
        "【底部标签区】需包含以下文字：",
        f"《核心优势》{card['strengths']}",
        f"《性格弱点》{card['weaknesses']}",
        f"底部标签：{card['body_strength']} ｜ 喜用神：{card['useful_god']} ｜ 忌神：{card['avoid_god']}",
        f"调候提示：{card['climate'][0] + '（' + card['climate'][1] + '）' if card['climate'][0] else card['climate'][1]}",
        "",
        "【风格】中国武侠玄幻游戏角色卡牌立绘，人物主体强化突出，光影柔和，细节丰富，"
        f"主色调融入「{card['element']}」五行意象，在卡牌角落添加「思维热布丁」水印文字，不要占星符号，不要罗马数字。",
    ])


# =====================================================================
# 五、文字分析拼装
# =====================================================================

def build_text(card):
    """拼装天赋 / 核心优势 / 性格弱点 / 性格总评 / 当下心态。"""
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
        "talent": build_talent(card),
        "strengths": "；".join(s for s in strengths if s),
        "weaknesses": "；".join(w for w in weaknesses if w),
        "summary": summary,
        "mood": mood,
    }


def build_talent(card):
    """天赋：主导十神天赋方向 + 日主五行气质呈现。"""
    deity_t = DEITY_TALENT.get(card["ten_god_dominant"], "")
    element_t = ELEMENT_TALENT.get(card["element"], "")
    if deity_t and element_t:
        return f"{deity_t}；{element_t}"
    return deity_t or element_t


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


def _advice_line(card):
    """子平法加点线：优先取相神/喜神（xishen），其次格局用神（fuyi），按五行归线。

    归线：印→印线；日主同气→比劫线；我生→食伤线；我克→财线；克我→官杀线。
    """
    element = card["element"]
    yin = paipan.source_element(element)
    shi = paipan.SHENG[element]
    cai = paipan.KE[element]
    guan = paipan.controller_element(element)
    candidates = card.get("xishen") or card.get("fuyi", [])
    for e, _ in candidates:
        if e == yin:
            return "印"
        if e == element:
            return "比劫"
        if e == shi:
            return "食伤"
        if e == cai:
            return "财"
        if e == guan:
            return "官杀"
    return "顺势"


ADVICE_BY_LINE = {
    "印": "多借助学习、长辈、贵人的力量，减少内耗",
    "比劫": "善用朋友与团队的力量，主动争取支持",
    "食伤": "专注创作与表达，把才华落地",
    "财": "务实经营、把握机会，专注积累",
    "官杀": "以目标为导向，用纪律和担当约束自己",
    "顺势": "顺着喜用神方向，顺势而为",
}

POINTS_BY_LINE = {
    "印": "优先点亮「传承之心」与「慧眼识机」：多读书、多拜师，善用长辈与贵人的力",
    "比劫": "优先点亮「并肩之力」：善用朋友与团队，主动争取支持，别一个人扛",
    "食伤": "优先点亮「创造之泉」与「破旧之刃」：把才华落到作品上，表达即修行",
    "财": "优先点亮「实业之基」与「机遇之眼」：务实经营，稳稳接住每一个机会",
    "官杀": "优先点亮「秩序光环」与「破阵之势」：以目标与纪律约束自己，压力会变成铠甲",
    "顺势": "顺着喜用神的方向加点，把自己的优势放大",
}


def _build_advice(card):
    """据子平法喜用（相神优先）给 1 条行动建议。"""
    if not (card.get("xishen") or card.get("fuyi")):
        return "结合格局成败与岁运，稳中求进"
    return ADVICE_BY_LINE[_advice_line(card)]


def build_script(card, chapter_no):
    """命运剧本：角色定位 + 主线任务 + 当前章节 + 顺风 / 低谷提示。"""
    role_name, role_desc = GAN_ROLE[card["day_gan"]]
    quest_name, quest_desc = PATTERN_QUEST.get(
        card["pattern"], ("「自定义之路」", "你的剧本由你自己执笔，主线任务等你亲手开启")
    )
    decade = card["decade_raw"]
    decade_deity = paipan.shishen(card["day_gan"], decade[0])
    chapter_name, chapter_desc = DECADE_CHAPTER.get(
        decade_deity, ("新篇章", "你正在书写属于自己的新篇章")
    )

    # 流年喜忌 → 顺风 / 低谷章节
    ln_wx = paipan.GAN_WX[card["year_raw"][0]]
    useful = {e.strip() for e in card["useful_god"].split("、")}
    avoid = {e.strip() for e in card["avoid_god"].split("、")}
    if ln_wx in useful:
        year_tone = f"这一章是顺风局（{card['current_year']}），风向正好，可以借势而上"
    elif ln_wx in avoid:
        year_tone = f"这一章是低谷章节（{card['current_year']}），风不顺，别硬刚——慢下来回血，低谷是用来渡过的"
    else:
        year_tone = f"这一章没有大风浪（{card['current_year']}），适合稳住节奏、照常推进"

    return {
        "role": role_name,
        "role_desc": role_desc,
        "quest": quest_name,
        "quest_desc": quest_desc,
        "chapter_no": chapter_no,
        "chapter": chapter_name,
        "chapter_desc": chapter_desc,
        "year_tone": year_tone,
    }


def build_talents(card):
    """天赋技能点：本命技能（主导十神）+ 角色定位（身强弱）+ 加点建议（喜用神）。"""
    deity = card["ten_god_dominant"]
    talent = TEN_GOD_TALENT.get(
        deity, {"name": "本命之力", "desc": "你的天赋尚未被完全点亮，正在等待合适的时机"}
    )
    role_type, role_desc = STRENGTH_ROLE[card["body_strength"]]

    if not (card.get("xishen") or card.get("fuyi")):
        points = "把天赋点都投在本命技能上，把一件事做到极致"
    else:
        points = POINTS_BY_LINE[_advice_line(card)]

    return {
        "deity": deity,
        "skill_name": talent["name"],
        "skill_desc": talent["desc"],
        "role_type": role_type,
        "role_desc": role_desc,
        "skill_points": points,
    }


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
    # 子平法喜忌合并：喜用 = 格局用神 + 相神/喜神五行（引擎输出，格局为纲）；
    # 忌神 = 引擎判定的破格病神（五行级，剔除与喜用同气者，如官杀混杂不作五行忌）；
    # 调候并入但不夺格局（身强调候置顶、中和附后、身弱不并）。
    useful_elements = [e for e, _ in use_gods["fuyi"]]
    climate_element = use_gods["climate"][0]
    ji_raw = [item["element"] for item in use_gods.get("jishen", [])]
    ji_elements = []
    for e in ji_raw:
        if e not in useful_elements and e not in ji_elements:
            ji_elements.append(e)
    if climate_element and climate_element not in useful_elements and climate_element not in ji_elements:
        if body_strength == "身强":
            useful_elements = [climate_element] + useful_elements  # 调候置顶
        elif body_strength == "中和":
            useful_elements = useful_elements + [climate_element]  # 兼顾，附于其后
        # 身弱：格局喜用优先，调候字不并入（若恰为喜用则已在上方列表中）
    useful_god = "、".join(useful_elements)
    avoid_god = "、".join(ji_elements) if ji_elements else "无显著忌神"
    jishen_detail = "；".join(
        f"{item['element']}({item['deity']}：{item['reason']})"
        + ("【实见】" if item["present"] else "【岁运防】")
        for item in use_gods.get("jishen", [])
    ) or "未见明显破格病神"
    current_decade, current_year, decade_idx = current_decade_and_year(chart, now)
    rank = _rarity_rank(chart)
    name, desc = RARITY_LEVELS[rank]

    card = {
        "day_master": f"{day_gan}{element}",
        "yin_yang": "阳" if day_gan in paipan.GAN_YANG else "阴",
        "gender": chart["gender"],
        "age": _current_age(chart, now),
        "rarity": {"level": rank, "name": name, "desc": desc},
        "element": element,
        "pattern": pattern,
        "pattern_type": _map_pattern_type(pattern_analysis),
        "body_strength": body_strength,
        "useful_god": useful_god,
        "avoid_god": avoid_god,
        "five_elements_count": {k: round(v, 1) for k, v in chart["wuxing"].items()},
        "current_decade": f"{current_decade}大运",
        "current_year": f"{current_year}年",
        "decade_raw": current_decade,
        "year_raw": current_year,
        "ten_god_dominant": selected["deity"],
        "composite_demeanor": _composite_demeanor(pattern_analysis),
        "fuyi": use_gods["fuyi"],
        "xishen": use_gods.get("xishen", []),
        "jishen_detail": jishen_detail,
        "climate": use_gods["climate"],
        "day_gan": day_gan,
    }
    card["script"] = build_script(card, decade_idx + 1)
    card["talents"] = build_talents(card)
    card["image_prompt"] = build_image_prompt(card)
    text = build_text(card)
    card.update(text)
    card["card_prompt"] = build_card_layout_prompt(card)
    return card


def render_text(card):
    """人类可读输出。"""
    line = "=" * 50
    top = f"{card['day_master']} · {card['pattern']}"
    s = card["script"]
    t = card["talents"]
    return "\n".join([
        line,
        f"八字人物卡牌 · {top}",
        f"稀有度：{card['rarity']['name']} —— {card['rarity']['desc']}",
        f"角色：{s['role']} ｜ 主线任务：{s['quest']}",
        line,
        "",
        f"【命运剧本】",
        f"  角色定位：{s['role']} —— {s['role_desc']}",
        f"  主线任务：{s['quest']} —— {s['quest_desc']}",
        f"  当前章节：第 {s['chapter_no']} 章「{s['chapter']}」—— {s['chapter_desc']}",
        f"  {s['year_tone']}",
        "",
        f"【天赋与技能点】",
        f"  本命技能：「{t['skill_name']}」（{t['deity']}）—— {t['skill_desc']}",
        f"  天赋方向：{card['talent']}",
        f"  角色定位：{t['role_type']} —— {t['role_desc']}",
        f"  加点建议：{t['skill_points']}",
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
        f"【身强弱与喜用神】",
        f"  {card['gender']} · {card['age']} 岁 ｜ {card['body_strength']} ｜ 喜用神: {card['useful_god']} ｜ 忌神: {card['avoid_god']}",
        f"  忌神明细(病神): {card['jishen_detail']}",
        f"  调候提示: {card['climate'][0] + '（' + card['climate'][1] + '）' if card['climate'][0] else card['climate'][1]}",
        f"  格局大类: {card['pattern_type']} ｜ 主导十神: {card['ten_god_dominant']}",
        "",
        f"【出图 Prompt】",
        card["image_prompt"],
        "",
        f"【完整卡牌 Prompt】（人物 + 文字一体，可直接出图）",
        card["card_prompt"],
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

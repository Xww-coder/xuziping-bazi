#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
徐子平排盘引擎 —— 依《渊海子平》子平法排四柱、定五行、取十神、起大运。
依赖: pip install sxtwl  (寿星天文历, 精确到节气与真太阳时分界)

用法:
    python3 paipan.py --date 1990-05-20 --time 14:30 --gender 男 [--city 北京]
                      [--zwt 116.4] [--tz-offset 8]
                      # 出生地经度与出生时 UTC 时差, 用于真太阳时校正(可选)
输出为结构化文本, 供徐子平口吻解读时引用。
"""
import argparse, calendar, math, sys
from datetime import datetime, timedelta
try:
    import sxtwl
except ImportError:
    sys.exit("缺少依赖: 请先运行  pip install sxtwl --break-system-packages")

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
GAN_WX = {"甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土","庚":"金","辛":"金","壬":"水","癸":"水"}
ZHI_WX = {"子":"水","丑":"土","寅":"木","卯":"木","辰":"土","巳":"火","午":"火","未":"土","申":"金","酉":"金","戌":"土","亥":"水"}
GAN_YANG = set("甲丙戊庚壬")   # 阳干
# 地支藏干(主气,中气,余气)
CANG = {
    "子":["癸"], "丑":["己","癸","辛"], "寅":["甲","丙","戊"], "卯":["乙"],
    "辰":["戊","乙","癸"], "巳":["丙","庚","戊"], "午":["丁","己"], "未":["己","丁","乙"],
    "申":["庚","壬","戊"], "酉":["辛"], "戌":["戊","辛","丁"], "亥":["壬","甲"],
}
# 五行生克
SHENG = {"木":"火","火":"土","土":"金","金":"水","水":"木"}   # 我生
KE    = {"木":"土","土":"水","水":"火","火":"金","金":"木"}   # 我克
# 十二节(用于起大运, 只取节不取气)
JIE_NAMES = {"立春","惊蛰","清明","立夏","芒种","小暑","立秋","白露","寒露","立冬","大雪","小寒"}

HIDDEN_LEVELS = ("本气", "中气", "余气")
SUPPORT_DEITIES = {"比肩", "劫财", "正印", "偏印"}
OUTPUT_DEITIES = {"食神", "伤官"}
WEALTH_DEITIES = {"正财", "偏财"}
OFFICER_DEITIES = {"正官", "七杀"}
PATTERN_NAMES = {
    "正官": "正官格", "七杀": "七杀格",
    "正财": "正财格", "偏财": "偏财格",
    "正印": "正印格", "偏印": "偏印格",
    "食神": "食神格", "伤官": "伤官格",
}
JIANLU_BRANCH = {
    "甲":"寅", "乙":"卯", "丙":"巳", "丁":"午", "戊":"巳",
    "己":"午", "庚":"申", "辛":"酉", "壬":"亥", "癸":"子",
}
# 阳刃（阳干帝旺之位）：甲刃卯、丙刃午、戊刃午、庚刃酉、壬刃子
YANG_REN = {"甲":"卯", "丙":"午", "戊":"午", "庚":"酉", "壬":"子"}
# 调候简表：依《穷通宝鉴》大意，按 日主五行 × 月令季节 取调候字（调候为辅，不夺格局喜忌）
CLIMATE_TABLE = {
    "木": {"春": ("火", "春木余寒未退，喜火暖局"), "夏": ("水", "夏木繁茂，喜水润局"),
           "秋": ("火", "秋金克木，喜火制金护木"), "冬": ("火", "冬木寒凝，喜火暖局")},
    "火": {"春": ("水", "春火初升，喜水润局"), "夏": ("水", "夏火炎烈，喜水调候"),
           "秋": ("木", "秋火气衰，喜木生火"), "冬": ("木", "冬火寒微，喜木生火暖局")},
    "土": {"春": ("火", "春土寒湿，喜火暖局"), "夏": ("水", "夏土燥热，喜水润局"),
           "秋": ("火", "秋金泄土，喜火生土"), "冬": ("火", "冬土寒凝，喜火暖局")},
    "金": {"春": ("火", "春金寒弱，喜火暖局"), "夏": ("水", "夏火克金，喜水淘洗降温"),
           "秋": ("火", "秋金旺相，喜火锻炼成器"), "冬": ("火", "冬金寒凝，喜火暖局")},
    "水": {"春": ("金", "春木泄水，喜金发水源"), "夏": ("金", "夏水衰弱，喜金生源"),
           "秋": ("火", "秋水汪洋，喜火暖局调候"), "冬": ("火", "冬水寒盛，喜火暖局")},
}
SEASON_BY_BRANCH = {
    **{z: "春" for z in "寅卯辰"},
    **{z: "夏" for z in "巳午未"},
    **{z: "秋" for z in "申酉戌"},
    **{z: "冬" for z in "亥子丑"},
}
STEM_COMBINATIONS = {"甲":"己", "己":"甲", "乙":"庚", "庚":"乙", "丙":"辛", "辛":"丙", "丁":"壬", "壬":"丁", "戊":"癸", "癸":"戊"}
STEM_COMBINATION_ELEMENT = {frozenset("甲己"):"土", frozenset("乙庚"):"金", frozenset("丙辛"):"水", frozenset("丁壬"):"木", frozenset("戊癸"):"火"}

BRANCH_SIX_COMBINES = {frozenset(x) for x in ("子丑", "寅亥", "卯戌", "辰酉", "巳申", "午未")}
BRANCH_SIX_CLASHES = {frozenset(x) for x in ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥")}
BRANCH_SIX_HARMS = {frozenset(x) for x in ("子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌")}
BRANCH_THREE_COMBINES = {
    frozenset("申子辰"): ("申子辰", "水"), frozenset("亥卯未"): ("亥卯未", "木"),
    frozenset("寅午戌"): ("寅午戌", "火"), frozenset("巳酉丑"): ("巳酉丑", "金"),
}
BRANCH_THREE_MEETINGS = {
    frozenset("亥子丑"): ("亥子丑", "水"), frozenset("寅卯辰"): ("寅卯辰", "木"),
    frozenset("巳午未"): ("巳午未", "火"), frozenset("申酉戌"): ("申酉戌", "金"),
}


def shishen(day_gan, other):
    """other 相对 日主 day_gan 的十神。"""
    if other == day_gan_placeholder:
        pass
    dw, ow = GAN_WX[day_gan], GAN_WX[other]
    same_pol = (day_gan in GAN_YANG) == (other in GAN_YANG)
    if dw == ow:
        return "比肩" if same_pol else "劫财"
    if SHENG[dw] == ow:            # 我生 -> 食伤
        return "食神" if same_pol else "伤官"
    if KE[dw] == ow:              # 我克 -> 财
        return "偏财" if same_pol else "正财"
    if KE[ow] == dw:              # 克我 -> 官杀
        return "七杀" if same_pol else "正官"
    return "偏印" if same_pol else "正印"   # 生我 -> 印


day_gan_placeholder = None


def gz_str(o):
    return GAN[o.tg] + ZHI[o.dz]


def equation_of_time_minutes(local_dt):
    """NOAA 近似公式计算均时差（分钟）。"""
    days_in_year = 366 if calendar.isleap(local_dt.year) else 365
    fractional_hour = local_dt.hour + local_dt.minute / 60.0 + local_dt.second / 3600.0
    gamma = 2.0 * math.pi / days_in_year * (
        local_dt.timetuple().tm_yday - 1 + (fractional_hour - 12.0) / 24.0
    )
    return 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2.0 * gamma)
        - 0.040849 * math.sin(2.0 * gamma)
    )


def solar_time_adjust(local_dt, lon, tz_offset=8.0):
    """把当地钟表时间校正为真太阳时，并保留日期跨越。

    使用 NOAA 的时间偏移公式：均时差 + 4×经度 - 60×时区。
    ``tz_offset`` 是出生时当地相对 UTC 的小时偏移；中国标准时间为 +8。
    """
    if lon is None:
        return local_dt, 0.0, 0.0
    longitude_offset = 4.0 * lon - 60.0 * tz_offset
    equation_offset = equation_of_time_minutes(local_dt)
    total_offset = longitude_offset + equation_offset
    return local_dt + timedelta(minutes=total_offset), longitude_offset, equation_offset


def calculate_ganzhi(local_dt, lon=None, tz_offset=8.0):
    """返回真太阳时、校正量与年/月/日/时干支对象。"""
    solar_dt, longitude_offset, equation_offset = solar_time_adjust(local_dt, lon, tz_offset)
    day = sxtwl.fromSolar(solar_dt.year, solar_dt.month, solar_dt.day)
    yGZ, mGZ, dGZ = day.getYearGZ(), day.getMonthGZ(), day.getDayGZ()
    # sxtwl 官方接口直接接收 0-23 小时，并在 23 时区分晚子时；不可四舍五入。
    hGZ = day.getHourGZ(solar_dt.hour)
    return solar_dt, longitude_offset, equation_offset, (yGZ, mGZ, dGZ, hGZ)


def source_element(element):
    """返回生 ``element`` 的五行。"""
    return next(k for k, v in SHENG.items() if v == element)


def controller_element(element):
    """返回克 ``element`` 的五行。"""
    return next(k for k, v in KE.items() if v == element)


def wuxing_distribution(pillars):
    """只做可复核的五行出现分布，不据此直接判旺衰。"""
    score = {"木":0.0, "火":0.0, "土":0.0, "金":0.0, "水":0.0}
    for _, g, z in pillars:
        score[GAN_WX[g]] += 1.0
        hidden = CANG[z]
        weights = [1.0] + [0.5] * (len(hidden) - 1)
        for stem, weight in zip(hidden, weights):
            score[GAN_WX[stem]] += weight
    return score


def analyze_day_master(pillars):
    """以月令为提纲，结合通根和透干给出可解释的旺衰候选。"""
    day_gan = pillars[2][1]
    day_element = GAN_WX[day_gan]
    month_branch = pillars[1][2]
    month_main = CANG[month_branch][0]
    month_deity = shishen(day_gan, month_main)

    if month_deity in {"比肩", "劫财"}:
        month_judgment, evidence_score = "得令（比劫当令）", 3.0
    elif month_deity in {"正印", "偏印"}:
        month_judgment, evidence_score = "得月令之生（印星当令）", 2.0
    elif month_deity in OUTPUT_DEITIES:
        month_judgment, evidence_score = "失令且泄身（食伤当令）", -1.75
    elif month_deity in WEALTH_DEITIES:
        month_judgment, evidence_score = "失令且耗身（财星当令）", -1.25
    else:
        month_judgment, evidence_score = "失令受制（官杀当令）", -2.5

    roots = []
    for label, _, branch in pillars:
        for index, hidden_stem in enumerate(CANG[branch]):
            if GAN_WX[hidden_stem] == day_element:
                roots.append({
                    "pillar": label, "branch": branch, "stem": hidden_stem,
                    "level": HIDDEN_LEVELS[index], "index": index,
                })
                evidence_score += (1.75, 1.0, 0.5)[index]
                break

    supportive_stems, draining_stems = [], []
    position_factor = {"年":0.8, "月":1.2, "时":1.0}
    for label, stem, _ in pillars:
        if label == "日":
            continue
        deity = shishen(day_gan, stem)
        item = {"pillar": label, "stem": stem, "deity": deity}
        factor = position_factor[label]
        if deity in SUPPORT_DEITIES:
            supportive_stems.append(item)
            evidence_score += factor * (1.0 if deity in {"比肩", "劫财"} else 0.8)
        else:
            draining_stems.append(item)
            if deity in OFFICER_DEITIES:
                evidence_score -= factor
            elif deity in OUTPUT_DEITIES:
                evidence_score -= factor * 0.75
            else:
                evidence_score -= factor * 0.65

    # 非月支只取主气作辅助证据；同类根已在上面计入，不重复计算。
    for label, _, branch in pillars:
        if label == "月":
            continue
        main_deity = shishen(day_gan, CANG[branch][0])
        if main_deity in {"正印", "偏印"}:
            evidence_score += 0.6
        elif main_deity in OFFICER_DEITIES:
            evidence_score -= 0.6
        elif main_deity in OUTPUT_DEITIES:
            evidence_score -= 0.45
        elif main_deity in WEALTH_DEITIES:
            evidence_score -= 0.35

    if evidence_score >= 3.0:
        status = "偏旺"
    elif evidence_score <= -3.0:
        status = "偏弱"
    else:
        status = "中和"
    confidence = "高" if abs(evidence_score) >= 5.0 else "中" if abs(evidence_score) >= 2.5 else "低"

    special_candidates = []
    if status == "偏弱" and not roots and not supportive_stems:
        special_candidates.append("从弱格候选（须再核对合化、制化与岁运，不能仅凭无根定从）")
    if status == "偏旺" and not draining_stems:
        special_candidates.append("专旺格候选（须再核对气势是否纯粹）")

    return {
        "day_gan": day_gan,
        "day_element": day_element,
        "month_branch": month_branch,
        "month_main": month_main,
        "month_deity": month_deity,
        "month_judgment": month_judgment,
        "roots": roots,
        "supportive_stems": supportive_stems,
        "draining_stems": draining_stems,
        "status": status,
        "confidence": confidence,
        "special_candidates": special_candidates,
    }


def _lu_ren_name(day_gan, month_branch):
    """月令为日主禄/刃/劫时，不以月令立格，命名建禄格、羊刃格或月劫格。"""
    if month_branch == JIANLU_BRANCH[day_gan]:
        return "建禄格"
    if month_branch == YANG_REN.get(day_gan):
        return "羊刃格"
    return "月劫格"


def analyze_pattern(pillars, day_analysis):
    """按月令藏干及透干列出常规格局候选，并标记特殊格局复核项。"""
    day_gan = day_analysis["day_gan"]
    month_branch = day_analysis["month_branch"]
    month_hidden = CANG[month_branch]
    transparent = []
    for index, stem in enumerate(month_hidden):
        positions = [label for label, visible, _ in pillars if label != "日" and visible == stem]
        if positions:
            transparent.append({
                "stem": stem, "deity": shishen(day_gan, stem),
                "level": HIDDEN_LEVELS[index], "index": index, "positions": positions,
            })

    selected = transparent[0] if transparent else {
        "stem": month_hidden[0], "deity": shishen(day_gan, month_hidden[0]),
        "level": "本气", "index": 0, "positions": [],
    }
    selected_deity = selected["deity"]
    # 严格子平法：月令本气为日主比劫（禄/刃/劫）者，不立八格，属建禄/羊刃/月劫，
    # 透干财官食伤只决定用神，不改格局名称（《子平真诠》论建禄月劫）。
    month_main_deity = shishen(day_gan, month_hidden[0])
    if month_main_deity in {"比肩", "劫财"}:
        pattern_name = _lu_ren_name(day_gan, month_branch)
    elif selected_deity in PATTERN_NAMES:
        pattern_name = PATTERN_NAMES[selected_deity]
    elif month_main_deity in PATTERN_NAMES:
        # 透干者为比劫（不立八格）时，退而以月令本气立格（如癸水申月壬透 → 正印格）
        pattern_name = PATTERN_NAMES[month_main_deity]
    else:
        pattern_name = "月劫格"

    candidates = []
    source_items = list(transparent)
    if not any(item["stem"] == month_hidden[0] for item in source_items):
        source_items.append({
            "stem": month_hidden[0], "deity": shishen(day_gan, month_hidden[0]),
            "level": "本气", "index": 0, "positions": [],
        })
    for item in source_items:
        deity = item["deity"]
        if month_main_deity in {"比肩", "劫财"}:
            name = _lu_ren_name(day_gan, month_branch)
        elif deity in PATTERN_NAMES:
            name = PATTERN_NAMES[deity]
        elif month_main_deity in PATTERN_NAMES:
            name = PATTERN_NAMES[month_main_deity]
        else:
            name = "月劫格"
        candidates.append({**item, "pattern": name})

    # 三合、三会若覆盖月支，可能改变月令取用；只列候选，不擅自认定成化。
    branch_set = {branch for _, _, branch in pillars}
    for relation_name, relation_map in (("三合", BRANCH_THREE_COMBINES), ("三会", BRANCH_THREE_MEETINGS)):
        for combo, (_, element) in relation_map.items():
            if combo <= branch_set and month_branch in combo:
                transformed_stem = next(
                    (stem for stem in month_hidden if GAN_WX[stem] == element),
                    next(stem for stem in GAN if GAN_WX[stem] == element),
                )
                deity = shishen(day_gan, transformed_stem)
                if month_main_deity in {"比肩", "劫财"}:
                    name = _lu_ren_name(day_gan, month_branch)
                elif deity in PATTERN_NAMES:
                    name = PATTERN_NAMES[deity]
                elif month_main_deity in PATTERN_NAMES:
                    name = PATTERN_NAMES[month_main_deity]
                else:
                    name = "月劫格"
                if not any(item["stem"] == transformed_stem and item["pattern"] == name for item in candidates):
                    candidates.append({
                        "stem": transformed_stem, "deity": deity, "level": f"{relation_name}{element}候选",
                        "index": 0, "positions": [], "pattern": name,
                    })

    special_candidates = list(day_analysis["special_candidates"])
    combining_stem = STEM_COMBINATIONS[day_gan]
    combination_positions = [
        label for label, stem, _ in pillars if label != "日" and stem == combining_stem
    ]
    if combination_positions:
        combination_element = STEM_COMBINATION_ELEMENT[frozenset((day_gan, combining_stem))]
        special_candidates.append(
            f"{day_gan}{combining_stem}合化{combination_element}候选（{combining_stem}见于{'、'.join(combination_positions)}干；须核对化神得令与有无破局）"
        )

    confidence = "高" if len(candidates) == 1 and selected["index"] == 0 and selected["positions"] else "中" if len(candidates) == 1 else "低"
    return {
        "month_hidden": [
            {"stem": stem, "deity": shishen(day_gan, stem), "level": HIDDEN_LEVELS[index]}
            for index, stem in enumerate(month_hidden)
        ],
        "transparent": transparent,
        "selected": {**selected, "pattern": pattern_name},
        "candidates": candidates,
        "confidence": confidence,
        "special_candidates": special_candidates,
    }


def analyze_branch_relations(pillars):
    """列出可客观识别的地支关系；是否成化留给格局层判断。"""
    labels = [(label, branch) for label, _, branch in pillars]
    branches = [branch for _, branch in labels]
    branch_set = set(branches)
    relations = []

    for combo, (name, element) in BRANCH_THREE_COMBINES.items():
        if combo <= branch_set:
            relations.append(f"{name}三合{element}局")
    for combo, (name, element) in BRANCH_THREE_MEETINGS.items():
        if combo <= branch_set:
            relations.append(f"{name}三会{element}方")

    for i, (left_label, left) in enumerate(labels):
        for right_label, right in labels[i + 1:]:
            pair = frozenset((left, right))
            position = f"{left_label}{left}-{right_label}{right}"
            if pair in BRANCH_SIX_COMBINES:
                relations.append(f"{position}六合")
            if pair in BRANCH_SIX_CLASHES:
                relations.append(f"{position}六冲")
            if pair in BRANCH_SIX_HARMS:
                relations.append(f"{position}相害")
            if pair == frozenset("子卯"):
                relations.append(f"{position}相刑")

    if set("寅巳申") <= branch_set:
        relations.append("寅巳申三刑")
    if set("丑未戌") <= branch_set:
        relations.append("丑未戌三刑")
    for branch in "辰午酉亥":
        if branches.count(branch) >= 2:
            relations.append(f"{branch}{branch}自刑")
    return relations


def _deity_present(pillars, day_gan, deity_name):
    """命局中某十神是否实见（天干透出或地支藏干，任一层级）。"""
    for label, g, z in pillars:
        if label == "日":
            continue
        if shishen(day_gan, g) == deity_name:
            return True
        for c in CANG[z]:
            if shishen(day_gan, c) == deity_name:
                return True
    return False


def _transparent_deities(pillars, day_gan):
    """年、月、时三干透出之十神（去重、按柱序）。"""
    out = []
    for label, g, _ in pillars:
        if label == "日":
            continue
        d = shishen(day_gan, g)
        if d not in out:
            out.append(d)
    return out


def _month_clash_note(pillars, month_branch):
    """月令地支是否被年/日/时支六冲，冲则格局根基动摇，须提示。"""
    for label, _, z in pillars:
        if label == "月":
            continue
        if frozenset((month_branch, z)) in BRANCH_SIX_CLASHES:
            return f"月令{month_branch}逢{label}支{z}之冲（用神根基动摇，须防破格）"
    return None


def _cong_follow_type(pillars, day_gan):
    """从弱格候选所从何神：财 / 官杀 / 食伤(从儿)，按月令主气与透干加权。"""
    counts = {"财": 0.0, "官杀": 0.0, "食伤": 0.0}
    month_main = shishen(day_gan, CANG[pillars[1][2]][0])
    if month_main in WEALTH_DEITIES:
        counts["财"] += 3.0
    elif month_main in OFFICER_DEITIES:
        counts["官杀"] += 3.0
    elif month_main in OUTPUT_DEITIES:
        counts["食伤"] += 3.0
    for label, g, _ in pillars:
        if label == "日":
            continue
        d = shishen(day_gan, g)
        if d in WEALTH_DEITIES:
            counts["财"] += 1.5
        elif d in OFFICER_DEITIES:
            counts["官杀"] += 1.5
        elif d in OUTPUT_DEITIES:
            counts["食伤"] += 1.5
    return max(counts, key=counts.get)


def analyze_use_gods(pillars, day_analysis, pattern_analysis):
    """子平法喜忌：以月令格局为纲，分定 用神/相神(喜神)/忌神(病神)/药神，调候为辅。

    严格依《渊海子平》《子平真诠》之旨：
      - 用神专求月令（立格之神）；身强身弱只作格局内部选相之参考，
        不以“身弱喜印比、身旺喜财官食伤”的笼统口诀替代格局判断。
      - 喜神/相神：辅佐用神成格之神；忌神：破格之病神；
        药神：制病之神；另列“岁运须防”之潜在忌神。
      - 调候（《穷通宝鉴》简表）为辅，不夺格局喜忌。
    """
    day_gan = day_analysis["day_gan"]
    day_element = day_analysis["day_element"]
    yin = source_element(day_element)          # 印
    shi = SHENG[day_element]                   # 食伤
    cai = KE[day_element]                      # 财
    guan = controller_element(day_element)     # 官杀
    bijie = day_element                        # 比劫
    status = day_analysis["status"]
    selected = pattern_analysis["selected"]
    pattern_name = selected["pattern"]
    pattern_element = GAN_WX[selected["stem"]]
    month_branch = day_analysis["month_branch"]
    special = "、".join(pattern_analysis.get("special_candidates", []))
    # 特殊格局候选覆盖名义格局名，喜忌按实际所从/所旺之神取（仍标注“候选须复核”）
    cong = None
    if "专旺格候选" in special:
        pattern_name = "专旺格"
    elif "从弱格候选" in special:
        cong = _cong_follow_type(pillars, day_gan)
        pattern_name = {"财": "从财格", "官杀": "从杀格"}.get(cong, "从儿格")

    yongshen = []   # (element, 十神称谓, 理由)
    xishen = []     # (element, 理由)
    jishen = []     # {"element","deity","reason","present"}
    yaoshen = []    # (element, 理由)

    def add_ji(element, deity, reason, present):
        if not any(item["deity"] == deity and item["reason"] == reason for item in jishen):
            jishen.append({"element": element, "deity": deity, "reason": reason, "present": present})

    def add_yong(element, deity, reason):
        if not any(e == element and d == deity for e, d, _ in yongshen):
            yongshen.append((element, deity, reason))

    def add_xi(element, reason):
        if not any(e == element and r == reason for e, r in xishen):
            xishen.append((element, reason))

    def add_yao(element, reason):
        if not any(e == element and r == reason for e, r in yaoshen):
            yaoshen.append((element, reason))

    # ---------------- 禄刃格（建禄 / 月劫 / 羊刃）：月令为日主旺地，不取月令立格 ----------------
    if pattern_name in ("建禄格", "月劫格", "羊刃格"):
        transparent = [d for d in _transparent_deities(pillars, day_gan) if d in OFFICER_DEITIES | WEALTH_DEITIES | OUTPUT_DEITIES]
        if transparent:
            lead = transparent[0]
            yong_deity = lead
            yong_reason = "禄刃格不取月令为用，取透干之财官食伤为用（%s透干）" % lead
            add_yong({"正官": guan, "七杀": guan, "正财": cai, "偏财": cai,
                      "食神": shi, "伤官": shi}[lead], lead, yong_reason)
        else:
            add_yong(cai, "财", "禄刃格不取月令为用，财官食伤喜透；无透则以财为用（建禄用财，须带食伤）")
        if any(e == cai for e, _, _ in yongshen):
            add_xi(shi, "食伤生财（防比劫分财）")
        uses_guan = any(e == guan for e, _, _ in yongshen)
        if uses_guan:
            add_xi(cai, "财生官（官星有源）")
            if _deity_present(pillars, day_gan, "正印") or _deity_present(pillars, day_gan, "偏印"):
                add_xi(yin, "印护官（防伤官克官）")
        if any(e == shi for e, _, _ in yongshen):
            add_xi(cai, "食伤生财（泄秀流通）")
        # 忌
        if _deity_present(pillars, day_gan, "比肩") or _deity_present(pillars, day_gan, "劫财"):
            add_ji(bijie, "比劫", "群比争财（禄刃格最忌比劫分夺）", True)
        # 印：用官/杀时印为护官相神，不作忌；用财/食伤时印纯生比劫，透干者为忌
        if not uses_guan and (_deity_present(pillars, day_gan, "正印") or _deity_present(pillars, day_gan, "偏印")):
            add_ji(yin, "印", "印绶生比劫（禄刃身旺，忌印比再助）", True)
        if uses_guan and _deity_present(pillars, day_gan, "伤官"):
            add_ji(shi, "伤官", "伤官克官（禄刃用官，忌伤官）", True)
        add_yao(guan, "官杀制比劫（群比争财之病，官为药）")

    # ---------------- 专旺格候选：顺旺势 ----------------
    elif pattern_name == "专旺格":
        add_yong(yin, "印", "专旺顺势，喜印生旺气")
        add_yong(bijie, "比劫", "专旺顺势，喜比劫帮身")
        add_xi(shi, "食伤泄秀（专旺亦喜泄其菁英）")
        add_ji(cai, "财", "财逆旺气（专旺格忌财）", False)
        add_ji(guan, "官杀", "官杀逆旺（专旺格忌官杀）", False)

    # ---------------- 从弱格候选：从其所旺之神，忌印比逆从 ----------------
    elif pattern_name in ("从财格", "从杀格", "从儿格"):
        yin_present = _deity_present(pillars, day_gan, "正印") or _deity_present(pillars, day_gan, "偏印")
        bi_present = _deity_present(pillars, day_gan, "比肩") or _deity_present(pillars, day_gan, "劫财")
        if cong == "财":
            add_yong(cai, "财", "从财格，顺势从财")
            add_xi(shi, "食伤生财（从财喜食伤）")
            add_ji(yin, "印", "印逆从（从财忌印帮身）", yin_present)
            add_ji(bijie, "比劫", "比劫逆从（从财忌比劫争财）", bi_present)
        elif cong == "官杀":
            add_yong(guan, "官杀", "从杀格（从官杀），顺势而从")
            add_xi(cai, "财生杀（从杀喜财滋杀）")
            add_ji(yin, "印", "印逆从（从杀忌印帮身）", yin_present)
            add_ji(bijie, "比劫", "比劫逆从（从杀忌比劫抗杀）", bi_present)
        else:
            add_yong(shi, "食伤", "从儿格，顺势从食伤")
            add_xi(cai, "食伤生财（从儿喜财）")
            add_ji(yin, "印", "印逆从（从儿忌印夺食）", yin_present)
            add_ji(bijie, "比劫", "比劫逆从（从儿忌比劫帮身）", bi_present)
        yaoshen.append(("顺势", "从格喜顺势，无须制化（忌逆从之神）"))

    # ---------------- 正官格 ----------------
    elif pattern_name == "正官格":
        add_yong(guan, "正官", "月令立格之神（正官为用）")
        if status == "偏弱":
            add_xi(yin, "官格身弱，印为相神（化官生身，官印相生）")
            add_xi(bijie, "比劫帮身（身弱任官）")
        elif status == "偏旺":
            add_xi(cai, "财为相神（财生官，官星有源）")
        else:
            add_xi(yin, "印护官生身（中和之官格，印财两相）")
            add_xi(cai, "财生官（中和之官格，印财两相）")
        if _deity_present(pillars, day_gan, "伤官"):
            add_ji(shi, "伤官", "伤官见官，为祸百端（官格最忌伤官破格）", True)
        else:
            add_ji(shi, "伤官", "伤官见官，为祸百端（岁运逢伤官须防破格）", False)
        if _deity_present(pillars, day_gan, "七杀"):
            add_ji(guan, "七杀", "官杀混杂（去杀留官方清）", True)
        else:
            add_ji(guan, "七杀", "官杀混杂（岁运逢七杀须防混局）", False)
        if status == "偏弱" and (_deity_present(pillars, day_gan, "正财") or _deity_present(pillars, day_gan, "偏财")):
            add_ji(cai, "财", "财滋官杀（身弱财生官杀，耗身加重）", True)
        add_yao(yin, "印制伤官而护官（伤官为病，印为药）")

    # ---------------- 七杀格 ----------------
    elif pattern_name == "七杀格":
        add_yong(guan, "七杀", "月令立格之神（七杀为用，须制化）")
        if status == "偏弱":
            add_xi(yin, "杀印相生（印化杀生身，身弱用印）")
            add_xi(bijie, "比劫帮身（身弱任杀）")
            # 身弱杀重：财党杀为病
            if _deity_present(pillars, day_gan, "正财") or _deity_present(pillars, day_gan, "偏财"):
                add_ji(cai, "财", "财滋弱杀（财党杀，杀更攻身）", True)
            else:
                add_ji(cai, "财", "财滋弱杀（岁运逢财须防党杀）", False)
        else:
            add_xi(shi, "食神制杀（身强杀浅，食制为贵）")
            add_xi(cai, "财滋杀（身强杀浅，财生杀为贵）")
            # 身强杀浅：财为喜不作忌；杀重无制、财党杀之戒见诸岁运复核
        if _deity_present(pillars, day_gan, "正官"):
            add_ji(guan, "正官", "官杀混杂（杀格忌官来混）", True)
        else:
            add_ji(guan, "正官", "官杀混杂（岁运逢正官须防混局）", False)
        if status == "偏弱" and not (
            _deity_present(pillars, day_gan, "正印") or _deity_present(pillars, day_gan, "食神")
        ):
            add_ji(guan, "七杀", "杀重身轻，无制无化（大运须防杀攻身）", False)
        add_yao(yin, "印化杀生身（杀为病，印为药）")
        add_yao(shi, "食神制杀（杀为病，食为药）")

    # ---------------- 财格（正财 / 偏财） ----------------
    elif pattern_name in ("正财格", "偏财格"):
        add_yong(cai, "财", "月令立格之神（财为用）")
        if status == "偏弱":
            add_xi(bijie, "比劫帮身任财（财多身弱，富屋贫人，须帮身）")
            add_xi(yin, "印星生身（身弱任财）")
            add_ji(cai, "财", "财多身弱（富屋贫人，财反为病）", True)
            if _deity_present(pillars, day_gan, "正官") or _deity_present(pillars, day_gan, "七杀"):
                add_ji(guan, "官杀", "官杀泄财攻身（身弱财生官杀，日主不胜）", True)
            if _deity_present(pillars, day_gan, "食神") or _deity_present(pillars, day_gan, "伤官"):
                add_ji(shi, "食伤", "食伤泄身生财（身弱愈泄愈弱）", True)
            add_yao(bijie, "比劫制财帮身（财多身弱之病，比劫为药）")
            add_yao(yin, "印星生身（财多身弱之病，印亦为药）")
        else:
            add_xi(shi, "食伤生财（财有源头）")
            add_xi(guan, "官星护财（身强财格，官护财不被劫）")
            if _deity_present(pillars, day_gan, "比肩") or _deity_present(pillars, day_gan, "劫财"):
                add_ji(bijie, "比劫", "比劫夺财（身强逢比劫分财，破格）", True)
            else:
                add_ji(bijie, "比劫", "比劫夺财（岁运逢比劫须防分财）", False)
            add_yao(shi, "食伤化比劫而生财（比劫夺财之病，食伤为药）")
            add_yao(guan, "官星制比劫而护财（比劫夺财之病，官亦为药）")

    # ---------------- 印格（正印 / 偏印） ----------------
    elif pattern_name in ("正印格", "偏印格"):
        add_yong(yin, "印", "月令立格之神（印为用）")
        if status == "偏旺":
            add_xi(cai, "财星破印（印旺身强，喜财坏印为用）")
            add_xi(shi, "食伤泄秀（印旺身强，食伤泄身生财）")
            add_ji(yin, "印", "印旺为病（印重身强，印反为忌，喜财破印）", True)
            add_yao(cai, "财星破印（印旺为病，财为药）")
            add_yao(shi, "食伤泄秀生财（印旺为病，食伤亦为药）")
        else:
            add_xi(guan, "官印相生（官杀生印，印再生身）")
            add_xi(bijie, "比劫帮身（印格身弱喜助）")
            if _deity_present(pillars, day_gan, "正财") or _deity_present(pillars, day_gan, "偏财"):
                add_ji(cai, "财", "财星坏印（印为用，财破之）", True)
            else:
                add_ji(cai, "财", "财星坏印（岁运逢财须防破印）", False)
            if _deity_present(pillars, day_gan, "食神") or _deity_present(pillars, day_gan, "伤官"):
                add_ji(shi, "食伤", "食伤泄身耗印（身弱印格，忌泄）", True)
            add_yao(bijie, "比劫制财护印（财坏印之病，比劫为药）")
        if pattern_name == "偏印格" and _deity_present(pillars, day_gan, "食神"):
            add_ji(yin, "偏印", "枭神夺食（偏印夺食为病）", True)
            add_yao(cai, "财制枭护食（枭神夺食之病，财为药）")

    # ---------------- 食神格 ----------------
    elif pattern_name == "食神格":
        add_yong(shi, "食神", "月令立格之神（食神为用）")
        if status == "偏弱":
            add_xi(yin, "食神配印（身弱食神泄身，喜印制食生身）")
            add_xi(bijie, "比劫帮身")
            add_ji(shi, "食神", "食多泄身（身弱食神泄身太过）", True)
            add_yao(yin, "印制食生身（食多泄身之病，印为药）")
        else:
            add_xi(cai, "食神生财（食神为用，喜财流通）")
            if _deity_present(pillars, day_gan, "偏印"):
                add_ji(yin, "偏印", "枭神夺食（食神为用，枭印夺之）", True)
            else:
                add_ji(yin, "偏印", "枭神夺食（岁运逢枭印须防夺食）", False)
            add_yao(cai, "财制枭护食（枭神夺食之病，财为药）")

    # ---------------- 伤官格 ----------------
    elif pattern_name == "伤官格":
        add_yong(shi, "伤官", "月令立格之神（伤官为用）")
        if status == "偏弱":
            add_xi(yin, "伤官配印（身弱伤官泄身，喜印止泄生身）")
            add_xi(bijie, "比劫帮身")
            add_ji(shi, "伤官", "伤官泄身太过（身弱伤官为病）", True)
            if _deity_present(pillars, day_gan, "正财") or _deity_present(pillars, day_gan, "偏财"):
                add_ji(cai, "财", "伤官生财泄身（身弱愈泄愈弱）", True)
            add_yao(yin, "印制伤生身（伤官泄身之病，印为药）")
        else:
            add_xi(cai, "伤官生财（身强伤官，喜财流通）")
            if _deity_present(pillars, day_gan, "正官"):
                add_ji(guan, "正官", "伤官见官，为祸百端（伤官格忌正官破格）", True)
            else:
                add_ji(guan, "正官", "伤官见官，为祸百端（岁运逢正官须防破格）", False)
            add_yao(yin, "印制伤护官（伤官见官之病，佩印为解）")

    # ---------------- 兜底：常规格但无专属规则（不应发生） ----------------
    else:
        add_yong(pattern_element, selected["deity"], "以月令立格之神为用")
        add_xi(yin if status == "偏弱" else shi, "中和之局，兼顾格局成败与日主平衡")

    # 喜用神候选（兼容旧口径 fuyi，供卡牌/加点建议取用）：用神 + 相神喜神 之五行，去重
    fuyi = []
    for e, d, r in yongshen:
        if not any(x == e for x, _ in fuyi):
            fuyi.append((e, r))
    for e, r in xishen:
        if not any(x == e for x, _ in fuyi):
            fuyi.append((e, r))
    if not fuyi:
        fuyi = [(day_element, "日主同气，兼顾全局复核")]

    # 调候（《穷通宝鉴》简表，按日主五行 × 季节）
    season = SEASON_BY_BRANCH[month_branch]
    climate = CLIMATE_TABLE[day_element][season]
    climate = (
        climate[0],
        f"{climate[1]}（简表参考，仍须按日主阴阳、干支组合与格局复核；调候为辅，不夺格局喜忌）",
    )

    clash_note = _month_clash_note(pillars, month_branch)
    notes = []
    if clash_note:
        notes.append(clash_note)
    notes.append("身强身弱仅作格局内部选相参考，不以强弱笼统定喜忌；忌神为破格之病神，药神为制病之神，均须结合合冲制化与大运复核。")

    return {
        "method": "子平法（以月令格局为纲）",
        "pattern_name": pattern_name,
        "pattern_stem": selected["stem"],
        "pattern_deity": selected["deity"],
        "pattern_element": pattern_element,
        "yongshen": yongshen,
        "xishen": xishen,
        "jishen": jishen,
        "yaoshen": yaoshen,
        "fuyi": fuyi,
        "climate": climate,
        "note": "；".join(notes),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="公历生日 YYYY-MM-DD")
    ap.add_argument("--time", required=True, help="出生时刻 HH:MM (24h)")
    ap.add_argument("--gender", required=True, choices=["男", "女"])
    ap.add_argument("--city", default="")
    ap.add_argument("--zwt", type=float, default=None, help="出生地经度(东经为正), 用于真太阳时校正")
    ap.add_argument("--tz-offset", type=float, default=8.0, help="出生时当地 UTC 时差, 默认 +8(中国标准时间)")
    a = ap.parse_args()

    try:
        local_dt = datetime.strptime(f"{a.date} {a.time}", "%Y-%m-%d %H:%M")
    except ValueError as exc:
        ap.error(f"日期或时间格式无效: {exc}")
    if a.zwt is not None and not -180.0 <= a.zwt <= 180.0:
        ap.error("出生地经度必须在 -180 到 180 之间")
    if not -14.0 <= a.tz_offset <= 14.0:
        ap.error("UTC 时差必须在 -14 到 +14 之间")

    y, m, d, hh, mm = local_dt.year, local_dt.month, local_dt.day, local_dt.hour, local_dt.minute
    solar_dt, longitude_offset, equation_offset, ganzhi = calculate_ganzhi(
        local_dt, a.zwt, a.tz_offset
    )
    yGZ, mGZ, dGZ, hGZ = ganzhi
    day_gan = GAN[dGZ.tg]

    pillars = [
        ("年", GAN[yGZ.tg], ZHI[yGZ.dz]),
        ("月", GAN[mGZ.tg], ZHI[mGZ.dz]),
        ("日", GAN[dGZ.tg], ZHI[dGZ.dz]),
        ("时", GAN[hGZ.tg], ZHI[hGZ.dz]),
    ]

    print("=" * 46)
    print(f"公历 {y}-{m:02d}-{d:02d} {hh:02d}:{mm:02d}  {a.gender}" + (f"  出生地 {a.city}" if a.city else ""))
    if a.zwt is not None:
        print(
            f"(真太阳时校正: {solar_dt:%Y-%m-%d %H:%M:%S}, 时支 {ZHI[hGZ.dz]}时; "
            f"经度/时区 {longitude_offset:+.1f} 分, 均时差 {equation_offset:+.1f} 分)"
        )
    print("=" * 46)

    # 四柱 + 十神
    print("\n【四柱八字】")
    header = "        " + "  ".join(p[0] + "柱" for p in pillars)
    print(header)
    gan_line = "天干    " + "    ".join(p[1] for p in pillars)
    zhi_line = "地支    " + "    ".join(p[2] for p in pillars)
    print(gan_line)
    print(zhi_line)
    # 天干十神
    tg_ss = []
    for lbl, g, z in pillars:
        tg_ss.append("日主" if lbl == "日" else shishen(day_gan, g))
    print("干神    " + "  ".join(tg_ss))
    # 地支藏干主气十神
    dz_ss = []
    for lbl, g, z in pillars:
        main_cang = CANG[z][0]
        dz_ss.append(shishen(day_gan, main_cang))
    print("支神    " + "  ".join(dz_ss) + "  (取地支主气)")

    # 藏干明细
    print("\n【地支藏干】")
    for lbl, g, z in pillars:
        items = [f"{c}({shishen(day_gan, c)})" for c in CANG[z]]
        print(f"  {lbl}支 {z}: " + "、".join(items))

    # 五行数字只作出现分布；旺衰另按月令、通根和透干给出证据链。
    print("\n【五行分布】(仅统计出现, 不直接据此判旺衰)")
    score = wuxing_distribution(pillars)
    for wx in ["木","火","土","金","水"]:
        bar = "█" * int(round(score[wx] * 2))
        print(f"  {wx}: {score[wx]:4.1f}  {bar}")

    day_analysis = analyze_day_master(pillars)
    pattern_analysis = analyze_pattern(pillars, day_analysis)
    branch_relations = analyze_branch_relations(pillars)
    use_gods = analyze_use_gods(pillars, day_analysis, pattern_analysis)

    print("\n【月令与旺衰证据】")
    print(
        f"  月令 {day_analysis['month_branch']}: 主气 {day_analysis['month_main']}"
        f"({day_analysis['month_deity']}), {day_analysis['month_judgment']}"
    )
    root_text = "、".join(
        f"{item['pillar']}支{item['branch']}藏{item['stem']}({item['level']}根)"
        for item in day_analysis["roots"]
    ) or "无同五行通根"
    support_text = "、".join(
        f"{item['pillar']}干{item['stem']}({item['deity']})"
        for item in day_analysis["supportive_stems"]
    ) or "无"
    drain_text = "、".join(
        f"{item['pillar']}干{item['stem']}({item['deity']})"
        for item in day_analysis["draining_stems"]
    ) or "无"
    print(f"  通根: {root_text}")
    print(f"  天干生扶: {support_text}")
    print(f"  天干克泄耗: {drain_text}")
    print(
        f"  地支关系: {'、'.join(branch_relations) if branch_relations else '未见完整三合/三会或明显六合六冲刑害'}"
        " (是否成化未直接折算)"
    )
    print(
        f"  日主候选: {day_analysis['day_gan']}({day_analysis['day_element']})"
        f" {day_analysis['status']} (置信度 {day_analysis['confidence']}; 非按五行数量直接相加)"
    )

    print("\n【月令透干与格局候选】")
    hidden_text = "、".join(
        f"{item['stem']}({item['deity']}/{item['level']})"
        for item in pattern_analysis["month_hidden"]
    )
    transparent_text = "、".join(
        f"{item['stem']}({item['deity']}/{item['level']})透{'、'.join(item['positions'])}干"
        for item in pattern_analysis["transparent"]
    ) or "月令藏干未透于年、月、时干"
    candidate_text = "、".join(
        f"{item['pattern']}[{item['stem']}{item['deity']}/{item['level']}]"
        for item in pattern_analysis["candidates"]
    )
    selected = pattern_analysis["selected"]
    selected_basis = (
        f"透{'、'.join(selected['positions'])}干" if selected["positions"] else "本气未透, 以月令本气立候选"
    )
    print(f"  月令藏干: {hidden_text}")
    print(f"  透干: {transparent_text}")
    print(f"  常规格局: {candidate_text} (候选置信度 {pattern_analysis['confidence']})")
    print(f"  暂取: {selected['pattern']} —— {selected['stem']}({selected['deity']}/{selected['level']}), {selected_basis}")
    print(
        "  特殊格局复核: "
        + ("；".join(pattern_analysis["special_candidates"]) if pattern_analysis["special_candidates"] else "未触发从格、专旺或合化候选")
    )

    print("\n【喜用神与忌神】(子平法：格局为纲，分列 用神/相神喜神/忌神病神/药神/调候)")
    yong_text = "；".join(f"{e}({d}: {r})" for e, d, r in use_gods["yongshen"])
    print(f"  格局用神: {yong_text} —— 对应 {selected['pattern']}")
    xi_text = "；".join(f"{e}({r})" for e, r in use_gods["xishen"]) or "（相神与用神同气或已含于用神）"
    print(f"  相神/喜神: {xi_text}")
    ji_text = "；".join(
        f"{item['element']}({item['deity']}: {item['reason']})"
        + ("【实见于命局】" if item["present"] else "【岁运须防】")
        for item in use_gods["jishen"]
    ) or "未见明显破格病神"
    print(f"  忌神(病神): {ji_text}")
    yao_text = "；".join(f"{e}({r})" for e, r in use_gods["yaoshen"]) or "（无需制化，顺势为吉）"
    print(f"  药神(制病): {yao_text}")
    climate_element, climate_reason = use_gods["climate"]
    print(f"  调候提示: {(climate_element + '，') if climate_element else ''}{climate_reason}")
    print(f"  注: {use_gods['note']}")

    # 起大运
    print("\n【起大运】")
    yang_year = GAN[yGZ.tg] in GAN_YANG
    forward = (yang_year and a.gender == "男") or (not yang_year and a.gender == "女")
    print(f"  {'阳' if yang_year else '阴'}年生{a.gender}, {'顺' if forward else '逆'}排大运")

    # 起运岁数: 顺行数至下一节, 逆行数至上一节, 天数÷3
    days_to = _days_to_jie(y, m, d, hh, mm, forward)
    start_age = days_to / 3.0
    yrs = int(start_age)
    mos = int(round((start_age - yrs) * 12))
    print(f"  距{'下' if forward else '上'}一节约 {days_to:.1f} 天 ÷3 = 起运 {yrs} 岁 {mos} 个月")

    # 排大运干支
    seq = []
    idx_g, idx_z = mGZ.tg, mGZ.dz
    step = 1 if forward else -1
    for i in range(8):
        idx_g = (idx_g + step) % 10
        idx_z = (idx_z + step) % 12
        seq.append(GAN[idx_g] + ZHI[idx_z])
    ages = [yrs + 10 * i for i in range(8)]
    print("  大运:  " + "   ".join(f"{a_}岁 {g}" for a_, g in zip(ages, seq)))
    dy_ss = [f"{g}({shishen(day_gan, g[0])})" for g in seq]
    print("  运神:  " + "  ".join(dy_ss))

    # 大运喜忌（以运干五行为主标喜/忌/闲；运支须与命局合冲制化合参，此处只作初判）
    xi_elements = [e for e, _ in use_gods["fuyi"]]
    ji_elements = [item["element"] for item in use_gods["jishen"] if item["element"] not in xi_elements]
    dy_marks = []
    for g in seq:
        wx = GAN_WX[g[0]]
        if wx in xi_elements:
            dy_marks.append(f"{g}({wx}·喜)")
        elif wx in ji_elements:
            dy_marks.append(f"{g}({wx}·忌)")
        else:
            dy_marks.append(f"{g}({wx}·闲)")
    print("  运程喜忌: " + "  ".join(dy_marks) + "  (以运干五行初判，运支合冲制化须另复核)")
    print("=" * 46)


# --- 节气辅助 ---
_JQ_ORDER = ["冬至","小寒","大寒","立春","雨水","惊蛰","春分","清明","谷雨","立夏","小满","芒种",
             "夏至","小暑","大暑","立秋","处暑","白露","秋分","寒露","霜降","立冬","小雪","大雪"]

def _jq_name(i):
    try:
        return _JQ_ORDER[int(i) % 24]
    except Exception:
        return str(i)

def _days_to_jie(y, m, d, hh, mm, forward):
    """生日到 顺行下一节 / 逆行上一节 的天数。"""
    t = sxtwl.Time(); t.Y, t.M, t.D = y, m, d; t.h, t.m, t.s = hh, mm, 0
    bjd = sxtwl.toJD(t)
    jies = []
    for yy in (y - 1, y, y + 1):
        for info in sxtwl.getJieQiByYear(yy):
            nm = _jq_name(info.jqIndex)
            if nm in JIE_NAMES:
                jies.append((info.jd, nm))
    jies.sort()
    if forward:
        nxt = [jd for jd, nm in jies if jd > bjd]
        return (nxt[0] - bjd) if nxt else 0.0
    else:
        prv = [jd for jd, nm in jies if jd < bjd]
        return (bjd - prv[-1]) if prv else 0.0


if __name__ == "__main__":
    main()

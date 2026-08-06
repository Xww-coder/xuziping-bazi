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
    if selected_deity in PATTERN_NAMES:
        pattern_name = PATTERN_NAMES[selected_deity]
    elif month_branch == JIANLU_BRANCH[day_gan]:
        pattern_name = "建禄格"
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
        if deity in PATTERN_NAMES:
            name = PATTERN_NAMES[deity]
        elif month_branch == JIANLU_BRANCH[day_gan]:
            name = "建禄格"
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
                name = PATTERN_NAMES.get(deity, "建禄格" if month_branch == JIANLU_BRANCH[day_gan] else "月劫格")
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


def analyze_use_gods(pillars, day_analysis, pattern_analysis):
    """分开给出格局、扶抑与调候三种口径，避免把“用神”混成一个答案。"""
    day_element = day_analysis["day_element"]
    resource = source_element(day_element)
    output = SHENG[day_element]
    wealth = KE[day_element]
    officer = controller_element(day_element)
    status = day_analysis["status"]
    selected = pattern_analysis["selected"]

    if status == "偏弱":
        has_officer_pressure = day_analysis["month_deity"] in OFFICER_DEITIES or any(
            item["deity"] in OFFICER_DEITIES for item in day_analysis["draining_stems"]
        )
        first_reason = "印星通关官杀并生身" if has_officer_pressure else "印星生扶日主"
        fuyi = [(resource, first_reason), (day_element, "比劫帮身并固根")]
    elif status == "偏旺":
        fuyi = [(output, "食伤泄秀"), (wealth, "财星耗身并承接食伤"), (officer, "官杀制身")]
    else:
        pattern_element = GAN_WX[selected["stem"]]
        fuyi = [(pattern_element, "日主近中和，优先围绕格局成败取用")]

    season = SEASON_BY_BRANCH[day_analysis["month_branch"]]
    if season == "夏":
        climate = ("水", "夏令先看润燥降温；仍须服从全局制化")
    elif season == "冬":
        climate = ("火", "冬令先看暖局解寒；仍须服从全局制化")
    else:
        climate = (None, f"{season}令不设机械调候单字，结合寒暖燥湿复核")

    return {
        "pattern_stem": selected["stem"],
        "pattern_deity": selected["deity"],
        "pattern_element": GAN_WX[selected["stem"]],
        "fuyi": fuyi,
        "climate": climate,
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

    print("\n【喜用神建议】(格局 / 扶抑 / 调候分列)")
    print(
        f"  格局用神(月令义): {use_gods['pattern_stem']}({use_gods['pattern_deity']}, "
        f"{use_gods['pattern_element']}) —— 对应 {selected['pattern']}候选"
    )
    print(
        "  扶抑喜神候选: "
        + "；".join(f"{element}({reason})" for element, reason in use_gods["fuyi"])
    )
    climate_element, climate_reason = use_gods["climate"]
    print(f"  调候提示: {(climate_element + '，') if climate_element else ''}{climate_reason}")
    print("  注: 三种口径不强行合并成唯一用神; 须结合格局成败、合冲制化及大运复核。")

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

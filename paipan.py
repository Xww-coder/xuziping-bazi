#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
徐子平排盘引擎 —— 依《渊海子平》子平法排四柱、定五行、取十神、起大运。
依赖: pip install sxtwl  (寿星天文历, 精确到节气与真太阳时分界)

用法:
    python3 paipan.py --date 1990-05-20 --time 14:30 --gender 男 [--city 北京]
                      [--zwt 116.4]   # 出生地经度, 用于真太阳时校正(可选)
输出为结构化文本, 供徐子平口吻解读时引用。
"""
import argparse, sys
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


def solar_time_adjust(hour, minute, lon):
    """真太阳时粗校正: 按经度相对120°E 每度4分钟。返回校正后小时(float)。"""
    if lon is None:
        return hour + minute / 60.0
    delta_min = (lon - 120.0) * 4.0
    t = hour + minute / 60.0 + delta_min / 60.0
    return t % 24


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="公历生日 YYYY-MM-DD")
    ap.add_argument("--time", required=True, help="出生时刻 HH:MM (24h)")
    ap.add_argument("--gender", required=True, choices=["男", "女"])
    ap.add_argument("--city", default="")
    ap.add_argument("--zwt", type=float, default=None, help="出生地经度(东经为正), 用于真太阳时校正")
    a = ap.parse_args()

    y, m, d = map(int, a.date.split("-"))
    hh, mm = map(int, a.time.split(":"))

    true_h = solar_time_adjust(hh, mm, a.zwt)
    hour_for_gz = int(round(true_h)) % 24   # 用于定时支的整点(23-1为子)

    day = sxtwl.fromSolar(y, m, d)
    yGZ, mGZ, dGZ = day.getYearGZ(), day.getMonthGZ(), day.getDayGZ()
    day_gan = GAN[dGZ.tg]
    hGZ = sxtwl.getShiGz(dGZ.tg, hour_for_gz)   # 五鼠遁定时柱

    pillars = [
        ("年", GAN[yGZ.tg], ZHI[yGZ.dz]),
        ("月", GAN[mGZ.tg], ZHI[mGZ.dz]),
        ("日", GAN[dGZ.tg], ZHI[dGZ.dz]),
        ("时", GAN[hGZ.tg], ZHI[hGZ.dz]),
    ]

    print("=" * 46)
    print(f"公历 {y}-{m:02d}-{d:02d} {hh:02d}:{mm:02d}  {a.gender}" + (f"  出生地 {a.city}" if a.city else ""))
    if a.zwt is not None:
        print(f"(真太阳时校正: 用时支 {ZHI[hGZ.dz]}时, 校正后约 {true_h:.2f} 时)")
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

    # 五行统计(天干各1, 地支藏干主气1 + 中余各0.5 近似权重)
    print("\n【五行力量】(天干计1, 地支主气计1, 中余气各计0.5)")
    score = {"木":0.0,"火":0.0,"土":0.0,"金":0.0,"水":0.0}
    for lbl, g, z in pillars:
        score[GAN_WX[g]] += 1
        cang = CANG[z]
        weights = [1.0] + [0.5] * (len(cang) - 1)
        for c, w in zip(cang, weights):
            score[GAN_WX[c]] += w
    total = sum(score.values())
    for wx in ["木","火","土","金","水"]:
        bar = "█" * int(round(score[wx] * 2))
        print(f"  {wx}: {score[wx]:4.1f}  {bar}")
    dw = GAN_WX[day_gan]
    same = score[dw] + score[[k for k,v in SHENG.items() if v==dw][0]]  # 同类=比劫+印
    print(f"  日主 {day_gan}({dw}) —— 同党(比劫+印)约 {same:.1f} / 全局 {total:.1f}")
    strong = same >= total / 2
    print(f"  日主粗断: {'偏旺' if strong else '偏弱'} (仅供参考, 须结合月令得地/透干细断)")

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

# 徐子平 · AI 八字排盘与批命

> AI 算命准不准，差别不在它多会说，在它有没有先把盘排对。

一个"先排盘、再开口"的八字工具。底层是一个严谨的四柱排盘引擎（精确到立春分界、节气换月、真太阳时校时），上层是一段让大模型扮演北宋徐子平、只能引着盘里干支说话的提示词（Claude Skill）。

*An "compute-first, then interpret" Bazi (Chinese Four Pillars) tool. A rigorous Python engine casts the chart — Four Pillars, Five Elements, Ten Gods, luck cycles — using precise solar-term boundaries and true-solar-time correction. An LLM prompt then reads only what the engine computed, instead of hallucinating a chart. Engine depends on [`sxtwl`](https://github.com/yuangu/sxtwl_cpp).*

---

## 为什么要有这个东西

市面上多数"AI 算命"，其实是让模型凭生日直接脑补一段话。问题出在最前面一步：**排盘**。八字排盘有几个地方极易错，错一步则五行、十神、大运全盘皆错，后面说得再好听也是空中楼阁：

- **年柱以立春分界**，不是正月初一，更不是元旦。2 月初出生的人，年柱到底算哪一年，一大半 AI 会算错。
- **月柱以节气（节）换月**，不是农历初一。
- **时柱宜用真太阳时**，按出生地经度校正，不是照搬钟表时。

这个项目把"排盘"这件事交给一个可验证的程序去做，让模型退回到它真正该干的活——**解读**。模型只能引用引擎算出的四柱、十神、大运，说不出盘里没有的东西。

## 引擎能算什么

`paipan.py` 依子平法输出一份结构化命盘：

- **四柱八字**：年、月、日、时干支（立春 / 节气 / 五鼠遁定时柱）
- **地支藏干**：主气、中气、余气
- **十神**：天干、地支主气相对日主的十神
- **五行力量**：加权统计 + 日主旺衰粗断
- **起大运**：阳男阴女顺行、阴男阳女逆行，按节气天数 ÷3 起运，排八步大运及运神

天文历算基于寿星天文历 [`sxtwl`](https://github.com/yuangu/sxtwl_cpp)，节气与朔望精度足够排盘之用。

## 快速开始

```bash
pip install -r requirements.txt   # 仅依赖 sxtwl

python3 paipan.py --date 1990-05-20 --time 14:30 --gender 男 --city 北京 --zwt 116.4
```

参数：

| 参数 | 说明 | 必需 |
|---|---|---|
| `--date` | 公历生日 `YYYY-MM-DD`（农历请先自行换算） | 是 |
| `--time` | 出生时刻 `HH:MM`（24 小时制） | 是 |
| `--gender` | `男` / `女`（定大运顺逆） | 是 |
| `--city` | 出生城市（仅作标注） | 否 |
| `--zwt` | 出生地经度（东经为正），用于真太阳时校正 | 否 |

常见城市经度：北京 116.4，上海 121.5，广州 113.3，成都 104.0，西安 108.9，乌鲁木齐 87.6。

输出样例见 [`examples/sample_output.txt`](examples/sample_output.txt)。

## 上层：让 AI 扮演徐子平

[`SKILL.md`](SKILL.md) 是配套的提示词，可作为 [Claude Skill](https://docs.claude.com) 使用，也可直接贴给任意大模型。它规定的流程只有一句话能概括：**先跑 `paipan.py` 排盘，再据盘解读**，默认就事业财运、家庭婚姻、健康性格流年、子女四门展开，口吻是古典半白的命师风，每个术语随即用白话点破。

核心约束是：模型不得凭空断命，每句断语都要能回指到盘中某一干支、某一十神。

## 校验

排盘逻辑可与任意权威排盘工具交叉核对。已知立春 / 节气分界、五鼠遁时柱、大运顺逆与起运岁数均按古法。欢迎提 issue 指出算法上的出入。

## 声明

八字命理是传统文化，输出仅供参详与自省，非科学定论，更非宿命判决。不构成医疗、投资、婚配等任何重大决策的依据。健康相关只作养生提示，不替代医嘱。

## License

MIT

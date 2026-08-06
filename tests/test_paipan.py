import subprocess
import sys
import unittest
from datetime import date, datetime
from pathlib import Path

import sxtwl

import paipan


def gz_text(gz):
    return paipan.GAN[gz.tg] + paipan.ZHI[gz.dz]


class TimePillarTests(unittest.TestCase):
    def chart_hour_gz(self, local_dt, lon=None, tz_offset=8.0):
        _, _, _, ganzhi = paipan.calculate_ganzhi(local_dt, lon, tz_offset)
        return gz_text(ganzhi[3])

    def test_hour_branch_changes_only_at_odd_hour_boundaries(self):
        cases = [
            (datetime(1990, 5, 20, 0, 59), "丙子"),
            (datetime(1990, 5, 20, 1, 0), "丁丑"),
            (datetime(1990, 5, 20, 2, 59), "丁丑"),
            (datetime(1990, 5, 20, 3, 0), "戊寅"),
        ]
        for local_dt, expected in cases:
            with self.subTest(local_dt=local_dt):
                self.assertEqual(self.chart_hour_gz(local_dt), expected)

    def test_reported_rounding_cases(self):
        self.assertEqual(self.chart_hour_gz(datetime(1990, 5, 20, 2, 31)), "丁丑")
        self.assertEqual(self.chart_hour_gz(datetime(1990, 5, 20, 23, 30)), "戊子")

    def test_every_minute_matches_sxtwl_hour_api_without_rounding(self):
        local_day = sxtwl.fromSolar(1990, 5, 20)
        for minute_of_day in range(24 * 60):
            hour, minute = divmod(minute_of_day, 60)
            local_dt = datetime(1990, 5, 20, hour, minute)
            expected = local_day.getHourGZ(hour)
            _, _, _, ganzhi = paipan.calculate_ganzhi(local_dt)
            actual = ganzhi[3]
            self.assertEqual((actual.tg, actual.dz), (expected.tg, expected.dz))

    def test_equation_of_time_is_included(self):
        local_dt = datetime(2026, 11, 1, 12, 0)
        corrected, longitude_offset, equation_offset = paipan.solar_time_adjust(
            local_dt, lon=120.0, tz_offset=8.0
        )
        self.assertAlmostEqual(longitude_offset, 0.0, places=6)
        self.assertAlmostEqual(equation_offset, 16.38, delta=0.1)
        self.assertAlmostEqual((corrected - local_dt).total_seconds() / 60.0, 16.38, delta=0.1)

    def test_true_solar_time_preserves_previous_day_rollover(self):
        local_dt = datetime(1990, 5, 20, 0, 30)
        corrected, _, _, ganzhi = paipan.calculate_ganzhi(local_dt, lon=104.0, tz_offset=8.0)
        self.assertEqual(corrected.date(), date(1990, 5, 19))
        self.assertEqual(corrected.hour, 23)
        self.assertEqual(gz_text(ganzhi[3]), "丙子")

    def test_cli_uses_correct_time_pillar(self):
        result = subprocess.run(
            [
                sys.executable,
                str(Path(paipan.__file__)),
                "--date",
                "1990-05-20",
                "--time",
                "02:31",
                "--gender",
                "男",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("天干    庚    辛    乙    丁", result.stdout)
        self.assertIn("地支    午    巳    酉    丑", result.stdout)


class ZipingAnalysisTests(unittest.TestCase):
    sample_pillars = [
        ("年", "庚", "午"),
        ("月", "辛", "巳"),
        ("日", "乙", "酉"),
        ("时", "癸", "未"),
    ]

    def test_month_position_changes_strength_judgment(self):
        month_shen = [
            ("年", "丙", "寅"),
            ("月", "庚", "申"),
            ("日", "甲", "子"),
            ("时", "丁", "卯"),
        ]
        month_yin = [
            ("年", "庚", "申"),
            ("月", "丙", "寅"),
            ("日", "甲", "子"),
            ("时", "丁", "卯"),
        ]
        self.assertEqual(
            paipan.wuxing_distribution(month_shen),
            paipan.wuxing_distribution(month_yin),
        )
        shen_analysis = paipan.analyze_day_master(month_shen)
        yin_analysis = paipan.analyze_day_master(month_yin)
        self.assertEqual(shen_analysis["month_judgment"], "失令受制（官杀当令）")
        self.assertEqual(yin_analysis["month_judgment"], "得令（比劫当令）")
        self.assertNotEqual(shen_analysis["status"], yin_analysis["status"])

    def test_month_hidden_stem_transparency_drives_pattern_candidate(self):
        day_analysis = paipan.analyze_day_master(self.sample_pillars)
        pattern = paipan.analyze_pattern(self.sample_pillars, day_analysis)
        self.assertEqual(pattern["selected"]["stem"], "庚")
        self.assertEqual(pattern["selected"]["deity"], "正官")
        self.assertEqual(pattern["selected"]["pattern"], "正官格")
        self.assertEqual(pattern["selected"]["positions"], ["年"])
        self.assertEqual({item["pattern"] for item in pattern["candidates"]}, {"正官格", "伤官格"})
        self.assertEqual(pattern["confidence"], "低")
        self.assertTrue(any("乙庚合化金候选" in item for item in pattern["special_candidates"]))

    def test_use_god_methods_are_reported_separately(self):
        day_analysis = paipan.analyze_day_master(self.sample_pillars)
        pattern = paipan.analyze_pattern(self.sample_pillars, day_analysis)
        use_gods = paipan.analyze_use_gods(self.sample_pillars, day_analysis, pattern)
        self.assertEqual(day_analysis["status"], "偏弱")
        self.assertEqual(use_gods["pattern_element"], "金")
        self.assertEqual(use_gods["fuyi"][0][0], "水")
        self.assertEqual(use_gods["climate"][0], "水")

    def test_branch_relations_are_exposed_without_forcing_transformation(self):
        relations = paipan.analyze_branch_relations(self.sample_pillars)
        self.assertIn("巳午未三会火方", relations)
        self.assertIn("年午-时未六合", relations)
        water_combo = [
            ("年", "甲", "申"), ("月", "甲", "子"),
            ("日", "甲", "辰"), ("时", "甲", "午"),
        ]
        self.assertIn("申子辰三合水局", paipan.analyze_branch_relations(water_combo))

    def test_cli_labels_distribution_as_non_decisive(self):
        result = subprocess.run(
            [
                sys.executable,
                str(Path(paipan.__file__)),
                "--date",
                "1990-05-20",
                "--time",
                "14:30",
                "--gender",
                "男",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("【五行分布】(仅统计出现, 不直接据此判旺衰)", result.stdout)
        self.assertIn("【月令透干与格局候选】", result.stdout)
        self.assertIn("【喜用神建议】(格局 / 扶抑 / 调候分列)", result.stdout)
        self.assertNotIn("日主粗断", result.stdout)

    def test_all_day_stems_and_month_branches_produce_structured_analysis(self):
        for day_index, day_gan in enumerate(paipan.GAN):
            for month_index, month_branch in enumerate(paipan.ZHI):
                pillars = [
                    ("年", "甲", "子"),
                    ("月", paipan.GAN[(day_index + month_index) % 10], month_branch),
                    ("日", day_gan, "午"),
                    ("时", "己", "酉"),
                ]
                with self.subTest(day_gan=day_gan, month_branch=month_branch):
                    day_analysis = paipan.analyze_day_master(pillars)
                    pattern = paipan.analyze_pattern(pillars, day_analysis)
                    use_gods = paipan.analyze_use_gods(pillars, day_analysis, pattern)
                    self.assertIn(day_analysis["status"], {"偏旺", "中和", "偏弱"})
                    self.assertTrue(pattern["candidates"])
                    self.assertTrue(use_gods["fuyi"])


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalize_recording_date import normalize_recording_date


class RecordingDateNormalizationTests(unittest.TestCase):
    def test_relative_words_use_explicit_local_today(self):
        self.assertEqual(normalize_recording_date("сегодня", today="2026-08-16", timezone="Asia/Shanghai")["date"], "2026-08-16")
        self.assertEqual(normalize_recording_date("вчера", today="2026-08-16", timezone="Asia/Shanghai")["date"], "2026-08-15")
        self.assertEqual(normalize_recording_date("позавчера", today="2026-08-16", timezone="Asia/Shanghai")["date"], "2026-08-14")

    def test_bare_weekday_is_most_recent_non_future_occurrence(self):
        result = normalize_recording_date("в среду", today="2026-08-16", timezone="Asia/Shanghai")
        self.assertEqual(result["date"], "2026-08-12")
        self.assertEqual(result["interpretation"], "most-recent-weekday")

    def test_same_weekday_means_today_but_previous_means_prior_week(self):
        self.assertEqual(normalize_recording_date("в среду", today="2026-08-12", timezone="Asia/Shanghai")["date"], "2026-08-12")
        self.assertEqual(normalize_recording_date("в прошлую среду", today="2026-08-12", timezone="Asia/Shanghai")["date"], "2026-08-05")

    def test_exact_iso_date_is_preserved_and_future_is_rejected(self):
        self.assertEqual(normalize_recording_date("2026-08-12", today="2026-08-16", timezone="Asia/Shanghai")["date"], "2026-08-12")
        with self.assertRaisesRegex(ValueError, "future"):
            normalize_recording_date("2026-08-17", today="2026-08-16", timezone="Asia/Shanghai")


if __name__ == "__main__":
    unittest.main()
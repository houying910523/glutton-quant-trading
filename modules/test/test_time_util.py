from __future__ import annotations

import unittest

from modules.utils.time_util import (
    compact_date,
    format_date,
    parse_date,
)


class ParseDateTest(unittest.TestCase):
    def test_parse_date_supports_compact_and_iso(self) -> None:
        self.assertEqual(parse_date("20260903").isoformat(), "2026-09-03")
        self.assertEqual(parse_date("2026-09-03").isoformat(), "2026-09-03")


class FormatDateTest(unittest.TestCase):
    def test_format_date_normalizes_compact_string(self) -> None:
        self.assertEqual(format_date("20260903"), "2026-09-03")


class CompactDateTest(unittest.TestCase):
    def test_compact_date_normalizes_iso_string(self) -> None:
        self.assertEqual(compact_date("2026-09-03"), "20260903")


if __name__ == "__main__":
    unittest.main()

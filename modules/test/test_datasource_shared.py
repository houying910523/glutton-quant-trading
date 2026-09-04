from __future__ import annotations

import unittest

from modules.datasource.shared import (
    compact_date,
    format_date,
    parse_date,
)


class SharedHelpersTest(unittest.TestCase):
    def test_parse_date_supports_compact_and_iso(self) -> None:
        self.assertEqual(parse_date("20260903").isoformat(), "2026-09-03")
        self.assertEqual(parse_date("2026-09-03").isoformat(), "2026-09-03")

    def test_date_helpers_normalize_output(self) -> None:
        self.assertEqual(format_date("20260903"), "2026-09-03")
        self.assertEqual(compact_date("2026-09-03"), "20260903")


if __name__ == "__main__":
    unittest.main()

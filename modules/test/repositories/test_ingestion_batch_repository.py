from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from modules.repositories.ingestion_batch_repository import BatchRepository


class _FakeUuid:
    def __init__(self, value: str) -> None:
        self.hex = value


class BatchRepositoryNextBatchKeyTest(unittest.TestCase):
    @patch("modules.repositories.ingestion_batch_repository.uuid4")
    def test_next_batch_key_uses_unique_suffix_without_count_query(
        self,
        mock_uuid4,
    ) -> None:
        mock_uuid4.side_effect = [
            _FakeUuid("abcdef1234567890"),
            _FakeUuid("12345678abcdef90"),
        ]
        connection = MagicMock()
        repository = BatchRepository(connection)

        first = repository._next_batch_key("stock_daily", "2026-10-13")
        second = repository._next_batch_key("stock_daily", "2026-10-13")

        self.assertRegex(first, r"^stock_daily_2026-10-13_[0-9a-f]{8}$")
        self.assertRegex(second, r"^stock_daily_2026-10-13_[0-9a-f]{8}$")
        self.assertNotEqual(first, second)
        connection.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from modules.repositories.stock_info_repository import StockInfoRepository


class StockInfoRepositoryUpdateTest(unittest.TestCase):
    def test_update_defers_commit_to_session(self) -> None:
        connection = MagicMock()
        repository = StockInfoRepository(connection)

        repository.update(stock_id=7, optional=1)

        connection.execute.assert_called_once()
        connection.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()

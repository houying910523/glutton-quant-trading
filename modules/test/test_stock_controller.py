from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from modules.controller.object import StockOptionalRequest
from modules.controller.stock_controller import StockController


class StockControllerOptionalTest(unittest.TestCase):
    @patch("modules.controller.stock_controller.RepositorySession")
    def test_optional_uses_transactional_session(self, mock_repository_session) -> None:
        controller = StockController()
        session = MagicMock()
        session.__enter__.return_value = session
        mock_repository_session.return_value = session
        session.stock_info.get.return_value = MagicMock()

        result = controller.optional(StockOptionalRequest(stock_id=7, action="add"))

        self.assertTrue(result)
        mock_repository_session.assert_called_once_with(
            controller.database,
            transactional=True,
        )
        session.stock_info.update.assert_called_once_with(7, optional=1)


if __name__ == "__main__":
    unittest.main()

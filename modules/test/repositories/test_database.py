from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.repositories.database import SQLiteDatabase


class SQLiteDatabaseConnectTest(unittest.TestCase):
    @patch("modules.repositories.database.sqlite3.connect")
    def test_connect_sets_timeout_and_busy_timeout(self, mock_connect) -> None:
        connection = MagicMock()
        mock_connect.return_value = connection

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "glutton.db"
            SQLiteDatabase(db_path).connect()

        mock_connect.assert_called_once_with(db_path, timeout=30)
        connection.execute.assert_any_call("PRAGMA busy_timeout = 30000")


if __name__ == "__main__":
    unittest.main()

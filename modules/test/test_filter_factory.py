import unittest
from unittest.mock import patch

import modules.filters as filters_package


CURRENT_MODULE = __import__(__name__, fromlist=["_current_module"])


class ExampleFilter:
    name = "example"
    params = {}

    def dependencies(self) -> list[str]:
        return []

    def filter(self, data):
        return data


class CreateFilterTest(unittest.TestCase):
    @patch("modules.filters.importlib.import_module", return_value=CURRENT_MODULE)
    def test_create_filter_creates_filter_from_named_module(
        self,
        mock_import_module,
    ) -> None:
        from modules.filters import create_filter

        filter_instance = create_filter("example")

        mock_import_module.assert_called_once_with("modules.filters.example")
        self.assertIsInstance(filter_instance, ExampleFilter)

    @patch(
        "modules.filters.importlib.import_module",
        side_effect=ModuleNotFoundError(
            "No module named 'modules.filters.missing'",
            name="modules.filters.missing",
        ),
    )
    def test_create_filter_rejects_unknown_filter_name(
        self,
        mock_import_module,
    ) -> None:
        from modules.filters import create_filter

        with self.assertRaisesRegex(ValueError, "unsupported filter: missing"):
            create_filter("missing")

        mock_import_module.assert_called_once_with("modules.filters.missing")

    @patch("modules.filters.importlib.import_module", return_value=filters_package)
    def test_create_filter_requires_expected_class_name(
        self,
        mock_import_module,
    ) -> None:
        from modules.filters import create_filter

        with self.assertRaisesRegex(
            ValueError,
            "filter module 'modules.filters.invalid' must define 'InvalidFilter'",
        ):
            create_filter("invalid")

        mock_import_module.assert_called_once_with("modules.filters.invalid")


if __name__ == "__main__":
    unittest.main()

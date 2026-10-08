import unittest
from pkgutil import ModuleInfo
from unittest.mock import patch

import modules.filters as filters_package
from modules.core.context import ParamsProperty
from modules.filters.models import FilterMeta


CURRENT_MODULE = __import__(__name__, fromlist=["_current_module"])


class ExampleFilter:
    """Example filter description."""

    name = "example"
    params = {}
    params_schema = [
        ParamsProperty(
            name="window_size",
            type="int",
            description="Rolling window size.",
        )
    ]

    def dependencies(self) -> list[str]:
        return []

    def filter(self, data):
        return data


class SecondaryFilter:
    """Secondary filter description."""

    name = "secondary"
    params = {}
    params_schema = []

    def dependencies(self) -> list[str]:
        return []

    def filter(self, data):
        return data


class CreateFilterTest(unittest.TestCase):
    @patch.object(
        filters_package.pkgutil,
        "iter_modules",
        return_value=[
            ModuleInfo(None, "secondary", False),
            ModuleInfo(None, "_internal", False),
            ModuleInfo(None, "models", False),
            ModuleInfo(None, "example", False),
        ],
    )
    @patch.object(
        filters_package.importlib, "import_module", return_value=CURRENT_MODULE
    )
    def test_list_filters_returns_filter_meta(
        self,
        mock_import_module,
        mock_iter_modules,
    ) -> None:
        from modules.filters import list_filters

        filters = list_filters()

        mock_iter_modules.assert_called_once_with(filters_package.__path__)
        self.assertEqual(
            filters,
            [
                FilterMeta(
                    name="example",
                    module_name="example",
                    description="Example filter description.",
                    params_schema=[
                        ParamsProperty(
                            name="window_size",
                            type="int",
                            description="Rolling window size.",
                        )
                    ],
                ),
                FilterMeta(
                    name="secondary",
                    module_name="secondary",
                    description="Secondary filter description.",
                    params_schema=[],
                ),
            ],
        )
        self.assertEqual(mock_import_module.call_count, 3)

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

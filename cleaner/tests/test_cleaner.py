import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from app.cleaner import (
    get_prefix_and_retention,
    filter_components_to_delete,
    clear_repository,
)


class TestRepositoryCleaner(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2024, 5, 1, tzinfo=timezone.utc)

    def test_get_prefix_and_retention_known_prefix(self):
        with (
            patch.dict("app.cleaner.PREFIX_RETENTION", {"release": timedelta(days=30)}),
            patch("app.cleaner.DEFAULT_RETENTION", timedelta(days=20)),
        ):
            prefix, retention = get_prefix_and_retention("release-1.0.0")
            self.assertEqual(prefix, "release")
            self.assertEqual(retention, timedelta(days=30))

    def test_get_prefix_and_retention_unknown_prefix(self):
        with (
            patch.dict("app.cleaner.PREFIX_RETENTION", {"release": timedelta(days=30)}),
            patch("app.cleaner.DEFAULT_RETENTION", timedelta(days=20)),
        ):
            prefix, retention = get_prefix_and_retention("1.0.0")
            self.assertIsNone(prefix)
            self.assertEqual(retention, timedelta(days=20))

    def test_filter_skips_missing_version_or_assets(self):
        components = [
            {"id": "1", "name": "App", "version": "", "assets": []},
        ]
        result = filter_components_to_delete(components)
        self.assertEqual(result, [])

    def test_filter_skips_missing_last_modified(self):
        components = [
            {"id": "2", "name": "App", "version": "1.0.0", "assets": [{}]},
        ]
        result = filter_components_to_delete(components)
        self.assertEqual(result, [])

    def test_filter_skips_invalid_last_modified(self):
        components = [
            {
                "id": "3",
                "name": "App",
                "version": "1.0.0",
                "assets": [{"lastModified": "invalid-date"}],
            },
        ]
        result = filter_components_to_delete(components)
        self.assertEqual(result, [])

    @patch("app.cleaner.datetime")
    def test_filter_components_to_delete_with_multiple_prefixes(self, mock_datetime):
        mock_datetime.now.return_value = self.now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        components = [
            {
                "id": "10",
                "name": "App",
                "version": "release-1.0.0",
                "assets": [
                    {"lastModified": (self.now - timedelta(days=40)).isoformat()}
                ],
            },  # старше retention, но не в RESERVED_MINIMUM
            {
                "id": "11",
                "name": "App",
                "version": "test-1.0.0",
                "assets": [
                    {"lastModified": (self.now - timedelta(days=35)).isoformat()}
                ],
            },  # старше retention
            {
                "id": "12",
                "name": "App",
                "version": "release-1.0.1",
                "assets": [
                    {"lastModified": (self.now - timedelta(days=10)).isoformat()}
                ],
            },  # входит в RESERVED_MINIMUM
            {
                "id": "13",
                "name": "App",
                "version": "1.0.0",
                "assets": [
                    {"lastModified": (self.now - timedelta(days=40)).isoformat()}
                ],
            },  # без префикса, старше DEFAULT_RETENTION
        ]

        with (
            patch("app.cleaner.RESERVED_MINIMUM", 1),
            patch.dict(
                "app.cleaner.PREFIX_RETENTION",
                {"release": timedelta(days=30), "test": timedelta(days=15)},
            ),
            patch("app.cleaner.DEFAULT_RETENTION", timedelta(days=20)),
        ):
            to_delete = filter_components_to_delete(components)

        deleted_ids = [c["id"] for c in to_delete]

        # ✅ Компоненты с префиксом "release":
        self.assertIn("10", deleted_ids)  # старше retention и не в RESERVED_MINIMUM
        self.assertNotIn("12", deleted_ids)  # свежий и входит в RESERVED_MINIMUM

        # ✅ Префикс "test":
        self.assertIn("11", deleted_ids)  # старше 15 дней

        # ✅ Без префикса:
        self.assertIn("13", deleted_ids)  # старше DEFAULT_RETENTION

    @patch("app.cleaner.get_repository_components", return_value=[])
    def test_clear_repository_no_components(self, mock_get):
        with self.assertLogs(level="WARNING") as log:
            clear_repository("test-repo")
            self.assertIn("⚠️ Компоненты в репозитории", log.output[0])

    @patch("app.cleaner.filter_components_to_delete", return_value=[])
    @patch(
        "app.cleaner.get_repository_components",
        return_value=[
            {
                "id": "1",
                "version": "v1",
                "assets": [{"lastModified": "2020-01-01T00:00:00Z"}],
            }
        ],
    )
    def test_clear_repository_nothing_to_delete(self, mock_get, mock_filter):
        with self.assertLogs(level="INFO") as log:
            clear_repository("test-repo")
            self.assertIn("✅ Нет компонентов для удаления", log.output[-1])

    @patch("app.cleaner.delete_component")
    @patch("app.cleaner.filter_components_to_delete")
    @patch("app.cleaner.get_repository_components")
    def test_clear_repository_deletes_components(
        self, mock_get, mock_filter, mock_delete
    ):
        mock_get.return_value = [
            {
                "id": "1",
                "name": "App",
                "version": "v1",
                "assets": [{"lastModified": "2020-01-01T00:00:00Z"}],
            }
        ]
        mock_filter.return_value = [mock_get.return_value[0]]
        clear_repository("test-repo")
        mock_delete.assert_called_once_with("1", "App", "v1")


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

from app.cleaner import filter_components_to_delete, get_prefix_and_retention


class TestRepositoryCleaner(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)

    def test_filter_components_to_delete_with_retention_and_reserved(self):
        components = [
            {
                "id": "1",
                "name": "App",
                "version": "release-1.0.0",
                "assets": [{"lastModified": (self.now - timedelta(days=40)).isoformat()}],
            },
            {
                "id": "2",
                "name": "App",
                "version": "release-1.0.1",
                "assets": [{"lastModified": (self.now - timedelta(days=20)).isoformat()}],
            },
            {
                "id": "3",
                "name": "App",
                "version": "release-1.0.2",
                "assets": [{"lastModified": (self.now - timedelta(days=10)).isoformat()}],
            },
            {
                "id": "4",
                "name": "App",
                "version": "release-1.0.3",
                "assets": [{"lastModified": (self.now - timedelta(days=5)).isoformat()}],
            },
        ]

        with patch("app.cleaner.RESERVED_MINIMUM", 2), \
             patch.dict("app.cleaner.PREFIX_RETENTION", {"release": timedelta(days=30)}):
            to_delete = filter_components_to_delete(components)

        deleted_ids = [comp["id"] for comp in to_delete]
        self.assertIn("1", deleted_ids)
        self.assertNotIn("2", deleted_ids)
        self.assertNotIn("3", deleted_ids)
        self.assertNotIn("4", deleted_ids)

    def test_filter_components_to_delete_with_no_assets(self):
        components = [
            {
                "id": "5",
                "name": "BrokenComponent",
                "version": "release-0.0.0",
                "assets": [],
            }
        ]

        with patch("app.cleaner.RESERVED_MINIMUM", 0):
            to_delete = filter_components_to_delete(components)

        self.assertEqual(len(to_delete), 0)

    def test_filter_components_to_delete_with_missing_version(self):
        components = [
            {
                "id": "6",
                "name": "Unnamed",
                "assets": [{"lastModified": (self.now - timedelta(days=100)).isoformat()}],
            }
        ]

        with patch("app.cleaner.RESERVED_MINIMUM", 0):
            to_delete = filter_components_to_delete(components)

        self.assertEqual(len(to_delete), 0)

    def test_get_prefix_and_retention(self):
        with patch.dict("app.cleaner.PREFIX_RETENTION", {"alpha": timedelta(days=15)}):
            prefix, retention = get_prefix_and_retention("Alpha-2.3.1")

        self.assertEqual(prefix, "alpha")
        self.assertEqual(retention, timedelta(days=15))

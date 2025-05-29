import unittest
from datetime import datetime, timedelta, timezone
from reg import filter_components_to_delete  # Импортируйте из своего файла
import logging

def make_component(name, version, last_modified_offset_days, assets_count=1):
    last_modified = (
        datetime.now(timezone.utc) - timedelta(days=last_modified_offset_days)
    ).isoformat()
    return {
        "name": name,
        "version": version,
        "assets": [{"lastModified": last_modified}] * assets_count,
    }

def get_matching_rule(version, regex_rules, no_match_retention, no_match_reserved):
    # Простой заглушка-функция
    return (
        "pattern",  # matched pattern
        timedelta(days=no_match_retention) if no_match_retention else None,
        no_match_reserved,
    )


class TestFilterComponents(unittest.TestCase):
    def setUp(self):
        # Переопределяем функцию внутри модуля
        global get_matching_rule
        from reg import get_matching_rule as original
        self.original_get_matching_rule = original
        # Подменяем
        import reg
        reg.get_matching_rule = get_matching_rule

    def tearDown(self):
        # Восстанавливаем оригинальную функцию
        import reg
        reg.get_matching_rule = self.original_get_matching_rule

    def test_no_retention_no_reserved_no_max(self):
        component = make_component("comp1", "v1", 100)
        deleted = filter_components_to_delete(
            [component], [], None, None, None
        )
        self.assertEqual(deleted, [])

    def test_retention_only(self):
        component = make_component("comp2", "v1", 10)
        deleted = filter_components_to_delete(
            [component], [], None, 5, None  # retention=5
        )
        self.assertEqual(len(deleted), 1)

    def test_reserved_only(self):
        components = [
            make_component("comp3", f"v{i}", i) for i in range(5)
        ]
        deleted = filter_components_to_delete(
            components, [], None, None, 2  # reserved=2
        )
        self.assertEqual(len(deleted), 3)

    def test_retention_and_reserved(self):
        components = [
            make_component("comp4", f"v{i}", i + 10) for i in range(5)
        ]
        deleted = filter_components_to_delete(
            components, [], None, 15, 2  # retention=15, reserved=2
        )
        self.assertEqual(len(deleted), 3)

    def test_max_retention_overrides_all(self):
        component = make_component("comp5", "v1", 100)
        deleted = filter_components_to_delete(
            [component], [], 90, None, None  # max_retention=90
        )
        self.assertEqual(len(deleted), 1)

    def test_max_retention_with_reserved(self):
        components = [
            make_component("comp6", f"v{i}", 91 + i) for i in range(3)
        ]
        deleted = filter_components_to_delete(
            components, [], 90, None, 2  # max_retention=90, reserved=2
        )
        self.assertEqual(len(deleted), 3)  # All too old — all deleted

    def test_reserved_but_not_enough(self):
        components = [
            make_component("comp7", f"v{i}", i) for i in range(10)
        ]
        deleted = filter_components_to_delete(
            components, [], None, None, 3
        )
        self.assertEqual(len(deleted), 7)  # Keep only 3


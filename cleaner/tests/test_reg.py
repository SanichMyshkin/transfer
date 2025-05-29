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


    def test_none_retention_none_reserved_none_max(self):
        component = make_component("no_rule", "v1", 10)
        deleted = filter_components_to_delete(
            [component], {}, None, None, None
        )
        self.assertEqual(deleted, [], "Компонент должен сохраниться (все правила отсутствуют)")

    def test_retention_only_applies(self):
        component = make_component("retention_only", "v1", 10)
        deleted = filter_components_to_delete(
            [component], {}, None, 5, None  # retention_days=5
        )
        self.assertEqual(len(deleted), 1, "Удаляется по retention_days")

    def test_reserved_only_applies(self):
        components = [make_component("reserved_only", f"v{i}", i) for i in range(5)]
        deleted = filter_components_to_delete(
            components, {}, None, None, 2  # reserved=2
        )
        self.assertEqual(len(deleted), 3, "Сохраняются только 2 последних")

    def test_retention_and_reserved_combined(self):
        components = [make_component("ret+res", f"v{i}", i + 10) for i in range(5)]
        deleted = filter_components_to_delete(
            components, {}, None, 15, 2  # retention_days=15, reserved=2
        )
        self.assertEqual(len(deleted), 3, "2 последних по reserved, остальные по retention")

    def test_max_retention_overrides_retention(self):
        component = make_component("max_over_ret", "v1", 100)
        deleted = filter_components_to_delete(
            [component], {}, 90, 150, None  # max=90, retention=150
        )
        self.assertEqual(len(deleted), 1, "Удаляется по max_retention, несмотря на retention")

    def test_max_retention_overrides_reserved(self):
        components = [make_component("max_over_res", f"v{i}", 91 + i) for i in range(3)]
        deleted = filter_components_to_delete(
            components, {}, 90, None, 2  # max=90, reserved=2
        )
        self.assertEqual(len(deleted), 3, "Все удаляются по max_retention")

    def test_max_retention_applies_with_none_retention_reserved(self):
        component = make_component("max_only", "v1", 95)
        deleted = filter_components_to_delete(
            [component], {}, 90, None, None
        )
        self.assertEqual(len(deleted), 1, "Удаляется по max_retention, даже без других правил")

    def test_keep_reserved_ignore_retention_for_reserved_items(self):
        components = [make_component("combo_edge", f"v{i}", 100) for i in range(3)]
        deleted = filter_components_to_delete(
            components, {}, None, 90, 2  # retention=90, reserved=2
        )
        self.assertEqual(len(deleted), 1, "Сохраняются 2 последних по reserved, старый удаляется по retention")

    def test_exact_reserved_not_more(self):
        components = [make_component("exact_reserved", f"v{i}", i) for i in range(3)]
        deleted = filter_components_to_delete(
            components, {}, None, None, 3
        )
        self.assertEqual(len(deleted), 0, "Все остаются, ровно столько, сколько указано в reserved")

    def test_retention_not_triggered_if_not_expired(self):
        component = make_component("not_expired_ret", "v1", 2)
        deleted = filter_components_to_delete(
            [component], {}, None, 10, None  # retention=10, age=2
        )
        self.assertEqual(len(deleted), 0, "Сохраняется, потому что не просрочен")

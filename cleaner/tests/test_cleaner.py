from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from cleaner import filter_components_to_delete

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def make_component(name, version, days_old=10, last_download_days=None):
    last_modified = (NOW - timedelta(days=days_old)).isoformat()
    assets = [{"lastModified": last_modified}]
    if last_download_days is not None:
        last_downloaded = (NOW - timedelta(days=last_download_days)).isoformat()
        assets[0]["lastDownloaded"] = last_downloaded

    return {
        "id": f"{name}-{version}",
        "name": name,
        "version": version,
        "assets": assets,
    }


# 1. Все правила указаны (retention + reserved + min_days_since_last_download)
def test_all_rules_applied():
    components = [
        make_component("lib", "dev-1", days_old=10, last_download_days=5),  # удалится
        make_component(
            "lib", "dev-2", days_old=1, last_download_days=0
        ),  # останется (скачан недавно)
    ]
    regex_rules = {
        "^dev-.*": {
            "retention_days": 7,
            "reserved": 1,
            "min_days_since_last_download": 3,
        }
    }
    to_delete = filter_components_to_delete(
        components,
        regex_rules,
        no_match_retention=12,
        no_match_reserved=1,
        no_match_min_days_since_last_download=2,
    )
    assert len(to_delete) == 1
    assert to_delete[0]["version"] == "dev-1"


# 2. Проверка retention с no_match_retention
def test_retention_applies_no_match():
    components = [make_component("any", "v1", days_old=200, last_download_days=100)]
    to_delete = filter_components_to_delete(
        components,
        {},
        no_match_retention=180,
        no_match_reserved=0,
        no_match_min_days_since_last_download=1,
    )
    assert len(to_delete) == 1


# 3. Только reserved
def test_only_reserved():
    components = [
        make_component("lib", "r1", 5),  # свежий
        make_component("lib", "r2", 10),  # старше — должен быть удалён
    ]
    regex_rules = {"^r.*": {"reserved": 1}}
    to_delete = filter_components_to_delete(
        components,
        regex_rules,
        no_match_retention=None,
        no_match_reserved=None,
        no_match_min_days_since_last_download=None,
    )
    # reserved=1 → сохраняется только r1 (самый свежий)
    # r2 должен быть удалён
    assert len(to_delete) == 1
    assert to_delete[0]["version"] == "r2"


# 4. Только retention
def test_only_retention():
    components = [make_component("lib", "old", 20)]
    regex_rules = {".*": {"retention_days": 10}}
    to_delete = filter_components_to_delete(
        components,
        regex_rules,
        no_match_retention=300,
        no_match_reserved=0,
        no_match_min_days_since_last_download=0,
    )
    assert len(to_delete) == 1


# 5. Только min_days_since_last_download
def test_only_min_days_since_last_download():
    components = [make_component("lib", "v", 5, last_download_days=1)]
    regex_rules = {".*": {"min_days_since_last_download": 3}}
    to_delete = filter_components_to_delete(
        components,
        regex_rules,
        no_match_retention=300,
        no_match_reserved=0,
        no_match_min_days_since_last_download=0,
    )
    assert len(to_delete) == 1


# 6. Retention + reserved
def test_retention_and_reserved():
    components = [
        make_component("lib", "v1", 15),
        make_component("lib", "v2", 20),
    ]
    regex_rules = {".*": {"retention_days": 10, "reserved": 1}}
    to_delete = filter_components_to_delete(
        components,
        regex_rules,
        no_match_retention=12,
        no_match_reserved=1,
        no_match_min_days_since_last_download=1,
    )
    assert len(to_delete) == 1
    assert to_delete[0]["version"] == "v2"


# 7. Retention + min_days_since_last_download
def test_retention_and_min_download():
    components = [make_component("lib", "v1", 15, 10)]
    regex_rules = {".*": {"retention_days": 5, "min_days_since_last_download": 7}}
    to_delete = filter_components_to_delete(
        components,
        regex_rules,
        no_match_retention=20,
        no_match_reserved=0,
        no_match_min_days_since_last_download=1,
    )
    assert len(to_delete) == 1


# 8. Reserved + min_days_since_last_download
def test_reserved_and_min_download():
    comps = [
        make_component("lib", "v1", 5, 1),  # в reserved — сохраняется
        make_component(
            "lib", "v2", 10, 10
        ),  # не в reserved, скачан 10 дней назад → удаляется
    ]
    rules = {".*": {"reserved": 1, "min_days_since_last_download": 3}}

    deleted = filter_components_to_delete(comps, rules, 10, 0, 0)

    assert [d["version"] for d in deleted] == ["v2"]


# 9. Не удаляется latest
def test_latest_not_deleted():
    components = [make_component("lib", "latest", 100)]
    to_delete = filter_components_to_delete(
        components,
        {},
        no_match_retention=1,
        no_match_reserved=0,
        no_match_min_days_since_last_download=0,
    )
    assert len(to_delete) == 0


# 10. Пропуск без assets
def test_ignore_no_assets():
    c = {"id": "1", "name": "lib", "version": "v1", "assets": []}
    to_delete = filter_components_to_delete(
        [c],
        {},
        no_match_retention=10,
        no_match_reserved=0,
        no_match_min_days_since_last_download=0,
    )
    assert len(to_delete) == 0


# 11. Пропуск без lastModified
def test_ignore_no_last_modified():
    c = {"id": "1", "name": "lib", "version": "v1", "assets": [{}]}
    to_delete = filter_components_to_delete(
        [c],
        {},
        no_match_retention=10,
        no_match_reserved=0,
        no_match_min_days_since_last_download=0,
    )
    assert len(to_delete) == 0


# 12. Пропуск без name/version
def test_ignore_missing_name_version():
    c = make_component(None, None, 100)
    c.pop("name")
    c.pop("version")
    to_delete = filter_components_to_delete(
        [c],
        {},
        no_match_retention=10,
        no_match_reserved=0,
        no_match_min_days_since_last_download=0,
    )
    assert len(to_delete) == 0


# 13. Группировка по name + pattern
def test_grouping_by_name_and_pattern():
    components = [
        make_component("pkg", "dev-1", 20),
        make_component("pkg", "dev-2", 30),
        make_component("pkg", "rel-1", 40),
    ]
    regex_rules = {
        "^dev-.*": {"reserved": 1},
        "^rel-.*": {"reserved": 1},
    }
    to_delete = filter_components_to_delete(
        components,
        regex_rules,
        no_match_retention=12,
        no_match_reserved=0,
        no_match_min_days_since_last_download=0,
    )
    assert len(to_delete) == 1
    assert to_delete[0]["version"] == "dev-2"


# 14. Без lastDownloaded, есть min_days_since_last_download
def test_missing_last_download_with_min_days_rule():
    components = [make_component("lib", "v1", 15, None)]
    regex_rules = {".*": {"retention_days": 10, "min_days_since_last_download": 1}}
    to_delete = filter_components_to_delete(
        components,
        regex_rules,
        no_match_retention=12,
        no_match_reserved=0,
        no_match_min_days_since_last_download=0,
    )
    assert len(to_delete) == 1


# 15. Проверка no_match логики
def test_no_match_retention():
    components = [make_component("lib", "nomatch", 15, 10)]
    to_delete = filter_components_to_delete(
        components,
        {},
        no_match_retention=5,
        no_match_reserved=0,
        no_match_min_days_since_last_download=0,
    )
    assert len(to_delete) == 1


# 16. no_match_reserved без удаления
def test_no_match_reserved_protection():
    components = [
        make_component("lib", "a", 10),
        make_component("lib", "b", 15),
    ]
    to_delete = filter_components_to_delete(
        components,
        {},
        no_match_retention=5,
        no_match_reserved=1,
        no_match_min_days_since_last_download=0,
    )
    assert len(to_delete) == 1
    assert to_delete[0]["version"] == "b"


# 17. Удаляется только после строго min_days_since_last_download


@patch("cleaner.datetime")
def test_strict_min_days_since_last_download(mock_datetime):
    fixed_now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    mock_datetime.now.return_value = fixed_now
    mock_datetime.side_effect = lambda *args, **kwargs: datetime(
        *args, **kwargs
    )  # чтобы parse работал корректно
    mock_datetime.timezone = timezone

    components = [
        make_component("lib", "v1", 10, last_download_days=3),
        make_component("lib", "v2", 10, last_download_days=4),
    ]
    regex_rules = {".*": {"min_days_since_last_download": 3}}
    to_delete = filter_components_to_delete(
        components,
        regex_rules,
        no_match_retention=300,
        no_match_reserved=0,
        no_match_min_days_since_last_download=3,
    )
    assert len(to_delete) == 1
    assert to_delete[0]["version"] == "v2"


def test_specific_regex_priority():
    components = [
        make_component("lib", "dev-latest.20250601", 15, 10),  # попадает под оба
    ]
    regex_rules = {
        "^dev-.*": {"retention_days": 10},
        "dev-latest.*": {"min_days_since_last_download": 5},
    }

    to_delete = filter_components_to_delete(
        components,
        regex_rules,
        no_match_retention=20,
        no_match_reserved=0,
        no_match_min_days_since_last_download=0,
    )

    # Скачан 10 дней назад, а min_days_since_last_download = 5 → удаляется
    assert len(to_delete) == 1


def test_hello_world_does_not_match_suffix():
    components = [make_component("lib", "some-hello-world", 15, 10)]
    regex_rules = {
        "^hello-.*": {"retention_days": 10},
        "hello-world.*": {"min_days_since_last_download": 5},
    }

    to_delete = filter_components_to_delete(
        components,
        regex_rules,
        no_match_retention=5,
        no_match_reserved=0,
        no_match_min_days_since_last_download=0,
    )

    # Ни один паттерн не подходит → применяется no_match_retention = 5 → удаляется
    assert len(to_delete) == 1

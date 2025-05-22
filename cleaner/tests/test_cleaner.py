import pytest
from datetime import datetime, timezone, timedelta
from universal import filter_components_to_delete

# Хелпер для создания фейкового компонента
def make_component(name, version, age_days):
    last_modified = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
    return {
        "name": name,
        "version": version,
        "assets": [{"lastModified": last_modified}],
        "id": f"{name}:{version}"
    }

@pytest.mark.parametrize("description,components,prefix_rules,max_retention,no_prefix_retention,no_prefix_reserved,expected_deleted", [
    (
        "1️⃣ Только retention — устаревшее удаляется",
        [
            make_component("app", "dev.v1", 5),
            make_component("app", "dev.v2", 1),
        ],
        {
            "dev": {"retention_days": 2}
        },
        None,
        0,
        0,
        ["app:dev.v1"]
    ),
    (
        "2️⃣ Только reserved — сохраняем 1 свежий",
        [
            make_component("app", "dev.v1", 3),
            make_component("app", "dev.v2", 2),
            make_component("app", "dev.v3", 1),
        ],
        {
            "dev": {"reserved": 1}
        },
        None,
        0,
        0,
        ["app:dev.v1", "app:dev.v2"]
    ),
    (
        "3️⃣ Reserved + retention — приоритет у reserved",
        [
            make_component("app", "dev.v1", 4),
            make_component("app", "dev.v2", 3),
        ],
        {
            "dev": {
                "retention_days": 0,
                "reserved": 1
            }
        },
        None,
        0,
        0,
        ["app:dev.v1"]
    ),
    (
        "4️⃣ Max retention имеет наивысший приоритет",
        [
            make_component("app", "release.v1", 10),
            make_component("app", "release.v2", 5),
        ],
        {
            "release": {"retention_days": 20, "reserved": 1}
        },
        6,  # max_retention_days
        0,
        0,
        ["app:release.v1"]
    ),
    (
        "5️⃣ Защита latest — никогда не удаляется",
        [
            make_component("app", "latest", 100)
        ],
        {},
        0,
        0,
        0,
        []
    ),
    (
        "6️⃣ Нет retention и reserved — не удаляется",
        [
            make_component("app", "test.v1", 100)
        ],
        {
            "test": {}
        },
        None,
        0,
        0,
        []
    ),
    (
        "7️⃣ no_prefix: только retention — удаляем устаревшее",
        [
            make_component("app", "v1", 5),
            make_component("app", "v2", 1),
        ],
        {},  # нет префиксов — попадёт в no_prefix
        None,
        2,   # retention: 2 дня
        None,
        ["app:v1"]
    ),
    (
        "8️⃣ no_prefix: только reserved — оставляем 1 свежий",
        [
            make_component("app", "v1", 3),
            make_component("app", "v2", 2),
            make_component("app", "v3", 1),
        ],
        {},
        None,
        None,
        1,  # reserved = 1
        ["app:v1", "app:v2"]
    ),
    (
        "9️⃣ no_prefix: retention + reserved — приоритет у reserved",
        [
            make_component("app", "v1", 5),
            make_component("app", "v2", 4),
        ],
        {},
        None,
        0,  # retention = 0
        1,  # reserved = 1 → сохраняем свежий
        ["app:v1"]
    ),
])
def test_filter_components_to_delete(description, components, prefix_rules, max_retention, no_prefix_retention, no_prefix_reserved, expected_deleted):
    result = filter_components_to_delete(
        components,
        prefix_rules=prefix_rules,
        max_retention=max_retention,
        no_prefix_retention=no_prefix_retention,
        no_prefix_reserved=no_prefix_reserved,
    )
    deleted_ids = [f"{c['name']}:{c['version']}" for c in result]
    assert sorted(deleted_ids) == sorted(expected_deleted), f"❌ Ошибка в тесте: {description}"

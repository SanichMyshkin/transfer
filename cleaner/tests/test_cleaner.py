from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from requests.exceptions import RequestException
import cleaner

# 🔧 Пример компонента
EXAMPLE_COMPONENT = {
    "id": "1",
    "name": "test-image",
    "version": "dev-1.0",
    "assets": [
        {"lastModified": (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()}
    ],
}

# === 🔍 Тесты логики префиксов ===


def test_get_prefix_rules_with_known_prefix():
    prefix, retention, reserved = cleaner.get_prefix_rules("dev-1.0")
    assert prefix == "dev"
    assert retention.days == 7
    assert reserved == 2


def test_get_prefix_rules_with_unknown_prefix():
    prefix, retention, reserved = cleaner.get_prefix_rules("unknown-1.0")
    assert prefix is None
    assert retention.days == 30
    assert reserved == 2


# === 🧹 Тесты фильтрации компонентов ===


def test_filter_components_to_delete_retention_expired():
    base_component = EXAMPLE_COMPONENT.copy()
    base_component["assets"][0]["lastModified"] = (
        datetime.now(timezone.utc) - timedelta(days=31)
    ).isoformat()
    components = [base_component.copy() for _ in range(3)]  # > reserved=2
    result = cleaner.filter_components_to_delete(components)
    assert len(result) == 1


def test_filter_components_to_delete_retention_not_expired():
    component = EXAMPLE_COMPONENT.copy()
    component["assets"][0]["lastModified"] = (
        datetime.now(timezone.utc) - timedelta(days=1)
    ).isoformat()
    components = [component.copy() for _ in range(3)]
    result = cleaner.filter_components_to_delete(components)
    assert result == []


def test_filter_skips_component_with_no_assets_or_version():
    component = {"id": "1", "name": "broken", "version": "", "assets": []}
    result = cleaner.filter_components_to_delete([component])
    assert result == []


def test_filter_component_with_invalid_date():
    component = EXAMPLE_COMPONENT.copy()
    component["assets"][0]["lastModified"] = "неправильная-дата"
    result = cleaner.filter_components_to_delete([component])
    assert result == []


def test_filter_components_to_delete_not_expired_but_in_reserved():
    now = datetime.now(timezone.utc)
    component1 = {
        "id": "id-1",
        "name": "test-image",
        "version": "dev-1",
        "assets": [{"lastModified": (now - timedelta(days=7)).isoformat()}],
    }
    component2 = {
        "id": "id-2",
        "name": "test-image",
        "version": "dev-2",
        "assets": [{"lastModified": (now - timedelta(days=10)).isoformat()}],
    }
    components = [component1, component2]

    result = cleaner.filter_components_to_delete(components)
    assert result == []  # компонент не удаляется, потому что он в резерве


def test_filter_components_to_delete_not_expired_but_beyond_reserved():
    now = datetime.now(timezone.utc)
    component1 = {
        "id": "id-1",
        "name": "test-image",
        "version": "dev-1",
        "assets": [{"lastModified": (now - timedelta(days=2)).isoformat()}],
    }
    component2 = {
        "id": "id-2",
        "name": "test-image",
        "version": "dev-2",
        "assets": [{"lastModified": (now - timedelta(days=3)).isoformat()}],
    }
    components = [component1, component2]

    result = cleaner.filter_components_to_delete(components)
    assert result == []  # ничего не удаляется — не просрочено


# === 📦 Тесты получения компонентов из репозитория ===


@patch("cleaner.requests.get")
def test_get_repository_components_success(mock_get):
    mock_response = MagicMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {"items": [EXAMPLE_COMPONENT]}
    mock_get.return_value = mock_response

    components = cleaner.get_repository_components("test1")
    assert len(components) == 1


@patch("cleaner.requests.get")
def test_get_repository_components_empty_items(mock_get):
    mock_response = MagicMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {"items": []}
    mock_get.return_value = mock_response

    components = cleaner.get_repository_components("test1")
    assert components == []


@patch("cleaner.requests.get")
def test_get_repository_components_failure(mock_get):
    mock_get.side_effect = RequestException("Ошибка сети")
    components = cleaner.get_repository_components("test1")
    assert components == []


@patch("cleaner.requests.get")
def test_get_repository_components_missing_items(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {}  # отсутствует 'items'
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    components = cleaner.get_repository_components("test1")
    assert components == []


# 🔹 2. Тест: компонент с asset без поля 'lastModified'
def test_filter_components_to_delete_missing_last_modified():
    component = {
        "name": "test-image",
        "version": "dev-1",
        "assets": [{}],  # отсутствует 'lastModified'
    }
    result = cleaner.filter_components_to_delete([component])
    assert result == []


# 🔹 3. Тест: вне резерва, но не просрочен (age < retention)
def test_filter_components_to_delete_not_expired_but_beyond_reserved():
    now = datetime.now(timezone.utc)
    component1 = {
        "id": "id-1",
        "name": "test-image",
        "version": "dev-1",
        "assets": [{"lastModified": (now - timedelta(days=2)).isoformat()}],
    }
    component2 = {
        "id": "id-2",
        "name": "test-image",
        "version": "dev-2",
        "assets": [{"lastModified": (now - timedelta(days=3)).isoformat()}],
    }
    components = [component1, component2]

    result = cleaner.filter_components_to_delete(components)
    assert result == []  # ничего не удаляется — не просрочено


# === ❌ Удаление компонентов ===


@patch("cleaner.requests.delete")
def test_delete_component_real(mock_delete):
    mock_response = MagicMock()
    mock_response.raise_for_status = lambda: None
    mock_delete.return_value = mock_response

    cleaner.DRY_RUN = False
    cleaner.delete_component("1", "test-image", "v1.0")
    mock_delete.assert_called_once()


@patch("cleaner.logging.info")
@patch("cleaner.requests.delete")
def test_delete_component_dry_run(mock_delete, mock_info):
    cleaner.DRY_RUN = True
    cleaner.delete_component("1", "test-image", "v1.0")  # Просто лог
    mock_info.assert_called_once_with(
        "🧪 [DRY_RUN] Пропущено удаление: test-image (версия v1.0, ID: 1)"
    )
    mock_delete.assert_not_called()


# === 🔄 Тесты очистки репозитория ===


@patch("cleaner.get_repository_components", return_value=None)
def test_clear_repository_none_returned(mock_get):
    cleaner.clear_repository("test1")
    mock_get.assert_called_once()


@patch("cleaner.get_repository_components", return_value=[])
def test_clear_repository_no_components(mock_get):
    cleaner.clear_repository("test1")
    mock_get.assert_called_once()


@patch("cleaner.get_repository_components")
@patch("cleaner.filter_components_to_delete")
@patch("cleaner.delete_component")
def test_clear_repository_deletes_components(mock_delete, mock_filter, mock_get):
    mock_get.return_value = [EXAMPLE_COMPONENT.copy()]
    to_delete = [EXAMPLE_COMPONENT.copy()]
    mock_filter.return_value = to_delete

    cleaner.clear_repository("test1")
    mock_delete.assert_called_once()


# === ▶️ Тест main() ===


@patch("cleaner.clear_repository")
def test_main_calls_clear_repository(mock_clear):
    cleaner.main()
    mock_clear.assert_called()

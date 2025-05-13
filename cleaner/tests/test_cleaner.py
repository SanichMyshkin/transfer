from datetime import datetime, timezone, timedelta
from unittest.mock import patch, Mock
from cleaner import (
    get_repository_components,
    delete_component,
    filter_components_to_delete,
    get_prefix_and_retention,
    DEFAULT_RETENTION,
)


# ----------------- get_prefix_and_retention -----------------

def test_get_prefix_and_retention_known_prefix():
    prefix, retention = get_prefix_and_retention("dev-1.0")
    assert prefix == "dev"
    assert retention.days == 7

def test_get_prefix_and_retention_unknown_prefix():
    prefix, retention = get_prefix_and_retention("feature-1.0")
    assert prefix is None
    assert retention == DEFAULT_RETENTION


# ----------------- filter_components_to_delete -----------------

def test_filter_components_to_delete():
    now = datetime.now(timezone.utc)
    components = [
        {
            "id": "1",
            "name": "lib-a",
            "version": "dev-1.0",
            "assets": [{"lastModified": (now - timedelta(days=10)).isoformat()}],
        },
        {
            "id": "2",
            "name": "lib-a",
            "version": "dev-2.0",
            "assets": [{"lastModified": (now - timedelta(days=2)).isoformat()}],
        },
        {
            "id": "3",
            "name": "lib-a",
            "version": "dev-3.0",
            "assets": [{"lastModified": (now - timedelta(days=20)).isoformat()}],
        },
    ]
    result = filter_components_to_delete(components)
    # RESERVED_MINIMUM = 2 => старые идут с 3-го
    assert len(result) == 1
    assert result[0]["id"] == "3"


# ----------------- get_repository_components -----------------

@patch("requests.get")
def test_get_repository_components_success(mock_get):
    mock_response = Mock()
    mock_response.json.return_value = {
        "items": [
            {
                "id": "123",
                "name": "test-comp",
                "version": "dev-1.0",
                "assets": [{"lastModified": "2024-01-01T00:00:00Z"}],
            }
        ],
        "continuationToken": None,
    }
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    result = get_repository_components("test1")
    assert isinstance(result, list)
    assert result[0]["id"] == "123"


@patch("requests.get")
def test_get_repository_components_error(mock_get):
    from requests.exceptions import RequestException
    mock_get.side_effect = RequestException("Connection error")

    result = get_repository_components("test1")
    assert result == []


# ----------------- delete_component -----------------

@patch("requests.delete")
def test_delete_component_real(mock_delete):
    mock_response = Mock()
    mock_response.status_code = 204
    mock_response.raise_for_status = Mock()
    mock_delete.return_value = mock_response

    delete_component("123", "comp-name", "1.0")
    mock_delete.assert_called_once()


@patch("cleaner.DRY_RUN", True)
@patch("requests.delete")
def test_delete_component_dry_run(mock_delete):
    delete_component("123", "comp-name", "1.0")
    mock_delete.assert_not_called()

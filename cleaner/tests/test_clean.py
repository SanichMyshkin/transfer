from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
import requests

from cleaner import (
    extract_prefix,
    filter_components_to_delete,
    get_repository_components,
    delete_component,
)


def test_extract_prefix():
    assert extract_prefix("dev-123") == "dev-"
    assert extract_prefix("test-abc") == "test-"
    assert extract_prefix("release1.0") == "release"
    assert extract_prefix("master-2024") == "master"
    assert extract_prefix("custom-image") == "custom-"
    assert extract_prefix("something") == ""


def test_filter_components_to_delete_logic():
    now = datetime.now(timezone.utc)
    # now = datetime.utcnow().replace(tzinfo=pytz.UTC)
    components = [
        {
            "version": "dev-1",
            "assets": [{"lastModified": (now - timedelta(days=2)).isoformat()}],
        },
        {
            "version": "dev-2",
            "assets": [{"lastModified": (now - timedelta(days=1)).isoformat()}],
        },
        {
            "version": "dev-3",
            "assets": [{"lastModified": (now - timedelta(days=5)).isoformat()}],
        },
    ]
    to_delete = filter_components_to_delete(components)
    assert len(to_delete) == 1
    assert to_delete[0]["version"] == "dev-3"


def test_filter_components_to_delete_skips_invalid():
    components = [
        {"version": "dev-", "assets": []},  # no assets
        {"version": "dev-", "assets": [{}]},  # no lastModified
        {"version": "dev-", "assets": [{"lastModified": "bad-date"}]},  # bad date
    ]
    to_delete = filter_components_to_delete(components)
    assert to_delete == []


@patch("cleaner.requests.get")
def test_get_repository_components_success(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"items": [{"id": "1"}], "continuationToken": None},
    )
    result = get_repository_components("my-repo")
    assert isinstance(result, list)
    assert result[0]["id"] == "1"


@patch("cleaner.requests.get")
def test_get_repository_components_empty_items(mock_get):
    mock_get.return_value = MagicMock(status_code=200, json=lambda: {"no_items": []})
    result = get_repository_components("my-repo")
    assert result == []


@patch("cleaner.requests.get")
def test_get_repository_components_exception(mock_get):
    mock_get.side_effect = requests.exceptions.RequestException("fail")
    result = get_repository_components("my-repo")
    assert result == []


@patch("cleaner.requests.delete")
def test_delete_component_success(mock_delete):
    mock_delete.return_value = MagicMock(status_code=204)
    delete_component("id123", "comp", "v1")
    mock_delete.assert_called_once()


@patch("cleaner.requests.delete")
def test_delete_component_error(mock_delete):
    mock_delete.side_effect = requests.exceptions.RequestException("fail")
    delete_component("id123", "comp", "v1")
    mock_delete.assert_called_once()

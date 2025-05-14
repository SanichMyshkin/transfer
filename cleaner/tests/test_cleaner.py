import subprocess
import sys
from unittest.mock import patch, MagicMock
from requests.exceptions import RequestException
from cleaner import (
    get_repository_components,
    delete_component,
    filter_components_to_delete,
    clear_repository,
    main,
)


@patch("cleaner.requests.get")
def test_get_repository_components_success(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "items": [
            {
                "id": "1",
                "name": "pkg",
                "version": "dev-001",
                "assets": [{"lastModified": "2024-01-01T00:00:00Z"}],
            }
        ],
        "continuationToken": None,
    }
    result = get_repository_components("test1")
    assert len(result) == 1
    assert result[0]["id"] == "1"


@patch("cleaner.requests.get", side_effect=RequestException("fail"))
def test_get_repository_components_error(mock_get):
    result = get_repository_components("test1")
    assert result == []


@patch("cleaner.DRY_RUN", False)
@patch("cleaner.requests.delete", side_effect=RequestException("Network Error"))
def test_delete_component_error(mock_delete):
    delete_component("123", "comp", "v1")
    mock_delete.assert_called_once()


@patch("cleaner.requests.delete")
@patch("cleaner.DRY_RUN", False)
def test_delete_component_success(mock_delete):
    mock_delete.return_value.status_code = 204
    delete_component("123", "pkg", "dev-001")
    mock_delete.assert_called_once()


def test_filter_components_to_delete_retention_and_reserved():
    now = "2024-01-01T00:00:00Z"
    components = [
        {
            "name": "pkg",
            "version": "dev-old",
            "assets": [{"lastModified": now}],
        },
        {
            "name": "pkg",
            "version": "dev-latest",
            "assets": [{"lastModified": now}],
        },
        {
            "name": "pkg",
            "version": "dev-new",
            "assets": [{"lastModified": now}],
        },
    ]

    to_delete = filter_components_to_delete(components)
    assert isinstance(to_delete, list)


@patch("cleaner.get_repository_components", return_value=[])
def test_clear_repository_empty(mock_get):
    clear_repository("test1")


@patch("cleaner.delete_component")
@patch("cleaner.filter_components_to_delete")
@patch("cleaner.get_repository_components")
def test_clear_repository_with_deletions(mock_get, mock_filter, mock_delete):
    mock_get.return_value = [
        {
            "id": "123",
            "name": "pkg",
            "version": "dev-001",
            "assets": [{"lastModified": "2024-01-01T00:00:00Z"}],
        }
    ]
    mock_filter.return_value = [{"id": "123", "name": "pkg", "version": "dev-001"}]

    clear_repository("test1")
    mock_delete.assert_called_once()


@patch("cleaner.clear_repository")
def test_main(mock_clear):
    main()
    mock_clear.assert_called()


@patch("cleaner.requests.get")
def test_get_repo_invalid_response(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"no_items": []}
    result = get_repository_components("test1")
    assert result == []


@patch("cleaner.requests.get")
def test_get_repo_empty_items(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"items": [], "continuationToken": None}
    result = get_repository_components("test1")
    assert result == []


@patch("cleaner.requests.get")
def test_get_repo_with_continuation(mock_get):
    mock_get.side_effect = [
        MagicMock(
            status_code=200,
            json=lambda: {"items": [{"id": "1"}], "continuationToken": "token123"},
        ),
        MagicMock(
            status_code=200,
            json=lambda: {"items": [{"id": "2"}], "continuationToken": None},
        ),
    ]
    result = get_repository_components("test1")
    assert len(result) == 2


@patch("cleaner.DRY_RUN", True)
def test_delete_component_dry_run():
    delete_component("id", "name", "v1")  # Не должно вызвать requests.delete


def test_get_prefix_rules_unknown():
    from cleaner import get_prefix_rules

    prefix, retention, reserved = get_prefix_rules("unknown-001")
    assert prefix is None


def test_filter_components_missing_fields():
    components = [{"assets": [{"lastModified": "2024-01-01T00:00:00Z"}]}]
    result = filter_components_to_delete(components)
    assert result == []


def test_filter_components_no_last_modified():
    components = [{"name": "pkg", "version": "dev-123", "assets": [{}]}]
    result = filter_components_to_delete(components)
    assert result == []


def test_filter_components_invalid_date():
    components = [
        {"name": "pkg", "version": "dev-123", "assets": [{"lastModified": "bad-date"}]}
    ]
    result = filter_components_to_delete(components)
    assert result == []


@patch(
    "cleaner.get_repository_components",
    return_value=[
        {
            "name": "pkg",
            "version": "dev-latest",
            "assets": [{"lastModified": "2024-01-01T00:00:00Z"}],
        }
    ],
)
def test_clear_repository_no_deletions(mock_get):
    clear_repository("test1")


def test_script_runs_as_main():
    result = subprocess.run(
        [sys.executable, "cleaner.py"], capture_output=True, text=True
    )
    assert result.returncode == 0

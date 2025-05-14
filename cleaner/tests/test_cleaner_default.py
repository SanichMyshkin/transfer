import logging
from unittest.mock import patch
from reset.clean_default import (
    get_repository_components,
    delete_component,
    filter_default_components_to_delete,
)
from requests.exceptions import RequestException
from datetime import datetime, timedelta, timezone


@patch("reset.clean_default.requests.get")
def test_get_repository_components_success(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "items": [
            {
                "id": "1",
                "name": "comp1",
                "version": "1.0",
                "assets": [{"lastModified": "2023-01-01T00:00:00Z"}],
            }
        ],
        "continuationToken": None,
    }
    result = get_repository_components("test1")
    assert len(result) == 1
    assert result[0]["name"] == "comp1"


@patch("reset.clean_default.requests.get")
def test_get_repository_components_empty(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"items": [], "continuationToken": None}
    result = get_repository_components("test1")
    assert result == []


@patch("reset.clean_default.requests.get")
def test_get_repository_components_no_items(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {}
    result = get_repository_components("test1")
    assert result == []


@patch("reset.clean_default.requests.get")
def test_get_repository_components_bad_response(mock_get):
    mock_get.side_effect = RequestException("connection error")
    result = get_repository_components("test1")
    assert result == []


@patch("reset.clean_default.DRY_RUN", True)
def test_delete_component_dry_run(caplog):
    with caplog.at_level(logging.INFO):
        delete_component("id1", "comp1", "v1")
    assert any(
        "[DRY_RUN] Пропущено удаление" in message
        for message in caplog.text.splitlines()
    )


@patch("reset.clean_default.DRY_RUN", False)
@patch("reset.clean_default.requests.delete")
def test_delete_component_success(mock_delete):
    mock_delete.return_value.status_code = 204
    delete_component("id1", "comp1", "v1")
    mock_delete.assert_called_once()


@patch("reset.clean_default.DRY_RUN", False)
@patch("reset.clean_default.requests.delete")
def test_delete_component_fails(mock_delete):
    mock_delete.side_effect = RequestException("fail")
    delete_component("id1", "comp1", "v1")
    mock_delete.assert_called_once()


def test_filter_default_components_to_delete():
    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=10)
    new_date = now - timedelta(days=1)

    components = [
        {
            "id": "1",
            "name": "comp1",
            "version": "1.0",
            "assets": [{"lastModified": old_date.isoformat()}],
        },
        {
            "id": "2",
            "name": "comp1",
            "version": "1.1",
            "assets": [{"lastModified": new_date.isoformat()}],
        },
        {
            "id": "3",
            "name": "comp2",
            "version": "dev-xyz",
            "assets": [{"lastModified": old_date.isoformat()}],
        },
        {
            "id": "4",
            "name": "comp3",
            "version": "",
            "assets": [{"lastModified": old_date.isoformat()}],
        },
        {
            "id": "5",
            "name": "comp4",
            "version": "1.0",
            "assets": [],
        },
        {
            "id": "6",
            "name": "comp5",
            "version": "1.0",
            "assets": [{"lastModified": "invalid-date"}],
        },
    ]

    result = filter_default_components_to_delete(components)
    # Согласно логике к удалению попадёт только comp1 со старой версией,
    # вторая версия comp1 не удаляется как резерв.
    assert len(result) == 1
    assert result[0]["id"] == "1"

from unittest.mock import patch, MagicMock
from requests.exceptions import RequestException
from app.nexus_api import get_repository_components, delete_component


@patch("app.nexus_api.requests.get")
def test_get_repository_components_success(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [{"id": "1", "name": "comp", "version": "1.0"}],
        "continuationToken": None,
    }
    mock_response.raise_for_status = lambda: None
    mock_get.return_value = mock_response

    result = get_repository_components("test-repo")
    assert len(result) == 1
    assert result[0]["id"] == "1"


@patch("app.nexus_api.requests.get")
def test_get_repository_components_request_exception(mock_get):
    mock_get.side_effect = RequestException("Network error")

    result = get_repository_components("test-repo")
    assert result == []


@patch("app.nexus_api.requests.get")
def test_get_repository_components_no_items(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"unexpected": "data"}
    mock_response.raise_for_status = lambda: None
    mock_get.return_value = mock_response

    result = get_repository_components("test-repo")
    assert result == []


@patch("app.nexus_api.requests.delete")
def test_delete_component_success(mock_delete):
    mock_response = MagicMock()
    mock_response.raise_for_status = lambda: None
    mock_delete.return_value = mock_response

    delete_component("123", "test-comp", "1.0")  # Проверка, что не падает


@patch("app.nexus_api.requests.delete")
def test_delete_component_error(mock_delete, caplog):
    mock_delete.side_effect = RequestException("Delete failed")

    delete_component("123", "test-comp", "1.0")
    assert "Ошибка при удалении компонента" in caplog.text

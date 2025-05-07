import requests
import logging
from typing import List, Dict
from config import BASE_URL, USER_NAME, PASSWORD


def get_repository_components(repo_name: str) -> List[Dict]:
    components = []
    continuation_token = None
    url = f"{BASE_URL}service/rest/v1/components"

    while True:
        params = {"repository": repo_name}
        if continuation_token:
            params["continuationToken"] = continuation_token

        try:
            response = requests.get(
                url, auth=(USER_NAME, PASSWORD), params=params, timeout=10
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Ошибка при получении компонентов '{repo_name}': {e}")
            return []

        items = data.get("items", None)
        if items is None:
            logging.error("❌ Некорректный формат ответа: отсутствует поле 'items'")
            return []

        if not items:
            logging.info(f"ℹ️  В репозитории '{repo_name}' нет компонентов для обработки")
            return []

        components.extend(items)
        continuation_token = data.get("continuationToken")

        if not continuation_token:
            break

    return components


def delete_component(
    component_id: str, component_name: str, component_version: str
) -> None:
    url = f"{BASE_URL}service/rest/v1/components/{component_id}"
    try:
        response = requests.delete(url, auth=(USER_NAME, PASSWORD), timeout=10)
        response.raise_for_status()
        logging.info(
            f"✅ Удалён образ: {component_name} (версия {component_version}, ID: {component_id})"
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Ошибка при удалении компонента {component_id}: {e}")

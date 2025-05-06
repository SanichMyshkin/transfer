import requests
import logging
from config import BASE_URL, USER_NAME, PASSWORD


def get_repository_components(repo_name):
    components = []
    continuation_token = None

    while True:
        params = {"repository": repo_name}
        if continuation_token:
            params["continuationToken"] = continuation_token

        try:
            response = requests.get(
                f"{BASE_URL}service/rest/v1/components",
                auth=(USER_NAME, PASSWORD),
                params=params,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Ошибка при получении компонентов '{repo_name}': {e}")
            return []

        if "items" not in data:
            logging.error("❌ Некорректный формат ответа: нет 'items'")
            return []

        components.extend(data["items"])
        continuation_token = data.get("continuationToken")

        if not continuation_token:
            break

    return components


def delete_component(component_id, component_name, component_version):
    url = f"{BASE_URL}service/rest/v1/components/{component_id}"
    try:
        response = requests.delete(url, auth=(USER_NAME, PASSWORD))
        response.raise_for_status()
        logging.info(
            f"✅ Удалён образ: {component_name} (версия {component_version}, ID: {component_id})"
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Ошибка при удалении компонента {component_id}: {e}")

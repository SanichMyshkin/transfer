import requests
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Конфигурация
NEXUS_URL = os.getenv("BASE_URL")
USER_NAME = os.getenv("USER_NAME")
PASSWORD = os.getenv("PASSWORD")


# Логирование
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_repository_components(repo_name):
    """
    Получить все компоненты (артефакты) репозитория.
    """
    logging.info(f"🔄 Получение списка компонентов для репозитория: {repo_name}")
    components = []
    continuation_token = None

    while True:
        params = {}
        if continuation_token:
            params["continuationToken"] = continuation_token

        resp = requests.get(
            f"{NEXUS_URL}/service/rest/v1/components",
            params={**params, "repository": repo_name},
            auth=(USER_NAME, PASSWORD),
        )
        resp.raise_for_status()
        data = resp.json()
        items = data["items"]
        logging.info(f"📦 Найдено {len(items)} компонентов в репозитории '{repo_name}'")

        components.extend(items)
        continuation_token = data.get("continuationToken")

        if not continuation_token:
            break

    logging.info(f"✅ Всего компонентов в репозитории '{repo_name}': {len(components)}")
    return components


def delete_component(component):
    """
    Удалить компонент (артефакт) по его ID.
    """
    component_id = component.get("id")
    url = f"{NEXUS_URL}/service/rest/v1/components/{component_id}"
    resp = requests.delete(url, auth=(USER_NAME, PASSWORD))
    if resp.status_code == 204:
        logging.info(
            f"✅ Компонент {component.get('version')} с ID {component_id} успешно удалён."
        )
    else:
        logging.warning(
            f"⚠️ Ошибка удаления  компонента {component.get('version')} c ID {component_id}: {resp.status_code} - {resp.text}"
        )


def clear_repository(repo_name):
    """
    Очищает репозиторий, удаляя все его компоненты.
    """
    components = get_repository_components(repo_name)
    for component in components:
        component_id = component["id"]
        logging.info(
            f"🔴 Удаление компонента {component.get('version')}с ID {component_id} из репозитория '{repo_name}'"
        )
        delete_component(component)


def main():
    repo_name = "trash"  # Имя репозитория, который нужно очистить
    logging.info(f"🚮 Начинаю очистку репозитория: {repo_name}")
    clear_repository(repo_name)


if __name__ == "__main__":
    main()

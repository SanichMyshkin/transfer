import os
from dotenv import load_dotenv
import requests
import logging
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse

load_dotenv()

USER_NAME = os.getenv("USER_NAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")


IMAGE_PREFIXES = [
    "dev-",
    "test-",
    "release",
    "master",
]

TIME_LIMIT = timedelta(days=0)
RESERVED_MINIMUM = 2  # Количество сохраняемых последних образов на префикс

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def extract_prefix(version):
    for prefix in IMAGE_PREFIXES:
        if version.startswith(prefix):
            return prefix
    if "-" in version:
        return version.split("-")[0] + "-"
    return ""


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
            logging.error(f"Ошибка при получении компонентов: {e}")
            return []

        if "items" not in data:
            logging.error("Некорректный формат ответа: отсутствует 'items'")
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
            f"✅ Удалён: {component_name} (версия {component_version}, ID: {component_id})"
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при удалении компонента {component_id}: {e}")


def filter_components_to_delete(components):
    prefix_groups = {}
    for component in components:
        version = component.get("version", "")
        prefix = extract_prefix(version)
        if not prefix:
            continue

        assets = component.get("assets", [])
        if not assets:
            continue

        last_modified_str = assets[0].get("lastModified")
        if not last_modified_str:
            continue

        try:
            last_modified = parse(last_modified_str)
        except Exception as e:
            logging.error(f"Ошибка парсинга даты {last_modified_str}: {e}")
            continue

        component["last_modified"] = last_modified
        prefix_groups.setdefault(prefix, []).append(component)

    now_utc = datetime.now(timezone.utc)
    # now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)

    to_delete = []
    for prefix, group in prefix_groups.items():
        sorted_components = sorted(
            group, key=lambda x: x["last_modified"], reverse=True
        )

        for component in sorted_components[RESERVED_MINIMUM:]:
            age = now_utc - component["last_modified"]
            if age > TIME_LIMIT:
                to_delete.append(component)

    return to_delete


def clear_repository(repo_name):
    logging.info(f"🔄 Начало очистки репозитория {repo_name}")

    components = get_repository_components(repo_name)
    if not components:
        logging.warning("Компоненты не найдены")
        return

    to_delete = filter_components_to_delete(components)

    if not to_delete:
        logging.info("Нет компонентов для удаления")
        return

    logging.info(f"🚮 Найдено {len(to_delete)} компонентов для удаления")
    for component in to_delete:
        delete_component(
            component["id"],
            component.get("name", "Без имени"),
            component.get("version", "Без версии"),
        )


if __name__ == "__main__":
    response = requests.get(f"{BASE_URL}/service/rest/v1/repositories")
    data = response.json()

    result = [
        repo.get("name")
        for repo in data
        if repo.get("format") == "docker" and repo.get("type") == "hosted"
    ]

    list(map(clear_repository, result))

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

# Настраиваемые сроки хранения по префиксам
PREFIX_RETENTION = {
    "dev": timedelta(days=7),
    "test": timedelta(days=14),
    "release": timedelta(days=90),
    "master": timedelta(days=180),
}

DEFAULT_RETENTION = timedelta(days=30)
RESERVED_MINIMUM = 2  # Минимум сохраняемых образов на префикс

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


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
            logging.error(
                f"❌ Ошибка при получении компонентов репозитория '{repo_name}': {e}"
            )
            return []

        if "items" not in data:
            logging.error("❌ Некорректный формат ответа: отсутствует 'items'")
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


def get_prefix_and_retention(version: str):
    version_lower = version.lower()
    for prefix, retention in PREFIX_RETENTION.items():
        if version_lower.startswith(prefix.lower()):
            return prefix, retention
    return "без_префикса", DEFAULT_RETENTION



def filter_components_to_delete(components):
    now_utc = datetime.now(timezone.utc)
    grouped = {}

    for component in components:
        version = component.get("version", "")
        assets = component.get("assets", [])
        if not assets or not version:
            logging.info(
                f"ℹ️ Пропущен компонент без версии или ассетов: {component.get('name', 'Без имени')}"
            )
            continue

        last_modified_str = assets[0].get("lastModified")
        if not last_modified_str:
            logging.info(f"ℹ️ Пропущен компонент без даты: {version}")
            continue

        try:
            last_modified = parse(last_modified_str)
        except Exception as e:
            logging.error(
                f"❌ Ошибка парсинга даты '{last_modified_str}' для версии {version}: {e}"
            )
            continue

        prefix, retention = get_prefix_and_retention(version)
        component.update(
            {"last_modified": last_modified, "retention": retention, "prefix": prefix}
        )
        grouped.setdefault(prefix, []).append(component)

    to_delete = []

    for prefix, group in grouped.items():
        sorted_group = sorted(group, key=lambda x: x["last_modified"], reverse=True)
        logging.info(
            f"📦 Префикс '{prefix}' — срок хранения: {group[0]['retention'].days} дней, всего образов: {len(group)}"
        )

        for i, component in enumerate(sorted_group):
            name = component.get("name", "Без имени")
            version = component.get("version", "Без версии")
            age = now_utc - component["last_modified"]
            retention = component["retention"]

            if i < RESERVED_MINIMUM:
                logging.info(
                    f"⏸ Сохранён (входит в RESERVED_MINIMUM): {name} {version}"
                )
                continue

            if age > retention:
                logging.info(
                    f"🗑 К удалению: {name} {version} — старше {retention.days} дней (возраст: {age.days} дн.)"
                )
                to_delete.append(component)
            else:
                logging.info(
                    f"⏩ Пропущен (срок хранения не вышел): {name} {version} — возраст: {age.days} дн., лимит: {retention.days} дн."
                )

    return to_delete


def clear_repository(repo_name):
    logging.info(f"🔄 Начало очистки репозитория '{repo_name}'")

    components = get_repository_components(repo_name)
    if not components:
        logging.warning(f"⚠️ Компоненты в репозитории '{repo_name}' не найдены")
        return

    to_delete = filter_components_to_delete(components)

    if not to_delete:
        logging.info(f"✅ Нет компонентов для удаления в репозитории '{repo_name}'")
        return

    logging.info(
        f"🚮 Удаляется {len(to_delete)} компонент(ов) из репозитория '{repo_name}'"
    )
    for component in to_delete:
        delete_component(
            component["id"],
            component.get("name", "Без имени"),
            component.get("version", "Без версии"),
        )


if __name__ == "__main__":
    try:
        response = requests.get(
            f"{BASE_URL}/service/rest/v1/repositories", auth=(USER_NAME, PASSWORD)
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Не удалось получить список репозиториев: {e}")
        exit(1)

    result = [
        repo.get("name")
        for repo in data
        if repo.get("format") == "docker" and repo.get("type") == "hosted"
    ]

    if not result:
        logging.error("❌ Репозитории типа docker/hosted не найдены")
        exit(1)

    for repo_name in result:
        clear_repository(repo_name)

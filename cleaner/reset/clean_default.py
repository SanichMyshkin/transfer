# cleaner_default.py

import os
import logging
import requests
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()

USER_NAME = os.getenv("USER_NAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

os.makedirs("logs", exist_ok=True)
log_filename = "logs/cleaner_default.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

REPO_NAME = ["test1"]

DEFAULT_RETENTION = timedelta(days=30)
DEFAULT_RESERVED = 1


def get_repository_components(repo_name):
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
            logging.info(f"ℹ️ В репозитории '{repo_name}' нет компонентов для обработки")
            return []

        components.extend(items)
        continuation_token = data.get("continuationToken")

        if not continuation_token:
            break

    return components


def delete_component(component_id, component_name, component_version):
    if DRY_RUN:
        logging.info(
            f"🧪 [DRY_RUN] Пропущено удаление: {component_name} (версия {component_version}, ID: {component_id})"
        )
        return

    url = f"{BASE_URL}service/rest/v1/components/{component_id}"
    try:
        response = requests.delete(url, auth=(USER_NAME, PASSWORD), timeout=10)
        response.raise_for_status()
        logging.info(
            f"✅ Удалён образ: {component_name} (версия {component_version}, ID: {component_id})"
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Ошибка при удалении компонента {component_id}: {e}")


def filter_default_components_to_delete(components):
    now_utc = datetime.now(timezone.utc) + timedelta(seconds=1)
    grouped = defaultdict(list)

    for component in components:
        version = component.get("version", "")
        name = component.get("name", "")
        assets = component.get("assets", [])
        if not assets or not version or not name:
            continue

        last_modified_strs = [
            a.get("lastModified") for a in assets if a.get("lastModified")
        ]
        if not last_modified_strs:
            continue

        try:
            last_modified = max(parse(s) for s in last_modified_strs)
        except Exception:
            continue

        # Отфильтровываем компоненты без подходящего префикса
        if any(
            version.lower().startswith(p) for p in ["dev", "test", "release", "master"]
        ):
            continue

        component.update(
            {
                "last_modified": last_modified,
            }
        )

        grouped[name].append(component)

    to_delete = []

    for name, group in grouped.items():
        sorted_group = sorted(group, key=lambda x: x["last_modified"], reverse=True)

        for i, component in enumerate(sorted_group):
            version = component.get("version", "Без версии")
            age = now_utc - component["last_modified"]

            if i < DEFAULT_RESERVED:
                logging.info(
                    f"⏸ Сохранён (резерв {DEFAULT_RESERVED}): {name}:{version}"
                )
                continue

            if age > DEFAULT_RETENTION:
                logging.info(
                    f"🗑 К удалению: {name}:{version} (возраст: {age.days} дн., лимит: {DEFAULT_RETENTION.days} дн.)"
                )
                to_delete.append(component)

    return to_delete


def clear_repository(repo_name):
    logging.info(f"🔄 Начало очистки репозитория '{repo_name}'")
    components = get_repository_components(repo_name)
    if not components:
        return

    to_delete = filter_default_components_to_delete(components)
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


def main():
    list(map(clear_repository, REPO_NAME))


if __name__ == "__main__":
    main()

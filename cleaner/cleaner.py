import os
import logging
import requests
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse
from dotenv import load_dotenv
from collections import defaultdict
from logging.handlers import TimedRotatingFileHandler

load_dotenv()

USER_NAME = os.getenv("USER_NAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

REPO_NAME = ["test1"]


PREFIX_RULES = {
    "dev": {"retention": timedelta(days=7), "reserved": 0},
    "test": {"retention": timedelta(days=14), "reserved": 0},
    "release": {"retention": timedelta(days=30), "reserved": 1},
    "master": {"retention": timedelta(days=180), "reserved": 1},
}

MAX_RETENTION = timedelta(days=180)



log_filename = "logs/cleaner.log"
file_handler = TimedRotatingFileHandler(
    log_filename, when="midnight", interval=1, backupCount=7, encoding="utf-8"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        file_handler,
        logging.StreamHandler(),
    ],
)


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

        if not items and not components:
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


def get_prefix_rules(version):
    version_lower = version.lower()
    for prefix, rules in PREFIX_RULES.items():
        if version_lower.startswith(prefix.lower()):
            return prefix, rules["retention"], rules["reserved"]
    return None, None, None  # Сигнализируем, что префикс не найден


def filter_components_to_delete(components):
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

        # Отсекаем latest-теги сразу — у них иммунитет
        if "latest" in version.lower():
            logging.info(
                f"🔒 Пропущен тег {version}: {name}:{version} — иммунитет от удаления"
            )
            continue  # Не попадают в группы и в резерв

        # Определяем правила по префиксу
        prefix, retention, reserved = get_prefix_rules(version)
        if prefix is None:
            # Для тегов без префикса используем глобальное правило: 30 дней, без резерва
            retention = timedelta(days=30)
            reserved = 0
            prefix = "global"

        component.update(
            {
                "last_modified": last_modified,
                "retention": retention,
                "reserved": reserved,
                "prefix": prefix,
            }
        )

        grouped[(name, prefix)].append(component)

    to_delete = []

    for (name, prefix), group in grouped.items():
        # Сортируем по дате последнего изменения (новейшие — впереди)
        sorted_group = sorted(group, key=lambda x: x["last_modified"], reverse=True)

        for i, component in enumerate(sorted_group):
            version = component.get("version", "Без версии")
            age = now_utc - component["last_modified"]
            retention = component["retention"]
            reserved = component["reserved"]

            # Проверяем лимит максимального возраста
            if age > MAX_RETENTION:
                logging.info(
                    f"🗑 К удалению (старше {MAX_RETENTION.days} дн.): {name}:{version} (возраст: {age.days} дн.)"
                )
                to_delete.append(component)
                continue

            # Проверяем резерв — сохраняем первые N образов по префиксу
            if i < reserved:
                logging.info(
                    f"📦 Сохранён (резерв {reserved}): {name}:{version} ({prefix})"
                )
                continue

            # Если возраст больше retention, удаляем
            if age > retention:
                logging.info(
                    f"🗑 К удалению по правилу {prefix}: {name}:{version} (возраст: {age.days} дн., лимит: {retention.days} дн.)"
                )
                to_delete.append(component)
            else:
                logging.info(
                    f"📦 Сохранён: {name}:{version} (возраст: {age.days} дн., лимит: {retention.days} дн.)"
                )

    return to_delete


def clear_repository(repo_name):
    logging.info(f"🔄 Начало очистки репозитория '{repo_name}'")
    components = get_repository_components(repo_name)
    if not components:
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


def main():
    list(map(clear_repository, REPO_NAME))


if __name__ == "__main__":
    main()

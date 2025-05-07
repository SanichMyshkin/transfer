import os
import logging
import requests
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse
from dotenv import load_dotenv

# Загрузка переменных из .env
load_dotenv()

USER_NAME = os.getenv("USER_NAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")

# Настройка логирования
os.makedirs("logs", exist_ok=True)
log_filename = datetime.now().strftime("logs/cleaner_%Y-%m-%d.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# Конфигурация
REPO_NAME = "docket2"  # <-- укажи тут нужное имя репозитория
PREFIX_RETENTION = {
    "dev": timedelta(days=7),
    "test": timedelta(days=14),
    "release": timedelta(days=90),
    "master": timedelta(days=180),
}
DEFAULT_RETENTION = timedelta(days=30)
RESERVED_MINIMUM = 2


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
    url = f"{BASE_URL}service/rest/v1/components/{component_id}"
    try:
        response = requests.delete(url, auth=(USER_NAME, PASSWORD), timeout=10)
        response.raise_for_status()
        logging.info(
            f"✅ Удалён образ: {component_name} (версия {component_version}, ID: {component_id})"
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Ошибка при удалении компонента {component_id}: {e}")


def get_prefix_and_retention(version):
    version_lower = version.lower()
    for prefix, retention in PREFIX_RETENTION.items():
        if version_lower.startswith(prefix.lower()):
            return prefix, retention
    return None, DEFAULT_RETENTION


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
            {
                "last_modified": last_modified,
                "retention": retention,
                "prefix": prefix,
                "has_prefix": prefix is not None,
            }
        )
        grouped.setdefault(prefix, []).append(component)

    to_delete = []

    for prefix, group in grouped.items():
        sorted_group = sorted(group, key=lambda x: x["last_modified"], reverse=True)
        retention_days = group[0]["retention"].days
        prefix_display = prefix if prefix else "Отсутствует"
        logging.info(
            f"📦 Префикс '{prefix_display}' — срок хранения: {retention_days} дней, всего образов: {len(group)}"
        )

        for i, component in enumerate(sorted_group):
            name = component.get("name", "Без имени")
            version = component.get("version", "Без версии")
            age = now_utc - component["last_modified"]
            retention = component["retention"]

            if prefix is not None and i < RESERVED_MINIMUM and age <= retention:
                logging.info(
                    f"⏸ Сохранён (входит в RESERVED_MINIMUM для префикса '{prefix}'): {name} {version}"
                )
                continue

            if age > retention:
                logging.info(
                    f"🗑 К удалению: {name} {version} — старше {retention.days} дней (возраст: {age.days} дн.)"
                )
                to_delete.append(component)
            else:
                if prefix is None:
                    logging.info(
                        f"⏩ Пропущен (без префикса, срок хранения не вышел): {name} {version} — возраст: {age.days} дн., лимит: {retention.days} дн."
                    )
                else:
                    logging.info(
                        f"⏩ Пропущен (с префиксом '{prefix}', срок хранения не вышел): {name} {version} — возраст: {age.days} дн., лимит: {retention.days} дн."
                    )

    return to_delete


def clear_repository(repo_name):
    logging.info(f"🔄 Начало очистки репозитория '{repo_name}'")

    components = get_repository_components(repo_name)
    if components is None:
        logging.warning(f"⚠️ Ошибка при получении компонентов репозитория '{repo_name}'")
        return

    if not components:
        # Уже залогировано в get_repository_components
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
    clear_repository(REPO_NAME)


if __name__ == "__main__":
    main()

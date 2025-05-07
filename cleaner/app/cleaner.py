import logging
import os
from datetime import datetime, timezone
from dateutil.parser import parse

from config import RESERVED_MINIMUM, PREFIX_RETENTION, DEFAULT_RETENTION
from nexus_api import get_repository_components, delete_component


os.makedirs("logs", exist_ok=True)

# 🪵 Настройка логгера
log_filename = datetime.now().strftime("logs/cleaner_%Y-%m-%d.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def get_prefix_and_retention(version: str):
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

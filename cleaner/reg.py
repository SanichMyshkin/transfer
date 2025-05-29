import os
import logging
import requests
import yaml
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse
from collections import defaultdict
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

USER_NAME = os.getenv("USER_NAME")
PASSWORD = os.getenv("PASSWORD")
BASE_URL = os.getenv("BASE_URL")

log_filename = os.path.join(os.path.dirname(__file__), "logs", "cleaner.log")

os.makedirs(os.path.dirname(log_filename), exist_ok=True)

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


def load_config(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"❌ Ошибка загрузки конфига '{path}': {e}")
        return None


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
                url, auth=(USER_NAME, PASSWORD), params=params, timeout=10, verify=False
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Ошибка при получении компонентов '{repo_name}': {e}")
            return []

        items = data.get("items")

        if not items and not components:
            logging.info(f"ℹ️ В репозитории '{repo_name}' нет компонентов для обработки")
            return []

        components.extend(items)
        continuation_token = data.get("continuationToken")

        if not continuation_token:
            break

    return components


def delete_component(component_id, component_name, component_version, dry_run):
    if dry_run:
        logging.info(
            f"🧪 [DRY_RUN] Пропущено удаление: {component_name} (версия {component_version}, ID: {component_id})"
        )
        return

    url = f"{BASE_URL}service/rest/v1/components/{component_id}"
    try:
        response = requests.delete(
            url, auth=(USER_NAME, PASSWORD), timeout=10, verify=False
        )
        response.raise_for_status()
        logging.info(
            f"✅ Удалён образ: {component_name} (версия {component_version}, ID: {component_id})"
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Ошибка при удалении компонента {component_id}: {e}")


def get_matching_rule(version, regex_rules, no_match_retention, no_match_reserved):
    version_lower = version.lower()
    for pattern, rules in regex_rules.items():
        if re.match(pattern, version_lower):
            retention_days = rules.get("retention_days")
            reserved = rules.get("reserved")
            retention = (
                timedelta(days=retention_days) if retention_days is not None else None
            )
            return pattern, retention, reserved
    retention = (
        timedelta(days=no_match_retention) if no_match_retention is not None else None
    )
    return "no-match", retention, no_match_reserved


from collections import defaultdict
from datetime import datetime, timezone, timedelta
import logging
from dateutil.parser import parse


def filter_components_to_delete(
    components, regex_rules, max_retention, no_match_retention, no_match_reserved
):
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

        if version.lower() == "latest":
            logging.info(
                f"🔒 Пропущен тег {version}: {name}:{version} — иммунитет от удаления"
            )
            continue

        pattern, retention, reserved = get_matching_rule(
            version, regex_rules, no_match_retention, no_match_reserved
        )

        component.update(
            {
                "last_modified": last_modified,
                "retention": retention,
                "reserved": reserved,
                "pattern": pattern,
            }
        )
        grouped[(name, pattern)].append(component)

    to_delete = []

    for (name, pattern), group in grouped.items():
        sorted_group = sorted(group, key=lambda x: x["last_modified"], reverse=True)

        for i, component in enumerate(sorted_group):
            version = component.get("version", "Без версии")
            age = now_utc - component["last_modified"]
            retention = component.get("retention")
            reserved = component.get("reserved")

            # 🔥 Удаляем, если превышен max_retention
            if max_retention is not None and age.days > max_retention:
                logging.info(
                    f"🗑 К удалению (max_retention {max_retention} дн.): {name}:{version} (возраст: {age.days} дн.)"
                )
                to_delete.append(component)
                continue

            # 🧷 Проверка по retention (даже если зарезервирован)
            if retention is not None and age > retention:
                logging.info(
                    f"🗑 К удалению по retention: {name}:{version} (возраст: {age.days} дн., лимит: {retention.days} дн.)"
                )
                to_delete.append(component)
                continue

            # 🔒 Зарезервированные — сохраняем
            if reserved is not None and i < reserved:
                logging.info(
                    f"📦 Сохранён (резерв {reserved}): {name}:{version}, осталось мест: {reserved - (i + 1)}"
                )
                continue

            # 🗑 Если не зарезервирован и retention не сработал — удалить
            if reserved is not None and i >= reserved:
                logging.info(
                    f"🗑 К удалению (вышел за пределы резерва {reserved}): {name}:{version}"
                )
                to_delete.append(component)
                continue

            # 🟢 Всё остальное сохраняется
            logging.info(
                f"📦 Сохранён: {name}:{version} — ни retention, ни reserved не заданы"
            )

    logging.info(f"🧹 Компонентов к удалению: {len(to_delete)}")
    return to_delete





def clear_repository(repo_name, cfg):
    logging.info(f"🔄 Начало очистки репозитория '{repo_name}'")
    components = get_repository_components(repo_name)
    if not components:
        return

    to_delete = filter_components_to_delete(
        components,
        regex_rules=cfg.get("regex_rules", {}),
        max_retention=cfg.get("max_retention_days"),
        no_match_retention=cfg.get("no_match_retention_days"),
        no_match_reserved=cfg.get("no_match_reserved", None),
    )

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
            cfg.get("dry_run", False),
        )


def main():
    config_dir = os.path.join(os.path.dirname(__file__), "configs")
    config_files = [f for f in os.listdir(config_dir) if f.endswith(".yaml")]

    if not config_files:
        logging.warning("⚠️ В папке 'configs/' не найдено ни одного YAML-файла")
        return

    for cfg_file in config_files:
        full_path = os.path.join(config_dir, cfg_file)
        logging.info(f"📄 Обработка конфига: {cfg_file}")
        config = load_config(full_path)
        if not config:
            continue
        repos = config.get("repo_names", [])
        for repo in repos:
            clear_repository(repo, config)


if __name__ == "__main__":
    main()

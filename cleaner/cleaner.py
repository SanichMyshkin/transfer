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
        logging.error(f"[LOAD] ❌ Ошибка загрузки конфига '{path}': {e}")
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
            logging.error(
                f"[API] ❌ Ошибка при получении компонентов '{repo_name}': {e}"
            )
            return []

        items = data.get("items")

        if not items and not components:
            logging.info(f"[API] ℹ️ Репозиторий '{repo_name}' пуст")
            return []

        components.extend(items)
        continuation_token = data.get("continuationToken")

        if not continuation_token:
            break

    return components


def delete_component(component_id, component_name, component_version, dry_run):
    if dry_run:
        logging.info(
            f"[DELETE] 🧪 [DRY_RUN] Пропущено удаление: {component_name}:{component_version} (ID: {component_id})"
        )
        return

    url = f"{BASE_URL}service/rest/v1/components/{component_id}"
    try:
        response = requests.delete(
            url, auth=(USER_NAME, PASSWORD), timeout=10, verify=False
        )
        response.raise_for_status()
        logging.info(
            f"[DELETE] ✅ Удалён: {component_name}:{component_version} (ID: {component_id})"
        )
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            logging.warning(
                f"[DELETE] ⚠️ Компонент не найден (404): {component_name}:{component_version} (ID: {component_id})"
            )
        else:
            logging.error(f"[DELETE] ❌ Ошибка HTTP при удалении {component_id}: {e}")
    except requests.exceptions.RequestException as e:
        logging.error(f"[DELETE] ❌ Ошибка при удалении {component_id}: {e}")


def get_matching_rule(
    version,
    regex_rules,
    no_match_retention,
    no_match_reserved,
    no_match_min_days_since_last_download,
):
    version_lower = version.lower()
    for pattern, rules in regex_rules.items():
        if re.match(pattern, version_lower):
            retention_days = rules.get("retention_days")
            reserved = rules.get("reserved")
            min_days_since_last_download = rules.get("min_days_since_last_download")
            retention = (
                timedelta(days=retention_days) if retention_days is not None else None
            )
            return pattern, retention, reserved, min_days_since_last_download
    retention = (
        timedelta(days=no_match_retention) if no_match_retention is not None else None
    )
    return (
        "no-match",
        retention,
        no_match_reserved,
        no_match_min_days_since_last_download,
    )


def filter_components_to_delete(
    components,
    regex_rules,
    no_match_retention,
    no_match_reserved,
    no_match_min_days_since_last_download,
):
    now_utc = datetime.now(timezone.utc)
    grouped = defaultdict(list)

    for component in components:
        version = component.get("version", "")
        name = component.get("name", "")
        assets = component.get("assets", [])
        if not assets or not version or not name:
            logging.info(f" ⏭ Пропуск: отсутствует имя, версия или assets у компонента {component}")
            continue

        last_modified_strs = [a.get("lastModified") for a in assets if a.get("lastModified")]
        last_download_strs = [a.get("lastDownloaded") for a in assets if a.get("lastDownloaded")]

        if not last_modified_strs:
            logging.info(f" ⏭ Пропуск: отсутствует lastModified у компонента {name}:{version}")
            continue

        try:
            last_modified = max(parse(s) for s in last_modified_strs)
        except Exception:
            logging.info(f" ⏭ Пропуск: ошибка парсинга lastModified у {name}:{version}")
            continue

        last_download = None
        if last_download_strs:
            try:
                last_download = max(parse(s) for s in last_download_strs)
            except Exception:
                logging.info(f" ⚠ Ошибка парсинга lastDownloaded у {name}:{version}")
                pass

        if version.lower() == "latest":
            logging.info(f" 🔒 Защищён от удаления (latest): {name}:{version}")
            continue

        pattern, retention, reserved, min_days_since_last_download = get_matching_rule(
            version,
            regex_rules,
            no_match_retention,
            no_match_reserved,
            no_match_min_days_since_last_download,
        )

        component.update({
            "last_modified": last_modified,
            "last_download": last_download,
            "retention": retention,
            "reserved": reserved,
            "pattern": pattern,
            "min_days_since_last_download": min_days_since_last_download,
        })

        grouped[(name, pattern)].append(component)

    to_delete = []

    for (name, pattern), group in grouped.items():
        sorted_group = sorted(group, key=lambda x: x["last_modified"], reverse=True)

        for i, component in enumerate(sorted_group):
            version = component.get("version", "Без версии")
            age = now_utc - component["last_modified"]
            last_download = component.get("last_download")
            retention = component.get("retention")
            reserved = component.get("reserved")
            min_days_since_last_download = component.get("min_days_since_last_download")

            if reserved is not None and i < reserved:
                logging.info(
                    f" 📦 Зарезервирован: {name}:{version} | правило ({pattern}) (позиция {i + 1}/{reserved})"
                )
                continue

            if last_download and min_days_since_last_download is not None:
                since_download = (now_utc - last_download).days
                if since_download <= min_days_since_last_download:
                    logging.info(
                        f" 📦 Использовался недавно: {name}:{version} | правило ({pattern}) (скачивали {since_download} дн. назад ≤ {min_days_since_last_download})"
                    )
                    continue
                else:
                    logging.info(
                        f" 🗑 Не скачивали давно: {name}:{version} | правило ({pattern}) (скачивали {since_download} дн. назад > {min_days_since_last_download})"
                    )
                    to_delete.append(component)
                    continue

            if retention is not None:
                if age.days > retention.days:
                    logging.info(
                        f" 🗑 Удаление по retention: {name}:{version} | правило ({pattern}) (возраст {age.days} дн. > {retention.days})"
                    )
                    to_delete.append(component)
                    continue
                else:
                    logging.info(
                        f" 📦 Сохранён по retention: {name}:{version} | правило ({pattern}) (возраст {age.days} дн. ≤ {retention.days})"
                    )
                    continue

            if reserved is not None and i >= reserved:
                logging.info(
                    f" 🗑 Удаление по правилу reserved: {name}:{version} | правило ({pattern}) (позиция {i + 1} > {reserved})"
                )
                to_delete.append(component)
            else:
                logging.info(
                    f" 📦 Сохранён: {name}:{version} | правило ({pattern}) — не попал под условия удаления"
                )

    logging.info(f" 🧹 Обнаружено к удалению: {len(to_delete)} компонент(ов)")
    return to_delete


def clear_repository(repo_name, cfg):
    logging.info(f"\n🔄 Начало очистки репозитория: {repo_name}")

    components = get_repository_components(repo_name)
    if not components:
        logging.info(
            f"Репозиторий '{repo_name}' не содержит компонентов"
        )
        return

    to_delete = filter_components_to_delete(
        components,
        regex_rules=cfg.get("regex_rules", {}),
        no_match_retention=cfg.get("no_match_retention_days"),
        no_match_reserved=cfg.get("no_match_reserved", None),
        no_match_min_days_since_last_download=cfg.get(
            "no_match_min_days_since_last_download", None
        ),
    )

    if not to_delete:
        logging.info(f"✅ Нет компонентов для удаления в '{repo_name}'")
        return

    logging.info(f"🚮 Удаление {len(to_delete)} компонент(ов)...")
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
        logging.warning("[MAIN] ⚠️ В папке 'configs/' нет YAML-файлов")
        return

    for cfg_file in config_files:
        full_path = os.path.join(config_dir, cfg_file)
        logging.info(f"\n📄 Обработка файла конфигурации: {cfg_file}")
        config = load_config(full_path)
        if not config:
            continue
        repos = config.get("repo_names", [])
        for repo in repos:
            clear_repository(repo, config)


if __name__ == "__main__":
    main()

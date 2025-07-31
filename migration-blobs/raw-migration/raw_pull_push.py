import os
import sys
import tempfile
import logging
import requests
import urllib3
from urllib.parse import urljoin
from pathlib import Path
from dotenv import load_dotenv

# === Загрузка переменных окружения ===
load_dotenv()

# === Логгирование ===
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# === Отключаем предупреждения SSL ===
urllib3.disable_warnings()

# === Переменные окружения ===
NEXUS_URL = os.getenv("NEXUS_URL")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
SOURCE_REPO = os.getenv("SOURCE_REPO", "source-raw")
TARGET_REPO = os.getenv("TARGET_REPO", "target-raw")

if not all([NEXUS_URL, USERNAME, PASSWORD]):
    log.error("❌ Не заданы переменные окружения: NEXUS_URL, USERNAME, PASSWORD")
    sys.exit(1)

session = requests.Session()
session.auth = (USERNAME, PASSWORD)
session.verify = False
session.headers.update({"Accept": "application/json"})


def get_all_raw_assets(repo_name):
    log.info(f"📋 Получаем список файлов из RAW-репозитория {repo_name}")
    url = f"{NEXUS_URL}/service/rest/v1/assets"
    continuation_token = None
    assets = []

    while True:
        params = {"repository": repo_name}
        if continuation_token:
            params["continuationToken"] = continuation_token

        resp = session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        for item in data["items"]:
            path = item["path"]
            assets.append(path)

        continuation_token = data.get("continuationToken")
        if not continuation_token:
            break

    log.info(f"🔍 Найдено {len(assets)} файлов")
    return assets


def download_asset(path, download_dir):
    url = f"{NEXUS_URL}/repository/{SOURCE_REPO}/{path}"
    log.info(f"⬇️ Скачиваем {path}")
    local_path = Path(download_dir) / path
    local_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        r = session.get(url, stream=True)
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return local_path
    except requests.RequestException as e:
        log.warning(f"⚠️ Ошибка при скачивании {path}: {e}")
        return None


def upload_asset(local_path, relative_path):
    upload_url = f"{NEXUS_URL}/repository/{TARGET_REPO}/{relative_path.as_posix()}"
    log.info(f"⬆️ Загружаем {relative_path}")
    try:
        with open(local_path, "rb") as f:
            r = session.put(upload_url, data=f)
            r.raise_for_status()
    except requests.RequestException as e:
        log.error(f"❌ Ошибка загрузки {relative_path}: {e}")


def verify_all_files(local_base: Path, asset_paths):
    log.info("🔍 Начинаем проверку всех загруженных файлов...")
    failed = []

    for asset_path in asset_paths:
        relative_path = Path(asset_path)
        local_file = local_base / relative_path
        verify_url = f"{NEXUS_URL}/repository/{TARGET_REPO}/{relative_path.as_posix()}"

        try:
            r = session.get(verify_url, stream=True)
            r.raise_for_status()
            remote_data = r.content

            with open(local_file, "rb") as f:
                local_data = f.read()

            if local_data == remote_data:
                log.info(f"🟢 Проверка пройдена: {relative_path}")
            else:
                log.error(f"🔴 Несовпадение содержимого: {relative_path}")
                failed.append(str(relative_path))

        except requests.RequestException as e:
            log.error(f"❌ Ошибка при проверке {relative_path}: {e}")
            failed.append(str(relative_path))

    if failed:
        log.warning(f"❗ Проверка завершена с ошибками. Несовпавшие файлы: {len(failed)}")
        for f in failed:
            log.warning(f"  - {f}")
    else:
        log.info("✅ Все файлы успешно проверены")


def migrate_raw_assets():
    assets = get_all_raw_assets(SOURCE_REPO)
    if not assets:
        log.warning("❗ Нет файлов для миграции")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = Path(tmpdir)
        for asset_path in assets:
            local_path = download_asset(asset_path, base_path)
            if local_path:
                upload_asset(local_path, Path(asset_path))

        # После всех загрузок — проверка целостности
        verify_all_files(base_path, assets)

    log.info("✅ Миграция RAW-файлов завершена")


if __name__ == "__main__":
    migrate_raw_assets()

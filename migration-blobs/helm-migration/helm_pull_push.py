import os
import sys
import tempfile
import logging
import requests
import urllib3
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
SOURCE_REPO = os.getenv("SOURCE_REPO", "source-helm")
TARGET_REPO = os.getenv("TARGET_REPO", "target-helm")

if not all([NEXUS_URL, USERNAME, PASSWORD]):
    log.error("❌ Не заданы переменные окружения: NEXUS_URL, USERNAME, PASSWORD")
    sys.exit(1)

session = requests.Session()
session.auth = (USERNAME, PASSWORD)
session.verify = False
session.headers.update({"Accept": "application/json"})

def get_all_helm_charts(repo_name):
    log.info(f"📋 Получаем список Helm-чартов из репозитория {repo_name}")
    url = f"{NEXUS_URL}/service/rest/v1/components"
    continuation_token = None
    charts = []

    while True:
        params = {"repository": repo_name}
        if continuation_token:
            params["continuationToken"] = continuation_token

        resp = session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        for item in data["items"]:
            name = item["name"]
            version = item["version"]
            charts.append((name, version))

        continuation_token = data.get("continuationToken")
        if not continuation_token:
            break

    log.info(f"🔍 Найдено {len(charts)} чартов")
    return charts

def is_chart_uploaded(name, version):
    url = f"{NEXUS_URL}/service/rest/v1/components"
    continuation_token = None

    while True:
        params = {"repository": TARGET_REPO}
        if continuation_token:
            params["continuationToken"] = continuation_token

        resp = session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        for item in data["items"]:
            if item["name"] == name and item["version"] == version:
                log.info(f"✅ {name}-{version} уже загружен, пропускаем")
                return True

        continuation_token = data.get("continuationToken")
        if not continuation_token:
            break

    return False

def download_chart(name, version, download_dir):
    url = f"{NEXUS_URL}/repository/{SOURCE_REPO}/{name}-{version}.tgz"
    log.info(f"⬇️ Скачиваем {name}-{version}.tgz из {SOURCE_REPO}")
    dest = os.path.join(download_dir, f"{name}-{version}.tgz")

    try:
        r = session.get(url, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return dest
    except requests.RequestException as e:
        log.warning(f"⚠️ Ошибка загрузки {name}-{version}: {e}")
        return None

def upload_chart(filepath):
    filename = os.path.basename(filepath)
    upload_url = f"{NEXUS_URL}/repository/{TARGET_REPO}/{filename}"
    log.info(f"⬆️ Загружаем {filename} в {TARGET_REPO}")
    try:
        r = session.put(upload_url, data=open(filepath, "rb"))
        r.raise_for_status()
    except requests.RequestException as e:
        log.error(f"❌ Ошибка загрузки {filename}: {e}")

def migrate_helm_charts():
    charts = get_all_helm_charts(SOURCE_REPO)
    if not charts:
        log.warning("❗ Нет чартов для миграции")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        for name, version in charts:
            if is_chart_uploaded(name, version):
                continue

            chart_path = download_chart(name, version, tmpdir)
            if chart_path:
                upload_chart(chart_path)

    log.info("✅ Миграция Helm-чартов завершена")

if __name__ == "__main__":
    migrate_helm_charts()

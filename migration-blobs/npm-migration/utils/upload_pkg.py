import os
import subprocess
import tempfile
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

# === Логгирование ===
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# === Переменные окружения ===
NEXUS_URL = os.getenv("NEXUS_URL")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
NPM_REPO = os.getenv("NPM_REPO", "npm-hosted")

# === Список популярных пакетов для загрузки ===
npm_packages = [
    ("lodash", "4.17.21"),
    ("axios", "1.6.8"),
    ("chalk", "5.3.0"),
    ("commander", "11.1.0"),
    ("express", "4.18.2"),
    ("moment", "2.29.4"),
    ("dotenv", "16.3.1"),
    ("debug", "4.3.4"),
    ("uuid", "9.0.1"),
    ("react", "18.2.0"),
]

def download_npm_tarball(name, version, dest_dir):
    log.info(f"⬇️ Скачиваем {name}@{version}")
    url = f"https://registry.npmjs.org/{name}/{version}"
    resp = requests.get(url)
    resp.raise_for_status()
    tarball_url = resp.json()["dist"]["tarball"]

    filename = os.path.join(dest_dir, f"{name}-{version}.tgz")
    with requests.get(tarball_url, stream=True) as r:
        r.raise_for_status()
        with open(filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    return filename

def upload_to_nexus(tarball_path):
    filename = os.path.basename(tarball_path)
    url = f"{NEXUS_URL}/repository/{NPM_REPO}/{filename}"
    log.info(f"⬆️ Загружаем {filename} в Nexus")

    with open(tarball_path, "rb") as f:
        resp = requests.put(
            url,
            auth=(USERNAME, PASSWORD),
            headers={"Content-Type": "application/octet-stream"},
            data=f,
            verify=False,
        )
    if resp.status_code not in (200, 201, 204):
        log.error(f"❌ Ошибка загрузки: {resp.status_code} {resp.text}")
    else:
        log.info("✅ Успешно загружен")

def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        for name, version in npm_packages:
            try:
                tarball = download_npm_tarball(name, version, tmpdir)
                upload_to_nexus(tarball)
            except Exception as e:
                log.warning(f"⚠️ Ошибка с {name}@{version}: {e}")

if __name__ == "__main__":
    main()

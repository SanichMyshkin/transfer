import os
import tempfile
import logging
import requests
import subprocess
import urllib3
import argparse

# === Конфигурация ===
NEXUS_URL = "https://nexus.sanich.space"
USERNAME = "admin"
PASSWORD = "admin123"

SOURCE_REPO = "source-maven2"
TARGET_REPO = "target-maven2"
TARGET_UPLOAD_URL = f"{NEXUS_URL}/repository/{TARGET_REPO}/"

# === Логгирование ===
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# === Отключаем SSL предупреждения ===
urllib3.disable_warnings()

# === requests с авторизацией ===
session = requests.Session()
session.auth = (USERNAME, PASSWORD)
session.verify = False
session.headers.update({"Accept": "application/json"})


def get_all_components(repo_name):
    log.info(f"📋 Получаем список артефактов из {repo_name}...")
    url = f"{NEXUS_URL}/service/rest/v1/components"
    continuation_token = None
    components = []

    while True:
        params = {"repository": repo_name}
        if continuation_token:
            params["continuationToken"] = continuation_token

        resp = session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        for item in data["items"]:
            components.append(item)

        continuation_token = data.get("continuationToken")
        if not continuation_token:
            break

    log.info(f"🔍 Найдено {len(components)} артефактов")
    return components


def download_assets(component, download_dir):
    for asset in component["assets"]:
        download_url = asset["downloadUrl"]
        filename = asset["path"].split("/")[-1]
        dest_path = os.path.join(download_dir, filename)
        log.info(f"⬇️  Скачиваем {filename} → {dest_path}")

        with session.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)


def create_temp_settings_xml(tmp_path):
    settings = f"""
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 https://maven.apache.org/xsd/settings-1.0.0.xsd">
  <servers>
    <server>
      <id>inline</id>
      <username>{USERNAME}</username>
      <password>{PASSWORD}</password>
    </server>
  </servers>
</settings>
"""
    fpath = os.path.join(tmp_path, "settings.xml")
    with open(fpath, "w") as f:
        f.write(settings.strip())
    return fpath


def deploy_with_maven(component, tmpdir):
    group_id = component["group"]
    artifact_id = component["name"]
    version = component["version"]
    settings_path = create_temp_settings_xml(tmpdir)

    for filename in os.listdir(tmpdir):
        if not filename.startswith(f"{artifact_id}-{version}"):
            continue

        ext = filename.replace(f"{artifact_id}-{version}.", "")
        artifact_path = os.path.join(tmpdir, filename)

        if ext in ("jar", "pom"):
            packaging = ext
        elif ext in ("md5", "sha1"):
            continue  # мета-файлы не деплоим отдельно
        else:
            log.warning(f"Пропущен файл: {filename}")
            continue

        log.info(f"⬆️  Загружаем {filename} через Maven")

        args = [
            "mvn",
            "--settings",
            settings_path,
            "deploy:deploy-file",
            f"-DrepositoryId=inline",
            f"-Durl={TARGET_UPLOAD_URL}",
            f"-Dfile={artifact_path}",
            f"-DgroupId={group_id}",
            f"-DartifactId={artifact_id}",
            f"-Dversion={version}",
            f"-Dpackaging={packaging}",
            "-DgeneratePom=false",
        ]

        try:
            subprocess.run(args, check=True)
        except subprocess.CalledProcessError as e:
            log.error(f"❌ Ошибка при загрузке {filename}: {e}")


def migrate_maven_packages():
    components = get_all_components(SOURCE_REPO)
    if not components:
        log.warning("❗ Нет артефактов для миграции")
        return

    for component in components:
        with tempfile.TemporaryDirectory() as tmpdir:
            download_assets(component, tmpdir)
            deploy_with_maven(component, tmpdir)


def main():
    parser = argparse.ArgumentParser(
        description="Миграция Maven2 артефактов между Nexus репозиториями"
    )
    args = parser.parse_args()

    migrate_maven_packages()
    log.info("✅ Миграция завершена.")


if __name__ == "__main__":
    main()

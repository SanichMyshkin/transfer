import requests
import logging
from prometheus_client import Gauge
import urllib3
import json
from pathlib import Path


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Метрика для размеров репозиториев
REPO_STORAGE = Gauge(
    "nexus_repo_size",
    "Total size of Nexus repositories in bytes",
    ["repo_name", "repo_type", "repo_format", "repo_blob_name"],
)


def nexus_api_call(nexus_url, endpoint, auth):
    """Выполняет GET-запрос к Nexus API."""
    url = f"{nexus_url}{endpoint}"
    try:
        response = requests.get(url, auth=auth, verify=False)
        if response.status_code == 200:
            return response.json()
        else:
            logging.warning(f"Ошибка при запросе {endpoint}: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при вызове {endpoint}: {e}")
        return None


def get_repo_size(file_path):
    path = Path(file_path)
    with open(path, "r") as f:
        data = json.load(f)

    result = {}
    for repositories in data.values():
        repo = repositories["repositories"]
        for name, size in repo.items():
            result[name] = size["totalBytesMB"]
    return result



def fetch_repository_sizes(nexus_url, auth, path_file):
    """Запрашивает список репозиториев и собирает их размеры."""
    logging.info("Получение списка репозиториев...")

    repositories = nexus_api_call(
        nexus_url, "/service/rest/v1/repositorySettings", auth
    )

    if not repositories:
        logging.error("Не удалось получить список репозиториев!")
        return

    logging.info(f"Найдено {len(repositories)} репозиториев.")

    all_repo_size = get_repo_size(path_file)

    for repo in repositories:
        repo_name = repo.get("name")
        repo_type = repo.get("type", "unknown")
        repo_format = repo.get("format", "unknown")
        storage_info = repo.get("storage", "unknown")
        repo_blob_name = storage_info.get("blobStoreName", "unknown")
        repo_size = all_repo_size.get(repo_name, 'unknow')

        if not repo_name:
            logging.warning(f"Пропущен репозиторий без имени: {repo}")
            continue

        logging.info(
            f"Обрабатываем репозиторий: {repo_name} (type={repo_type}, format={repo_format})"
        )

        
        REPO_STORAGE.labels(
            repo_name=repo_name,
            repo_type=repo_type,
            repo_format=repo_format,
            repo_blob_name=repo_blob_name,
        ).set(repo_size)
        logging.info(f"Метрика обновлена: {repo_name} (size={repo_size})")

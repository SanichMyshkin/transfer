import requests
import logging
from prometheus_client import Gauge
import urllib3
from db import get_repository_sizes

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Метрика для размеров репозиториев
REPO_STORAGE = Gauge(
    "nexus_repo_size",
    "Total size of Nexus repositories in bytes",
    ["repo_name", "repo_type", "repo_format", "repo_blob_name", "repo_cleanup"],
)


def nexus_api_call(nexus_url, endpoint, auth):
    """Выполняет GET-запрос к Nexus API."""
    url = f"{nexus_url}{endpoint}"
    try:
        response = requests.get(url, auth=auth, verify=False)
        if response.status_code == 200:
            return response.json()
        else:
            logging.warning(f"Ошибка при запросе {endpoint}: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при вызове {endpoint}: {e}")
        return None


def fetch_repository_sizes(nexus_url, db_url, auth):
    """Запрашивает список репозиториев и собирает их размеры."""
    logging.info("Получение списка репозиториев...")

    repositories = nexus_api_call(
        nexus_url, "/service/rest/v1/repositorySettings", auth
    )

    if not repositories:
        logging.error("Не удалось получить список репозиториев!")
        return

    logging.info(f"Найдено {len(repositories)} репозиториев.")

    dict_repo_size = get_repository_sizes(db_url)

    for repo in repositories:
        if not isinstance(repo, dict):
            logging.warning(f"Пропущен некорректный объект: {repo}")
            continue

        repo_name = repo.get("name")
        if not repo_name:
            logging.warning(f"Пропущен репозиторий без имени: {repo}")
            continue

        repo_type = repo.get("type")
        repo_format = repo.get("format")

        # Обработка repo_cleanup
        repo_cleanup = repo.get("cleanup")
        if isinstance(repo_cleanup, dict):
            repo_cleanup = repo_cleanup.get("policyNames")

        # Обработка storage
        storage_info = repo.get("storage")
        if isinstance(storage_info, dict):
            repo_blob_name = storage_info.get("blobStoreName")

        repo_size = dict_repo_size.get(repo_name, 0)

        logging.info(
            f"Обрабатываем репозиторий: {repo_name} (type={repo_type}, format={repo_format}, size={repo_size})"
        )

        REPO_STORAGE.labels(
            repo_name=repo_name,
            repo_type=repo_type,
            repo_format=repo_format,
            repo_blob_name=repo_blob_name,
            repo_cleanup=repo_cleanup,
        ).set(repo_size)

        logging.info(f"Метрика обновлена: {repo_name} (size={repo_size})")

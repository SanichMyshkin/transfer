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

# Метрика для размеров репозиториев с учетом статусов задач
REPO_STORAGE = Gauge(
    "nexus_repo_size",
    "Total size of Nexus repositories in bytes",
    [
        "repo_name",
        "repo_type",
        "repo_format",
        "repo_blob_name",
        "repo_cleanup",
        "delete_temp_status",
        "compact_status",
    ],
)


def fetch_nexus_data(nexus_url, endpoint, auth):
    """Выполняет GET-запрос к Nexus API и возвращает ответ в формате JSON."""
    url = f"{nexus_url}{endpoint}"
    try:
        response = requests.get(url, auth=auth, verify=False)
        if response.status_code == 200:
            return response.json()
        else:
            logging.warning(
                f"Ошибка при запросе {endpoint}: {response.status_code} - {response.text}"
            )
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при вызове {endpoint}: {e}")
        return None


def fetch_nexus_tasks(nexus_url, endpoint, auth):
    """Получает список задач из Nexus."""
    tasks = fetch_nexus_data(nexus_url, endpoint, auth).get("items", [])
    result = []
    for task in tasks:
        if task.get("type") in ["blobstore.delete-temp-files", "blobstore.compact"]:
            if task.get("message") and task.get("message") != "null":
                task["blob_name"] = task.get("message").split()[1]
                result.append(task)
    return result


def get_task_status_for_blob(task_dict, repo_dict):
    """Возвращает статус задачи для указанного блоба."""
    if repo_dict.get("blobStoreName") == task_dict.get("blob_name"):
        if task_dict.get("lastRun") == "null":
            return -1  # Существует, но никогда не запускалась
        if task_dict.get("lastRunResult") != "OK":
            return -2  # Завершилось с ошибкой
        return 1  # Все в норме, отработала
    return 0  # Таски на такой репозиторий не существует


def fetch_repository_sizes(nexus_url, db_url, auth):
    """Запрашивает список репозиториев и собирает их размеры."""
    logging.info("Получение списка репозиториев...")
    repositories = fetch_nexus_data(
        nexus_url, "/service/rest/v1/repositorySettings", auth
    )

    if not repositories:
        logging.error("Не удалось получить список репозиториев!")
        return

    logging.info(f"Найдено {len(repositories)} репозиториев.")
    dict_repo_size = get_repository_sizes(db_url)
    task_list = fetch_nexus_tasks(nexus_url, "/service/rest/v1/tasks/", auth)

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
        storage_info = repo.get("storage", {})
        repo_blob_name = storage_info.get("blobStoreName", "N/A")
        repo_size = dict_repo_size.get(repo_name, 0)

        # Определяем статусы задач для блоба
        delete_temp_status = 0
        compact_status = 0

        for task in task_list:
            if task["type"] == "blobstore.delete-temp-files":
                delete_temp_status = get_task_status_for_blob(task, storage_info)
            elif task["type"] == "blobstore.compact":
                compact_status = get_task_status_for_blob(task, storage_info)

        # Обрабатываем repo_cleanup
        repo_cleanup = repo.get("cleanup")
        if isinstance(repo_cleanup, dict):
            repo_cleanup = repo_cleanup.get("policyNames", "N/A")
        else:
            repo_cleanup = "N/A"

        logging.info(
            f"Обрабатываем репозиторий: {repo_name} (size={repo_size}, delete_temp={delete_temp_status}, compact={compact_status})"
        )

        REPO_STORAGE.labels(
            repo_name=repo_name,
            repo_type=repo_type,
            repo_format=repo_format,
            repo_blob_name=repo_blob_name,
            repo_cleanup=repo_cleanup,
            delete_temp_status=delete_temp_status,
            compact_status=compact_status,
        ).set(repo_size)

        logging.info(f"Метрика обновлена: {repo_name} (size={repo_size})")

import requests
import logging
from prometheus_client import Gauge
import urllib3
from db import get_repository_sizes

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Настройка логов
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Метрика размера репозиториев + статусы задач
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
    url = f"{nexus_url}{endpoint}"
    try:
        response = requests.get(url, auth=auth, verify=False, timeout=15)
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


def extract_blob_name_from_task(task):
    """Извлекает имя блоба из message."""
    message = task.get("message")
    if not message:
        return None

    message = message.lower()
    if "blob store" in message:
        # Удаляем всё после "blob store", берём последнее слово перед ним
        before = message.split("blob store")[0].strip().split()
        if before:
            return before[-1]
    return None


def fetch_nexus_tasks(nexus_url, endpoint, auth):
    """Получает задачи из Nexus и добавляет поле blob_name."""
    data = fetch_nexus_data(nexus_url, endpoint, auth)
    if not data:
        return []

    tasks = data.get("items", [])
    result = []
    for task in tasks:
        if task.get("type") in ["blobstore.delete-temp-files", "blobstore.compact"]:
            task["blob_name"] = extract_blob_name_from_task(task)
            result.append(task)
    return result


def get_task_status_for_blob(tasks, blob_name, task_type):
    """Определяет статус задач типа task_type для конкретного блоба."""
    status = 0  # По умолчанию — задачи нет

    for task in tasks:
        if task.get("type") != task_type:
            continue
        if task.get("blob_name") != blob_name:
            continue

        last_result = task.get("lastRunResult")

        if last_result != "OK":
            return -1  # Ошибка

        status = 1  # Успешный запуск, если не было ошибок
    return status


def fetch_repository_sizes(nexus_url, db_url, auth):
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

    REPO_STORAGE.clear()

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

        # Получаем статусы задач
        delete_temp_status = get_task_status_for_blob(
            task_list, repo_blob_name, "blobstore.delete-temp-files"
        )
        compact_status = get_task_status_for_blob(
            task_list, repo_blob_name, "blobstore.compact"
        )

        # Очистка по политике (если есть)
        repo_cleanup = repo.get("cleanup")
        if isinstance(repo_cleanup, dict):
            repo_cleanup = repo_cleanup.get("policyNames", "N/A")
        else:
            repo_cleanup = "N/A"

        logging.info(
            f"Обрабатываем: {repo_name} | size={repo_size}, delete_temp={delete_temp_status}, compact={compact_status}"
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

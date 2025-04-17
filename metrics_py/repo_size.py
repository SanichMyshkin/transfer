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

# Метрика размера репозиториев
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

# Метрика с полной инфой о задачах
TASK_INFO = Gauge(
    "nexus_task_info",
    "Raw info about all Nexus tasks",
    [
        "id",
        "name",
        "type",
        "message",
        "current_state",
        "last_run_result",
        "next_run",
        "last_run",
    ],
)


def fetch_nexus_data(nexus_url, endpoint, auth):
    url = f"{nexus_url}{endpoint}"
    try:
        response = requests.get(url, auth=auth, verify=False, timeout=15)
        if response.status_code == 401:
            logging.error(f"❌ Нет доступа (401 Unauthorized) к {url}")
            return None
        elif response.status_code == 403:
            logging.error(f"❌ Доступ запрещён (403 Forbidden) к {url}")
            return None
        elif response.status_code != 200:
            logging.warning(
                f"⚠️ Ошибка при запросе {url}: {response.status_code} - {response.text}"
            )
            return None
        return response.json()
    except requests.exceptions.ConnectionError as e:
        logging.error(f"❌ Не удалось подключиться к Nexus: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Ошибка при вызове {url}: {e}")
        return None


def extract_blob_name_from_task(task):
    message = task.get("message")
    if not message:
        return None
    message = message.lower()
    if "blob store" in message:
        before = message.split("blob store")[0].strip().split()
        if before:
            return before[-1]
    return None


def fetch_nexus_tasks(nexus_url, endpoint, auth):
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
    status = 0
    for task in tasks:
        if task.get("type") != task_type:
            continue
        if task.get("blob_name") != blob_name:
            continue
        last_result = task.get("lastRunResult")
        if last_result != "OK":
            return -1
        status = 1
    return status


def update_task_info_metrics(tasks):
    TASK_INFO.clear()
    for task in tasks:
        last_run_result = task.get("lastRunResult", "N/A")

        # Логика для last_run_result
        if last_run_result == "OK":
            value = 0
        elif last_run_result is None:
            value = -1
        else:
            value = 1

        TASK_INFO.labels(
            id=task.get("id", "N/A"),
            name=str(task.get("name", "N/A")),
            type=task.get("type", "N/A"),
            message=str(task.get("message", "N/A")),
            current_state=task.get("currentState", "N/A"),
            last_run_result=last_run_result,
            next_run=task.get("nextRun", "null") or "null",
            last_run=task.get("lastRun", "null") or "null",
        ).set(value)


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
    if not dict_repo_size:
        logging.warning(
            "❌ Пропуск сбора метрик размера: не удалось получить данные из БД."
        )
        return

    task_list = fetch_nexus_tasks(nexus_url, "/service/rest/v1/tasks", auth)
    update_task_info_metrics(task_list)
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

        delete_temp_status = get_task_status_for_blob(
            task_list, repo_blob_name, "blobstore.delete-temp-files"
        )
        compact_status = get_task_status_for_blob(
            task_list, repo_blob_name, "blobstore.compact"
        )

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

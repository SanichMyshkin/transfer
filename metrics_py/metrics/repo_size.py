import logging
import urllib3
import requests

from requests import Session
from prometheus_client import Gauge
from db.repository_query import get_repository_sizes

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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

session: Session = requests.Session()


def fetch_nexus_data(nexus_url: str, endpoint: str, auth: tuple) -> dict | list | None:
    url = f"{nexus_url}{endpoint}"
    try:
        response = session.get(url, auth=auth, verify=False, timeout=15)
        if response.status_code == 200:
            return response.json()
        logger.error(f"Ошибка {response.status_code} при запросе {url}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при вызове {url}: {e}")
    return None


def extract_blob_name_from_task(task: dict) -> str | None:
    message = task.get("message", "")
    if not message:
        return None
    message = message.lower()
    if "blob store" in message:
        parts = message.split("blob store")[0].strip().split()
        if parts:
            return parts[-1]
    return None


def fetch_nexus_tasks(nexus_url: str, endpoint: str, auth: tuple) -> list:
    data = fetch_nexus_data(nexus_url, endpoint, auth)
    if not data:
        return []

    tasks = data.get("items", [])
    for task in tasks:
        if task.get("type") in ["blobstore.delete-temp-files", "blobstore.compact"]:
            task["blob_name"] = extract_blob_name_from_task(task)
    return tasks


def get_task_status_for_blob(tasks: list, blob_name: str, task_type: str) -> int:
    status = 0
    for task in tasks:
        if task.get("type") != task_type:
            continue
        if task.get("blob_name") != blob_name:
            continue
        if task.get("lastRunResult") != "OK":
            return -1
        status = 1
    return status


def update_task_info_metrics(tasks: list) -> None:
    TASK_INFO.clear()
    for task in tasks:
        last_result = task.get("lastRunResult", "N/A")
        value = 0 if last_result == "OK" else -1 if last_result is None else 1

        TASK_INFO.labels(
            id=task.get("id", "N/A"),
            name=str(task.get("name", "N/A")),
            type=task.get("type", "N/A"),
            message=str(task.get("message", "N/A")),
            current_state=task.get("currentState", "N/A"),
            last_run_result=last_result,
            next_run=task.get("nextRun", "null") or "null",
            last_run=task.get("lastRun", "null") or "null",
        ).set(value)


def fetch_repository_sizes(nexus_url: str, auth: tuple) -> None:
    logger.info("Получение списка репозиториев...")
    repositories = fetch_nexus_data(
        nexus_url, "/service/rest/v1/repositorySettings", auth
    )

    if not repositories:
        logger.error("Не удалось получить список репозиториев!")
        return

    logger.info(f"Найдено {len(repositories)} репозиториев.")
    dict_repo_size: dict = get_repository_sizes()

    if not dict_repo_size:
        logger.warning(
            "❌ Пропуск сбора метрик размера: не удалось получить данные из БД."
        )
        return

    task_list = fetch_nexus_tasks(nexus_url, "/service/rest/v1/tasks", auth)
    update_task_info_metrics(task_list)
    REPO_STORAGE.clear()

    for repo in repositories:
        if not isinstance(repo, dict):
            logger.warning(f"Пропущен некорректный объект: {repo}")
            continue

        repo_name = repo.get("name")
        if not repo_name:
            logger.warning(f"Пропущен репозиторий без имени: {repo}")
            continue

        repo_type = repo.get("type", "N/A")
        repo_format = repo.get("format", "N/A")
        storage_info = repo.get("storage", {})
        repo_blob_name = storage_info.get("blobStoreName", "N/A")
        repo_size = dict_repo_size.get(repo_name, 0)

        delete_temp_status = get_task_status_for_blob(
            task_list, repo_blob_name, "blobstore.delete-temp-files"
        )
        compact_status = get_task_status_for_blob(
            task_list, repo_blob_name, "blobstore.compact"
        )

        repo_cleanup = "N/A"
        if isinstance(repo.get("cleanup"), dict):
            repo_cleanup = repo["cleanup"].get("policyNames", "N/A")

        logger.info(
            f"Обрабатываем: {repo_name} | size={repo_size}, delete_temp={delete_temp_status}, compact={compact_status}"
        )

        REPO_STORAGE.labels(
            repo_name=repo_name,
            repo_type=repo_type,
            repo_format=repo_format,
            repo_blob_name=repo_blob_name,
            repo_cleanup=repo_cleanup,
            delete_temp_status=str(delete_temp_status),
            compact_status=str(compact_status),
        ).set(repo_size)

        logger.info(f"Метрика обновлена: {repo_name} (size={repo_size})")

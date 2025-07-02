import logging

from prometheus_client import Gauge
from database.repository_query import get_repository_sizes, get_repository_data
from database.jobs_query import get_jobs_data

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
)
logger = logging.getLogger(__name__)

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

# Допустимые типы задач
ALLOWED_TASK_TYPES = {
    "blobstore.delete-temp-files": "delete",
    "blobstore.compact": "compact",
}


def fetch_repository_metrics() -> list:
    logger.info("🔄 Сбор информации о репозиториях и метриках...")

    try:
        repo_size = get_repository_sizes()
        repo_data = get_repository_data()
    except Exception as e:
        logger.error(f"❌ Ошибка при получении данных из БД: {e}")
        return []

    if not repo_data:
        logger.error("❌ Не удалось получить данные о репозиториях — метрики не будут обновлены")
        return []

    for repo in repo_data:
        repo["size"] = repo_size.get(repo.get("repository_name"), 0)

    try:
        task_data = get_jobs_data()
    except Exception as e:
        logger.error(f"❌ Ошибка при получении задач из БД: {e}")
        task_data = []

    # Сопоставление blobStoreName -> наличие задач по типу
    task_statuses = {}
    for task in task_data:
        task_type = task.get(".typeId")
        blob_name = task.get("blobstoreName")
        if task_type in ALLOWED_TASK_TYPES and blob_name:
            status_key = ALLOWED_TASK_TYPES[task_type]
            if blob_name not in task_statuses:
                task_statuses[blob_name] = {"delete": 0, "compact": 0}
            task_statuses[blob_name][status_key] = 1

    # Очистка предыдущих метрик
    REPO_STORAGE.clear()

    for repo in repo_data:
        blob_name = repo.get("blob_store_name")
        presence_flags = task_statuses.get(blob_name, {"delete": 0, "compact": 0})
        repo.update(presence_flags)

        # Логирование по задачам
        logger.info(
            f"📦 Репозиторий: {repo.get('repository_name', 'unknown')} | "
            f"blob: {blob_name} | "
            f"delete: {'✅' if repo.get('delete') else '❌'} | "
            f"compact: {'✅' if repo.get('compact') else '❌'}"
        )

        REPO_STORAGE.labels(
            repo_name=repo.get("repository_name", "unknown"),
            repo_type=repo.get("repository_type", "unknown"),
            repo_format=repo.get("format", "unknown"),
            repo_blob_name=blob_name,
            repo_cleanup=repo.get("cleanup_policy", "N/A"),
            delete_temp_status=str(repo.get("delete", 0)),
            compact_status=str(repo.get("compact", 0)),
        ).set(float(repo.get("size", 0)))

    logger.info("✅ Метрики репозиториев собраны успешно")
    return repo_data
